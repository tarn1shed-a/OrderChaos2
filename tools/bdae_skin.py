"""Recover verified 946 node trees and per-mesh skinning data."""
import math

def multiply(a, b):
    return [sum(a[k * 4 + row] * b[column * 4 + k] for k in range(4))
            for column in range(4) for row in range(4)]


def compose(position, quaternion, scale):
    x, y, z, w = quaternion
    sx, sy, sz = scale
    return [(1 - 2 * (y*y + z*z))*sx, 2*(x*y + z*w)*sx, 2*(x*z - y*w)*sx, 0,
            2*(x*y - z*w)*sy, (1 - 2*(x*x + z*z))*sy, 2*(y*z + x*w)*sy, 0,
            2*(x*z + y*w)*sz, 2*(y*z - x*w)*sz, (1 - 2*(x*x + y*y))*sz, 0,
            *position, 1]


def read_nodes(reader):
    count, table = reader.section(220)
    if count != 1:
        raise ValueError('Expected one 946 node tree')
    roots, start = reader.u(table + 16), reader.rel(table + 20)
    if not 0 < roots < 1024:
        raise ValueError('Invalid node root count')
    nodes, seen = [], set()

    def visit(address, parent):
        reader.at(address, 96)
        if address in seen or len(nodes) >= 2048:
            raise ValueError('Cyclic or oversized node hierarchy')
        seen.add(address)
        names = [reader.string(reader.q(address + offset)) for offset in (0, 8, 16)]
        translation = list(reader.unpack('3f', address + 24))
        quaternion = list(reader.unpack('4f', address + 36))
        scale = list(reader.unpack('3f', address + 52))
        if not all(math.isfinite(v) for v in translation + quaternion + scale):
            raise ValueError('Non-finite node transform')
        length = math.sqrt(sum(v*v for v in quaternion))
        if abs(length - 1) > .002 or any(abs(v) < 1e-8 for v in scale):
            raise ValueError('Invalid node rotation or scale')
        quaternion = [v / length for v in quaternion]
        index = len(nodes)
        nodes.append({'name': names[0], 'aliases': [name for name in names[1:] if name],
                      'parent': parent, 'position': translation,
                      'quaternion': quaternion, 'scale': scale})
        children = reader.u(address + 72)
        if children > 1024:
            raise ValueError('Invalid node child count')
        if children:
            children_start = reader.rel(address + 76)
            reader.at(children_start, children * 96)
            for child in range(children):
                visit(children_start + child * 96, index)

    for index in range(roots):
        visit(start + index * 96, -1)
    return nodes


