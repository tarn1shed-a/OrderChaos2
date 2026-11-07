"""Select source streams by primitive semantic bindings, not stream order.

The source BDAE semantic IDs differ from native runtime attribute IDs. The
mapping below is limited to position, normal and the first two UV sets traced
through 12db214, runtime stream masks, GL reflection and semantic name aliases.
Original scene shader execution, lighting and render states remain separate.
"""
import hashlib
import struct

FORMAT = 'oc2-source-attribute-bindings-v1'
ROLES = {
    'positions': (0, 0, 'position', 3),
    'normals': (1, 15, 'normal', 3),
    'uvs': (4, 1, 'texcoord0', 2),
    'sourceUV1': (5, 2, 'texcoord1', 2),
}
ROUTINES = {
    0x12db214: (3828, '78146b401c2c6daa238ffec76562dbf8d603c5e14216b630db45cda96eac1d34'),
    0x1450548: (348, '92194f9dec28cf96651f1590454fba260cba717538087875f4a299ef67f9f360'),
    0x1450da0: (728, '02c12d2c6afa528aa2d5f8764814cf88ca18c845708b0360998874ae51811260'),
    0x1469d88: (448, '0d77fad86597f52518d3f378897c779184e25ddf307c7380394033a6ce3961e5'),
    0x146a65c: (624, 'd2973d5478758591866e3d240dbf2c6fe7eeffc35819f4a9c084d77b42b53fa6'),
    0x1432f2c: (2212, 'dc4220daa036b16e9fdb980b783b504798e43595df15f1bbb3915bd3f267093e'),
    0x13cee9c: (8432, 'd52f1e63117f3a8045ffad6b019b0028c20b9ef1bf398678286dd03d599fc1d8'),
    0x1462e28: (368, 'fc4d083820ff69540b50c36c9c8eab32e8feafe97b36ad85eef4b3be67b839e0'),
    0x148b304: (164, 'cc580cff5b4a32e1538ded353d6dd93dc6222af7324a285910dc6ec0f8563706'),
    0x14118f8: (916, '1614c768cd6bd4f1cb325d5e08d0643205496ff567c594b9babc8fbe22278614'),
}
NAME_TABLE = 0x250e758
NAME_TARGETS = {0: 0x1faf02e, 1: 0x1f4c12a, 2: 0x1f4c134, 15: 0x1e15fa3}
# Alias records are (relocated name pointer, uint32 runtime semantic, padding).
SHADER_ALIASES = {
    'vertex': (0x2499ae0, 0x1f488b0, 0),
    'normal': (0x24998e0, 0x1e15fa3, 15),
    'texcoord0': (0x2499a00, 0x1f4c12a, 1),
    'texcoord1': (0x2499a10, 0x1f4c134, 2),
}


def verify_native(image):
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Source attribute binding code changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for _, runtime_id, name, _ in ROLES.values():
        target = NAME_TARGETS[runtime_id]
        if (rels.get(NAME_TABLE + runtime_id*8) != target or
                image.read(target, len(name)+1) != name.encode()+b'\0'):
            raise ValueError('Native attribute semantic name table changed; retrace required')
    if rels.get(0x250e740) != 0x24996d0 or rels.get(0x250e748) != 0x2499b00:
        raise ValueError('Native shader semantic alias range changed; retrace required')
    for name, (record, target, runtime_id) in SHADER_ALIASES.items():
        if (rels.get(record) != target or image.read(target, len(name)+1) != name.encode()+b'\0' or
                image.read(record+8, 4) != struct.pack('<I', runtime_id)):
            raise ValueError('Native shader semantic alias changed; retrace required')
    return {'routineCount': len(ROUTINES), 'checkedRuntimeNames': len(NAME_TARGETS),
            'checkedShaderAliases': len(SHADER_ALIASES), 'sourceToGLSemanticChainVerified': True,
            'sourceUV0Semantic': 4, 'sourceUV1Semantic': 5,
            'originalSceneShaderExecutionRestored': False}


def primitive_bindings(reader, primitive, attribute_count):
    """Source 88-byte primitive +20/+24 points to 8-byte semantic/index rows."""
    reader.at(primitive, 88)
    count, table = reader.u(primitive + 20), reader.rel(primitive + 24)
    if not 1 <= count <= 64:
        raise ValueError('Unsupported source primitive semantic count')
    reader.at(table, count*8)
    result = {}
    for index in range(count):
        at = table + index*8
        source_id, attribute = reader.u(at), reader.unpack('b', at + 4)[0]
        if source_id in result:
            raise ValueError('Duplicate source primitive semantic')
        # Native ldrsb plus sign test: any negative index is an absent stream.
        if attribute >= attribute_count:
            raise ValueError('Source semantic attribute index outside stream table')
        result[source_id] = None if attribute < 0 else attribute
    return result


def select_attributes(reader, primitive_table, primitive_count, attributes,
                      vertex_count, vertex_bytes):
    """Require shared role bindings across primitives in a converted mesh.

    The web format has mesh-wide streams; differing per-primitive bindings
    need separate geometry instead of silently applying the first group's UV.
    UV1 is retained as source data only, pending original lightmap evaluation.
    """
    if not 1 <= primitive_count <= 255 or not 1 <= len(attributes) <= 16 or vertex_count < 1:
        raise ValueError('Invalid source mesh attribute/primitive counts')
    reader.at(primitive_table, primitive_count*88)
    selected = None
    for index in range(primitive_count):
        bindings = primitive_bindings(reader, primitive_table + index*88, len(attributes))
        current = {role: bindings.get(source_id) for role, (source_id, _, _, _) in ROLES.items()}
        if any(current[role] is None for role in ('positions', 'normals', 'uvs')):
            raise ValueError('Missing required source position/normal/UV0 semantic')
        if selected is not None and current != selected:
            raise ValueError('Per-primitive attribute bindings differ; mesh splitting is required')
        selected = current
    streams, descriptors = {}, {}
    for role, attribute in selected.items():
        if attribute is None:
            continue
        stride, offset, kind, count = attributes[attribute]
        source_id, runtime_id, name, expected_count = ROLES[role]
        if (kind != 6 or count != expected_count or not 0 < stride <= 65535 or offset < 0 or
                offset + count*4 > stride or (vertex_count-1)*stride + offset + count*4 > vertex_bytes):
            raise ValueError('Unsupported or truncated source semantic stream: ' + name)
        streams[role] = attributes[attribute]
        descriptors[role] = {'sourceSemantic': source_id, 'runtimeSemantic': runtime_id,
                             'runtimeName': name, 'attributeIndex': attribute,
                             'stride': stride, 'offset': offset, 'type': kind, 'components': count}
    return streams, {'format': FORMAT, 'checkedPrimitives': primitive_count,
                     'streams': descriptors,
                     'uv1Usage': 'retained source coordinates; original lightmap not applied'}
