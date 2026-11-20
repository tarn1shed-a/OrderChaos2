"""Build-only lossless XZ -> fixed STORED gzip; the old runtime loader is unchanged."""
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import tarfile
import tempfile
import zlib

FORMAT = 'oc2-private-runtime-xz-transport-v1'
ENCODING = 'gzip-stored-65535-v1'
PLAN_NAME = 'private-runtime.transport.json'
XZ_NAME = 'private-runtime.tar.xz'
GZIP_NAME = 'private-runtime.tar.gz'
SIDECAR_NAME = 'private-runtime.sha256'
HEADER = bytes.fromhex('1f8b08000000000000ff')
FINAL_BLOCK = bytes.fromhex('010000ffff')
BLOCK_BYTES = 65535
IO_BYTES = 65536
XZ_MAGIC = b'\xfd7zXZ\x00'
XZ_MEMORY_LIMIT = 64 * 1024 * 1024  # Supports the pinned preset6 8 MiB dictionary.


class TransportError(ValueError):
    pass


def stored_gzip_size(size):
    return 23 + size + 5 * ((size + BLOCK_BYTES - 1) // BLOCK_BYTES)


def _row(row):
    if (type(row) is not dict or set(row) != {'sha256', 'bytes'} or
            type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']) or
            type(row['bytes']) is not int or not 0 < row['bytes'] < 2**63):
        raise TransportError('Exact positive byte count and lowercase SHA256 required')
    return dict(row)


def validate_plan(plan):
    keys = {'format', 'encoding', 'canonicalGzip', 'xz', 'tar', 'storedGzip'}
    if (type(plan) is not dict or set(plan) != keys or plan['format'] != FORMAT or
            plan['encoding'] != ENCODING):
        raise TransportError('Exact full-XZ build-transport declaration required')
    result = {key: plan[key] for key in ('format', 'encoding')}
    for key in ('canonicalGzip', 'xz', 'tar', 'storedGzip'):
        result[key] = _row(plan[key])
    if result['storedGzip']['bytes'] != stored_gzip_size(result['tar']['bytes']):
        raise TransportError('Declared STORED gzip length disagrees with its fixed encoding')
    identities = {}
    for key in ('canonicalGzip', 'xz', 'tar', 'storedGzip'):
        row = result[key]
        if row['sha256'] in identities and identities[row['sha256']] != row['bytes']:
            raise TransportError('One SHA256 cannot have ambiguous byte lengths')
        identities[row['sha256']] = row['bytes']
    return result


def _signature(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _local_path(path):
    if not isinstance(path, (str, os.PathLike)) or '://' in os.fspath(path):
        raise TransportError('Local regular file required; no URI')
    return Path(path)


def _open_regular(path):
    path = _local_path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise TransportError('Only a non-symlink regular file is accepted')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        current = os.fstat(descriptor)
        if _signature(current) != _signature(before):
            raise TransportError('Input changed while opening')
        return os.fdopen(descriptor, 'rb'), _signature(current)
    except BaseException:
        os.close(descriptor)
        raise


def _same_file(path, stream, identity):
    if (_signature(os.fstat(stream.fileno())) != identity or
            _signature(Path(path).lstat()) != identity):
        raise TransportError('Input identity changed during verification')


def _verify_stream(stream, row):
    if os.fstat(stream.fileno()).st_size != row['bytes']:
        raise TransportError('Input byte count differs')
    digest, count = hashlib.sha256(), 0
    for chunk in iter(lambda: stream.read(IO_BYTES), b''):
        count += len(chunk)
        if count > row['bytes']:
            raise TransportError('Input grew while reading')
        digest.update(chunk)
    if count != row['bytes'] or digest.hexdigest() != row['sha256']:
        raise TransportError('Input SHA256 or byte count differs')


def verify_file(path, row):
    expected = _row(row)
    stream, identity = _open_regular(path)
    with stream:
        _verify_stream(stream, expected)
        _same_file(path, stream, identity)
    return expected


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise TransportError('Duplicate declaration key')
        value[key] = item
    return value


def _read_plan(path):
    stream, identity = _open_regular(path)
    with stream:
        raw = stream.read(16385)
        if len(raw) > 16384:
            raise TransportError('Transport declaration is too large')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
        _same_file(path, stream, identity)
    return validate_plan(value), identity


def read_plan(path):
    return _read_plan(path)[0]


def _xz_chunks(source):
    pending, streams = b'', 0
    while True:
        while len(pending) < len(XZ_MAGIC):
            chunk = source.read(IO_BYTES)
            if not chunk:
                if not pending and streams:
                    return
                raise TransportError('Missing or truncated XZ stream')
            pending += chunk
        if not pending.startswith(XZ_MAGIC):
            raise TransportError('Trailing or non-XZ bytes are refused')
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=XZ_MEMORY_LIMIT)
        streams += 1
        feed, pending = pending, b''
        while True:
            try:
                raw = decoder.decompress(feed, max_length=IO_BYTES)
            except lzma.LZMAError as error:
                raise TransportError('XZ integrity or format check failed') from error
            if raw:
                yield raw
            if decoder.eof:
                pending = decoder.unused_data
                break
            if decoder.needs_input:
                feed = source.read(IO_BYTES)
                if not feed:
                    raise TransportError('Truncated XZ stream')
            else:
                feed = b''


class _StoredWriter:
    def __init__(self, sink):
        self.sink, self.digest = sink, hashlib.sha256()
        self.encoded_bytes = self.raw_bytes = self.crc = 0
        self.buffer = bytearray()
        self._emit(HEADER)

    def _emit(self, raw):
        if self.sink.write(raw) != len(raw):
            raise OSError('Incomplete transport output write')
        self.digest.update(raw)
        self.encoded_bytes += len(raw)

    def feed(self, raw):
        self.raw_bytes += len(raw)
        self.crc = zlib.crc32(raw, self.crc)
        self.buffer.extend(raw)
        while len(self.buffer) >= BLOCK_BYTES:
            block = bytes(self.buffer[:BLOCK_BYTES])
            del self.buffer[:BLOCK_BYTES]
            self._block(block)

    def _block(self, raw):
        self._emit(b'\x00' + struct.pack('<HH', len(raw), len(raw) ^ 0xffff))
        self._emit(raw)

    def finish(self):
        if self.buffer:
            self._block(bytes(self.buffer))
            self.buffer.clear()
        self._emit(FINAL_BLOCK)
        self._emit(struct.pack('<II', self.crc & 0xffffffff, self.raw_bytes & 0xffffffff))
        return {'sha256': self.digest.hexdigest(), 'bytes': self.encoded_bytes}


def write_stored_gzip(chunks, sink):
    """One encoding core, also usable by small host-only fixtures."""
    writer = _StoredWriter(sink)
    for chunk in chunks:
        writer.feed(chunk)
    return writer.finish()


class _TarReader:
    def __init__(self, chunks, writer, expected):
        self.chunks, self.writer, self.expected = iter(chunks), writer, expected
        self.buffer, self.digest, self.count, self.done = bytearray(), hashlib.sha256(), 0, False

    def read(self, size=IO_BYTES):
        if size < 0:
            raise TransportError('Unbounded tar read refused')
        size = min(size, IO_BYTES)
        while len(self.buffer) < size and not self.done:
            try:
                self.buffer.extend(next(self.chunks))
            except StopIteration:
                self.done = True
        raw = bytes(self.buffer[:size])
        del self.buffer[:size]
        self.count += len(raw)
        if self.count > self.expected['bytes']:
            raise TransportError('Decoded tar exceeds its declared length')
        self.digest.update(raw)
        self.writer.feed(raw)
        return raw


def _validate_tar(reader):
    names, expanded = set(), 0
    try:
        with tarfile.open(fileobj=reader, mode='r|') as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if (not member.isfile() or not member.name or path.is_absolute() or
                        '..' in path.parts or str(path) != member.name or '\\' in member.name or
                        member.name in names):
                    raise TransportError('Unsafe or ambiguous tar member')
                names.add(member.name)
                expanded += member.size
                if len(names) > 20000 or expanded > 2 * 1024**3:
                    raise TransportError('Tar exceeds the old bootstrap limits')
                archive.members.clear()
    except tarfile.TarError as error:
        raise TransportError('Tar structure or header check failed') from error
    if 'bundle-manifest.json' not in names:
        raise TransportError('Full tar must contain bundle-manifest.json')
    # Include original end markers/padding and validate every concatenated XZ
    # stream, even if the tar reader stopped at its first end-of-archive marker.
    while reader.read(IO_BYTES):
        pass
    if reader.count != reader.expected['bytes'] or reader.digest.hexdigest() != reader.expected['sha256']:
        raise TransportError('Decoded tar SHA256 or length differs')
    return len(names)


def reconstruct(root):
    root = _local_path(root)
    if root.is_symlink():
        raise TransportError('Root directory must not be a symlink')
    directory = root.resolve(strict=True) / 'deploy'
    if directory.is_symlink() or not directory.is_dir():
        raise TransportError('Real deploy directory required')
    plan_path, source_path, target = directory / PLAN_NAME, directory / XZ_NAME, directory / GZIP_NAME
    if target.exists() or target.is_symlink():
        raise TransportError('Existing target is preserved; no overwrite')
    plan, plan_identity = _read_plan(plan_path)
    sidecar = directory / SIDECAR_NAME
    sidecar_stream, sidecar_identity = _open_regular(sidecar)
    with sidecar_stream:
        if sidecar_stream.read(256) != (plan['storedGzip']['sha256'] + '  ' + GZIP_NAME + '\n').encode():
            raise TransportError('Fixed gzip checksum sidecar differs')
        _same_file(sidecar, sidecar_stream, sidecar_identity)
    source, source_identity = _open_regular(source_path)
    temporary = None
    try:
        with source:
            _verify_stream(source, plan['xz'])
            _same_file(source_path, source, source_identity)
            source.seek(0)
            fd, name = tempfile.mkstemp(prefix='.private-runtime.transport-', dir=directory)
            temporary = Path(name)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'wb') as sink:
                writer = _StoredWriter(sink)
                reader = _TarReader(_xz_chunks(source), writer, plan['tar'])
                count = _validate_tar(reader)
                encoded = writer.finish()
                if encoded != plan['storedGzip']:
                    raise TransportError('Materialized gzip SHA256 or length differs')
                sink.flush()
                os.fsync(sink.fileno())
            _same_file(source_path, source, source_identity)
        if _signature(plan_path.lstat()) != plan_identity or _signature(sidecar.lstat()) != sidecar_identity:
            raise TransportError('Declaration or checksum changed during reconstruction')
        os.link(temporary, target, follow_symlinks=False)  # Atomic no-replace publication.
        temporary.unlink()
        temporary = None
        # These are only the two exact COPY inputs verified above, never an
        # original canonical archive or any wildcard. The final image needs
        # only the standard gzip and its unchanged-format checksum sidecar.
        if _signature(source_path.lstat()) != source_identity or _signature(plan_path.lstat()) != plan_identity:
            raise TransportError('Verified transport inputs changed before cleanup')
        source_path.unlink()
        plan_path.unlink()
        return {'format': FORMAT, 'reconstructed': True, 'members': count,
                'tar': plan['tar'], 'storedGzip': encoded, 'canonicalGzipEvidence': plan['canonicalGzip'],
                'sourceXZRemoved': True, 'transportPlanRemoved': True}
    finally:
        source.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    if len(sys.argv) != 1:
        raise TransportError('No CLI paths or URIs accepted; use fixed adjacent files')
    print(json.dumps(reconstruct(Path(__file__).resolve().parents[1]), sort_keys=True))


if __name__ == '__main__':
    main()
