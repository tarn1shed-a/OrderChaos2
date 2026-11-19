"""Opt-in disk-backed residency for the SAME serial ARM64 Unicorn instance.

This changes host page residency only. Guest addresses, permissions, original
mem_write calls, registers, heap, callbacks, clock and RNG remain untouched.
The caller must serialize mapping/reclaim with all execution and host writes;
reclaim belongs AFTER the outer request finally/clock/observer scopes finish.
No timer, actor destruction, heap reconstruction or readiness is provided here.
"""
import ctypes
import mmap
import os
import platform
import stat
import tempfile
from pathlib import Path

from source_code_pages import (PAGE_BYTES, _abort_mapping,
                               _attach_mapping, _existing_lifetime,
                               _original_finalizer)

_DIRECTORY = '/tmp/oc2-native-guest-pages-v1'
_MEMORY_FILESYSTEMS = {0x01021994, 0x858458f6, 0x958458f6}  # tmpfs/ramfs/hugetlbfs


class GuestPageSupportError(RuntimeError):
    pass


class GuestPageReclaimError(RuntimeError):
    def __init__(self, stage, receipt):
        self.stage = stage
        self.receipt = receipt
        super().__init__('Guest page reclaim failed during ' + stage)


def _enabled():
    return os.environ.get('OC2_NATIVE_GUEST_PAGES') == '1'


def _require_supported():
    if (platform.system() != 'Linux' or
            platform.machine().lower() not in ('x86_64', 'amd64') or
            os.sysconf('SC_PAGE_SIZE') != PAGE_BYTES):
        raise GuestPageSupportError('Guest pages require Linux amd64 and 4 KiB pages')
    try:
        import unicorn
    except ImportError as error:
        raise GuestPageSupportError('Guest pages require official Unicorn 2.1.4') from error
    if unicorn.__version__ != '2.1.4':
        raise GuestPageSupportError('Guest pages require official Unicorn 2.1.4')
    if not hasattr(mmap.mmap, 'madvise') or not hasattr(mmap, 'MADV_DONTNEED'):
        raise GuestPageSupportError('Guest pages require mmap MADV_DONTNEED')


def _filesystem_type(fd):
    # Linux amd64 struct statfs starts with signed long f_type. Allocate more
    # than the complete structure; do not interpret platform-dependent tails.
    libc = ctypes.CDLL(None, use_errno=True)
    query = libc.fstatfs
    query.argtypes = (ctypes.c_int, ctypes.c_void_p)
    query.restype = ctypes.c_int
    result = ctypes.create_string_buffer(256)
    if query(fd, result) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    return ctypes.c_long.from_buffer(result).value & 0xffffffff


def _private_file(size):
    root = Path('/tmp').resolve()  # Never honor TMPDIR or write into /data.
    directory = Path(_DIRECTORY).resolve()
    if directory == root or not directory.is_relative_to(root):
        raise ValueError('Guest backing belongs only in its private /tmp directory')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY |
                           os.O_CLOEXEC | os.O_NOFOLLOW)
    fd, name = None, None
    try:
        info = os.fstat(directory_fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or
                info.st_mode & 0o077):
            raise ValueError('Guest backing directory must be owner-only')
        # Check the directory BEFORE creating a file on a memory filesystem.
        filesystem = _filesystem_type(directory_fd)
        if filesystem in _MEMORY_FILESYSTEMS or not filesystem:
            raise GuestPageSupportError('Guest backing must not use a memory filesystem')
        fd, name = tempfile.mkstemp(prefix='.guest-', dir=directory)
        os.fchmod(fd, 0o600)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or
                _filesystem_type(fd) != filesystem):
            raise ValueError('Private guest backing file differs')
        os.unlink(name)
        name = None
        os.ftruncate(fd, size)  # Preserve the exact zero-filled guest extent.
        # Reserve backing BEFORE mmap/pointer exposure. A merely sparse file can
        # SIGBUS on a later original native write when the filesystem is full;
        # that failure cannot be made safe by catching a later flush exception.
        reserve = getattr(os, 'posix_fallocate', None)
        if not callable(reserve):
            raise GuestPageSupportError('Guest backing requires posix_fallocate')
        try:
            reserve(fd, 0, size)
        except (OSError, NotImplementedError) as error:
            raise GuestPageSupportError('Guest backing reservation failed') from error
        info = os.fstat(fd)
        if info.st_size != size or info.st_nlink != 0:
            raise ValueError('Guest backing must be unlinked with the exact size')
        return fd, (info.st_dev, info.st_ino), filesystem
    except BaseException:
        if fd is not None:
            os.close(fd)
        raise
    finally:
        if name is not None:
            os.unlink(name)
        os.close(directory_fd)


