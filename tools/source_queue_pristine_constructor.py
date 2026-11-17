"""Pure original pristine queue constructor port. Standard-library only.

Copied byte-identically from the frozen first-history function for old-package
compatibility; no six/eight-body RPC, resources, factory or VM is imported.
"""
import hashlib

ROUTINES = {3325100: (840, '8cf4ae00705fff7db2031b2cdc5656d9578f0005d227f9404ba49b33d20555bf'), 3326304: (1004, '5c236952b582a8f86c588a5fbc06cde36415cb6130ac5839021c65597a23f621')}


def complete_pristine_queue_constructor(engine, identity):
    if identity not in engine.humans:
        raise ValueError('Existing own actor required for constructor reset')
    human = engine.humans[identity]
    queue = human['q']
    if queue.get('originalConstructorReset') is not None:
        raise ValueError('Original constructor reset must execute only once')
    if any(layer['current'] is not None or layer['previous'] is not None or
           layer['control'] is not None or layer['sequence'] != 0
           for layer in queue['layers']):
        raise ValueError('Constructor reset cannot erase a selected track')
    at = queue['engine']
    if any(engine.r(at + channel * 0x218 + 0x2fa, 'B')[0] for channel in (0, 1)):
        raise ValueError('Constructor reset cannot erase a pending animation')
    if engine.r(at + 0x20, '3Q') != (0, 0, 0):
        raise ValueError('Pristine scalar model graph required')
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(engine.image.read(address, size)).hexdigest() != digest:
            raise ValueError('Original animation constructor/reset differs')
    if engine.image.read(0x32bea8, 12).hex() != '01008012e00313aaac000094':
        raise ValueError('Original constructor no longer calls32c160(-1)')
    before = bytes(engine.uc.mem_read(at, 0x700))
    if (before[0x10], before[0x14]) != (0, 0):
        raise ValueError('Unexpected original initial channel state')
    random_words = bytes(engine.uc.mem_read(0x2528410, 32))
    timeval = engine.source_timeval
    engine.scope(identity, lambda _: engine.call(0x32c160, {'X0': at, 'W1': 0xffffffff}))
    after = bytes(engine.uc.mem_read(at, 0x700))
    if random_words != bytes(engine.uc.mem_read(0x2528410, 32)) or timeval != engine.source_timeval:
        raise ValueError('Constructor reset unexpectedly changes source time/RNG')
    if (after[0x10], after[0x14]) != (1, 1):
        raise ValueError('Original constructor reset did not initialize both channels')
    changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
    if set(changed) - ({0x10, 0x14} | set(range(0x650, 0x660))):
        raise ValueError('Unexpected pristine scalar constructor side effect')
    receipt = {
        'originalEntry': '32c160', 'originalConstructorCall': '32beb0',
        'argumentW1': 0xffffffff, 'bothChannelsInitialized': True,
        'changedOffsets': changed, 'sourceTimeAndRNGUnchanged': True,
        'fullModelConstructorExecuted': False, 'GPUExecuted': False,
    }
    queue['originalConstructorReset'] = receipt
    return receipt