def recover_skin(reader, model, *, external_nodes=None):
    # Modular clothing references the player's skeleton rather than duplicating
    # it in the piece file. The same inverse-bind/rest-shape checks still apply.
    nodes = read_nodes(reader) if external_nodes is None else external_nodes
    aliases, world = {}, []
    for index, node in enumerate(nodes):
        for name in [node['name'], *node['aliases']]:
            if name in aliases and aliases[name] != index:
                raise ValueError(f'Ambiguous skeleton node alias: {name}')
            aliases[name] = index
        local = compose(node['position'], node['quaternion'], node['scale'])
        world.append(local if node['parent'] < 0 else multiply(world[node['parent']], local))
    count, table = reader.section(188)
    if not 0 < count <= len(model['meshes']):
        raise ValueError('Invalid mesh skin count')
    mesh_by_name = {mesh['name'] + '-skin': index for index, mesh in enumerate(model['meshes'])}
    skins, used_meshes = [], set()
    for ordinal in range(count):
        record = table + ordinal * 24
        name = reader.string(reader.q(record + 8))
        if name not in mesh_by_name or mesh_by_name[name] in used_meshes:
            raise ValueError(f'Missing or duplicated skin mesh: {name}')
        mesh_index = mesh_by_name[name]
        used_meshes.add(mesh_index)
        wrapper = reader.rel(record + 16)
        prefix = reader.u(wrapper + 4) & 0xffffff
        buffer, length = reader.q(wrapper + 8), reader.q(wrapper + 16)
        reader.at(buffer, length)
        def skin_range(address, size):
            if address < buffer or address + size > buffer + length:
                raise ValueError('Skin metadata escapes its removable buffer')
            reader.at(address, size)
        if not 1 <= prefix <= 1024:
            raise ValueError('Invalid skin relocation prefix')
        data = buffer + (prefix - 1) * 8
        skin_range(data, 184)
        bone_count, maximum = reader.u(data + 88), reader.u(data + 176)
        if not 0 < bone_count <= 256 or not 1 <= maximum <= 4:
            raise ValueError('Invalid bone count or influence count')
        if reader.u(data + 8) != bone_count * 16:
            raise ValueError('Inverse bind matrix count mismatch')
        bind_shape = list(reader.unpack('16f', data + 16))
        bind_start, names_start = reader.rel(data + 12), reader.rel(data + 92)
        skin_range(bind_start, bone_count * 64)
        skin_range(names_start, bone_count * 8)
        bone_names, bone_nodes, inverses, rest_errors = [], [], [], []
        for bone in range(bone_count):
            field = names_start + bone * 8
            name_pointer = field + reader.q(field)
            skin_range(name_pointer, 1)
            bone_name = reader.string(name_pointer)
            skin_range(name_pointer, len(bone_name.encode('utf-8')) + 1)
            if bone_name not in aliases:
                raise ValueError(f'Unmapped skin bone: {bone_name}')
            node = aliases[bone_name]
            inverse = list(reader.unpack('16f', bind_start + bone * 64))
            if not all(math.isfinite(v) for v in inverse + bind_shape):
                raise ValueError('Non-finite skin matrix')
            bone_names.append(bone_name)
            bone_nodes.append(node)
            inverses.append(inverse)
            product = multiply(world[node], inverse)
            rest_errors.append(max(abs(a - b) for a, b in zip(product, bind_shape)))
        if max(rest_errors) > .002:
            raise ValueError('Rest skeleton and inverse binds do not reproduce bind shape')
        weight_start, weight_bytes = reader.q(data + 104), reader.q(data + 112)
        vertices, stride = model['meshes'][mesh_index]['vertexCount'], (maximum + 1) * 4
        if weight_bytes != vertices * stride:
            raise ValueError('Skin vertex count differs from geometry')
        reader.at(weight_start, weight_bytes)
        indices, weights, max_sum_error = [], [], 0.0
        for vertex in range(vertices):
            address = weight_start + vertex * stride
            joints = list(reader.unpack('4B', address))
            values = list(reader.unpack('f' * maximum, address + 4))
            total = sum(values)
            if not all(math.isfinite(v) and 0 <= v <= 1.00001 for v in values) or abs(total - 1) > .002:
                raise ValueError('Invalid skin weights')
            for joint, weight in zip(joints, values):
                if weight > 0 and joint >= bone_count:
                    raise ValueError('Skin vertex references an unknown bone')
            max_sum_error = max(max_sum_error, abs(total - 1))
            indices.extend([joint if weight > 0 else 0 for joint, weight in zip(joints, values)] + [0] * (4 - maximum))
            weights.extend([v / total for v in values] + [0.0] * (4 - maximum))
        skins.append({'mesh': mesh_index, 'name': name, 'boneNames': bone_names,
                      'boneNodes': bone_nodes, 'inverseBindMatrices': inverses,
                      'bindShapeMatrix': bind_shape, 'skinIndices': indices, 'skinWeights': weights,
                      'verification': {'vertices': vertices, 'maximumInfluences': maximum,
                          'maximumWeightSumError': max_sum_error,
                          'maximumRestBindShapeError': max(rest_errors)}})
    return {'nodes': nodes, 'skins': skins, 'quaternionConvention': 'XYZW',
            'matrixConvention': 'column-major', 'coordinateSystem': 'Y_UP'}
