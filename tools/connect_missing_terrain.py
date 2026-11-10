"""Attach the verified native terrain-miss branch to the isolated preview.

Existing asset namespaces, lighting modules and physics code stay unchanged.
This connector accepts the already expanded preview, not the withdrawn game.
"""
import argparse
import json
import shutil
from tutorial_map_geometry import local_output
from connect_map_geometry import replace_once


def connect(runtime,geometry):
    runtime,geometry=map(local_output,(runtime,geometry))
    assets=runtime/'game-data/converted';p=runtime/'prototype';public=p/'public'
    if assets.is_symlink():raise ValueError('Preserve the backup; detach the preview assets first')
    audit=json.loads((geometry/'geometry-audit.json').read_text())
    if audit['nativeMissingTextureFallback']['originalTextureRecovered']:
        raise ValueError('A native fallback is not recovered original artwork')
    manifest=json.loads((geometry/'base/manifest.json').read_text())
    cfg=json.loads((p/'native-physics.json').read_text())
    collisions=json.loads((geometry/'physics/collision.json').read_text())
    # This bounded terrain-only change must not silently change static models.
    if set(cfg['sourceFiles'])!=set(collisions['sources']):raise ValueError('Static source set changed; needs a separate check')
    for name,item in collisions['sources'].items():
        if cfg['sourceFiles'][name]['sha256']!=item['sourceSHA256']:raise ValueError('Static source bytes changed')
    js=(public/'explore-map.js').read_text()
    js=replace_once(js,"json('/assets/geometry-expanded/manifest.json')","json('/assets/geometry-missing-terrain/manifest.json')")
    start=js.index("    $('asset-detail').textContent = '");end=js.index(';',start)
    js=js[:start]+"    $('asset-detail').textContent = '251块原地形资料；缺贴图处使用已核对的原程序占位纹理，水面和部分场景仍待恢复。'"+js[end:]
    files=[]
    for name in audit['addedAssetFiles']:
        if name in ('manifest.json','maps/terrain-materials.json','rendering/terrain-lighting.json'):continue
        files.append((geometry/'base'/name,assets/name))
    files.extend((src,assets/'geometry-missing-terrain'/src.relative_to(geometry/'verified'))
                 for src in (geometry/'verified').rglob('*')if src.is_file())
    for src,dest in files:
        if dest.exists()and dest.read_bytes()!=src.read_bytes():raise ValueError('Existing asset differs; preserve it: '+str(dest))
    for src,dest in files:
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    cfg.update(terrain=str(geometry/'base'/manifest['mapWindow']['url'].removeprefix('/assets/')),
               collision=str(geometry/'physics/collision.json'),terrainLighting=str(geometry/'verified/terrain-lighting.json'))
    (p/'native-physics.json').write_text(json.dumps(cfg,indent=2)+'\n')
    (public/'explore-map.js').write_text(js)
    html=(public/'explore-map.html').read_text()
    (public/'explore-map.html').write_text(replace_once(html,'/explore-map.js?expansion=1','/explore-map.js?terrain-missing=1'))
    return {'tiles':audit['tileCount'],'displayedInstances':audit['preview']['displayedInstances'],
            'originalMissingTexture':audit['nativeMissingTextureFallback']['nativeName'],
            'lightingChanged':False,'newListener':False,'automaticContinuation':'PAUSED'}


if __name__=='__main__':
    from pathlib import Path
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--runtime',type=Path,required=True);a.add_argument('--geometry',type=Path,required=True)
    x=a.parse_args();print(json.dumps(connect(x.runtime,x.geometry)))
