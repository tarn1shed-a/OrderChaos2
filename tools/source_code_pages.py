"""Optional exact-build Linux code pages; never shared mutable guest state.

NativeImage may explicitly own create_code_pages(data). The two original ELF
constructors call map_segment AFTER generating their original relocated bytes,
BEFORE mem_map/mem_write. False means execute the existing copy path unchanged.
No source file, guest permission/address/instruction, clock or RNG is changed.
"""
import ctypes
import hashlib
import mmap
import os
import platform
import stat
import tempfile
import threading
import weakref
from pathlib import Path

NATIVE_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
RX_ADDRESS = 0
RX_MEMORY_BYTES = 37726440
PAGE_BYTES = 4096
SHARED_BYTES = 37724160  # 9,210 full original RX pages; tail remains original copy.
PERMISSIONS = 7  # Same UC_PROT_ALL used by both original mapping constructors.
_FAILED_FINALIZATIONS = []


def _supported():
    if os.environ.get('OC2_NATIVE_CODE_PAGES') != '1':
        return False
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        return False
    if os.sysconf('SC_PAGE_SIZE') != PAGE_BYTES:
        return False
    import unicorn
    return unicorn.__version__ == '2.1.4'


def _digest_fd(fd, size):
    digest = hashlib.sha256()
    for offset in range(0, size, 1024 * 1024):
        data = os.pread(fd, min(1024 * 1024, size - offset), offset)
        if len(data) != min(1024 * 1024, size - offset):
            raise ValueError('Code backing was truncated')
        digest.update(data)
    return digest.hexdigest()


def _open_backing(view, digest, cache_dir):
    root = Path('/tmp').resolve()  # Never route original code into /data via TMPDIR.
    directory = Path(cache_dir or root / 'oc2-native-code-pages-v1').resolve()
    if not directory.is_relative_to(root):
        raise ValueError('Code backing belongs only in the temporary host cache')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise ValueError('Code cache directory owner differs')
    target = directory / (NATIVE_SHA256 + '-' + digest + '.rx')
    temporary = None
    try:
        if not target.exists():
            fd, temporary = tempfile.mkstemp(prefix='.rx-', dir=directory)
            try:
                offset = 0
                while offset < SHARED_BYTES:
                    count = os.write(fd, view[offset:SHARED_BYTES])
                    if count <= 0:
                        raise OSError('Incomplete code backing write')
                    offset += count
                os.fsync(fd)
                os.fchmod(fd, 0o444)
            finally:
                os.close(fd)
            try:
                os.link(temporary, target, follow_symlinks=False)
            except FileExistsError:
                pass  # Another process published the same exact immutable file.
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        fd = os.open(target, flags)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                    info.st_size != SHARED_BYTES or info.st_mode & 0o222 or
                    _digest_fd(fd, SHARED_BYTES) != digest):
                raise ValueError('Exact read-only code backing differs')
            return fd, str(target), (info.st_dev, info.st_ino)
        except BaseException:
            os.close(fd)
            raise
    finally:
        if temporary is not None:
            os.unlink(temporary)


class _Mapping:
    def __init__(self, fd):
        self.memory = mmap.mmap(fd, SHARED_BYTES, flags=mmap.MAP_PRIVATE,
                                prot=mmap.PROT_READ | mmap.PROT_WRITE)
        self.anchor = (ctypes.c_ubyte * SHARED_BYTES).from_buffer(self.memory)
        self.pointer = ctypes.addressof(self.anchor)

    def close(self):
        self.anchor = None
        self.memory.close()


class _Lifetime:
    def __init__(self, mapping):
        self.mapping = mapping
        self.engine_closed = False
        self.mapping_closed = False
        self.order = []
        self.error = None


def _close_then_release(close_handle, handle, lifetime,
                        quarantine=_FAILED_FINALIZATIONS):
    """ONE finalizer, independent of ordering between Python objects/finalizers.

    Capture the official ctypes uc_close function while the binding is alive.
    A failed/unknown close retains backing; it never unmaps a possibly live Uc.
    """
    try:
        status = close_handle(handle)
        if status != 0:
            raise RuntimeError('uc_close returned ' + str(status))
        lifetime.engine_closed = True
        lifetime.order.append('uc_close')
    except BaseException as error:
        lifetime.error = repr(error)
        quarantine.append(lifetime)
        return
    try:
        lifetime.mapping.close()
        lifetime.mapping_closed = True
        lifetime.order.append('mmap_close')
    except BaseException as error:
        lifetime.error = repr(error)
        quarantine.append(lifetime)


