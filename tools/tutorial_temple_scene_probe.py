"""Inspect exact source faces behind the current temple preview, without edits.

Source model records, native initial node assembly, preview groups, and explicit
ray inputs are kept separate. A ray/point is an inspection input, not a spawn.
This never changes a model, character position, production package, or save.
"""
import argparse
import hashlib
import json
import math
import struct
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-source-temple-scene-face-review-v1'
SOURCE_PREFIX = 'model/scene_generator_temple_000/'
MODELS = tuple(SOURCE_PREFIX + n + '.bdae' for n in (
    'god_temple01', 'god_temple02', 'god_temple03', 'god_temple04',
    'god_temple05', 'god_temple01_inside01', 'god_bridge_04'))
DEFAULT_PACKAGE = ROOT/'analysis/raw/tutorial-scene-effects-20261114/fire10-complete-v1.tar.gz'
DEFAULT_NATIVE = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
PACKAGE_SHA256 = '2319ad6189a95f88ef5e556c69303217ba6d27464a1d3ed955675578817f121b'
NATIVE_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def private_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Full source records must remain in analysis/raw/')
    return path


def transform(matrix, point):
    if len(matrix) != 16 or len(point) != 3:
        raise ValueError('A source 4x4 matrix and 3D point are required')
    return [sum(matrix[c*4+r]*point[c] for c in range(3))+matrix[12+r]
            for r in range(3)]


