"""Resolve explicit APK profile branches against original tutorial files.

This does not detect the emulator profile. Exports are conditional previews,
never a claim about the original Android session or complete native rendering.
Original files and complete manifests remain in ignored local directories.
"""
import argparse
import hashlib
import json
import struct
import tempfile
import zipfile
from pathlib import Path

from device_instance_evidence import level_inputs, verify_native as verify_device
from map_loading_evidence import Sources
from map_selection_evidence import DEFAULT_APK, apk_config, source_inputs
from resource_packs import DEFAULT_SOURCE
from scene_lightmap_binding import fresh_model_requests, material_request_slots
from scene_lightmaps import object_records, read_records, source_names
from terrain_convert import read_instances, read_tile
from terrain_lighting import lightmap_requests
from terrain_materials import mask_channels, effective_indices, tile_materials
from texture_decode import decode

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-tutorial-conditional-selection-v1'
KEYS = ('ModelDetailLevel', 'ForceModelLodLevel', 'DeviceLayer',
        'ShowModelLightMap', 'ShowTerrainLightMap', 'TerrainTileSight')
MASK_ROUTINES = {
    0x354fec: (384, '6a09f57257e209159ca291ad6f58677a1697eb1a822a8316385c20e80a54a350'),
    0x3bcb18: (76, '9af23db90257859d39ffa5f9b9093a6bc24a42f431331ff2392e13c09ca4f8d3'),
}


