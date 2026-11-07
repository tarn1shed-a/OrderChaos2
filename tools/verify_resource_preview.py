"""Verify generated preview references and geometry, without running the original game."""
import json
import math
import argparse
import hashlib
from pathlib import Path
from PIL import Image
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'game-data/converted'

def asset(url, output=OUT):
    assert url.startswith('/assets/')
    p = output/url.removeprefix('/assets/')
    assert p.resolve().is_relative_to(output.resolve()) and p.is_file(), url
    return p

def verify(output=OUT):
    output = Path(output)
    m = json.loads((output/'manifest.json').read_text())
    terrain = json.loads(asset(m['map']['url'], output).read_text())
    positions = terrain['positions']; vertices = len(positions)//3
    assert all(math.isfinite(v) for v in positions)
    assert len(terrain['normals']) == vertices*3
    assert len(terrain['uvs']) == vertices*2
    assert max(terrain['indices']) < vertices and min(terrain['indices']) >= 0
    assert all(math.isfinite(v) for v in terrain['grid']['heights'])
    assert len(terrain['grid']['heights']) == terrain['grid']['width']*terrain['grid']['height']
    assert terrain['verification']['seamSamplesMatched'] > 0
    refs = [m['player'],*m['exhibits'],*m['scenery'],*m['dynamicModels']]
    mesh_count = 0
    for ref in refs:
        data = json.loads(asset(ref['url'], output).read_text())
        if ref.get('animated'):
            assert data['format'] == 'bdae946-character-v1'
            rig = data['rig']
            assert set(ref['attachmentPoints']) <= {name for node in rig['nodes'] for name in [node['name'], *node.get('aliases', [])]}
            for index, node in enumerate(rig['nodes']):
                assert -1 <= node['parent'] < index
                assert all(math.isfinite(v) for key in ['position','quaternion','scale'] for v in node[key])
            for skin in rig['skins']:
                n = data['meshes'][skin['mesh']]['vertexCount']
                assert len(skin['skinIndices']) == len(skin['skinWeights']) == n * 4
                assert all(0 <= joint < len(skin['boneNodes']) for joint in skin['skinIndices'])
                assert all(0 <= node < len(rig['nodes']) for node in skin['boneNodes'])
                assert all(math.isfinite(weight) and 0 <= weight <= 1 for weight in skin['skinWeights'])
                assert all(abs(sum(skin['skinWeights'][at:at+4])-1)<1e-5 for at in range(0,n*4,4))
                assert skin['verification']['maximumRestBindShapeError'] < 1e-5
            expected = {'idle','walk_forward','attack','hurt','death'}
            if ref.get('skillAnimations'): expected |= {'skill_fireball','skill_frost_blast'}
            if ref.get('jumpAnimations'): expected |= {'jump_start','jump_air','jump_land','jumplandrun','jump_air_drop'}
            if ref is m['player']:
                profile=json.loads(asset(m['gameplay']['url'],output).read_text())
                expected |= {s['clip'] for s in profile['skills'].values() if s['clip']}
                expected |= {v[k]['clip'] for s in profile['casting']['spells'].values() for v in s['visuals'].values() for k in ('pre','loop') if k in v}
            assert {clip['name'] for clip in data['clips']} == expected
            for clip in data['clips']:
                for track in clip['tracks']:
                    components = 4 if track['type'] == 'quaternion' else 3
                    assert len(track['values']) == len(track['times']) * components
                    assert all(a < b for a,b in zip(track['times'],track['times'][1:]))
                    assert track['times'][0] == 0 and abs(track['times'][-1]-clip['duration']) < 1e-7
                    assert all(math.isfinite(value) for value in track['values'])
        for mesh in data['meshes']:
            n = len(mesh['positions'])//3
            assert n > 0 and all(math.isfinite(v) for v in mesh['positions'])
            assert len(mesh['normals']) == n*3 and len(mesh['uvs']) == n*2
            assert max(mesh['indices']) < n and min(mesh['indices']) >= 0
            assert sum(g['count'] for g in mesh['groups']) == len(mesh['indices'])
            assert all(0 <= g['material'] < len(data['materials']) for g in mesh['groups'])
            mesh_count += 1
    for url in m['textures'].values():
        with Image.open(asset(url, output)) as image: image.verify()
    effects = json.loads(asset(m['effects']['url'], output).read_text())
    assert effects['format'] == 'oc2-combat-effects-v4'
    attachments = effects['attachments']
    assert attachments['format'] == 'oc2-skill-attachments-v1'
    assert set(effects['effects']) == {'fireCast','fireMissile','fireHit','frostHit','playerFireCast','playerFireMissile','playerFireHit','arcaneCast','arcaneMissile','arcaneHit'}
    for key, effect in effects['effects'].items():
        assert effect['particleScale'] == attachments['effects'][key]['particleScale']
        assert effect['particleScale'] > 0 and 0 <= effect['fogRate'] <= 1
        assert effect['format'] == 'beff9-particle-system-v2'
        assert effect['verification']['completePayload']
        assert effect['verification']['fileSize'] == effect['verification']['bytesConsumed']
        for emitter in effect['emitters']:
            assert emitter['particle']['material']['id'] == emitter['particle']['materialId']
            assert emitter['particle']['texture'] in effect['textureURLs']
        assert len(effect['sourceSHA256']) == 64
        assert set(effect['textureURLs']) == set(effect['textures'])
        for name, url in effect['textureURLs'].items(): assert m['textures'][name] == url and asset(url, output).is_file()
    rendering = json.loads(asset(m['rendering']['url'], output).read_text())
    assert rendering['format'] == 'oc2-scene-render-v1'
    assert rendering['defaultZoneId'] in {zone['id'] for zone in rendering['zones']}
    assert rendering['hdr']['blurIterations'] == 2
    with Image.open(asset(rendering['lut']['url'], output)) as lut:
        assert lut.size == (512,16)
    ui = json.loads(asset(m['ui']['url'], output).read_text())
    assert ui['format'] == 'oc2-original-ui-v18' and not ui['provenance']['swfScriptExecution']
    controls=ui['controls'];assert controls['format']=='oc2-original-controls-v1' and not controls['scriptExecution']
    assert m['player']['jumpAnimations']
    collision=json.loads(asset(m['collision']['url'],output).read_text())
    assert collision['format']=='oc2-scene-collision-v2'
    assert len(collision['instances'])==39
    assert sum(len(s['shapes']) for s in collision['sources'].values())==111
    assert all(mesh.get('sourceNodeTransform') for ref in m['scenery'] for mesh in json.loads(asset(ref['url'],output).read_text())['meshes'])
    assert controls==json.loads((output/'ui/controls.json').read_text())
    gameplay=json.loads(asset(m['gameplay']['url'],output).read_text())
    assert gameplay==ui['gameplay'] and gameplay['format']=='oc2-native-gameplay-v9'
    quests=gameplay['quests'];assert quests['format']=='oc2-source-quests-v1' and not quests['serverScriptsRecovered']
    quest_ui=ui['questUI'];assert quest_ui['format']=='oc2-original-quest-ui-v2' and quest_ui['data']==quests
    assert len(quests['catalog'])==2 and len(quests['objects'])==3 and len(quest_ui['methods'])==11 and len(quest_ui['assets'])==4
    assert quests['clientStates']['status']['QMGR_QUEST_FINISHED']==9 and quests['clientStates']['status']['QMGR_QUEST_NOT_FINISHED']==4
    assert quest_ui['strings']['GENERAL_QUESTHUD_NOQUEST']['text']=='无可用任务！'
    assert quest_ui==json.loads(asset('/assets/ui/quests.json',output).read_text())
    for entry in quest_ui['assets'].values():
        with Image.open(asset(entry['url'],output)) as image:assert image.size==(entry['width'],entry['height'])
    interaction=gameplay['interaction'];assert interaction['format']=='oc2-source-interaction-v1'
    assert interaction['button']['tapCallback']=='onInteractionClick' and interaction['button']['nonemptyFunctionReplacesJump']
    assert len(interaction['previewObjectSpawns'])==3 and {r['entry'] for r in interaction['previewObjectProtos']}=={610,621}
    assert controls['icons']['loot']['sourcePath']=='ui/icons/interactive/loot.png'
    assert 'OperationPanel2.onInteractionClick' in controls['methods']
    navigation=json.loads(asset(m['navigation']['url'],output).read_text())
    assert navigation['format']=='oc2-source-navigation-v1' and len(navigation['tiles'])==9 and len(navigation['nodes'])==381
    assert gameplay['npc']['navigation']==m['navigation'] and gameplay['npc']['nonzeroAIPlans']==0
    assert gameplay['npc']['previewOriginalWolfSpawns']==[]
    assert all(t['verification']['bytesConsumed']==t['verification']['fileSize'] for t in navigation['tiles'])
    assert all(0<=e['to']<len(navigation['nodes']) for n in navigation['nodes'] for e in n['edges'])
    combat=gameplay['combat'];assert combat['format']=='oc2-native-combat-v1'
    assert combat['mechanics']['burnDurationMs']==7000 and combat['mechanics']['freezeDurationMs']==2000
    assert len(combat['baseAttributes'])==90
    for aura in combat['auras'].values():
        assert hashlib.sha256(asset(aura['icon']['url'],output).read_bytes()).hexdigest()==aura['icon']['sourceSHA256']
        with Image.open(asset(aura['icon']['url'],output)) as image:assert image.size==(96,96)
    assert gameplay['weapons']['trainingSword']['legacy']
    for icon in gameplay['icons'].values():
        assert hashlib.sha256(asset(icon['url'],output).read_bytes()).hexdigest()==icon['sourceSHA256']
    for icon in controls['icons'].values():
        path=asset(icon['url'],output)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==icon['sourceSHA256']
        with Image.open(path) as image:assert image.size==(96,96)
    assert set(controls['hitZones'])=={'attack','interaction'}
    for entry in ui['assets'].values():
        with Image.open(asset(entry['url'], output)) as image:
            assert image.size == (entry['width'], entry['height'])
    glyphs = 0
    assert {'chineseText','chineseDisplay'} <= set(ui['fonts']['faces'])
    for face in ui['fonts']['faces'].values():
        font_path = asset(face['url'], output)
        with TTFont(font_path) as font:
            if 'codePoints' in face:assert set(font.getBestCmap()) == set(face['codePoints'])
            else:
                assert len(font.getBestCmap()) == face['codePointCount']
                assert font['maxp'].numGlyphs == face['sourceGlyphCount']
                assert face['output']['allSourceTablesVerified'] and not face['subset']
                assert face['coverage']['requiredText']['status'] == 'complete'
                assert hashlib.sha256(font_path.read_bytes()).hexdigest() == face['output']['sha256']
            glyphs += len(font.getBestCmap())
    assert ui['fonts']['faces']['leagueGothic']['completeDigits']
    assert ui['fonts']['chineseStatus'] == 'source-fonts-available'
    assert ui['fonts']['requiredTextStatus'] == 'complete'
    icons = ui['skillIcons']
    assert icons['format'] == 'oc2-skill-icons-v1' and set(icons['icons']) == {'fireball','frost_blast','arcane_missile'}
    for icon in icons['icons'].values():
        path = asset(icon['url'], output)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == icon['sourceSHA256']
        with Image.open(path) as image:assert image.size == (96,96)
    hud=ui['hud'];assert hud['format']=='oc2-original-hud-v1'
    assert hud['nativeControls']['format']=='oc2-original-mobile-controls-v2'
    assert set(hud['layouts']['joystick']['fields'])=={'bg','stick'}
    assert hud['nativeControls']['joystick']['runtimeEvidenceProfile']==controls['format']
    assert hud['progress']['healthGreen']['sourceRole']=='self-health'
    assert hud['progress']['healthGreen']['frameCount']==50
    assert hud['progress']['healthGreen']['webMapping']['ratioOrder']=='descending'
    for entry in hud['assets'].values():
        with Image.open(asset(entry['url'],output)) as image:assert image.size==(entry['width'],entry['height'])
    for key in ('healthGreen','cooldownSkill','cooldownAttack','experience'):
        progress=hud['progress'][key]
        assert len(progress['frames'])==progress['frameCount']
        assert [frame['frame'] for frame in progress['frames']]==list(range(1,progress['frameCount']+1))
    portraits=ui['portraits'];assert portraits['format']=='oc2-character-portraits-v1'
    assert portraits['models']['player']['modelPath']==m['player']['model']
    assert portraits['models']['player']['webPlayerSelection']=='modular-elf-female-body'
    for key in ('player','targetWolf'):
        entry=portraits['models'][key];model=json.loads(asset(entry['modelURL'],output).read_text())
        assert entry['mode']=='source-model-web-framing'
        assert any(entry['headNode'] in [node['name'],*node.get('aliases',[])] for node in model['rig']['nodes'])
    inventory=ui['inventory'];assert inventory['format']=='oc2-original-inventory-v1'
    assert not inventory['provenance']['swfScriptExecution']
    assert inventory['layouts']['bag']['columns']==8 and len(inventory['layouts']['bag']['slots'])==40
    assert inventory['layouts']['bag']['visibleRowsAreNotTotalCapacity']
    assert {slot['index'] for slot in inventory['layouts']['equipment']['slots']}=={0,1,2,4,6,7,8,9,13,21}
    for entry in inventory['assets'].values():
        with Image.open(asset(entry['url'],output)) as image:assert image.size==(entry['width'],entry['height'])
    skill_ui=ui['skillUI'];assert skill_ui['format']=='oc2-original-skill-ui-v1'
    assert not skill_ui['provenance']['swfScriptExecution'] and not skill_ui['provenance']['nativeProgressionImplemented']
    assert len(skill_ui['skills'])==14
    assert [sum(skill['kind']==kind for skill in skill_ui['skills']) for kind in ('active','passive')]==[9,5]
    for skill in skill_ui['skills']:
        assert len(skill['runes'])==(3 if skill['kind']=='active' else 0)
        for entry in [skill['base'],*skill['runes']]:
            path=asset(entry['icon']['url'],output)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['icon']['sourceSHA256']
            with Image.open(path) as image:assert image.size==(96,96)
    for entry in skill_ui['assets'].values():
        with Image.open(asset(entry['url'],output)) as image:assert image.size==(entry['width'],entry['height'])
    item_icons=ui['itemIcons'];assert item_icons['format']=='oc2-item-icons-v1'
    assert set(item_icons['icons'])=={'trainingSword','trainingStaff','trainingGreatsword','linenArmor','travelerBoots','wolfPelt'}
    assert not item_icons['provenance']['nativeZeroDisplayFallbackVerified']
    for entry in item_icons['icons'].values():
        image_path=asset(entry['url'],output)
        assert hashlib.sha256(image_path.read_bytes()).hexdigest()==entry['sourceSHA256']
        with Image.open(image_path) as image:assert image.size==(96,96)
    player=json.loads(asset(m['player']['url'],output).read_text())
    appearance=player['appearance'];assert appearance['format']==m['player']['appearanceFormat']=='oc2-equipment-appearance-v1'
    hair=appearance['hair'];assert hair['format']==m['player']['hairFormat']=='oc2-character-hair-v1'
    assert set(hair['styles'])=={'hair1','hair2','hair3'}
    assert set(appearance['items'])=={'trainingSword','trainingStaff','trainingGreatsword','linenArmor','travelerBoots'}
    covered=set(appearance['baseMeshIndices'])
    for key,entry in appearance['items'].items():
        assert entry['meshIndices'] and set(entry['hideBaseMeshIndices'])<=set(appearance['baseMeshIndices'])
        assert not set(entry['meshIndices'])&covered
        covered.update(entry['meshIndices'])
    for entry in hair['styles'].values():
        assert not covered&set(entry['meshIndices']);covered.update(entry['meshIndices'])
    assert covered==set(range(len(player['meshes'])))
    for mesh in player['meshes']:
        assert len(mesh['sourceTangents'])==len(mesh['sourceBinormals'])==len(mesh['positions'])
        assert all(math.isfinite(v) for key in ('sourceTangents','sourceBinormals') for v in mesh[key])
        if 'attachment' in mesh:
            assert 0<=mesh['attachment']['node']<len(player['rig']['nodes'])
            assert len(mesh['attachment']['matrix'])==16 and all(math.isfinite(v) for v in mesh['attachment']['matrix'])
    materials=player['characterMaterials'];assert materials['format']==m['player']['materialFormat']=='oc2-character-materials-v1'
    assert len(materials['materials'])==len(player['materials'])==12
    assert materials['defaults']['neutralIdentityEye']==[0,0,0]
    assert not materials['colors']['skin']['color6']['enabled']
    for index,entry in enumerate(materials['materials']):
        assert entry['index']==index
        assert all(math.isfinite(v) for v in entry['scalars'].values())
        for url in entry['samplers'].values():
            with Image.open(asset(url,output)) as image:image.verify()
    catalog = json.loads(asset('/assets/library/catalog.json', output).read_text())
    assert catalog['format'] == 'oc2-art-catalog-v1'
    assert catalog['sourceFormats'] == {'web':m['format'], **{key:m[key]['format'] for key in ('effects','rendering','ui','gameplay','collision','navigation')}}
    assert catalog['fileCount'] == len(catalog['entries'])
    for entry in catalog['entries']:
        path = asset('/assets/'+entry['path'], output)
        assert path.stat().st_size == entry['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    assert catalog['totalBytes'] == sum(entry['bytes'] for entry in catalog['entries'])
    asset('/assets/library/index.html', output); asset('/assets/library/style.css', output)
    return {'status':'passed','terrainVertices':vertices,'terrainTriangles':len(terrain['indices'])//3,
                     'modelsReferenced':len(refs),'meshes':mesh_count,'textures':len(m['textures']), 'combatEffects':len(effects['effects']),
                     'sceneInstances':sum(len(s['instances']) for s in m['scenery']),
                     'renderZones':len(rendering['zones']), 'uiCrops':len(ui['assets']),
                     'skillIcons':len(icons['icons']), 'fontCharacters':glyphs,
                     'hudAssets':len(hud['assets']),'controlIcons':len(controls['icons']),'controlMethods':len(controls['methods']),'modelPortraits':len(portraits['models']),
                     'skillCatalog':len(skill_ui['skills']),'skillUIAssets':len(skill_ui['assets']),
                     'inventoryAssets':len(inventory['assets']),'itemIcons':len(item_icons['icons']),
                     'equipmentAppearances':len(appearance['items']),
                     'hairStyles':len(hair['styles']),'characterMaterials':len(materials['materials']),
                     'artFiles':catalog['fileCount'], 'warnings':m['warnings']}

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, default=OUT)
    args = cli.parse_args()
    print(json.dumps(verify(args.output)))

if __name__ == '__main__': main()
