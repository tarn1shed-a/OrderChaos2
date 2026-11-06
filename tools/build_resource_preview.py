"""Rebuild a bounded, local-only preview from the user's game data."""
import collections
import json
from pathlib import Path
from resource_packs import index, read_entry, safe_output, DEFAULT_SOURCE
from bdae_convert import BDAE
from terrain_convert import convert as terrain_convert
from texture_decode import convert as texture_convert

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT/'game-data/extracted'
OUT = ROOT/'game-data/converted'

def main():
    # Extract only needed archives, not accounts, databases, fonts or unrelated UI.
    packs = {'res.bin','res_a.bin','res_npc.bin','res_scene.bin','res_scene_generator_temple_000.bin','res_t.bin',
             'tutorial.bin','tutorial_layer.bin','tutorial_lmap_1.bin',
             'selection.bin','selection_layer.bin','selection_lmap_1.bin',
             'dawnwatch.bin','dawnwatch_layer.bin','dawnwatch_lmap_1.bin'}
    entries = index()
    count = 0
    for entry in entries:
        if entry['pack'] not in packs or entry['path'].endswith('/'):
            continue
        out = safe_output(EXTRACTED, entry['path'])
        data = read_entry(entry)
        out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data); count += 1
    OUT.mkdir(parents=True, exist_ok=True)
    terrain_convert('tutorial', -43, 2, 3, OUT/'maps/tutorial-preview.json')
    terrain = json.loads((OUT/'maps/tutorial-preview.json').read_text())
    textures = {}; warnings = []; models = {}
    def texture(path):
        if path in textures:
            return textures[path]
        try:
            rel = Path(path).with_suffix('.png')
            target = OUT/'textures'/rel
            texture_convert(safe_output(EXTRACTED,path), target)
            textures[path] = '/assets/textures/'+rel.as_posix()
            return textures[path]
        except Exception as e:
            warnings.append({'texture':path,'error':str(e)})
            return None
    def model(path, key):
        result = BDAE(safe_output(EXTRACTED,path)).parse()
        if not result['meshes']:
            raise ValueError('Model has no supported meshes')
        for mat in result['materials']:
            if mat['diffuse']: texture(mat['diffuse'])
        dest = OUT/'models'/f'{key}.json';dest.parent.mkdir(parents=True,exist_ok=True)
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
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    stats = {'archivesIndexed':len(set(e['pack'] for e in entries)),'archiveEntries':len(entries),'extractedVerifiedFiles':count,'convertedModels':len(models),'sceneInstances':sum(len(s['instances']) for s in scenery),'textures':len(textures),'mapVertices':len(terrain['positions'])//3,'mapTriangles':len(terrain['indices'])//3,'warnings':warnings}
    (ROOT/'analysis/raw/resource-preview-build.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':main()
