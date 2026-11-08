"""Rebuild a bounded, local-only preview from the user's game data."""
import collections
import argparse
import json
from pathlib import Path
from resource_packs import index, ResourceArchive, normalize_resource_name, safe_output, DEFAULT_SOURCE
from bdae_convert import BDAE
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling
from bdae_character import convert_character
from beff_effects import recover_effect, EFFECT_SOURCES
from beff_particles import recover_materials
from bdae_skin import read_nodes
from skill_attachments import recover_skill_attachments, REFERENCE_MODEL
from recover_scene_render import build_scene_profile
from ui_assets import recover_ui_assets
from chinese_fonts import recover_chinese_fonts, SOURCE_FONTS
from skill_icons import recover_skill_icons
from skill_ui_assets import recover_skill_ui
from art_library import build_catalog
from hud_assets import recover_hud_assets
from quest_assets import recover_quest_ui
from control_assets import recover_controls
from character_portraits import recover_character_portraits
from inventory_assets import recover_inventory_assets
from item_icons import recover_item_icons
from equipment_appearance import convert_equipment_character, BASE_MODEL, SELECTED
from native_gameplay import recover_gameplay
from player_spell_effects import recover_player_effects
from scene_collision import apply_scene_transforms, recover_collision
from character_hair import recover_character_hair
from character_materials import recover_character_materials
from terrain_convert import convert as terrain_convert
from terrain_materials import recover_materials as recover_terrain_materials
from scene_texture_sampling import recover_scene_sampling
from scene_baked_lighting import recover_model_lighting, recover_baked_lighting
from texture_decode import convert as texture_convert

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT/'game-data/extracted'
OUT = ROOT/'game-data/converted'

