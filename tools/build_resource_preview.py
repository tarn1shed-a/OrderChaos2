"""Rebuild a bounded, local-only preview from the user's game data."""
import collections
import argparse
import json
from pathlib import Path
from resource_packs import index, ResourceArchive, normalize_resource_name, safe_output, DEFAULT_SOURCE
from bdae_convert import BDAE
from terrain_convert import convert as terrain_convert
from texture_decode import convert as texture_convert

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT/'game-data/extracted'
OUT = ROOT/'game-data/converted'

def build(source=DEFAULT_SOURCE, extracted=EXTRACTED, output=OUT):
    source, extracted, output = Path(source), Path(extracted), Path(output)
    # Select archive namespaces explicitly while the complete native mounting
    # priority is still under investigation. Never guess between conflicting packs.
    packs = {'res.bin','res_a.bin','res_npc.bin','res_scene.bin','res_scene_generator_temple_000.bin','res_t.bin',
             'tutorial.bin','tutorial_layer.bin','tutorial_lmap_1.bin',
             'selection.bin','selection_layer.bin','selection_lmap_1.bin',
             'dawnwatch.bin','dawnwatch_layer.bin','dawnwatch_lmap_1.bin'}
    entries = index(source)
    by_name = collections.defaultdict(list)
    for entry in entries:
        if entry['pack'] not in packs or entry['path'].endswith('/'):
            continue
        by_name[normalize_resource_name(entry['path'])].append(entry)
    archives, extracted_names = {}, {}
    def extract(path):
        normalized = normalize_resource_name(path)
        destination = safe_output(extracted, path)
        if normalized in extracted_names:
            return extracted_names[normalized]
        candidates = by_name.get(normalized, [])
        if len(candidates) != 1:
            raise ValueError(f'Expected one original resource for {path}; found {len(candidates)}')
        pack = candidates[0]['pack']
        if pack not in archives:
            archives[pack] = ResourceArchive(source / pack)
        data = archives[pack].read(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        extracted_names[normalized] = destination
        return destination
    for z in range(2, 5):
        for x in range(-43, -40):
            extract(f'world/tutorial/terrain/{x:04d}_{z:04d}.trn')
            items = f'world/tutorial/items/{x:04d}_{z:04d}.itm'
            if normalize_resource_name(items) in by_name:
                extract(items)
            elif safe_output(extracted, items).exists():
                raise ValueError(f'Stale extracted items absent from the source: {items}')
    output.mkdir(parents=True, exist_ok=True)
    terrain_convert('tutorial', -43, 2, 3, output/'maps/tutorial-preview.json', source=extracted)
    terrain = json.loads((output/'maps/tutorial-preview.json').read_text())
    textures = {}; warnings = []; models = {}
    def texture(path):
        if path in textures:
            return textures[path]
        try:
            rel = Path(path).with_suffix('.png')
            target = output/'textures'/rel
            texture_convert(extract(path), target)
            textures[path] = '/assets/textures/'+rel.as_posix()
            return textures[path]
        except Exception as e:
            warnings.append({'texture':path,'error':str(e)})
            return None
    def model(path, key):
        result = BDAE(extract(path)).parse()
        result['source'] = path
        if not result['meshes']:
            raise ValueError('Model has no supported meshes')
        for mat in result['materials']:
            if mat['diffuse']: texture(mat['diffuse'])
        dest = output/'models'/f'{key}.json';dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False))
        record = {'url':f'/assets/models/{key}.json','model':path,'vertices':sum(m['vertexCount'] for m in result['meshes']),'triangles':sum(m['triangleCount'] for m in result['meshes'])}
        models[key] = record
        return record
    player = model('model/npc/creature/humanoid/forest_elf/forest_elf.bdae','forest-elf')
    exhibits = []
    for name in ['wolf','bear']:
        # Paths come from the observed archive index; reject ambiguity rather than guess.
        candidates = [e['path'] for e in entries if e['pack']=='res_npc.bin' and Path(e['path']).name==name+'.bdae']
        if len(candidates)!=1: raise ValueError(f'Ambiguous sample model {name}: {candidates}')
        exhibits.append(model(candidates[0],name))
    model('model/npc/character/human/male/oc2_human_m_body_01.bdae','human-male')
    grouped = collections.defaultdict(list)
    for instance in terrain['instances']:grouped[instance['model']].append(instance)
    scenery = []
    for i,(path,instances) in enumerate(grouped.items()):
        try:
            obj = model(path,f'scene-{i:02d}');obj['instances']=instances;scenery.append(obj)
        except Exception as e:warnings.append({'model':path,'error':str(e)})
    surface = texture('texture/tiles/textures/cliffside/cliffside_rock05.tga')
    manifest = {'format':'oc2-web-preview-v1','map':{'url':'/assets/maps/tutorial-preview.json','label':'新手区域 · 神殿遗迹','subtitle':'原作地形高程与场景摆放 · 地表使用单层材质预览','surfaceTexture':surface},
                'player':player,'exhibits':exhibits,'scenery':scenery,'textures':textures,
                'summary':f'真实新手地图 3×3 地块；穿衣精灵、狼与熊；接入 {sum(len(s["instances"]) for s in scenery)} 个原作场景摆放。地表混合材质和多节点变换尚未完整恢复。',
                'warnings':warnings}
    archive_names = {entry['pack'] for entry in entries}
    paired = {name for name in archive_names if (source/Path(name).with_name(Path(name).stem+'_i.bin')).is_file()}
    validation = {'originalIndexes':len(paired), 'originalIndexRecords':sum(e['pack'] in paired for e in entries),
                  'nativeNameLookup':True, 'extractedFiles':len(extracted_names)}
    manifest['sourceValidation'] = validation
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    stats = {'archivesIndexed':len(set(e['pack'] for e in entries)),'archiveEntries':len(entries),'extractedVerifiedFiles':len(extracted_names),'convertedModels':len(models),'sceneInstances':sum(len(s['instances']) for s in scenery),'textures':len(textures),'mapVertices':len(terrain['positions'])//3,'mapTriangles':len(terrain['indices'])//3,'sourceValidation':validation,'warnings':warnings}
    return stats

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--extracted', type=Path, default=EXTRACTED)
    cli.add_argument('--output', type=Path, default=OUT)
    args = cli.parse_args()
    stats = build(args.source, args.extracted, args.output)
    report = ROOT/'analysis/raw/resource-preview-build.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':main()
