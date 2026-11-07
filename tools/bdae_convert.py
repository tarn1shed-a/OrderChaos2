"""Conservative static mesh reader for the observed BDAE 0,0,0,946 assets.

Format research references (not runtime dependencies):
https://github.com/lOlbas/Game-Engines-Filetypes-Reverse-Engineering/tree/master/engines/Gameloft/bdae/v0.0.0.946/templates
https://github.com/fata1error404/oac-bdae-viewer

This is an independently written parser. It does not use original game engine code.
Current limits: little-endian unquantized, float32 position/normal/UV streams,
16-bit triangle lists, static bind pose. Skinning, node transforms, and original
shaders are not evaluated. Single-material models have a definitive material;
material names are resolved from each primitive's self-relative name pointer.
"""
import argparse
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path
from bdae_primitives import primitive_indices, FORMAT as PRIMITIVE_INDEX_FORMAT
from bdae_attributes import select_attributes, FORMAT as ATTRIBUTE_FORMAT


class BDAE:
    def __init__(self, path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        if raw[:4] == b'PK\x03\x04':
            with zipfile.ZipFile(self.path) as archive:
                raw = archive.read('little_endian_not_quantized.bdae')
        self.b = raw
        if raw[:8] != b'BRES\xfe\xff\x00\x00' or self.u(8) != 64 or self.u(12) != len(raw):
            raise ValueError('Unsupported BRES header')
        self.info = self.q(40)
        self.version = self.string(self.q(self.info))
        if self.version != '0,0,0,946':
            raise ValueError(f'Unsupported BDAE version: {self.version}')

    def at(self, offset, size):
        if offset < 0 or offset + size > len(self.b):
            raise ValueError(f'BDAE read outside buffer at {offset:#x}, size {size}')
        return offset

    def unpack(self, fmt, offset):
        return struct.unpack_from('<' + fmt, self.b, self.at(offset, struct.calcsize('<' + fmt)))

    def u(self, offset): return self.unpack('I', offset)[0]
    def i(self, offset): return self.unpack('i', offset)[0]
    def q(self, offset): return self.unpack('Q', offset)[0]
    def rel(self, offset): return offset + self.i(offset)

    def string(self, offset):
        self.at(offset, 1)
        end = self.b.find(b'\0', offset)
        if end < 0 or end - offset > 2048:
            raise ValueError('Invalid BDAE string')
        return self.b[offset:end].decode('utf-8')

    def section(self, relative):
        field = self.info + relative
        count = self.u(field)
        if count > 10000:
            raise ValueError('Unreasonable section count')
        return count, self.rel(field + 4)

    def named_technique(self, value):
        """Observed type28 record: native lookup uses the name at +8.

        Preserve the first word without mislabelling it a technique ordinal.
        Other value-record branches require separate recovery.
        """
        self.at(value, 16)
        if self.unpack('2I', value) != (2, 0):
            raise ValueError('Unsupported source technique value record')
        name = self.string(self.q(value + 8))
        if not name:
            raise ValueError('Empty source technique name')
        return {'valueWord0': 2, 'name': name}

    def parse(self):
        texture_count, texture_table = self.section(148)
        textures = [self.string(self.q(texture_table + n * 32 + 16)) for n in range(texture_count)]
        material_count, material_table = self.section(172)
        materials = []
        for n in range(material_count):
            at = material_table + n * 80
            props, prop_table = self.u(at + 32), self.rel(at + 36)
            samplers = {}
            for p in range(props):
                prop = prop_table + p * 32
                if self.u(prop + 16) == 17:
                    value = self.rel(prop + 28)
                    texture = self.rel(value)
                    index = (texture - texture_table) // 32
                    if texture_table <= texture < texture_table + texture_count * 32 and (texture - texture_table) % 32 == 0:
                        samplers[self.string(self.q(prop))] = textures[index]
            materials.append({'name': self.string(self.q(at)), 'samplers': samplers, 'diffuse': samplers.get('texture')})

        mesh_count, mesh_table = self.section(180)
        meshes = []
        bounds = [[float('inf')] * 3, [float('-inf')] * 3]
        warnings = []
        for n in range(mesh_count):
            record = mesh_table + n * 24
            wrapper = self.rel(record + 20)
            buffer_start = self.q(wrapper + 8)
            prefix_count = self.u(wrapper + 4) & 0xffffff
            if not 1 <= prefix_count <= 256:
                raise ValueError(f'Unsupported mesh buffer prefix count: {prefix_count}')
            # Removable mesh buffers contain a variable u64 relocation prefix.
            # The field layout below includes its final u64 word for historical
            # compatibility with the common one-prefix character samples.
            data = buffer_start + (prefix_count - 1) * 8
            vertex_count = self.u(data + 12)
            attribute_count = self.u(data + 16)
            if not 0 < vertex_count < 200000 or not 3 <= attribute_count <= 16:
                raise ValueError('Unexpected mesh vertex/attribute count')
            strides = self.rel(data + 20)
            offsets = self.rel(data + 28)
            types = self.rel(data + 36)
            components = self.rel(data + 44)
            attrs = [(self.u(strides + k * 4), self.u(offsets + k * 4), self.u(types + k * 4), self.u(components + k * 4)) for k in range(attribute_count)]
            primitive_count, primitive_table = self.u(data + 96), self.rel(data + 100)
            vertex_ptr, vertex_bytes = self.q(data + 64), self.q(data + 72)
            self.at(vertex_ptr, vertex_bytes)
            streams, source_attributes = select_attributes(self, primitive_table, primitive_count,
                                                           attrs, vertex_count, vertex_bytes)
            values = {role: [] for role in streams}
            for role, (stride, offset, dtype, count) in streams.items():
                for v in range(vertex_count):
                    elements = self.unpack('f' * count, vertex_ptr + v * stride + offset)
                    if not all(math.isfinite(f) for f in elements):
                        raise ValueError('Non-finite vertex attribute')
                    values[role].extend(round(f, 7) for f in elements)
                    if role == 'positions':
                        for axis in range(3):
                            bounds[0][axis] = min(bounds[0][axis], elements[axis])
                            bounds[1][axis] = max(bounds[1][axis], elements[axis])
            indices = []
            groups = []
            for k in range(primitive_count):
                primitive = primitive_table + k * 88
                face_indices, source_window = primitive_indices(self, primitive, vertex_count)
                count = len(face_indices)
                material_name = self.string(primitive + 8 + self.q(primitive + 8))
                material_index = next((i for i, m in enumerate(materials) if m['name'] == material_name), None)
                if material_index is None:
                    warnings.append(f'Unresolved primitive material: {material_name}')
                groups.append({'start': len(indices), 'count': count, 'material': material_index, 'materialName': material_name, **source_window})
                indices.extend(face_indices)
            unique_materials = set(g['material'] for g in groups)
            meshes.append({'name': self.string(self.q(record)), **values, 'sourceAttributes': source_attributes,
                           'indices': indices, 'material': groups[0]['material'] if len(unique_materials) == 1 else None,
                           'groups': groups, 'vertexCount': vertex_count, 'triangleCount': len(indices) // 3})
            # Verified character/equipment layout: native VS uses T at +32 and
            # negative B at +44. Retain these streams instead of inventing TBN.
            if attrs == [(56,0,6,3),(56,12,6,3),(56,24,6,2),(56,32,6,3),(56,44,6,3)]:
                for key,offset in [('sourceTangents',32),('sourceBinormals',44)]:
                    directions=[]
                    for v in range(vertex_count):
                        vector=self.unpack('3f',vertex_ptr+v*56+offset)
                        if not all(math.isfinite(value) for value in vector):raise ValueError('Non-finite source tangent/binormal')
                        directions.extend(round(value,7) for value in vector)
                    meshes[-1][key]=directions
        warnings.append('Static source geometry only; node transforms, skinning, original shaders, and animations are not evaluated.')
        return {'format': 'bdae946-static-v1', 'source': self.path.as_posix(), 'sourceSHA256': hashlib.sha256(self.path.read_bytes()).hexdigest(), 'version': self.version, 'coordinateSystem': 'Y_UP',
                'sourceIndexing':{'format':PRIMITIVE_INDEX_FORMAT,'mode':'mesh-wide indices rebased from each source primitive vertex window'},
                'sourceAttributes':{'format':ATTRIBUTE_FORMAT,'mode':'source semantics checked across each mesh primitive'},
                'textures': textures, 'materials': materials, 'meshes': meshes, 'bounds': bounds, 'warnings': warnings}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('source', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    result = BDAE(args.source).parse()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    print(json.dumps({'output': str(args.output), 'meshes': len(result['meshes']), 'vertices': sum(m['vertexCount'] for m in result['meshes']), 'triangles': sum(m['triangleCount'] for m in result['meshes']), 'bounds': result['bounds'], 'materials': result['materials']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
