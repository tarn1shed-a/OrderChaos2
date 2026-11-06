"""Verify generated preview references and geometry, without running the original game."""
import json
import math
import argparse
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
    refs = [m['player'],*m['exhibits'],*m['scenery']]
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
    assert effects['format'] == 'oc2-combat-effects-v3'
    attachments = effects['attachments']
    assert attachments['format'] == 'oc2-skill-attachments-v1'
    assert set(effects['effects']) == {'fireCast','fireMissile','fireHit','frostHit'}
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
    assert ui['format'] == 'oc2-original-ui-v1' and not ui['provenance']['swfScriptExecution']
    for entry in ui['assets'].values():
        with Image.open(asset(entry['url'], output)) as image:
            assert image.size == (entry['width'], entry['height'])
    glyphs = 0
    for face in ui['fonts']['faces'].values():
        with TTFont(asset(face['url'], output)) as font:
            assert set(font.getBestCmap()) == set(face['codePoints'])
            glyphs += len(face['codePoints'])
    assert ui['fonts']['faces']['leagueGothic']['completeDigits']
    assert ui['fonts']['chineseStatus'] == 'incomplete-use-system-fallback'
    return {'status':'passed','terrainVertices':vertices,'terrainTriangles':len(terrain['indices'])//3,
                     'modelsReferenced':len(refs),'meshes':mesh_count,'textures':len(m['textures']), 'combatEffects':len(effects['effects']),
                     'sceneInstances':sum(len(s['instances']) for s in m['scenery']),
                     'renderZones':len(rendering['zones']), 'uiCrops':len(ui['assets']), 'fontGlyphs':glyphs, 'warnings':m['warnings']}

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, default=OUT)
    args = cli.parse_args()
    print(json.dumps(verify(args.output)))

if __name__ == '__main__': main()