def subtract(a, b):
    return [x-y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def triangle_hit(origin, direction, vertices):
    """Two-sided inspection ray; report winding rather than change culling."""
    a, b, c = vertices
    e1, e2 = subtract(b, a), subtract(c, a)
    h = cross(direction, e2)
    determinant = dot(e1, h)
    if abs(determinant) < 1e-10:
        return None
    q = subtract(origin, a)
    u = dot(q, h)/determinant
    if u < -1e-7 or u > 1+1e-7:
        return None
    v = dot(direction, cross(q, e1))/determinant
    if v < -1e-7 or u+v > 1+1e-7:
        return None
    distance = dot(e2, cross(q, e1))/determinant
    if distance < 0:
        return None
    return {'distance': distance, 'barycentric': [1-u-v, u, v],
            'frontFacing': determinant > 0,
            'position': [origin[i]+distance*direction[i] for i in range(3)]}


def source_nodes(reader):
    count, table = reader.section(220)
    if count != 1:
        raise ValueError('A separately recovered source scene layout is required')
    rows, seen = [], set()

    def visit(at, parent):
        reader.at(at, 96)
        if at in seen or len(seen) >= 2048:
            raise ValueError('Unbounded source scene tree')
        seen.add(at)
        index = len(rows)
        attachments = []
        for i in range(reader.u(at+80)):
            desc = reader.rel(at+84)+i*8
            kind = reader.u(desc)
            ref = reader.rel(desc+4)
            attachments.append({'kind': kind, 'reference': reader.string(reader.q(ref+8)) if kind == 3 else None})
        rows.append({'sourceOffset': at, 'name': reader.string(reader.q(at)),
                     'parent': parent, 'literalTRS': list(reader.unpack('10f', at+24)),
                     'visibilityWord0x40': reader.u(at+64),
                     'modeByte0x44': reader.unpack('B', at+68)[0],
                     'attachments': attachments})
        for i in range(reader.u(at+72)):
            visit(reader.rel(at+76)+96*i, index)
    for i in range(reader.u(table+16)):
        visit(reader.rel(table+20)+96*i, -1)
    return rows


def primitive_records(reader, parsed):
    """Keep source buffer/window/material provenance for every face range."""
    count, table = reader.section(180)
    records = []
    if count != len(parsed['meshes']):
        raise ValueError('Source mesh count changed')
    for n, mesh in enumerate(parsed['meshes']):
        rec = table+n*24
        wrapper = reader.rel(rec+20)
        prefix = reader.u(wrapper+4) & 0xffffff
        body = reader.q(wrapper+8)+(prefix-1)*8
        primitives, ptr = reader.u(body+96), reader.rel(body+100)
        if primitives != len(mesh['groups']):
            raise ValueError('Source primitive/group count changed')
        rows = []
        for k, group in enumerate(mesh['groups']):
            at = ptr+k*88
            first, last = reader.unpack('2I', at+28)
            count = reader.u(at+36)
            address, length = reader.q(at+48), reader.q(at+56)
            raw = reader.b[address:address+count*2]
            if len(raw) != count*2 or count*2 > length:
                raise ValueError('Source index bytes escaped their buffer')
            actual = [v+first for v in struct.unpack('<'+'H'*count, raw)]
            if mesh['indices'][group['start']:group['start']+group['count']] != actual:
                raise ValueError('Parser indices differ from literal source window')
            rows.append({'part': k, 'sourceOffset': at, 'topologyWord': reader.u(at),
                         'sourceVertexStart': first, 'sourceVertexEndInclusive': last,
                         'sourceLocalIndexOffset': address, 'sourceLocalIndexBytes': len(raw),
                         'sourceLocalIndexSHA256': digest(raw), 'rebasedIndexSHA256': digest(struct.pack('<'+'I'*len(actual), *actual)),
                         'start': group['start'], 'count': count,
                         'material': group['material'], 'materialName': group['materialName']})
        records.append(rows)
    return records


def native_probe_type():
    # Keep the old six-model probe frozen. Its <=16 prefix scope predates this
    # 21-part interior; the original uncompressed reader itself handles 21.
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe

    class TempleSceneProbe(NativeBresWorldBoundsProbe):
        def prepare(self, wrapper):
            count = self.r(wrapper+4, 'h')[0]
            offset = self.r(wrapper+8, 'Q')[0]
            size, compressed = self.r(wrapper+0x10, '2I')
            if not 1 <= count <= 256 or size < count*8 or compressed:
                raise ValueError('This review only admits bounded original uncompressed prefixes')
            self.source_slice(offset, size)
            reader, vt = self.BASE+0x3000, self.BASE+0x4000
            self.w(reader, 'Q', vt)
            self.w(vt+0x10, 'Q', 0x30000108)
            self.regs()
            self.set('X0', wrapper)
            self.set('X1', reader)
            self.set('W2', 0)
            self.run(0x117c40c)
            body = self.get('X0')
            expected = self.source_slice(offset+count*8+0x60, 24)
            if bytes(self.uc.mem_read(body+0x60, 24)) != expected:
                raise ValueError('Original prefix preparation changed bbox bytes')
            self.prepared.append({'prefixCount': count, 'sourceBufferOffset': offset,
                                  'sourceBoxOffset': offset+count*8+0x60,
                                  'preparedBoxOffset': 0x60, 'bboxBytesEqual': True,
                                  'localBox': list(self.r(body+0x60, '6f'))})
            return body
    return TempleSceneProbe


def boundary_edges(mesh, matrix):
    """Geometric open-edge evidence; never fill, weld, or change these edges.

    Vertex streams split UV/material seams. Counting literal vertex indices
    alone would falsely label those seams as holes. Exact source positions are
    used here (no epsilon welding), and duplicate coincident faces are retained.
    """
    positions = [tuple(mesh['positions'][i:i+3]) for i in range(0, len(mesh['positions']), 3)]
    edges = {}
    for face in range(0, len(mesh['indices']), 3):
        indices = mesh['indices'][face:face+3]
        for a, b in zip(indices, indices[1:]+indices[:1]):
            p, q = positions[a], positions[b]
            if p == q:
                continue
            key = tuple(sorted((p, q)))
            edges.setdefault(key, []).append(face//3)
    return [{'sourceEndpoints': list(map(list, edge)),
             'worldEndpoints': [transform(matrix, v) for v in edge],
             'face': faces[0]} for edge, faces in edges.items() if len(faces) == 1]


def raycast(model, instance, matrix, ray, limit=12):
    origin, direction = ray['origin'], ray['direction']
    if len(origin) != 3 or len(direction) != 3 or not all(math.isfinite(v) for v in origin+direction):
        raise ValueError('Finite explicit world ray required')
    length = math.sqrt(dot(direction, direction))
    if not length:
        raise ValueError('Zero inspection direction')
    direction = [v/length for v in direction]
    rows = []
    for mi, mesh in enumerate(model['meshes']):
        # The caller supplies the per-mesh combined original placement/node.
        mat = matrix[mi]
        positions = [transform(mat, mesh['positions'][i:i+3]) for i in range(0, len(mesh['positions']), 3)]
        for index in range(0, len(mesh['indices']), 3):
            vertices = [positions[v] for v in mesh['indices'][index:index+3]]
            hit = triangle_hit(origin, direction, vertices)
            if hit is None:
                continue
            part, = [k for k, g in enumerate(mesh['groups']) if g['start'] <= index < g['start']+g['count']]
            group = mesh['groups'][part]
            rows.append({**hit, 'model': model['source'], 'instanceID': instance['id'],
                         'mesh': mi, 'meshName': mesh['name'], 'triangle': index//3,
                         'part': part, 'material': group['material'], 'materialName': group['materialName'],
                         'worldVertices': vertices})
    return sorted(rows, key=lambda r: r['distance'])[:limit]


def capture_rays(capture):
    if capture.get('format') != 'oc2-private-temple-viewport-audit-v1' or capture.get('observerOnly') is not True:
        raise ValueError('An explicit observer-only host viewport capture is required')
    offset = capture['origin']
    return [{'name': 'pixel-'+str(index), 'origin': [v+offset[a] for a, v in enumerate(sample['ray']['origin'])],
             'direction': sample['ray']['direction'], 'clientPixel': sample['clientPixel'],
             'fraction': sample['fraction']} for index, sample in enumerate(capture['samples'])]


def inverse4(matrix):
    rows = [[matrix[c*4+r] for c in range(4)]+[float(r == c) for c in range(4)] for r in range(4)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda i: abs(rows[i][column]))
        if abs(rows[pivot][column]) < 1e-15:
            raise ValueError('Singular captured camera matrix')
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        rows[column] = [v/scale for v in rows[column]]
        for r in range(4):
            if r == column:
                continue
            scale = rows[r][column]
            rows[r] = [a-scale*b for a, b in zip(rows[r], rows[column])]
    return [rows[r][4+c] for c in range(4) for r in range(4)]


def projected_point(matrix, point):
    value = [sum(matrix[c*4+r]*point[c] for c in range(4)) for r in range(4)]
    if value[3] == 0:
        raise ValueError('Captured point projects to infinity')
    return [v/value[3] for v in value[:3]]


def pixel_rays(capture, pixels):
    capture_rays(capture)  # Validate the observational boundary first.
    camera, viewport, offset = capture['camera'], capture['viewport'], capture['origin']
    inverse_projection = inverse4(camera['projection'])
    origin = camera['position']
    output = []
    for row in pixels:
        x, y = row['pixel']
        ndc = [(x-viewport['left'])/viewport['width']*2-1, 1-(y-viewport['top'])/viewport['height']*2, .5, 1]
        view = projected_point(inverse_projection, ndc)
        local = projected_point(camera['world'], view+[1])
        direction = subtract(local, origin)
        length = math.sqrt(dot(direction, direction))
        output.append({'name': row['name'], 'origin': [v+offset[i] for i, v in enumerate(origin)],
                       'direction': [v/length for v in direction], 'clientPixel': row['pixel'],
                       'captureFrame': capture['frame']})
    return output


def compare_capture(preview, row, bindings, capture):
    """Compare actual observed host draw ranges, not just serialized arrays."""
    from bdae_skin import compose, multiply
    matches = [r for r in capture['models'] if r['source'] == row['model']]
    reviews = []
    for item in matches:
        inst, = [r for r in row['instances'] if r['id'] == item['instance']['id']]
        if inst != item['instance'] or len(item['meshes']) != len(preview['meshes']):
            raise ValueError('Captured instance/mesh list differs from the current original-derived package')
        p = [v-capture['origin'][a] for a, v in enumerate(inst['position'])]
        placement = compose(p, inst['quaternion'], inst['scale'])
        mesh_reviews = []
        for index, (actual, model) in enumerate(zip(item['meshes'], preview['meshes'])):
            expected = multiply(placement, bindings[index]['matrix'])
            error = max(abs(a-b) for a, b in zip(actual['matrixWorld'], expected))
            if error > 2e-4:
                raise ValueError('Captured per-mesh placement/node matrix differs from source')
            groups = [{'start': g['start'], 'count': g['count'], 'materialIndex': g['material']} for g in model['groups']]
            if actual['groups'] != groups or actual['vertices'] != len(model['positions'])//3 or actual['indexCount'] != len(model['indices']):
                raise ValueError('Captured host geometry/groups differ from source')
            if actual['drawRange'] != {'start': 0, 'count': 'Infinity'}:
                raise ValueError('Captured host drawRange unexpectedly excludes source faces')
            materials = []
            for i, actual_material in enumerate(actual['materials']):
                source_alpha = preview['sceneAlpha']['materials'][i]
                source_cull = preview['sceneCulling']['materials'][i]
                pending = bool(preview.get('sourceInsideMaterials', {}).get('materials', [{}]*len(actual['materials']))[i].get('missingSamplers'))
                expected_side = 0 if source_cull['cullEnabled'] else 2
                if actual_material['visible'] != (not pending) or actual_material['side'] != expected_side:
                    raise ValueError('Captured material visibility/culling differs from the established source policy')
                materials.append({'index': i, 'sourceName': preview['materials'][i]['name'],
                                  'sourceEffect': source_alpha['effectPath'],
                                  'visible': actual_material['visible'], 'side': actual_material['side'],
                                  'sourceMissingSampler': pending})
            mesh_reviews.append({'mesh': index, 'sourceMatrixMaxDifference': error,
                                 'allSourceGroupsAndIndexCountRetained': True,
                                 'fullDrawRange': True, 'hostMeshVisible': actual['visible'],
                                 'sourcePartsSubmitted': [{'part': i, 'material': group['material'],
                                      'submitted': any(d['start'] == group['start'] and d['count'] == group['count']
                                                       and d['materialIndex'] == group['material'] for d in actual['mainCameraDraws'])}
                                      for i, group in enumerate(model['groups'])],
                                 'mainCameraDraws': actual['mainCameraDraws'], 'materials': materials})
        reviews.append({'instanceID': inst['id'], 'hostRootVisible': item['visible'], 'meshes': mesh_reviews,
                        'scope': 'Observed host main-camera submission, not original GPU or final pixel ownership'})
    return reviews


def compare_ray_capture(capture, ray_hits, models):
    rows = []
    for i, sample in enumerate(capture['samples']):
        actual = [h for h in sample['hits'] if h['source'] in models]
        source = ray_hits['pixel-'+str(i)]
        if not actual and not source:
            rows.append({'sample': i, 'bothEmptyInReviewedModelScope': True,
                         'allResidentHostHitCount': len(sample['hits']),
                         'nearestSourceFaceEqual': True})
            continue
        if not actual or not source:
            rows.append({'sample': i, 'nearestSourceFaceEqual': False,
                         'hostHitCount': len(actual), 'allResidentHostHitCount': len(sample['hits']),
                         'sourceHitCount': len(source)})
            continue
        a, b = actual[0], source[0]
        same = (a['source'] == b['model'] and a['id'] == b['instanceID'] and
                a['meshOrdinal'] == b['mesh'] and a['faceIndex'] == b['triangle'] and
                a['materialIndex'] == b['material'])
        delta = max(abs(x-y) for x, y in zip(a['sourcePoint'], b['position']))
        rows.append({'sample': i, 'nearestSourceFaceEqual': same,
                     'allResidentHostHitCount': len(sample['hits']),
                     'sourceModel': b['model'], 'sourceInstanceID': b['instanceID'],
                     'sourceMesh': b['mesh'], 'sourceTriangle': b['triangle'],
                     'sourcePart': b['part'], 'sourceMaterial': b['material'],
                     'worldPointMaxDifference': delta,
                     'distanceDifference': abs(a['distance']-b['distance']),
                     'withinFloat32PositionTolerance': delta <= 2e-4,
                     'scope': 'Source triangle versus observed host CPU raycast; this is not a GPU pixel readback'})
    return rows


def inspect(package, source, native=None, rays=None, models=MODELS, capture=None, pixels=None):
    from bdae_convert import BDAE
    from scene_collision import geometry_transforms
    from bdae_skin import compose, multiply
    from terrain_convert import read_instances
    raw_package = Path(package).read_bytes()
    if digest(raw_package) != PACKAGE_SHA256:
        raise ValueError('Current 53-effect source package identity differs')
    image = None
    if native is not None:
        native_bytes = Path(native).read_bytes()
        if digest(native_bytes) != NATIVE_SHA256:
            raise ValueError('Original native image differs')
        from analyze_native_resources import NativeImage
        image = NativeImage(native_bytes)
    if capture is not None:
        rays = list(rays or [])+capture_rays(capture)
        if pixels:
            rays += pixel_rays(capture, pixels)
    elif pixels:
        raise ValueError('Pixel inspection requires an explicit same-camera capture')
    results = []
    ray_results = {r['name']: [] for r in rays or []}
    with tarfile.open(package) as archive, tempfile.TemporaryDirectory(prefix='oc2-temple-face-') as temporary:
        manifest_raw = archive.extractfile('game-data/converted/source-tutorial-inside/manifest.json').read()
        manifest = json.loads(manifest_raw)
        wanted = {(tuple(i['tile']), i['id']) for r in manifest['scenery']
                  if r['model'] in models for i in r['instances']}
        original_instances = {}
        for name in sorted(source.lookup):
            if not (name.startswith('world/tutorial/items/') and name.endswith('.itm')):
                continue
            original = source.read(name)
            tile = struct.unpack_from('<2i', original, 8)
            if tile not in {k[0] for k in wanted}:
                continue
            path = Path(temporary)/'original.itm'
            path.write_bytes(original)
            for i in read_instances(path):
                if (tuple(i['tile']), i['id']) in wanted:
                    original_instances[(tuple(i['tile']), i['id'])] = i
        if set(original_instances) != wanted:
            raise ValueError('Original placement records are missing')
        for name in models:
            row, = [r for r in manifest['scenery'] if r['model'] == name]
            raw = source.read(name)
            path = Path(temporary)/'original.bdae'
            path.write_bytes(raw)
            reader = BDAE(path)
            parsed = reader.parse()
            bindings = geometry_transforms(reader, parsed)
            preview_raw = archive.extractfile('game-data/converted/'+row['url'][8:]).read()
            preview = json.loads(preview_raw)
            if preview['sourceSHA256'] != digest(raw) or len(preview['meshes']) != len(parsed['meshes']):
                raise ValueError('Preview model/source identity differs')
            # Source arrays and draw ranges are compared independently. Merely
            # matching bounds or the total number of faces is not sufficient.
            for i, (a, b) in enumerate(zip(parsed['meshes'], preview['meshes'])):
                for field in ('positions', 'indices', 'groups'):
                    if a[field] != b[field]:
                        raise ValueError('Source/preview face field differs: '+name+':'+field)
                if preview['meshes'][i]['sourceNodeTransform'] != bindings[i]:
                    raise ValueError('Source/preview node binding differs')
            source_tree = source_nodes(reader)
            assembled = None
            if image is not None:
                from bres_world_bounds_evidence import inner_bres, source_node_fields
                probe = native_probe_type()(image)
                loaded = probe.load(inner_bres(raw))
                native_source = source_node_fields(probe, loaded['info'])
                root = probe.scene(loaded['info'])
                probe.regs()
                probe.set('X0', root)
                probe.set('W1', 1)
                probe.run(0x1362320)
                assembled = {'nativeSourceNodes': native_source, 'tree': probe.tree(root),
                             'preparedBuffers': probe.prepared,
                             'flagWrites': probe.flag_writes,
                             'scope': 'Actual BRES/initial scene assembly; mesh storage adapter, no GPU/material/active scene visibility result'}
            parts = primitive_records(reader, parsed)
            instances = []
            for inst in row['instances']:
                original = original_instances[(tuple(inst['tile']), inst['id'])]
                for field in ('model', 'id', 'sourceType', 'sourceWord8', 'position', 'quaternion', 'scale', 'tile'):
                    if original[field] != inst[field]:
                        raise ValueError('Original placement differs: '+field)
                placement = compose(inst['position'], inst['quaternion'], inst['scale'])
                matrices = [multiply(placement, bindings[i]['matrix']) for i in range(len(parsed['meshes']))]
                entry = {'placement': inst, 'originalITMPlacementEqual': True, 'meshMatrices': matrices,
                         'boundaryEdges': [boundary_edges(mesh, matrices[i]) for i, mesh in enumerate(parsed['meshes'])]}
                instances.append(entry)
                for ray in rays or []:
                    hits = raycast({**parsed, 'source': name}, inst, matrices, ray)
                    ray_results[ray['name']].extend(hits)
            results.append({'model': name, 'sourceSHA256': digest(raw), 'sourceBytes': len(raw),
                            'previewPath': row['url'], 'previewSHA256': digest(preview_raw),
                            'sourceNodes': source_tree, 'originalInitialAssembly': assembled,
                            'parts': parts, 'instances': instances,
                            'hostCaptureReview': compare_capture(preview, row, bindings, capture) if capture else None,
                            'sourceFacesAndPreviewArraysEqual': True,
                            'sourceNodeBindingsEqual': True})
    for name in ray_results:
        ray_results[name] = sorted(ray_results[name], key=lambda v: v['distance'])[:24]
    return {'format': FORMAT, 'packageSHA256': PACKAGE_SHA256, 'manifestSHA256': digest(manifest_raw),
            'nativeSHA256': NATIVE_SHA256 if image else None,
            'models': results, 'rayInputs': rays or [], 'rayHits': ray_results,
            'hostRayComparisons': compare_ray_capture(capture, ray_results, models) if capture else None,
            'hostCapture': {k: capture[k] for k in ('format', 'frame', 'observerOnly', 'origin', 'player', 'viewport', 'camera', 'samples')} if capture else None,
            'sources': source.proofs, 'scope': {'productionChanged': False, 'savesChanged': False,
                'sourceGeometryChanged': False, 'sourceNodeInitialAssemblyExecuted': image is not None,
                'GPUOrAndroidFrameExecuted': False, 'originalSpawnEstablished': False,
                'rayCulling': 'two-sided inspection only; frontFacing reported, not a material override'},
            'gaps': ['Actual host draw calls and same-camera visibility must be recorded separately.',
                     'Original dynamic inside/phase/current-camera visibility remains a separate state input.',
                     'An original open boundary proves only the scoped file has no adjoining triangle there; it does not prove the full active map combination.']}


def main():
    from resource_packs import DEFAULT_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--native', type=Path, default=DEFAULT_NATIVE)
    parser.add_argument('--no-native', action='store_true')
    parser.add_argument('--rays', type=Path)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--pixels', type=Path)
    parser.add_argument('--models', nargs='+', default=MODELS)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = private_path(args.output)
    if output.exists():
        parser.error('Preserve previous face evidence; choose a new output')
    from map_loading_evidence import Sources
    result = inspect(args.package, Sources(args.source), None if args.no_native else args.native,
                     json.loads(args.rays.read_text()) if args.rays else None, args.models,
                     json.loads(args.capture.read_text()) if args.capture else None,
                     json.loads(args.pixels.read_text()) if args.pixels else None)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(output), 'models': len(result['models']),
                      'initialNativeAssembly': result['scope']['sourceNodeInitialAssemblyExecuted'],
                      'sourceFacesEqual': all(r['sourceFacesAndPreviewArraysEqual'] for r in result['models']),
                      'productionChanged': False}))


if __name__ == '__main__':
    main()
