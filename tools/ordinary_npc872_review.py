"""Build the private NPC872 material/finite-idle browser review site."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/quest227-visual-review-20261116'
PROFILE_SHA = '12ee38a91f0d5659a528cd9ed1bdd0bd21dafa0f6ca54483bec6a6b91da43cbd'


def build(candidate, output):
    output = output.resolve()
    if not output.is_relative_to(AREA) or output.exists():
        raise ValueError('New owned ignored review output required')
    path = candidate / 'assets/source-ordinary-npc872/profile.json'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROFILE_SHA:
        raise ValueError('The reviewed original NPC872 profile changed')
    profile = json.loads(raw)
    if profile['entry'] != 872 or not profile['sourceAssetOnly'] or profile['actorGUID'] is not None:
        raise ValueError('Independent original NPC872 candidate required')
    shutil.copytree(candidate, output)
    three = ROOT / 'analysis/raw/tutorial-npc-soldiers-20261114/candidate-v3'
    for name in ('three.module.js', 'three.core.js'):
        shutil.copyfile(three / name, output / name)
    for name in ('source-npc-final-pair-material.js', 'source-npc-weapon-material.js', 'source-npc-material.js'):
        source = ROOT / 'tools/preview' / name
        if (output / name).exists() and (output / name).read_bytes() != source.read_bytes():
            raise ValueError('Different frozen material helper ' + name)
        shutil.copyfile(source, output / name)
    shutil.copyfile(ROOT / 'tools/preview/ordinary-npc872-review.mjs', output / 'review.mjs')
    (output / 'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>原NPC872资源核查</title><style>body{margin:0;background:#14191d;color:#ddd;font:14px system-ui}canvas{display:block}aside{position:fixed;left:18px;top:14px;max-width:500px}pre{white-space:pre-wrap}button{margin:4px;padding:8px;background:#24333b;color:white;border:1px solid #647078}</style><canvas></canvas><aside><h1>原NPC872 · 独立资源核查</h1><pre id="status">读取原资源</pre><div id="poses"></div><div id="views"></div></aside><script type="application/json" id="review-state">{}</script><script type="module" src="review.mjs"></script></html>')
    return {'entry': 872, 'sourceProfileSHA256': PROFILE_SHA, 'sourceAssetOnly': True}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.candidate, a.output)))
