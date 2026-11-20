"""Candidate host-only constructor setting; not installed or executed.

Call ONLY immediately after a new official Uc object is returned and before
ANY mem_map/reg/hook/control getter or guest instruction. Unicorn's getter
initializes the engine, so it cannot verify this precondition. The two reviewed
constructor call sites, not a guessed initialized flag, enforce that boundary.
No size is selected here: an operator must explicitly supply validated bytes.
"""
import os
import platform
import re

ENVIRONMENT = 'OC2_NATIVE_TCG_BUFFER_BYTES'
_MINIMUM_BYTES = 1 << 20
_MAXIMUM_BYTES = 2 << 30
_MARKER = '_oc2_host_tcg_constructor_configuration_v1'


def configure_uc_tcg_before_init(uc):
    """Return a requested-setting receipt, never game/pose readiness.

Unset/0 preserves the complete old path: no Unicorn import, setter, getter or
private marker. Enabled configuration is limited to the reviewed 2.1.4 Linux
amd64 dynamic-code-buffer implementation. No running-engine resize is offered.
"""
    value = os.environ.get(ENVIRONMENT)
    if value is None or value == '0':
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('Explicit canonical decimal TCG buffer bytes required')
    # Validate BEFORE official ctypes converts to c_uint32. Refuse values that
    # its native code would clamp, rather than reporting a different budget.
    if len(value) > 10:
        raise ValueError('TCG buffer bytes exceed the reviewed uint32/native range')
    size = int(value)
    if not _MINIMUM_BYTES <= size <= _MAXIMUM_BYTES:
        raise ValueError('TCG buffer must be within the reviewed 1MiB..2GiB range')
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise ValueError('Explicit TCG buffer setting is reviewed only on Linux amd64')
    from unicorn import Uc, __version__
    if __version__ != '2.1.4' or not isinstance(uc, Uc):
        raise ValueError('Original official Unicorn 2.1.4 Uc instance required')
    if getattr(uc, _MARKER, None) is not None:
        raise ValueError('TCG buffer can only be configured once at construction')
    setter = getattr(Uc, 'ctl_set_tcg_buffer_size', None)
    if not callable(setter):
        raise ValueError('Official TCG buffer setter is unavailable')
    # DO NOT call ctl_get_tcg_buffer_size: even a read invokes UC_INIT.
    # The original official method is used directly, not a patched per-body
    # callback. Any UcError propagates; there is no silent default fallback.
    setter(uc, size)
    receipt = {'environment': ENVIRONMENT, 'requestedBytes': size,
        'setterReturnedWithoutException': True, 'readbackPerformed': False,
        'effectiveAllocationOrMemorySavingsMeasured': False,
        'callSiteMustPrecedeFirstUcInitialization': True,
        'originalGuestMathClockRNGOrAddressesChanged': False}
    setattr(uc, _MARKER, receipt)
    return dict(receipt)
