"""Opt-in immutable raw-BRES snapshots; host storage, never Native state.

No Unicorn/project module, actor/clock/RNG capability, GC, reclaim timer or
mem_map_ptr is provided. A live reader/raw/memoryview reference keeps its mmap
alive. No actor-forget close is valid. Both registries below are weak.
"""
import ctypes
import hashlib
import mmap
import os
import platform
import secrets
import stat
import struct
import threading
import weakref
from collections import namedtuple
from pathlib import Path

_DIRECTORY_NAME = 'oc2-native-source-pages-v1'
_MEMORY_FILESYSTEMS = {0x01021994, 0x858458f6, 0x958458f6}
_CHUNK = 65536
_MAP_TYPE = mmap.mmap
_LOCK = threading.RLock()
_VERIFIED = weakref.WeakKeyDictionary()
_CACHE = weakref.WeakValueDictionary()
_Proof = namedtuple('_Proof', 'path sha256 size source_stamp inode filesystem')


class SourcePageSupportError(RuntimeError):
    pass


def source_pages_enabled():
    value = os.environ.get('OC2_NATIVE_SOURCE_PAGES', '0')
    if value not in ('0', '1'):
        raise ValueError('OC2_NATIVE_SOURCE_PAGES must be 0 or 1')
    return value == '1'


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _descriptor(root, descriptor):
    if not isinstance(descriptor, dict) or set(descriptor) != {'path', 'sha256'} or not _sha(descriptor['sha256']):
        raise ValueError('Exact private path/SHA descriptor required')
    if not isinstance(descriptor['path'], (str, Path)) or not str(descriptor['path']):
        raise ValueError('Explicit private source path required')
    root = Path(root).resolve(strict=True)
    path = Path(descriptor['path'])
    if '..' in path.parts:
        raise ValueError('Private source traversal refused')
    if not path.is_absolute():
        path = root / path
    private = root / 'analysis' / 'raw'
    try:
        relative = path.relative_to(private)
    except ValueError as error:
        raise ValueError('Original source must remain in analysis/raw') from error
    cursor = root
    for part in ('analysis', 'raw', *relative.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError('Symlink private source refused')
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(private):
        raise ValueError('Private source escaped its runtime')
    return resolved, descriptor['sha256']


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _open_original(path):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size < 0 or os.get_inheritable(fd):
            raise ValueError('Regular non-inheritable original source required')
        if _stamp(info) != _stamp(os.stat(path, follow_symlinks=False)):
            raise ValueError('Original source identity changed at open')
        return fd, info
    except BaseException:
        os.close(fd)
        raise


def _unchanged(fd, path, before, count):
    if count != before.st_size or _stamp(os.fstat(fd)) != _stamp(before) or _stamp(os.stat(path, follow_symlinks=False)) != _stamp(before):
        raise ValueError('Original source changed while being read')


def _write_all(fd, block):
    view = memoryview(block)
    try:
        offset = 0
        while offset < len(view):
            wrote = os.write(fd, view[offset:])
            if type(wrote) is not int or wrote <= 0:
                raise OSError('Incomplete immutable-source copy')
            offset += wrote
    finally:
        view.release()


def _stream(fd, destination=None):
    digest, count = hashlib.sha256(), 0
    while True:
        block = os.read(fd, _CHUNK)
        if not block:
            break
        digest.update(block)
        count += len(block)
        if destination is not None:
            _write_all(destination, block)
    return digest.hexdigest(), count


def verify_source(root, descriptor):
    """Generic pinned regular-file check: (Path, SHA, size), streaming only.

    This does not admit an ELF/PHY/RNG buffer or brand anything as BRES.
    Existing downstream bytes gates remain their own exact checks.
    """
    path, expected = _descriptor(root, descriptor)
    fd, before = _open_original(path)
    try:
        actual, size = _stream(fd)
        _unchanged(fd, path, before, size)
        if actual != expected:
            raise ValueError('Pinned original source SHA differs')
        return path, actual, size
    finally:
        os.close(fd)


def checked_path(root, descriptor):
    return verify_source(root, descriptor)[0]


def _raw_bres(prefix, size):
    if size < 48 or size > 0xffffffff or len(prefix) < 48 or prefix[:8] != b'BRES\xfe\xff\x00\x00' or struct.unpack_from('<I', prefix, 8)[0] != 64 or struct.unpack_from('<I', prefix, 12)[0] != size:
        raise ValueError('Exact raw BRES header/size required; ZIP snapshot unsupported')


def _require_linux():
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64') or ctypes.sizeof(ctypes.c_long) != 8:
        raise SourcePageSupportError('Immutable source pages require checked Linux amd64')
    if not callable(getattr(os, 'posix_fallocate', None)):
        raise SourcePageSupportError('Immutable source pages require posix_fallocate')


def _filesystem_type(fd):
    # Checked Linux amd64 statfs starts with long f_type. No other fields read.
    libc = ctypes.CDLL(None, use_errno=True)
    query = libc.fstatfs
    query.argtypes = (ctypes.c_int, ctypes.c_void_p)
    query.restype = ctypes.c_int
    result = ctypes.create_string_buffer(256)
    if query(fd, result) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    return ctypes.c_long.from_buffer(result).value & 0xffffffff


def _directory():
    # Fixed private /tmp directory, never TMPDIR, /data, memfd or tmpfs.
    root = Path('/tmp').resolve(strict=True)
    directory = root / _DIRECTORY_NAME
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Immutable source directory must be private and owner-only')
        filesystem = _filesystem_type(fd)
        if not filesystem or filesystem in _MEMORY_FILESYSTEMS:
            raise SourcePageSupportError('Immutable source snapshots require non-memory filesystem')
        return fd, filesystem
    except BaseException:
        os.close(fd)
        raise


def _reserve(fd, size):
    try:
        os.ftruncate(fd, size)
        os.posix_fallocate(fd, 0, size)
    except (OSError, NotImplementedError) as error:
        raise SourcePageSupportError('Immutable source disk reservation failed') from error


def _map_readonly(fd, size):
    return _MAP_TYPE(fd, size, access=mmap.ACCESS_READ)


def _snapshot(source_fd, before, path, expected):
    directory_fd, filesystem = _directory()
    rwfd = rofd = None
    name = '.source-' + secrets.token_hex(16)  # Host tempfile naming only.
    linked = False
    buffer = None
    try:
        rwfd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
        linked = True
        os.fchmod(rwfd, 0o600)
        copy_info = os.fstat(rwfd)
        if not stat.S_ISREG(copy_info.st_mode) or copy_info.st_uid != os.geteuid() or copy_info.st_nlink != 1 or stat.S_IMODE(copy_info.st_mode) != 0o600 or os.get_inheritable(rwfd) or _filesystem_type(rwfd) != filesystem:
            raise ValueError('Exclusive private disk source backing required')
        _reserve(rwfd, before.st_size)
        actual, count = _stream(source_fd, rwfd)
        _unchanged(source_fd, path, before, count)
        if actual != expected:
            raise ValueError('Pinned source copy SHA differs')
        # Copy and original have the same streamed SHA; recheck the independent
        # file's structural prefix before it can receive any provenance.
        _raw_bres(os.pread(rwfd, 48, 0), count)
        os.fsync(rwfd)
        os.fchmod(rwfd, 0o400)
        rofd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
        ro = os.fstat(rofd)
        if (ro.st_dev, ro.st_ino) != (copy_info.st_dev, copy_info.st_ino) or ro.st_size != count or not stat.S_ISREG(ro.st_mode) or ro.st_nlink != 1 or stat.S_IMODE(ro.st_mode) != 0o400 or os.get_inheritable(rofd):
            raise ValueError('Read-only snapshot inode/size/permissions differ')
        os.close(rwfd)
        rwfd = None  # All our writable capabilities are gone BEFORE unlink/map.
        os.unlink(name, dir_fd=directory_fd)
        linked = False
        if os.fstat(rofd).st_nlink != 0:
            raise ValueError('Snapshot must be unlinked before readonly mapping')
        sealed = os.fstat(rofd)
        copied_sha, copied_size = _stream(rofd)
        if copied_sha != expected or copied_size != count or _stamp(os.fstat(rofd)) != _stamp(sealed):
            raise ValueError('Independent readonly snapshot SHA/size changed')
        buffer = _map_readonly(rofd, count)
        if type(buffer) is not _MAP_TYPE or len(buffer) != count:
            raise ValueError('Exact readonly mmap snapshot required')
        view = memoryview(buffer)
        try:
            if not view.readonly:
                raise ValueError('Snapshot buffer must have readonly access')
        finally:
            view.release()
        os.close(rofd)
        rofd = None  # mmap's internal retained fd comes only from O_RDONLY.
        proof = _Proof(path, expected, count, _stamp(before), (ro.st_dev, ro.st_ino), filesystem)
        return buffer, proof
    except BaseException:
        if buffer is not None:
            buffer.close()  # Not published; no exported views can exist.
        raise
    finally:
        if rwfd is not None:
            os.close(rwfd)
        if rofd is not None:
            os.close(rofd)
        if linked:
            os.unlink(name, dir_fd=directory_fd)
        os.close(directory_fd)


def is_verified_source(buffer):
    if type(buffer) is not _MAP_TYPE:
        return False
    with _LOCK:
        proof = _VERIFIED.get(buffer)
        try:
            return proof is not None and not buffer.closed and len(buffer) == proof.size
        except ValueError:  # A caller explicitly closed this exact object.
            return False


def require_source(buffer, path, expected_sha=None, expected_size=None):
    """Validate this exact live snapshot; never re-read the mutable original.

    Pass the provider-returned resolved Path. A view/copy/unbranded mmap is not
    this capability. Snapshot lifetime is independent of later path writes.
    """
    if not is_verified_source(buffer):
        raise ValueError('Authenticated live readonly source snapshot required')
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Provider-resolved absolute source path required')
    with _LOCK:
        proof = _VERIFIED[buffer]
        if path != proof.path or expected_sha is not None and (not _sha(expected_sha) or expected_sha != proof.sha256) or expected_size is not None and (type(expected_size) is not int or expected_size != proof.size):
            raise ValueError('Snapshot source identity/SHA/size differs')
        return buffer


def open_source(root, descriptor):
    """(resolved Path, bytes by default | authenticated readonly mmap if on).

    Flag1 failures never silently fall back to bytes. ZIP remains exclusively
    the original decoder's default branch; this provider accepts raw BRES only.
    """
    enabled = source_pages_enabled()
    if enabled:
        _require_linux()
    path, expected = _descriptor(root, descriptor)
    source_fd, before = _open_original(path)
    try:
        _raw_bres(os.pread(source_fd, 48, 0), before.st_size)
        if not enabled:
            with os.fdopen(source_fd, 'rb', closefd=False) as source:
                raw = source.read()
            _unchanged(source_fd, path, before, len(raw))
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Pinned original source SHA differs')
            return path, raw
        key = (path, expected, before.st_size)
        with _LOCK:
            cached = _CACHE.get(key)
            if cached is not None and is_verified_source(cached):
                # Cache shares the independent immutable copy, not permission
                # to skip current original-source validation at a new open.
                actual, count = _stream(source_fd)
                _unchanged(source_fd, path, before, count)
                if actual != expected:
                    raise ValueError('Pinned original source SHA differs')
                return path, cached
            buffer, proof = _snapshot(source_fd, before, path, expected)
            _VERIFIED[buffer] = proof
            _CACHE[key] = buffer
            return path, buffer
    finally:
        os.close(source_fd)


# Whole-program purpose is separate from raw-BRES provenance; reuse this
# provider's weak cache/lock and the existing code-pages CAS publisher.
_NATIVE_VERIFIED = weakref.WeakKeyDictionary()
_NATIVE_STREAMS = weakref.WeakKeyDictionary()
_NativeProof = namedtuple('_NativeProof', 'path sha256 size source_stamp inode filesystem backing backing_stamp')
def _native_identity():
    from source_code_pages import NATIVE_SHA256, NATIVE_FILE_BYTES
    return NATIVE_SHA256, NATIVE_FILE_BYTES


def _native_backing_stamp(info):
    # Closed-writer CAS link/unlink publication legitimately changes ctime/nlink.
    # These fields identify its immutable content backing; never use this for
    # the mutable original-source stamp, which remains the full _stamp.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_uid, info.st_mtime_ns)


def native_elf_file_enabled():
    value = os.environ.get('OC2_NATIVE_ELF_FILE', '0')
    if value not in ('0', '1'):
        raise ValueError('OC2_NATIVE_ELF_FILE must be 0 or 1')
    return value == '1'


def require_native_program(buffer, stream=None):
    if type(buffer) is not _MAP_TYPE:
        raise ValueError('Authenticated whole native-program mmap required')
    with _LOCK:
        proof = _NATIVE_VERIFIED.get(buffer)
        if proof is None or buffer.closed or len(buffer) != proof.size:
            raise ValueError('Live authenticated whole native program required')
        if stream is not None:
            if stream.closed or _NATIVE_STREAMS.get(stream) is not buffer:
                raise ValueError('Independent authenticated native-program FileIO lease required')
            info = os.fstat(stream.fileno())
            if _native_backing_stamp(info) != proof.backing_stamp:
                raise ValueError('Native-program stream backing changed')
        return proof


def native_program_stream(buffer):
    # A fresh open file description, NOT dup(): independent ELF seek/tell state.
    # FileIO owns this fd; ELFFile.close does not close the separate raw mmap.
    import io
    proof = require_native_program(buffer)
    fd = os.open(proof.backing, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if _native_backing_stamp(info) != proof.backing_stamp:
            raise ValueError('Native-program CAS inode/metadata changed')
        stream = io.FileIO(fd, 'rb', closefd=True)
        fd = None
        with _LOCK:
            _NATIVE_STREAMS[stream] = buffer  # Strong raw-map lease, weak stream key.
        return stream
    finally:
        if fd is not None:
            os.close(fd)


def open_native_program(root, descriptor):
    """Strict ELF purpose; current flag1 never falls back or brands raw BRES."""
    if not native_elf_file_enabled():
        raise ValueError('Explicit OC2_NATIVE_ELF_FILE=1 required')
    _require_linux()
    path, expected = _descriptor(root, descriptor)
    native_sha, native_size = _native_identity()
    if expected != native_sha:
        raise ValueError('Only the original verified program is admitted')
    source_fd, before = _open_original(path)
    rofd = None
    buffer = None
    try:
        actual, count = _stream(source_fd)
        _unchanged(source_fd, path, before, count)
        if actual != expected or count != native_size:
            raise ValueError('Original native program SHA/size differs')
        key = ('whole-native-program', path, expected, count)
        with _LOCK:
            cached = _CACHE.get(key)
            if cached is not None:
                require_native_program(cached)
                return path, cached
            from source_code_pages import open_native_program_backing
            rofd, backing, inode = open_native_program_backing(source_fd)
            _unchanged(source_fd, path, before, count)
            filesystem = _filesystem_type(rofd)
            if filesystem == 0 or filesystem in _MEMORY_FILESYSTEMS:
                raise SourcePageSupportError('Native program requires disk-backed CAS, not tmpfs')
            sealed = os.fstat(rofd)
            buffer = _map_readonly(rofd, count)
            view = memoryview(buffer)
            try:
                if type(buffer) is not _MAP_TYPE or not view.readonly or hashlib.sha256(view).hexdigest() != expected:
                    raise ValueError('Exact readonly native-program map required')
            finally:
                view.release()
            proof = _NativeProof(path, expected, count, _stamp(before), inode,
                                 filesystem, backing, _native_backing_stamp(sealed))
            _NATIVE_VERIFIED[buffer] = proof
            _CACHE[key] = buffer
            return path, buffer
    except BaseException:
        if buffer is not None:
            buffer.close()  # Not returned; no exported borrower exists.
        raise
    finally:
        if rofd is not None:
            os.close(rofd)
        os.close(source_fd)


def inspect_native_program(buffer):
    proof = require_native_program(buffer)
    return {'purpose': 'whole-original-native-program', 'sha256': proof.sha256,
            'bytes': proof.size, 'inode': list(proof.inode), 'backing': proof.backing,
            'readonly': True, 'BRESAdmission': False, 'UcOrGameReadiness': False}
