"""Build a private joint native-queue viewer; never a production game page."""
import json
import shutil
from pathlib import Path
from species_world_profiles import ROOT, CANDIDATES


def build(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'analysis/raw'):
        raise ValueError('Fresh ignored research output required')
    output.mkdir(parents=True)
    raw = ROOT/'analysis/raw/species-world-router-20261115'
    for name in ('profiles-v1.json', 'native-roundtrip-v1.json'):
        shutil.copyfile(raw/name, output/name)
    for key, folder in CANDIDATES.items():
        original = ROOT/'analysis/raw'/folder
        target = output/key
        target.mkdir()
        manifest = json.loads((original/'manifest.json').read_text())
        names = {'manifest.json', manifest['model'].lstrip('/')}
        names.update(url.lstrip('/') for row in manifest['materials'] for url in row['samplers'].values())
        if key == 'human-male':
            names.update({'three.module.js', 'three.core.js', 'source-npc-material.js'})
            shutil.copytree(original/'world-runtime', output/'world-runtime')
        for name in sorted(names):
            dest = target/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original/name, dest)
    for name in ('character_world_motion_avatar.mjs', 'character_human_world_avatar.mjs',
                 'character_human_female_world_avatar.mjs', 'character_elf_male_world_avatar.mjs',
                 'species_world_motion.mjs', 'species_world_motion_review.mjs'):
        shutil.copyfile(ROOT/'tools/preview'/name, output/name)
    (output/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>原模型动作队列联合验收 · 开发资料</title><style>
html,body{margin:0;height:100%;background:#14191d;color:#e5e7e6;font:15px system-ui}canvas{width:100%;height:100%;display:block}
aside{position:absolute;top:20px;left:24px;max-width:620px;pointer-events:none}p{line-height:1.6}nav{position:absolute;bottom:20px;left:24px}button{padding:8px 18px;margin-right:12px}
</style><canvas></canvas><aside><h2>原模型 · 各自的动作队列</h2>
<p>左：人类男性　中：人类女性　右：精灵男性<br>实际重放原 CPU 的跑动、停步、再跑动记录。<br>这是开发验收；固定审阅光照与相机，不是正式游戏界面。</p><p id="status">准备中</p></aside>
<nav><button id="play" disabled>暂停重放</button><button id="stop" disabled>查看停步差异</button><button id="resume" disabled>查看再移动</button></nav>
<script type="module" src="/species_world_motion_review.mjs"></script></html>''')
    return {'researchOnly': True, 'productionEntryChanged': False, 'files': sum(p.is_file() for p in output.rglob('*'))}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    print(json.dumps(build(p.parse_args().output)))
