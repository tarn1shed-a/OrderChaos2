"""Recover seven source instances using their original default lightMap.

Only the pinned fresh local texture-mount branch is applied. No alternate DAT,
invented white texture, new light, flame or object placement is supplied.
"""
import hashlib
import json
import tempfile
from pathlib import Path
from tutorial_map_geometry import local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE, read_entry
from scene_lightmaps import read_records, object_records, source_names
from scene_sampling import material_samplers
from scene_baked_lighting import recover_model_lighting
from scene_collision import apply_scene_transforms
from scene_render_state import effect_render_state
from bdae_convert import BDAE
from terrain_convert import read_instances
from texture_decode import decode

FORMAT = 'oc2-source-missing-records-v1'
IDS = {620952600, 600750792, 620955768, 620955624, 439318160, 620950728, 693455856}
MODELS = {'model/scene/main_human/hum_other_torch001.bdae': (58, 34),
          'model/scene_generator_temple_000/god_flagstone001.bdae': (117, 56)}
DEFAULT = 'texture/lightmap.tga'
DEFAULT_SHA = '822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b'
EFFECT_SHA = 'b0a169c06aef00e817f77ad965696d1f42e7d445879e27b6036de0e36bfadb72'


def export(runtime, output):
    from analyze_native_resources import NativeImage
    from native_missing_records import MissingRecordProbe
    runtime, output = map(local_output, (runtime, output))
    assets = runtime/'game-data/converted'; source = Sources(DEFAULT_SOURCE)
    manifest = json.loads((assets/'source-map-palette/manifest.json').read_text())
    selected = json.loads((assets/manifest['sourceSelection']['url'][8:]).read_text())
    if (selected['profile'] != 'APK_Default' or selected['settings']['ForceModelLodLevel'] != 0 or
            selected['phase'] != 0 or not selected['settings']['ShowModelLightMap'] or
            {r['id'] for r in selected['preview']['omitted']} != IDS):
        raise ValueError('Only the seven verified original slot0 omissions are supported')
    config = json.loads((runtime/'prototype/native-physics.json').read_text())
    image = NativeImage(Path(config['library']).read_bytes()); probe = MissingRecordProbe(image)
    candidates = source.candidates(DEFAULT)
    if {r['pack'] for r in candidates} != {'res_t.bin', 'res_t_upd10.bin'} or len(candidates) != 2:
        raise ValueError('Original default lightMap candidate set changed')
    available = [n for n in ['res_t.bin', *['res_t_upd%d.bin' % i for i in range(10, 16)]] if (DEFAULT_SOURCE/n).is_file()]
    mount = probe.fresh_archives(available, [r['pack'] for r in candidates])
    if mount['selected'] != 'res_t_upd10.bin':
        raise ValueError('Original cold texture lookup selected a different pack')
    raw = read_entry(next(r for r in candidates if r['pack'] == mount['selected']), DEFAULT_SOURCE)
    if hashlib.sha256(raw).hexdigest() != DEFAULT_SHA:
        raise ValueError('Original selected default lightMap changed')
    img = decode(raw)
    if img.size != (8, 8) or img.getextrema() != ((130, 130), (130, 130), (130, 130), (255, 255)):
        raise ValueError('Original default lightMap pixels differ')
    material_proofs = []; native_rows = []; recovered = []
    with tempfile.TemporaryDirectory() as tmp:
        fp = Path(tmp)/'effect.bdae'; fp.write_bytes(source.read('ut_lightmap_solid.bdae')); fx = BDAE(fp)
        if hashlib.sha256(fx.b).hexdigest() != EFFECT_SHA:
            raise ValueError('Original solid LIGHTMAP effect changed')
        states = effect_render_state(fx)['profiles']
        for p in states:
            s = p['state']
            if (p['technique'] != 'tech0' or s['blendEnabled'] or s['cullEnabled'] or
                    not s['depthWriteEnabled'] or not s['depthTestEnabled'] or s['depthFunctionGL'] != 515 or
                    any(p[k]['defines'] != {'LIGHTMAP': ''} for k in ('vertexShader', 'fragmentShader'))):
                raise ValueError('Original solid material state differs')
        for model, counts in MODELS.items():
            matches = [r for r in manifest['scenery'] if r['model'] == model]
            if len(matches) != 1:
                raise ValueError('Original models must already have one verified template')
            entry = matches[0]; data = json.loads((assets/entry['url'][8:]).read_text())
            raw_model = source.read(model); fp = Path(tmp)/'model.bdae'; fp.write_bytes(raw_model); reader = BDAE(fp)
            parsed = apply_scene_transforms(reader, reader.parse())
            materials = material_samplers(reader)
            if (data['sourceSHA256'] != hashlib.sha256(raw_model).hexdigest() or len(parsed['meshes']) != 1 or
                    len(materials) != 1 or materials[0]['effectPath'] != 'ut_lightmap_solid.bdae' or
                    materials[0]['samplers']['lightMap']['texture'] != DEFAULT or
                    (parsed['meshes'][0]['vertexCount'], parsed['meshes'][0]['triangleCount']) != counts):
                raise ValueError('Original missing-record source template differs')
            for key in ('positions', 'normals', 'uvs', 'sourceUV1', 'indices', 'sourceNodeTransform'):
                if data['meshes'][0].get(key) != parsed['meshes'][0].get(key):
                    raise ValueError('Existing geometry differs from original model: '+key)
            if recover_model_lighting(reader, parsed) != data['sceneBakedLighting']:
                raise ValueError('Original lightMap declaration differs from existing template')
            material_proofs.append({'model': model, 'sourceSHA256': data['sourceSHA256'], 'sourceURL': entry['url'],
                                    'material': materials[0]['material'], 'vertices': counts[0], 'triangles': counts[1]})
            for row in selected['instances']:
                if row['id'] not in IDS or row['requestedModel'] != model:
                    continue
                if row['bindings'] or row['modelSlot'] != 0 or row['admission'] != 'admittedBeforeTypeFactory':
                    raise ValueError('Original missing-record admission changed')
                tile = row['tile']; itm = f'world/tutorial/items/{tile[0]:04d}_{tile[1]:04d}.itm'
                fp = Path(tmp)/'tile.itm'; fp.write_bytes(source.read(itm))
                original = [r for r in read_instances(fp) if r['id'] == row['id']]
                if len(original) != 1 or any(original[0][k] != row[k] for k in ('model','position','quaternion','scale','tile','sourceType')):
                    raise ValueError('Original ITM placement differs')
                dat = source.read(row['recordPath'])
                if object_records(read_records(dat), row['id']):
                    raise ValueError('Original selected DAT now has object records')
                alternate = source_names('tutorial', *tile, slot=1)['record']
                alternate_count = len(object_records(read_records(source.read(alternate)), row['id']))
                native_rows.append(probe.no_record(dat, row['id']))
                recovered.append({**original[0], 'recordPath': row['recordPath'], 'selectedRecords': 0,
                                  'otherSlotRecords': alternate_count, 'otherSlotApplied': False})
                if any(r['id'] == row['id'] and r['tile'] == tile for r in entry['instances']):
                    raise ValueError('Original missing-record instance already exists')
                entry['instances'].append({**original[0], 'flags': 2})
    if {r['id'] for r in recovered} != IDS:
        raise ValueError('Seven original objects were not all accounted for')
    output.mkdir(parents=True, exist_ok=True); prefix = '/assets/source-map-record-gaps/'
    img.save(output/(DEFAULT_SHA+'.png'))
    policy = {'format': FORMAT, 'world': 'tutorial', 'profile': 'APK_Default', 'slot': 0,
              'scope': 'verified fresh local texture mount; no original device/cache observation',
              'defaultTexture': {'source': DEFAULT, 'pack': mount['selected'], 'sha256': DEFAULT_SHA,
                                 'url': prefix+DEFAULT_SHA+'.png', 'size': [8,8], 'rgba': [130,130,130,255]},
              'uvTransform': [0,0,1,1], 'UV1_TRANSFORM': False, 'LIGHTMAP': True,
              'nativeMount': mount, 'nativeEmptyRecords': native_rows, 'models': material_proofs, 'instances': recovered,
              'lightsChanged': False, 'originalDeviceObserved': False,
              'gaps': ['Hot name cache, extra filesystem providers, external mutations and original GPU state remain unobserved.',
                       'Existing browser filtering/mips, stable light globals and drawing schedule remain interfaces.']}
    count = sum(len(m['instances']) for m in manifest['scenery'])
    if len(manifest['scenery']) != 158 or count != 1258:
        raise ValueError('Unexpected original map scope after seven placements')
    selected['preview']['omitted'] = []; selected['preview']['displayedInstances'] = count
    manifest['sourceSelection']['url'] = prefix+'selection.json'
    manifest['sourceMissingRecords'] = {'format': FORMAT, 'url': prefix+'policy.json'}
    audit = {'format': FORMAT, 'instancesAdded': 7, 'displayedInstances': count, 'displayedModels': 158,
             'omittedInstances': 0, 'lightsChanged': False, 'sourceAssetsModified': False,
             'originalDeviceObserved': False, 'sources': source.proofs}
    for name, value in [('manifest.json',manifest),('selection.json',selected),('policy.json',policy),('audit.json',audit)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')))
    return audit


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k] for k in ('displayedInstances','instancesAdded','omittedInstances','lightsChanged')}))
