"""Verify generated preview references and geometry, without running the original game."""
import json
import math
import argparse
from pathlib import Path
from PIL import Image

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
    return {'status':'passed','terrainVertices':vertices,'terrainTriangles':len(terrain['indices'])//3,
                     'modelsReferenced':len(refs),'meshes':mesh_count,'textures':len(m['textures']),
                     'sceneInstances':sum(len(s['instances']) for s in m['scenery']), 'warnings':m['warnings']}

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, default=OUT)
    args = cli.parse_args()
    print(json.dumps(verify(args.output)))

if __name__ == '__main__': main()