def verify_mask(image):
    for address, (size, digest) in MASK_ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Original terrain mask selection changed')
    if image.read(0x1dfdb94, 20) != b'UseSmallTerrainMask\0':
        raise ValueError('Original mask configuration key changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x25077d8) != 0x2532f0f:
        raise ValueError('Original small-mask flag relocation changed')


class MaskProbe:
    """Execute the filename branch; stop before sprintf and resource I/O."""
    def __init__(self, image):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        from unicorn import arm64_const as reg
        verify_mask(image)
        self.reg = reg
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for address, size in [(0x354000, 0x2000), (0x1df9000, 0x1000)]:
            self.uc.mem_map(address, size)
            self.uc.mem_write(address, image.read(address, size))
        for address, size in [(0x2507000, 0x1000), (0x2528000, 0x1000),
                              (0x2532000, 0x1000), (0x10000000, 0x10000)]:
            self.uc.mem_map(address, size)
        self.uc.mem_write(0x25077d8, struct.pack('<Q', 0x2532f0f))
        self.uc.mem_write(0x2528db0, struct.pack('<Q', 0x10002000))
        self.uc.mem_write(0x10002270, struct.pack('<Q', 0x10003000))
        self.uc.mem_write(0x10003000, b'\0tutorial\0')

    def request(self, x, z, channel, level=0, phase=0, small=False):
        from unicorn import UC_HOOK_CODE
        if type(small) is not bool or channel not in range(4) or not 0 <= level <= 3 or not 0 <= phase <= 31:
            raise ValueError('Mask experiment outside explicit input bounds')
        u, r = self.uc, self.reg
        tile = 0x10001000
        u.mem_write(tile+8, struct.pack('<2i', x, z))
        u.mem_write(tile+0x170, struct.pack('<I', level))
        u.mem_write(tile+0x190, struct.pack('<I', phase))
        u.mem_write(0x2532f0f, bytes([small]))
        for name, value in [('X19', channel), ('X20', tile), ('X21', 0x2528000), ('SP', 0x1000f000)]:
            u.reg_write(getattr(r, 'UC_ARM64_REG_'+name), value)
        stop = []
        def finish(uc, address, size, data):
            stop.append(address)
            uc.emu_stop()
        hooks = [u.hook_add(UC_HOOK_CODE, finish, begin=a, end=a) for a in (0x35507c, 0x355090)]
        try:
            u.emu_start(0x355024, 0x355140, count=64)
        finally:
            for h in hooks:
                u.hook_del(h)
        if len(stop) != 1:
            raise ValueError('Original mask branch did not reach formatting boundary')
        pointer = u.reg_read(r.UC_ARM64_REG_X1)
        fmt = bytes(u.mem_read(pointer, 100)).split(b'\0')[0].decode()
        words = [u.reg_read(getattr(r, 'UC_ARM64_REG_W'+str(i))) for i in (3, 4, 5, 6)]
        words[:2] = [v-(1 << 32) if v & (1 << 31) else v for v in words[:2]]
        args = ('tutorial', *words[:3], *([words[3]] if phase else []))
        return fmt % args


def mask_baseline(config):
    declarations = []
    for group, data in config['profiles'].items():
        for obj in data['defaults']:
            for label, rows in obj.items():
                declarations.extend({'group': group, 'label': label, 'value': row[1]}
                                    for row in rows if row[0] == 'UseSmallTerrainMask')
        for label, values in (data['overrides'] or {}).items():
            if isinstance(values, dict) and 'UseSmallTerrainMask' in values:
                declarations.append({'group': group, 'label': label, 'value': values['UseSmallTerrainMask']})
    if not declarations or any(row['value'] is not False for row in declarations):
        raise ValueError('APK no longer has an invariant full-resolution mask branch')
    return {'key': 'UseSmallTerrainMask', 'declarations': declarations, 'value': False,
            'getterMissingKeyArgument': False, 'scope': 'verified APK baseline, excluding saved/debug/downloaded overrides'}


def resolve(image, source, apk, profile, legacy):
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_device_selection_probe import NativeDeviceSelectionProbe
    verify_device(image)
    verify_mask(image)
    apk_proof = apk_config(apk)
    with zipfile.ZipFile(apk) as archive:
        config = json.loads(archive.read('assets/GameOptions.json'))
    gpu = config['profiles']['GPU']
    if profile not in gpu['overrides']:
        raise ValueError('An explicit original GPU profile name is required')
    selector = NativeDeviceSelectionProbe(image)
    events = selector.updates(gpu, profile)
    values = dict(events)
    settings = {k: values[k] for k in KEYS}
    settings['DeviceLayer'] = selector.layer_clamp(settings['DeviceLayer'])
    mask = mask_baseline(config)
    sources, phase_rows, phase_evidence = source_inputs(image, source, apk)
    if any(r['mapId'] == 5 for r in phase_rows):
        raise ValueError('Tutorial phase table changed; do not assume phase 0')
    root = Path(legacy)
    manifest = json.loads((root/'manifest.json').read_text())
    terrain = json.loads((root/manifest['map']['url'].removeprefix('/assets/')).read_text())
    mask_probe = MaskProbe(image)
    models, overrides, entity = level_inputs(sources)
    query, gate = NativeDeviceInstanceProbe(image), NativeDeviceInstanceProbe(image)
    query.configure_levels(models, overrides)
    gate.level_delegate = query.lookup
    rows, tiles = [], []
    with tempfile.TemporaryDirectory(prefix='oc2-source-choice-') as temp:
        for source_tile in terrain['sourceTextures']:
            x, z = source_tile['tile']
            stem = f'{x:04d}_{z:04d}'
            trn = f'world/tutorial/terrain/{stem}.trn'
            raw = sources.read(trn)
            path = Path(temp)/(stem+'.trn'); path.write_bytes(raw)
            tile = read_tile(path)
            # The archived geometry is only reused after comparing source vertices.
            ox, oz = terrain['tileOrigin']; width = terrain['grid']['width']
            for zz in range(65):
                for xx in range(65):
                    at = ((z-oz)*64+zz)*width+(x-ox)*64+xx
                    expected = (x*64+xx, tile['heights'][zz*65+xx]*.01, z*64+zz)
                    if any(abs(a-b) > 2e-5 for a,b in zip(terrain['positions'][at*3:at*3+3], expected)):
                        raise ValueError('Archived terrain differs from original height samples')
            names = [mask_probe.request(x,z,c,small=mask['value']) for c in range(4)]
            channels = [sources.read(n) if sources.candidates(n) else None for n in names]
            lights = lightmap_requests('tutorial', x, z, enabled=settings['ShowTerrainLightMap'])
            available = [n for n in lights if sources.candidates(n)]
            # A first existing file is only a candidate, not original VFS success.
            tiles.append({'tile': [x,z], 'source': trn, 'maskRequests': names,
                          'maskPresent': [n for n,c in zip(names,channels) if c is not None],
                          'lightmapRequests': lights, 'uniqueLocalLightmapCandidate': available[0] if available else None})
            itm = f'world/tutorial/items/{stem}.itm'
            if not sources.candidates(itm):
                continue
            raw_itm = sources.read(itm); path = Path(temp)/(stem+'.itm'); path.write_bytes(raw_itm)
            gate.load_itm(raw_itm)
            for i, item in enumerate(read_instances(path)):
                status = gate.admission(i, settings['ModelDetailLevel'], settings['DeviceLayer'])
                slot = settings['ForceModelLodLevel']
                if slot not in (0,1):
                    raise ValueError('Non-forced slot selection is not exported by this bounded tool')
                lower = item['model'][:-5]+'_l.bdae'
                requests = fresh_model_requests(item['model'], slot, True, bool(sources.candidates(lower)))
                model_path = requests[0]['model']
                record_path = source_names('tutorial',x,z,slot)['record']
                bindings = []
                if settings['ShowModelLightMap'] and sources.candidates(record_path):
                    records = object_records(read_records(sources.read(record_path)),item['id'])
                    for request in material_request_slots(records):
                        atlas = source_names('tutorial',x,z,slot,atlas=request['atlasIndex'])['texture']
                        bindings.append({'ordinal':request['sortKey'], 'atlas':atlas,
                                         'uvTransform':request['uvParameter']['whenUniformPresent'],
                                         'available':len(sources.candidates(atlas)) == 1})
                rows.append({**item,'admission':status,'modelSlot':slot,'requestedModel':model_path,
                             'recordPath':record_path,'bindings':bindings})
    return {'format':FORMAT,'profile':profile,'actualDeviceObserved':False,
            'selection': 'explicit conditional input; emulator profile remains unknown',
            'settings':settings,'phase':0,'mask':mask,'APK':apk_proof,
            'region':{'tileOrigin':terrain['tileOrigin'],'tileCount':terrain['tileCount'],
                      'scope':'historical research region, not recovered original spawn/residency'},
            'tiles':tiles,'instances':rows,'sources':sources.proofs,
            'gaps':['Saved/debug/downloaded config and emulator selection are absent.',
                    'Terrain level is explicitly 0; complete runtime streaming/LOD is not observed.',
                    'Environment mode, camera, shader variants, VFS/GPU success and original final frame are not recovered.']}, sources


def export_preview(report, sources, legacy, destination):
    """Reuse the isolated viewer; replace only validated source asset bindings."""
    legacy, destination = Path(legacy), Path(destination)
    settings = report['settings']
    if not settings['ShowModelLightMap'] or not settings['ShowTerrainLightMap']:
        raise ValueError('Lightmap-disabled shader branches are not implemented; no substitute rendering')
    slot = settings['ForceModelLodLevel']
    manifest = json.loads((legacy/'manifest.json').read_text())
    baked = json.loads((legacy/'rendering/baked-lighting.json').read_text())
    ground = json.loads((legacy/'rendering/terrain-lighting.json').read_text())
    mats = json.loads((legacy/'maps/terrain-materials.json').read_text())
    prefix = '/assets/verified/'+report['profile']+'/'
    destination.mkdir(parents=True,exist_ok=True)
    def write(name,value):
        (destination/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        return prefix+name
    def texture(name):
        raw = sources.read(name)
        filename = 'texture-'+hashlib.sha256(raw).hexdigest()+'.png'
        target = destination/filename
        image = decode(raw)
        if not target.exists(): image.save(target)
        return prefix+filename,image
    for source_tile, tile, light in zip(report['tiles'], mats['tiles'], ground['tiles']):
        if source_tile['tile'] != tile['tile'] or tile['tile'] != light['tile']:
            raise ValueError('Preview tile order changed')
        parsed = tile_materials(sources.read(source_tile['source']))
        channels = [sources.read(n) if sources.candidates(n) else None for n in source_tile['maskRequests']]
        image,classes = mask_channels(channels)
        tile.update(parsed)
        tile['mask'] = None
        if image:
            filename = 'mask-'+str(tile['tile'][0])+'_'+str(tile['tile'][1])+'.png'; image.save(destination/filename)
            tile['mask'] = {'url':prefix+filename,'width':image.width,'height':image.height,
                            'channels':[n if c is not None else None for n,c in zip(source_tile['maskRequests'],channels)],'flipY':False}
        for chunk,cl in zip(tile['chunks'],classes):
            chunk.update(maskClasses=cl,effectiveIndices=effective_indices(chunk['indices'],cl))
        tile['textures'] = [{'sourcePath':n,'url':texture(n)[0]}for n in parsed['textures']]
        name = source_tile['uniqueLocalLightmapCandidate']
        if not name:
            raise ValueError('Original terrain lightmap absent; no replacement is generated')
        light['lightmap'].update(sourcePath=name,url=texture(name)[0],sha256=sources.proofs[name]['sha256'])
    mats['sources'].update(sources.proofs)
    manifest['map']['materials']['url'] = write('terrain-materials.json',mats)
    manifest['terrainLighting']['url'] = write('terrain-lighting.json',ground)
    selected = {row['id']:row for row in report['instances'] if row['admission']=='admittedBeforeTypeFactory'}
    omitted,scenery,instance_bindings,atlases = [],[],[],{}
    for entry in manifest['scenery']:
        data = json.loads((legacy/entry['url'].removeprefix('/assets/')).read_text())
        instances = []
        for instance in entry['instances']:
            row = selected.get(instance['id'])
            if row is None: continue
            if any(row[k]!=instance[k] for k in ('model','tile','position','quaternion','scale')):
                raise ValueError('Archived instance differs from original ITM')
            if row['requestedModel'] != entry['model']:
                omitted.append({'id':row['id'],'reason':'selected model differs from converted model','path':row['requestedModel']});continue
            raw = sources.read(row['requestedModel'])
            if data['sourceSHA256'] != hashlib.sha256(raw).hexdigest():
                raise ValueError('Converted model identity differs from original requested file')
            bindings = row['bindings']
            if not bindings or any(not b['available'] for b in bindings):
                omitted.append({'id':row['id'],'reason':'selected slot lightmap record or atlas missing','path':row['recordPath']});continue
            for binding in bindings:
                name = binding['atlas']
                if name not in atlases:
                    url,image = texture(name)
                    from scene_texture_sampling import texture_dimensions
                    atlases[name] = {'sourcePath':name,'url':url,'sha256':sources.proofs[name]['sha256'],**texture_dimensions(sources.read(name))}
            instance_bindings.append({'objectId':row['id'],'model':row['model'],'tile':row['tile'],
                                      'recordPath':row['recordPath'],
                                      'bindings':[{k:b[k]for k in ('ordinal','atlas','uvTransform')}for b in bindings]})
            instances.append(instance)
        if instances: scenery.append({**entry,'instances':instances})
    baked.update(instances=instance_bindings,atlases=list(atlases.values()))
    baked['configuration'].update(modelSlot=slot,forceSingleSlot=True)
    manifest['scenery'] = scenery
    manifest['sceneBakedLighting']['url'] = write('baked-lighting.json',baked)
    report['preview'] = {'displayedInstances':len(instance_bindings),'omitted':omitted,
                         'scope':'source file/slot bindings only; existing historical renderer and environment adapter retained'}
    report['sources'].update(sources.proofs)
    manifest['sourceSelection'] = {'url':write('selection.json',report),'profile':report['profile'],
                                   'actualDeviceObserved':False,'phase':0,'modelSlot':slot}
    write('manifest.json',manifest)
    return report['preview']


def main():
    from analyze_native_resources import NativeImage
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk',type=Path,default=DEFAULT_APK)
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--native',type=Path,default=ROOT/'analysis/raw/beff-native/library.so')
    parser.add_argument('--legacy',type=Path,required=True)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preview-output',type=Path)
    args = parser.parse_args()
    for path in [args.output,*([args.preview_output]if args.preview_output else [])]:
        if not path.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
            parser.error('Generated original data stays in ignored analysis/raw/')
    report,sources = resolve(NativeImage(args.native.read_bytes()),args.source,args.apk,args.profile,args.legacy)
    if args.preview_output:
        export_preview(report,sources,args.legacy,args.preview_output)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'profile':args.profile,'settings':report['settings'],'preview':report.get('preview'),
                      'actualDeviceObserved':False,'output':str(args.output)},ensure_ascii=False))


if __name__ == '__main__':
    main()
