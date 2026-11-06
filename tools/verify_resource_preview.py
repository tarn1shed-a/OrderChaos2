"""Verify generated preview references and geometry, without running the original game."""
import json
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'game-data/converted'

def asset(url):
    assert url.startswith('/assets/')
    p = OUT/url.removeprefix('/assets/')
    assert p.resolve().is_relative_to(OUT.resolve()) and p.is_file(), url
    return p

def main():
    m = json.loads((OUT/'manifest.json').read_text())
    terrain = json.loads(asset(m['map']['url']).read_text())
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
        data = json.loads(asset(ref['url']).read_text())
        for mesh in data['meshes']:
            n = len(mesh['positions'])//3
            assert n > 0 and all(math.isfinite(v) for v in mesh['positions'])
            assert len(mesh['normals']) == n*3 and len(mesh['uvs']) == n*2
            assert max(mesh['indices']) < n and min(mesh['indices']) >= 0
            assert sum(g['count'] for g in mesh['groups']) == len(mesh['indices'])
            assert all(0 <= g['material'] < len(data['materials']) for g in mesh['groups'])
            mesh_count += 1
    for url in m['textures'].values():
        with Image.open(asset(url)) as image: image.verify()
    print(json.dumps({'status':'passed','terrainVertices':vertices,'terrainTriangles':len(terrain['indices'])//3,
                     'modelsReferenced':len(refs),'meshes':mesh_count,'textures':len(m['textures']),
                     'sceneInstances':sum(len(s['instances']) for s in m['scenery']), 'warnings':m['warnings']}))

if __name__ == '__main__': main()