def _original_finalizer(uc):
    from unicorn import Uc
    from unicorn.unicorn_py3.arch.arm64 import UcAArch64
    from unicorn.unicorn_py3 import unicorn as binding
    if type(uc) is not UcAArch64:
        return None
    finalizer = getattr(uc, '_Uc__finalizer', None)
    if not isinstance(finalizer, weakref.finalize) or not finalizer.alive:
        return None
    record = finalizer.peek()
    if (record is None or record[0] is not uc or record[1] is not Uc.release_handle or
            len(record[2]) != 1 or record[2][0] is not uc._uch or record[3]):
        return None
    close = binding.uclib.uc_close
    if not isinstance(close, ctypes._CFuncPtr):
        return None
    return finalizer, close, uc._uch


class NativeCodePages:
    """Verified file metadata/fd only. Every Uc owns a distinct private mmap."""
    def __init__(self, fd, path, inode, full_digest, tail_digest):
        self._fd = fd
        self.path = path
        self.inode = inode
        self.full_digest = full_digest
        self.tail_digest = tail_digest
        self._thread = threading.get_ident()
        self._leases = weakref.WeakKeyDictionary()
        self._fd_finalizer = weakref.finalize(self, os.close, fd)

    def map_segment(self, uc, address, mem_size, initial_bytes, permissions=PERMISSIONS):
        if (address != RX_ADDRESS or mem_size != RX_MEMORY_BYTES or
                permissions != PERMISSIONS):
            return False
        if not _supported() or not self._fd_finalizer.alive:
            return False
        if threading.get_ident() != self._thread:
            raise ValueError('Code mapping requires its serial resource owner')
        lifecycle = _original_finalizer(uc)
        if lifecycle is None or list(uc.mem_regions()):
            return False  # Only the two known fresh-ARM64-Uc constructor entries.
        data = memoryview(initial_bytes)
        if (data.nbytes != RX_MEMORY_BYTES or data.ndim != 1 or
                data.itemsize != 1 or
                hashlib.sha256(data[:SHARED_BYTES]).hexdigest() != self.full_digest or
                hashlib.sha256(data[SHARED_BYTES:]).hexdigest() != self.tail_digest):
            raise ValueError('Original generated RX bytes or relocations differ')
        mapping = _Mapping(self._fd)
        lifetime = _Lifetime(mapping)
        original, close, handle = lifecycle
        # Install one ordered cleanup owner before exposing the pointer to Uc.
        # uc is strongly held locally; there is no weak-finalizer race here.
        try:
            finalizer = weakref.finalize(uc, _close_then_release, close, handle, lifetime)
        except BaseException:
            mapping.close()  # No guest mapping refers to it yet.
            raise
        if original.detach() is None:
            finalizer.detach()
            mapping.close()  # Still not exposed to the guest.
            return False
        uc._Uc__finalizer = finalizer
        try:
            self._leases[uc] = lifetime
            uc.mem_map_ptr(address, SHARED_BYTES, permissions, mapping.pointer)
            uc.mem_map(address + SHARED_BYTES, PAGE_BYTES, permissions)
            # mem_map supplies exactly the original zero padding on the tail.
            uc.mem_write(address + SHARED_BYTES, bytes(data[SHARED_BYTES:]))
            return True
        except BaseException:
            # A partial mapping is not a copy-mode fallback. The fresh Uc is
            # closed first, then backing is released by that same finalizer.
            finalizer()
            uc._uch = None
            self._leases.pop(uc, None)
            raise

    def inspect(self):
        return {'mappedBytesPerUc': SHARED_BYTES, 'privateTailBytesPerUc': PAGE_BYTES,
                'liveUcMappings': len(self._leases), 'inode': self.inode,
                'failedFinalizations': len(_FAILED_FINALIZATIONS),
                'retainsOriginalRawBytes': False, 'closed': not self._fd_finalizer.alive}

    def close(self):
        if self._leases:
            raise ValueError('Live Uc mappings still own code backing')
        if not self._fd_finalizer.alive:
            return False
        self._fd_finalizer()
        return True


def create_code_pages(native_bytes, *, cache_dir=None):
    """Default None preserves copy mode. No source is admitted by this helper."""
    if not _supported():
        return None
    if type(native_bytes) is not bytes or hashlib.sha256(native_bytes).hexdigest() != NATIVE_SHA256:
        raise ValueError('Exact supported original native image required')
    data = memoryview(native_bytes)
    full_digest = hashlib.sha256(data[:SHARED_BYTES]).hexdigest()
    tail_digest = hashlib.sha256(data[SHARED_BYTES:RX_MEMORY_BYTES]).hexdigest()
    fd, path, inode = _open_backing(data, full_digest, cache_dir)
    return NativeCodePages(fd, path, inode, full_digest, tail_digest)
