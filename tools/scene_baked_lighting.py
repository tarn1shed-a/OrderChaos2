"""Build the bounded slot0 scene-lighting branch, without copying source shaders.

The browser explicitly chooses config0 and immediate environment writes. These
are supported native branches, not observations of original-device settings.
"""
import hashlib
import struct
from pathlib import Path

from scene_lightmaps import source_names, read_records, object_records
from scene_lightmap_binding import material_request_slots
from scene_lighting import ZONE_SHA256, check_zone_layout, zone_targets
from scene_zone_selection import ZoneCatalog
from scene_sampling import material_samplers
from scene_texture_sampling import texture_dimensions, verify_native as verify_sampling
from scene_render_state import SHADERS
from scene_active_lighting import verify_native as verify_active_lighting
from skill_attachments import decode_ftable

FORMAT = 'oc2-scene-baked-lighting-v1'
ENCODING_ROUTINES = {
    0x13b4ee0: (132, '19e5861d6f2979383da59413066b6959c1cf72d06cccc4ad36d70f520d2b544a'),
    0x1432354: (2232, '760af01b94d73e07ebc16d8393df834ac61435224d9d6ce48bd01b2280e3afa4'),
    0x149ed30: (2264, 'f15ca8255280a86101e585ea9374c704486aa35bd749e1ce2c6e80fff65f8ec7'),
}


def verify_native(image):
    verify_sampling(image)  # Includes the PVR reader 13d7d8c.
    verify_active_lighting(image)
    for address, (size, digest) in ENCODING_ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Source encoded scene texture upload changed')
    # PVR low-byte0x36 dispatches to mov w9,0x34; b13d814c.
    delta, = struct.unpack('<i', image.read(0x1f3b90c+0x36*4, 4))
    if 0x1f3b90c+delta != 0x13d811c:
        raise ValueError('Source ETC1 PVR format dispatch changed')
    return {'formatIndex': 0x34, 'compressedUploadFormats': [0x8d64, 0x9274],
            'automaticSRGBDecode': False,
            'scope': 'Supported ETC1 / compatible ETC2 RGB upload, not the CPU fallback or observed device capabilities.'}


def _raw(extract, path):
    result = extract(path)
    return bytes(result) if isinstance(result, (bytes, bytearray)) else Path(result).read_bytes()


def recover_model_lighting(reader, data):
    records = material_samplers(reader)
    if len(records) != len(data['materials']): raise ValueError('Scene lightmap material count differs')
    materials = []
    count, table = reader.section(172)
    for index, (source, material) in enumerate(zip(records, data['materials'])):
        sampler = source['samplers'].get('lightMap')
        if (source['material'] != material['name'] or not sampler or
                sampler['texture'] != 'texture/lightmap.tga' or
                any(value is not None for value in sampler['request'].values())):
            raise ValueError('Scene lightmap override branch needs separate recovery')
        at = table+index*80
        size, properties = reader.u(at+32), reader.rel(at+36)
        fields = [(reader.string(reader.q(properties+i*32)), reader.u(properties+i*32+16)) for i in range(size)]
        # These BDAEs do not serialize uvTransform. It is a reflected shader
        # uniform under UV1_TRANSFORM, populated by 342194, not a model field.
        if any(name == 'uvTransform' for name, _ in fields):
            raise ValueError('Serialized source uvTransform override needs recovery')
        for mesh in data['meshes']:
            uv = mesh.get('sourceUV1')
            if not isinstance(uv, list) or len(uv) != len(mesh['positions'])//3*2:
                raise ValueError('Source scene UV1 is incomplete')
        materials.append({'index': index, 'name': material['name'], 'texture': material['diffuse'],
                          'sourceLightMap': sampler['texture'], 'sourceRequest': sampler['request'],
                          'uvTransformOrigin': 'shader-uniform-under-UV1_TRANSFORM'})
    return {'format': FORMAT, 'materials': materials, 'shaderSHA256': SHADERS}