def build(source=DEFAULT_SOURCE, extracted=EXTRACTED, output=OUT):
    source, extracted, output = Path(source), Path(extracted), Path(output)
    # Select archive namespaces explicitly while the complete native mounting
    # priority is still under investigation. Never guess between conflicting packs.
    packs = {'res.bin','res_a.bin','res_npc.bin','res_item.bin','model_phy.bin','res_scene.bin','res_scene_generator_temple_000.bin','res_t.bin','res_t_upd15.bin','tables.bin','ui.bin','ui_icon_1.bin','ui_icon_2.bin','conf.bin',
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
    gameplay, attack_actions = recover_gameplay(extract, output, SELECTED)
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
    def model(path, key, animated=False, profile='player', equipment=False, scene_model=False):
        if equipment:
            result = convert_equipment_character(extract, extra_actions=attack_actions)
            result['appearance']['hair']=recover_character_hair(extract,result)
            result['characterMaterials']=recover_character_materials(extract,result,texture)
            result['appearance']['provenance']['hairSelectionRecovered']=True
            result['appearance']['provenance']['materialProfile']='oc2-character-materials-v1'
            result['appearance']['provenance']['limitations']=[
                value for value in result['appearance']['provenance']['limitations']
                if not value.startswith('Original diffuse textures are used;')]
            result['appearance']['provenance']['limitations'].append('Hair and material parameters are recovered in their dedicated profiles; full native character creation, global lighting and device-quality selection remain outside this preview.')
        elif animated:
            animation_path = ('model/npc/creature/beast/wolf/anim/animations.bdae' if profile == 'wolf'
                              else 'model/npc/character/elf/female/anim/animations.bdae')
            animation_model = path if profile == 'wolf' else 'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'
            result = convert_character(extract(path), extract(animation_path), extract(animation_model), profile=profile)
            result['animationBinding']['source'] = animation_path
            result['animationBinding']['restSource'] = animation_model
        else:
            reader = BDAE(extract(path))
            result = reader.parse()
            if scene_model:
                apply_scene_transforms(reader,result)
                result['sceneSampling']=recover_scene_sampling(extract,reader,result)
                result['sceneAlpha']=recover_scene_alpha(extract,reader,result)
                result['sceneCulling']=recover_scene_culling(extract,reader,result)
                if key != 'dynamic-door': result['sceneBakedLighting']=recover_model_lighting(reader,result)
        result['source'] = path
        if not result['meshes']:
            raise ValueError('Model has no supported meshes')
        for mat in result['materials']:
            if mat['diffuse']: texture(mat['diffuse'])
        dest = output/'models'/f'{key}.json';dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False))
        record = {'url':f'/assets/models/{key}.json','model':path,'vertices':sum(m['vertexCount'] for m in result['meshes']),'triangles':sum(m['triangleCount'] for m in result['meshes'])}
        if animated:
            record['animated'] = True
            record['combatAnimations'] = True
            record['attachmentPoints']=['Dummy_R_Hand','Dummy_L_Hand','Dummy_Chest'] if profile=='player' else ['Dummy_Chest']
            if profile == 'player': record.update(skillAnimations=True,jumpAnimations=True)
        if equipment:
            record['appearanceFormat'] = result['appearance']['format']
            record['hairFormat']=result['appearance']['hair']['format']
            record['materialFormat']=result['characterMaterials']['format']
        models[key] = record
        return record
    player_path=BASE_MODEL
    wolf_path='model/npc/creature/beast/wolf/wolf.bdae'
    attachments=recover_skill_attachments(lambda path:extract(path).read_bytes(),
        read_nodes(BDAE(extract(REFERENCE_MODEL))),read_nodes(BDAE(extract(player_path))),read_nodes(BDAE(extract(wolf_path))))
    model('model/npc/creature/humanoid/forest_elf/forest_elf.bdae','forest-elf',animated=True)
    player = model(player_path,'elf-female', animated=True, equipment=True)
    exhibits = []
    for name in ['wolf','bear']:
        # Paths come from the observed archive index; reject ambiguity rather than guess.
        candidates = [e['path'] for e in entries if e['pack']=='res_npc.bin' and Path(e['path']).name==name+'.bdae']
        if len(candidates)!=1: raise ValueError(f'Ambiguous sample model {name}: {candidates}')
        exhibits.append(model(candidates[0],name,animated=name=='wolf',profile='wolf' if name=='wolf' else 'player'))
    model('model/npc/character/human/male/oc2_human_m_body_01.bdae','human-male')
    grouped = collections.defaultdict(list)
    for instance in terrain['instances']:grouped[instance['model']].append(instance)
    scenery = []
    for i,(path,instances) in enumerate(grouped.items()):
        try:
            obj = model(path,f'scene-{i:02d}',scene_model=True);obj['instances']=instances;scenery.append(obj)
        except Exception as e:warnings.append({'model':path,'error':str(e)})
    collision=recover_collision(extract,scenery)
    if sum(len(item['instances']) for item in scenery) != len(terrain['instances']):
        raise ValueError('Required source scene models failed conversion; refusing partial lighting package')
    dynamic_door=model('model/scene_generator_temple_000/god_door_01.bdae','dynamic-door',scene_model=True)
    (output/'maps/collision.json').write_text(json.dumps(collision,ensure_ascii=False,indent=2))
    surface = texture('texture/tiles/textures/cliffside/cliffside_rock05.tga')
    effects = {}
    effect_materials = recover_materials(extract('EfflibEffects.bdae'))
    player_effects=recover_player_effects(extract)
    attachments['effects'].update(player_effects['effects'])
    for key, path in {**EFFECT_SOURCES,**{k:v['path'] for k,v in player_effects['effects'].items()}}.items():
        effect = recover_effect(extract(path))
        effect['source'] = path
        if attachments['effects'][key]['path'].lower()!=path.lower():raise ValueError('Skill attachment effect path mismatch')
        effect['particleScale']=attachments['effects'][key]['particleScale']
        effect['textureURLs'] = {name: texture(name) for name in effect['textures']}
        for emitter in effect['emitters']:
            emitter['particle']['material'] = effect_materials[emitter['particle']['materialId']]
        for node in effect['modelNodes']:node['material']=effect_materials[node['materialId']]
        if not all(effect['textureURLs'].values()): raise ValueError(f'Missing original effect textures: {path}')
        effects[key] = effect
    effect_output = output/'effects/combat.json'
    effect_output.parent.mkdir(parents=True, exist_ok=True)
    effect_output.write_text(json.dumps({'format':'oc2-combat-effects-v4','effects':effects,'attachments':attachments,'playerSpells':player_effects,
        'adaptation':'Recovered particle parameters, materials and source skill slots. The modular elf female uses its native hand/chest dummies. Deterministic random seeds and overall skill flight path remain web adaptations.'}, ensure_ascii=False, indent=2))
    rendering=build_scene_profile(extract)
    baked_lighting=recover_baked_lighting(extract,scenery,texture)
    (output/'rendering').mkdir(parents=True,exist_ok=True)
    (output/'rendering/baked-lighting.json').write_text(json.dumps(baked_lighting,ensure_ascii=False,indent=2,allow_nan=False))
    rendering['format']='oc2-scene-render-v1'
    rendering['defaultZoneId']=min(rendering['zones'],key=lambda zone:zone['priority'])['id']
    rendering['lut']['url']=texture(rendering['lutPath'])
    if not rendering['lut']['url']:raise ValueError('Source HDR lookup texture missing')
    render_output=output/'rendering/tutorial.json';render_output.parent.mkdir(parents=True,exist_ok=True)
    render_output.write_text(json.dumps(rendering,ensure_ascii=False,indent=2))
    terrain_materials=recover_terrain_materials(extract,lambda p:normalize_resource_name(p) in by_name,output,terrain,texture)
    ui = recover_ui_assets(extract, output)
    ui['skillUI'] = recover_skill_ui(extract, output)
    ui['questUI'] = recover_quest_ui(extract, output, gameplay['quests'])
    allowed_loose = {spec['path'] for spec in SOURCE_FONTS.values()}
    def read_loose(path):
        if path not in allowed_loose:raise ValueError(f'Unexpected loose resource: {path}')
        return safe_output(source, path)
    # Check actual Chinese interface characters, including dynamic combat labels.
    ui_text = ''.join((ROOT/'prototype/public'/name).read_text() for name in ['explore.html','explore.js','skills.js','professions.js','recovered-hud.js','inventory-ui.js','skill-book.js','quest-book.js','terrain-materials.js','quest-list-state.js','object-interaction-state.js','mobile-hud.js','touch-joystick.js','items.js','character-equipment.js','character-look.js','character-materials.js'])
    ui_text += (ROOT/'prototype/public/monster-state.js').read_text()+(ROOT/'prototype/public/buff-presentation.js').read_text()+(ROOT/'prototype/public/context-control.js').read_text()
    ui_text += json.dumps(ui['skillUI'], ensure_ascii=False) + json.dumps(ui['questUI'], ensure_ascii=False)
    required_text = ''.join(sorted({ch for ch in ui_text if '\u3400' <= ch <= '\u9fff'}))
    chinese = recover_chinese_fonts(read_loose, output, required_text)
    if chinese['requiredTextStatus'] != 'complete':raise ValueError('Original Chinese fonts do not cover the current interface')
    icons = recover_skill_icons(extract, output)
    ui['format'] = 'oc2-original-ui-v19'
    ui['fonts']['faces'].update(chinese['faces'])
    ui['fonts']['chineseStatus'] = chinese['chineseStatus']
    ui['fonts']['requiredTextStatus'] = chinese['requiredTextStatus']
    ui['fonts']['chineseProfile'] = '/assets/ui/chinese-fonts.json'
    ui['fonts']['status'] = 'original-full-cjk-and-embedded-latin-subsets'
    ui['skillIcons'] = icons
    ui['hud'] = recover_hud_assets(extract, output)
    ui['controls'] = recover_controls(extract, output/'ui', ui['hud'])
    ui['gameplay'] = gameplay
    ui['controls']['attack'].pop('webEquipmentSelection',None)
    ui['controls']['attack'].update(nativeWeaponToSkillSelectionRecovered=False,nativeNormalWeaponSelectionRecovered=True,nativeWeaponTableFilterRecovered=True,runtimeProfile='/assets/gameplay/native.json',
        pressArguments=[1,1],releaseArguments=[1,2],releaseOutArguments=[1,3])
    ui['controls']['interaction'].update(nativeJumpPhysicsRecovered=False,nativeNormalJumpVerticalStepRecovered=True)
    (output/'ui/controls.json').write_text(json.dumps(ui['controls'],ensure_ascii=False,indent=2))
    ui['portraits'] = recover_character_portraits(extract, output, player_model=player_path)
    ui['inventory'] = recover_inventory_assets(extract, output)
    ui['itemIcons'] = recover_item_icons(extract, output)
    ui['provenance']['limitations'] = [
        'Original art and full source CJK fonts are reused in the web layout; complete original Flash UI behavior is not restored.',
        'Rare CJK extensions and characters absent from the source fonts require system fallback.',
        'Original square skill images are adapted to the existing circular web HUD slots.',
    ]
    (output/'ui/profile.json').write_text(json.dumps(ui,ensure_ascii=False,indent=2))
    manifest = {'format':'oc2-web-preview-v1','map':{'url':'/assets/maps/tutorial-preview.json','label':'新手区域 · 神殿遗迹','subtitle':'','surfaceTexture':surface,'materials':{'url':'/assets/maps/terrain-materials.json','format':terrain_materials['format']}},
                'player':player,'exhibits':exhibits,'scenery':scenery,'textures':textures,
                'effects': {'url':'/assets/effects/combat.json','format':'oc2-combat-effects-v4'},
                'rendering':{'url':'/assets/rendering/tutorial.json','format':'oc2-scene-render-v1'},
                'sceneBakedLighting':{'url':'/assets/rendering/baked-lighting.json','format':baked_lighting['format']},
                'ui':{'url':'/assets/ui/profile.json','format':ui['format']},
                'gameplay':{'url':'/assets/gameplay/native.json','format':gameplay['format']},
                'navigation':gameplay['npc']['navigation'],
                'collision':{'url':'/assets/maps/collision.json','format':collision['format']},
                'dynamicModels':[dynamic_door],
                'summary':f'真实新手地图 3×3 地块；可换装玩家精灵、狼与熊；接入 {sum(len(s["instances"]) for s in scenery)} 个原作场景摆放。已恢复场景节点与静态PHY碰撞；地表混合材质及完整物理引擎尚未恢复。',
                'warnings':warnings}
    archive_names = {entry['pack'] for entry in entries}
    paired = {name for name in archive_names if (source/Path(name).with_name(Path(name).stem+'_i.bin')).is_file()}
    validation = {'originalIndexes':len(paired), 'originalIndexRecords':sum(e['pack'] in paired for e in entries),
                  'nativeNameLookup':True, 'extractedFiles':len(extracted_names),
                  'looseFontSources':{face['sourcePath']:{'bytes':face['sourceBytes'],'sha256':face['sourceSHA256']}
                                      for face in chinese['faces'].values()}}
    manifest['sourceValidation'] = validation
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    catalog = build_catalog(output)
    stats = {'archivesIndexed':len(set(e['pack'] for e in entries)),'archiveEntries':len(entries),'extractedVerifiedFiles':len(extracted_names),'convertedModels':len(models),'sceneInstances':sum(len(s['instances']) for s in scenery),'textures':len(textures),'mapVertices':len(terrain['positions'])//3,'mapTriangles':len(terrain['indices'])//3,'sourceValidation':validation,'warnings':warnings}
    stats['artLibrary'] = {'files':catalog['fileCount'],'bytes':catalog['totalBytes']}
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