class _GuestMapping:
    def __init__(self, address, size, permissions):
        self.address, self.size, self.permissions = address, size, permissions
        self.fd, self.inode, self.filesystem = _private_file(size)
        self.memory = None
        self.anchor = None
        self.closed = False
        self.reclaims = 0
        try:
            self.memory = mmap.mmap(self.fd, size, flags=mmap.MAP_SHARED,
                                    prot=mmap.PROT_READ | mmap.PROT_WRITE)
            self.anchor = (ctypes.c_ubyte * size).from_buffer(self.memory)
            self.pointer = ctypes.addressof(self.anchor)
        except BaseException:
            self.anchor = None
            if self.memory is not None:
                self.memory.close()
            os.close(self.fd)
            self.closed = True
            raise

    def close(self):
        if self.closed:
            return
        self.anchor = None
        self.memory.close()
        os.close(self.fd)
        self.closed = True


def _shape(address, size, permissions):
    if (type(address) is not int or type(size) is not int or
            type(permissions) is not int or address < 0 or size <= 0 or
            address % PAGE_BYTES or size % PAGE_BYTES or
            address + size > 1 << 64 or size > (1 << 63) - 1 or
            not 0 <= permissions <= 7):
        raise ValueError('Aligned ARM64 guest address, size and original permissions required')


def map_guest_region(uc, address, size, permissions=7):
    """True only after actual mapping; disabled False preserves old mem_map.

    Explicit opt-in on an unsupported host/lifecycle/filesystem raises. Errors
    AFTER pointer ownership transfers close that Uc once, then all backings;
    callers must not catch these as an ordinary-map fallback.
    """
    if not _enabled():
        return False
    _require_supported()
    _shape(address, size, permissions)
    owner = _existing_lifetime(uc)
    if owner is None and _original_finalizer(uc) is None:
        raise GuestPageSupportError('Exact official ARM64 Uc lifecycle required')
    for start, end, _ in uc.mem_regions():
        if address <= end and start < address + size:
            raise ValueError('Guest backing overlaps an existing mapping')
    mapping = _GuestMapping(address, size, permissions)
    try:
        owner = _attach_mapping(uc, mapping)
    except BaseException:
        mapping.close()  # Not exposed to Unicorn yet.
        raise
    try:
        uc.mem_map_ptr(address, size, permissions, mapping.pointer)
    except BaseException:
        _abort_mapping(uc, owner)
        raise
    return True


def map_native_region(uc, address, size, permissions=7):
    """Constructor adapter; default-off executes exactly the old mapping call."""
    if not map_guest_region(uc, address, size, permissions):
        uc.mem_map(address, size, permissions)


def _guest_mappings(uc):
    owner = _existing_lifetime(uc)
    return [] if owner is None else [item for item in owner.mappings
                                   if isinstance(item, _GuestMapping)]


def inspect_guest_pages(uc):
    """Only actual host mappings, never a source actor/native-ready receipt."""
    mappings = _guest_mappings(uc)
    return {'enabled': _enabled(), 'actualMappingCount': len(mappings),
            'mappedBytes': sum(item.size for item in mappings),
            'ranges': [{'address': item.address, 'bytes': item.size,
                        'permissions': item.permissions, 'inode': list(item.inode),
                        'filesystem': item.filesystem, 'reclaims': item.reclaims}
                       for item in mappings]}


def reclaim_guest_pages(uc):
    """Flush ALL files before MADV_DONTNEED; same mappings/state remain alive.

    The serial caller guarantees no execution, callback or mem_write is active.
    On failure mapped state is retained, with a precise partial-action receipt;
    the exception is NOT successful reclamation. No new clock or RNG is read.
    """
    mappings = _guest_mappings(uc)
    receipt = {'attempted': bool(mappings), 'mappingCount': len(mappings),
               'mappedBytes': sum(item.size for item in mappings),
               'flushed': [], 'advised': [], 'reclaimed': False}
    if not mappings:
        return receipt
    _require_supported()
    stage = 'flush'
    try:
        for item in mappings:
            item.memory.flush()  # MS_SYNC: never advise a failed/dirty flush.
            receipt['flushed'].append({'address': item.address, 'bytes': item.size})
        stage = 'madvise'
        for item in mappings:
            item.memory.madvise(mmap.MADV_DONTNEED)
            receipt['advised'].append({'address': item.address, 'bytes': item.size})
            item.reclaims += 1
    except Exception as error:
        raise GuestPageReclaimError(stage, receipt) from error
    receipt['reclaimed'] = True  # Advice succeeded; NOT an RSS/physical-free claim.
    return receipt
