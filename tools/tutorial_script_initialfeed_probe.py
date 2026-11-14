"""Bounded local InitialFeed decoder controls; no network/config values emitted.

The original envelope, cipher, digest and JSON tokenizer execute on ARM64.
Allocation/COW-string storage and bounded libc are explicit host interfaces.
The disk file is NOT claimed to be the original inner file-system read result.
"""
import hashlib
import json
import struct
from pathlib import Path

from source_physics import SourcePhysics

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-initialfeed-20261115'
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SOURCE = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files/InitialFeed.dat'
SOURCE_SHA = 'a794b8e66758bdfd0baa09dd472c31034a5c16360f7ac38d5441bf093f3e5c55'


class InitialFeedProbe(SourcePhysics):
    DISK_READ = SourcePhysics.EXIT + 0xe20
    POSITION_ZERO = SourcePhysics.EXIT + 0xe24
    def __init__(self, image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.interfaces = []
        for at in (0x1de6260, 0x1de73b8, self.DISK_READ, self.POSITION_ZERO):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def string(self, raw):
        at = self.alloc(24 + len(raw) + 1)
        self.w(at, '3Q', len(raw), len(raw), 0)
        self.uc.mem_write(at + 24, raw + b'\0')
        return at + 24

    def hook(self, uc, at, size, data):
        if at == self.DISK_READ:
            count = self.get('X2')
            if count != len(self.control_read_bytes):
                raise ValueError('Only one complete, explicit local disk read admitted')
            uc.mem_write(self.get('X1'), self.control_read_bytes)
            self.interfaces.append({'kind': 'explicit-lower-stream-byte-read', 'bytes': count,
                                    'originalProviderOrOpenExecuted': False})
            self.set('W0', count)
        elif at == self.POSITION_ZERO:
            self.set('X0', 0)
            self.interfaces.append({'kind': 'explicit-stream-position', 'value': 0,
                                    'actualRuntimePositionObserved': False})
        elif at == 0x1de6260:
            count = self.get('X2')
            if count > 4096:
                raise ValueError('Bounded local string construction only')
            raw = bytes(uc.mem_read(self.get('X1'), count))
            self.w(self.get('X0'), 'Q', self.string(raw))
            self.interfaces.append({'kind': 'COW-string-construction', 'bytes': count})
        elif at == 0x1de73b8:
            source = self.r(self.get('X1'), 'Q')[0]
            count = self.r(source - 24, 'Q')[0]
            self.w(self.get('X0'), 'Q', self.string(bytes(uc.mem_read(source, count))))
            self.interfaces.append({'kind': 'COW-string-assignment', 'bytes': count})
        elif at in self.imports and self.imports[at] == 'strncmp':
            count = self.get('X2')
            if count != 32:
                raise ValueError('Only original 32-byte envelope digest comparison admitted')
            left = bytes(uc.mem_read(self.get('X0'), count)).split(b'\0')[0]
            right = bytes(uc.mem_read(self.get('X1'), count)).split(b'\0')[0]
            self.set('W0', 0 if left == right else (1 if left > right else 0xffffffff))
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def digest(self, raw):
        at = self.alloc(len(raw)); out = self.alloc(40)
        self.uc.mem_write(at, raw)
        assert self.call(0x18d3de4, {'X0': at, 'X1': len(raw), 'X2': out}) == 1
        result = bytes(self.uc.mem_read(out, 32))
        assert result == hashlib.md5(raw).hexdigest().upper().encode()
        return result

    def encrypt_fixture(self, payload, *, wrong_digest=False, wrong_length=False):
        raw = struct.pack('<I', len(payload) + (4096 if wrong_length else 0)) + payload
        raw += b'0' * 32 if wrong_digest else self.digest(raw)
        capacity = (len(raw) + 3) & ~3
        source = self.alloc(capacity); out = self.alloc(capacity)
        self.uc.mem_write(source, raw)
        result = self.call(0x18d4f84, {'X0': source, 'X1': len(raw), 'X2': out,
                                   'X3': capacity, 'X4': 0x250bef0})
        assert result == 1
        return bytes(self.uc.mem_read(out, capacity))

    def decode(self, raw):
        at = self.alloc(len(raw)); vector = self.alloc(24); output = self.alloc(8)
        self.uc.mem_write(at, raw)
        self.w(vector, '3Q', at, at + len(raw), at + len(raw))
        self.w(output, 'Q', self.string(b''))
        self.interfaces = []
        result = self.call(0xecbd54, {'X0': 0, 'X1': vector, 'X2': output}) & 0xffffffff
        result = result - (1 << 32) if result & (1 << 31) else result
        pointer = self.r(output, 'Q')[0]; count = self.r(pointer - 24, 'Q')[0]
        return result, bytes(self.uc.mem_read(pointer, count)), list(self.interfaces)

    def tokenizer_fixture(self):
        raw = b'{"probe":true,"n":null,"arr":[1,false]}'
        text = self.alloc(len(raw)); parser = self.alloc(0x100); token = self.alloc(24)
        self.uc.mem_write(text, raw)
        self.w(parser + 0xb0, '2Q', text + len(raw), text)
        tokens = []
        for _ in range(40):
            assert self.call(0x1984d9c, {'X0': parser, 'X1': token}, limit=3000) == 1
            kind, start, end = self.r(token, 'I4xQQ')
            tokens.append({'type': kind, 'start': start - text, 'end': end - text})
            if kind == 0:
                break
        assert [x['type'] for x in tokens] == [1, 5, 11, 7, 10, 5, 11, 9, 10, 5, 11, 3, 6, 10, 8, 4, 2, 0]
        return {'originalTokenizer': '0x1984d9c', 'fixtureIsNotOriginalConfiguration': True,
                'tokens': tokens, 'completeJsonReaderExecuted': False}

    def read_transform_control(self, raw, header_flag):
        """Execute the full original read method against a named byte-read interface.

        No open/provider factory or resource registration is claimed successful.
        File fields/position are explicit inputs, not recovered runtime defaults.
        """
        file = self.alloc(0x60); vt = self.alloc(0x90)
        stream = self.alloc(0x10); stream_vt = self.alloc(0x40)
        output = self.alloc(len(raw))
        self.w(file, 'Q', vt)
        self.w(file + 0x40, 'I', 0x80001 | (0x40000 if header_flag else 0))
        self.w(file + 0x48, 'Q', stream); self.w(vt + 0x80, 'Q', self.POSITION_ZERO)
        self.w(stream, 'Q', stream_vt); self.w(stream_vt + 0x30, 'Q', self.DISK_READ)
        self.control_read_bytes = raw; self.interfaces = []
        result = self.call(0x15405d0, {'X0': file, 'X1': output, 'X2': len(raw)})
        transformed = bytes(self.uc.mem_read(output, len(raw)))
        expected = bytes((b - i - 1) & 255 for i, b in enumerate(raw[:4])) + raw[4:] if header_flag else raw
        assert result == len(raw) and transformed == expected
        return transformed, list(self.interfaces)


def run():
    from analyze_native_resources import NativeImage
    image = NativeImage(SO.read_bytes()); original = SOURCE.read_bytes()
    assert hashlib.sha256(original).hexdigest() == SOURCE_SHA
    probe = InitialFeedProbe(image)
    payload = b'{"fixture":true}'
    encrypted = probe.encrypt_fixture(payload)
    good, decoded, interfaces = probe.decode(encrypted)
    assert good == 0 and decoded == payload
    bad_hash, _, _ = probe.decode(probe.encrypt_fixture(payload, wrong_digest=True))
    bad_length, _, _ = probe.decode(probe.encrypt_fixture(payload, wrong_length=True))
    assert bad_hash == -4 and bad_length == -3
    raw_result, raw_output, _ = probe.decode(original)
    nul_result, nul_output, _ = probe.decode(original + b'\0')
    assert raw_result == -3 and nul_result == -3 and not raw_output and not nul_output
    header_controls = []; private_decodes = []
    for flag in (False, True):
        transformed, read_interfaces = probe.read_transform_control(original, flag)
        status, payload_bytes, _ = probe.decode(transformed)
        plus_nul_status, _, _ = probe.decode(transformed + b'\0')
        item = {'originalReadMethod': '0x15405d0', 'explicitFlag40000': flag,
                'sameLocalDiskInput': True, 'bytesReturned': len(transformed),
                'firstFourBytesChanged': transformed[:4] != original[:4],
                'remainingBytesUnchanged': transformed[4:] == original[4:],
                'transformedSha256': hashlib.sha256(transformed).hexdigest(),
                'completeEnvelopeReturn': status, 'appendedNulEnvelopeReturn': plus_nul_status,
                'interfaces': read_interfaces, 'actualActiveFlagOrProviderEstablished': False}
        if status == 0:
            private_decodes.append(payload_bytes)
            item['decodedBytes'] = len(payload_bytes)
            item['decodedSha256'] = hashlib.sha256(payload_bytes).hexdigest()
            try:
                parsed = json.loads(payload_bytes)
                item['hostJsonShapeOnly'] = {'valid': True, 'rootType': type(parsed).__name__,
                    'rootCount': len(parsed), 'privateValuesOmitted': True}
            except Exception:
                item['hostJsonShapeOnly'] = {'valid': False, 'privateValuesOmitted': True}
        header_controls.append(item)
    task_table = 0x1f03078
    task_destination = task_table + struct.unpack('<i', image.read(task_table + 2 * 4, 4))[0]
    assert task_destination == 0xee0690
    assert image.read(0x1e38b69, 16) == b'InitialFeed.dat\0'
    result = {'format': 'oc2-local-initialfeed-envelope-controls-v1',
        'nativeSHA256': hashlib.sha256(SO.read_bytes()).hexdigest(),
        'sourceSHA256': SOURCE_SHA, 'sourceBytes': len(original),
        'originalDecodeEntry': '0xecbd54', 'originalCipher': '0x18d5140',
        'originalDigest': '0x18d3de4', 'keyAddress': '0x250bef0',
        'keyInput': 'Original ELF-mapped .data; not claimed to be complete runtime initialization',
        'fixtureControls': {'validEnvelopeReturn': good, 'payloadEqual': decoded == payload,
            'wrongDigestReturn': bad_hash, 'wrongLengthReturn': bad_length,
            'interfaces': interfaces},
        'diskByteControls': {'verbatimReturn': raw_result, 'appendedNulReturn': nul_result,
            'decodedOutputProduced': False, 'originalInnerFileReadEstablished': False,
            'originalFileCorruptionEstablished': False},
        'sourceContract': {
            'fileEntry': '0x8e3864', 'pathBuilder': '0x15427d4', 'openWrapper': '0xa7e490',
            'copyIncludesAppendedNul': '0x8e393c..0x8e3978',
            'firstManagerCall': '0x8e3c9c -> ed1aac, W3=1',
            'taskId': 0x1967, 'taskIdStore': '0xed1d20',
            'threadFunctionGot': '0x25059f0 -> 0xeda3e4',
            'taskJumpTable': hex(task_table), 'taskJumpIndex': 2,
            'taskJumpDestination': hex(task_destination),
            'syncManagerCall': '0xee075c -> ed1aac, W3=0',
            'sameVectorCopiedFrom': 'manager+0x198, ee06b0..ee0704',
            'decoderCall': '0xed1c34 -> ecbd54',
            'successfulParserCall': '0xed1e3c -> ed3808 -> 19837d0 -> 198381c',
            'parserFieldConsumers': ['iap', 'offline_store'],
            'defaultFileSystemOnly': ['10f75f8', '4d937c', '54b2d4', '24160f0+18=54bc84'],
            'registeredOrAliasedStreamsPrecedeLooseFileFallback': True,
            'looseFallbackOnly': ['1270178', '1274120', '153f940', '153fbec'],
            'pathBuilderCanAddFlags': '153fbec stores original 15427d4 flags',
            'conditionalFirstFourByteTransform': '15405d0, only original flag 0x40000',
            'activeFactoryProviderPathsFlagsOrReadBytesObserved': False,
            'runtimeKeyInitializationObserved': False,
            'scriptFileOrFunctionLoaderObservedInThisBoundedChain': False},
        'jsonTokenizer': probe.tokenizer_fixture(), 'actualInitialFeedDecoded': False,
        'actualContentClassifiedAsConfiguration': False, 'scriptNamesResolvedOrExecuted': False,
        'originalReadHeaderControls': header_controls,
        'wholeTaskOrCrmInitializationExecuted': False, 'networkOrSaveOrRuntimeChanged': False}
    return result, private_decodes


if __name__ == '__main__':
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / 'envelope-controls-v3.json'
    if target.exists():
        raise ValueError('Preserve previous source controls')
    result, private_decodes = run(); target.write_text(json.dumps(result, indent=2) + '\n')
    for index, payload in enumerate(private_decodes):
        (RAW / f'conditional-header-control-payload-private-{index}.bin').write_bytes(payload)
    print(json.dumps({'fixtureControls': 3, 'diskByteControls': 2, 'jsonTokenizer': True,
                      'actualInitialFeedDecoded': False, 'networkAccess': False}))