def recover_baked_lighting(extract, scenery, texture):
    # Source shaders are validated and kept local; runtime GLSL is independently written.
    for path, digest in SHADERS.items():
        if hashlib.sha256(_raw(extract, path)).hexdigest() != digest:
            raise ValueError('Source scene lighting shader changed')
    tables, instances, pages = {}, [], {}
    for entry in scenery:
        for instance in entry['instances']:
            names = source_names('tutorial', *instance['tile'], slot=0)
            if names['record'] not in tables:
                tables[names['record']] = read_records(_raw(extract, names['record']))
            requests = material_request_slots(object_records(tables[names['record']], instance['id']))
            if not requests: raise ValueError('Required slot0 instance lightmap record missing')
            bindings = []
            for request in requests:
                path = source_names('tutorial', *instance['tile'], slot=0, atlas=request['atlasIndex'])['texture']
                if path not in pages:
                    raw = _raw(extract, path)
                    dimensions = texture_dimensions(raw)
                    if dimensions['container'] != 'PVR2': raise ValueError('Unsupported atlas container')
                    url = texture(path)
                    if not url: raise ValueError('Required source atlas conversion failed')
                    pages[path] = {'sourcePath': path, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
                                   **dimensions}
                bindings.append({'ordinal': request['sortKey'], 'atlas': path,
                                 'uvTransform': request['uvParameter']['whenUniformPresent']})
            instances.append({'objectId': instance['id'], 'model': entry['model'], 'tile': instance['tile'],
                              'recordPath': names['record'], 'bindings': bindings})
    if len({(i['objectId'], tuple(i['tile'])) for i in instances}) != len(instances):
        raise ValueError('Ambiguous source scene instance identity')
    raw = _raw(extract, 'tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest() != ZONE_SHA256: raise ValueError('Source zones changed')
    table = decode_ftable(raw, id_column='ID'); check_zone_layout(table)
    catalog = ZoneCatalog(table['rows'], 5)
    bases = catalog.base
    rows = [r for r in catalog.rows if r in bases or any(r['parent_ID'] == b['ID'] for b in bases)]
    if any(r['definition'] != 0 or r['phasing_id'] != 0 for r in rows):
        raise ValueError('Unsupported active scene lighting zone')
    zones = []
    for row in rows:
        base = row if row in bases else next(b for b in bases if b['ID'] == row['parent_ID'])
        zones.append({'id': row['ID'], 'baseId': base['ID'], 'isBase': row in bases,
                      'priority': row['priority'], 'bounds': [row['x'], row['z'], row['x1'], row['z1']],
                      'targets': zone_targets(row, base)})
    return {'format': FORMAT, 'world': 'tutorial', 'instances': instances, 'atlases': list(pages.values()),
            'zones': zones, 'sourceZoneSHA256': ZONE_SHA256,
            'configuration': {'modelSlot': 0, 'forceSingleSlot': True, 'environmentMode': 0,
                              'rgbAdds': [0, 0], 'observedOriginalDevice': False},
            'limits': [
                'Browser explicitly selects the supported config0 / slot0 / w3=0 / phase0 branch; automatic original LOD, device quality and fade are not recreated.',
                'Environment mode0 uses immediate native target writes, not mode4 transition queues. Source raw rectangular base/overlay selection is sampled at >500ms using the existing capped browser-frame delta.',
                'RGB adds use the constructor zero branch; tutorial default weather is not lightning. Other aliases, server overrides and weather schedules remain unresolved.',
                'Raw decoded ETC RGB values multiply in the encoded HDR scene. Browser PNG decoding, mip generation, filtering, precision and camera remain technical adapters.',
                'Existing fog/HDR implementation remains separately scoped. Terrain, characters and the local dynamic door are outside this static instance atlas branch; full pixel-level equivalence is not asserted.']}
