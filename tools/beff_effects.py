"""Recover v9 BEFF dependencies and complete emitter/particle parameter streams."""
import hashlib
import struct
from pathlib import Path, PurePosixPath
from beff_particles import decode_particle_payload


EFFECT_SOURCES = {
    'fireCast': 'effects/skill/mage/fire_cast_inhand_red_loop.beff',
    'fireMissile': 'effects/skill/mage/fireball_default_missile_inhand_loop.beff',
    'fireHit': 'effects/skill/mage/fireball_hit_chest_red.beff',
    'frostHit': 'effects/skill/mage/frost_blast_default_channel_ground_acyclic.beff',
}


def decode_effect(data):
    if len(data) < 56 or data[:4] != b'beff':
        raise ValueError('Invalid or truncated BEFF header')
    version = struct.unpack_from('<I', data, 4)[0]
    if version != 9:
        raise ValueError(f'Unsupported BEFF version: {version}')
    duration = struct.unpack_from('<I', data, 24)[0]
    if duration != 0xffffffff and not 0 < duration <= 600000:
        raise ValueError('Unsupported BEFF duration header')
    count = struct.unpack_from('<I', data, 48)[0]
    if not 1 <= count <= 256:
        raise ValueError('Unsupported BEFF dependency count')
    at, names = 52, []
    for _ in range(count):
        if at + 4 > len(data):
            raise ValueError('Truncated BEFF dependency length')
        size = struct.unpack_from('<I', data, at)[0]
        at += 4
        if not 0 < size <= 4096 or size % 4 or at + size > len(data):
            raise ValueError('Invalid BEFF padded string extent')
        raw = data[at:at + size]
        at += size
        end = raw.find(b'\0')
        if end <= 0 or any(raw[end:]):
            raise ValueError('Invalid BEFF NUL-terminated dependency')
        try:
            name = raw[:end].decode('utf-8')
        except UnicodeDecodeError as error:
            raise ValueError('Invalid BEFF dependency encoding') from error
        if name != '.':
            path = PurePosixPath(name)
            if path.name != name or '\\' in name or ':' in name or path.suffix.lower() != '.tga':
                raise ValueError(f'Unsupported BEFF texture dependency: {name}')
        names.append(name)
    if names.count('.') != 1 or len(set(names)) != len(names) or len(names) < 2:
        raise ValueError('Unsupported BEFF dependency table')
    if at >= len(data):
        raise ValueError('Missing BEFF emitter payload')
    particles = decode_particle_payload(data, at, names, struct.unpack_from('<I',data,20)[0])
    return {
        'format': 'beff9-particle-system-v2',
        'headerWords': list(struct.unpack_from('<12I',data)),
        'sourceSHA256': hashlib.sha256(data).hexdigest(),
        'durationMs': None if duration == 0xffffffff else duration,
        'loop': duration == 0xffffffff,
        'emitters':particles['emitters'], 'sampleRate':30, 'keySampling':particles['keySampling'],
        'textures': ['texture/' + name for name in names if name != '.'],
        'verification': {
            'version': version, 'dependencyCount': count,
            'textureTableEnd': at, 'opaquePayloadBytes': 0,
            **particles['verification'],
            'durationFieldOffset': 24,
            'durationInterpretation': 'Finite milliseconds or 0xffffffff unbounded effect; emitter and particle times use 30 FPS frame counts.',
        },
        'limitations': [
            'Native random sequence, complete shaders/HDR and original skill attachment transforms are not reproduced.',
            'Unidentified header words and auxiliary curves are retained without inventing semantics.',
        ],
    }


def recover_effect(path):
    return decode_effect(Path(path).read_bytes())
