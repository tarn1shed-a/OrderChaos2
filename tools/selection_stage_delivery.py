"""Append verified map7 scene parts to the existing private creation runtime.

Never replaces an old member, changes the reviewed world/physics host, or packs
saves, full source tables, disassembly, screenshots or development review pages.
"""
import argparse
import copy
import gzip
import io
import json
import tarfile
from pathlib import Path
from creation_preview_delivery import ROOT, sha, encoded, safe_members
from runtime_delta import inspect

BASE = ROOT/'analysis/raw/creation-stage-transform-20261115/creation-preview-complete-v1.tar.gz'
BASE_SHA = 'a12ecf665d2776e0140367b013dd5cefc3bae8c60cf75d85a48eac53eb899af9'
FORMAT = 'oc2-source-creation-preview-delivery-v2'
MODULES = {
    'selection_scene_water_material.js': '10e6bf11369242793d77c282c83edaa588b70616ed2a423399f3310cf479e737',
    'selection_scene_flowers_material.js': 'f5a64b8309cfcfd6810f83cc725f188d0f12093761cd07d6dc30675919831a27',
    'selection_scene_grass_material.js': '4c773efaf9d750a43fc047e22abc3674361bdae2a1bc8929a8bebd6969744354',
    'selection_scene_waterfalls_material.js': 'fb7a504a4f7bdb2b2624043cb6b6211d3b8a9e15f3345133626335a1c7b80fdd',
    'selection_scene_water_surface.js': '711b237f573334989d2ca8f5f84f98001d241130ddf20591399bc8f958aaac41',
    'selection_scene_water_floor.js': 'ddfdd48ed8e4d4725f489ea22a61bac15dc2bb777b0406ac479832251b1c173e',
}
PACKS = [
    ('dry', 'selection-scene-water-20261115/selection-water-dry-append-v1.tar.gz',
     '1c025d2004195546b28d091bbe96d102fd41cc988ce45a0f9be9688a595ddad1',
     1, 'source-selection-water', 'selection_scene_water_material.js'),
    ('flowers', 'selection-scene-flowers-20261115/selection-flowers-append-v1.tar.gz',
     'cbd5ac5b262deafd52c82ed450caf5e2640e66281e2b76d9f1f15a96a591dcdb',
     3, 'source-selection-flowers', 'selection_scene_flowers_material.js'),
    ('grass', 'selection-scene-grass-20261115/selection-grass-append-v1.tar.gz',
     '79f5ff2295b1129804bc7f54fdc875a9ae7aa64ad80a022558fa61096ad714d4',
     2, 'source-selection-grass', 'selection_scene_grass_material.js'),
    ('waterfalls', 'selection-scene-waterfalls-20261115/selection-waterfalls-append-v1.tar.gz',
     '3029fc53fe082bb3433b1fead7afc92eaa6087f8af2cbcc3d66e737b4bcbf84f',
     9, 'source-selection-waterfalls', 'selection_scene_waterfalls_material.js'),
    ('waterSurface', 'selection-scene-water-20261115/selection-water-surface-append-v1.tar.gz',
     '02d113f2ac803f8ab3a76c599f36624c741065bc15dfc7396aa10afc671acc31',
     26, 'source-selection-water-surface', 'selection_scene_water_surface.js'),
    ('wetFloor', 'selection-scene-water-20261115/selection-water-floor-append-v1.tar.gz',
     'ce05105d16381bdd06933508b1d2459d4b2e297f6558419abb0bd1fbe45e2265',
     6, 'source-selection-water-floor', 'selection_scene_water_floor.js'),
]


def additions(previous):
    result, extensions = {}, []
    for kind, name, expected, count, namespace, module in PACKS:
        archive = ROOT/'analysis/raw'/name
        if sha(archive.read_bytes()) != expected:
            raise ValueError('Frozen original selection append differs: '+kind)
        members = safe_members(archive)
        assets = {k: v for k, v in members.items() if k.startswith('assets/')}
        if len(assets) != count or not all(k.startswith('assets/'+namespace+'/') for k in assets):
            raise ValueError('Selection append contains unrelated resources')
        for path, raw in assets.items():
            if path.endswith(('.so', '.tbl', '.c', '.html')) or '-private.json' in path:
                raise ValueError('Non-runtime source data cannot be publicly served')
            key = 'game-data/converted/'+path.removeprefix('assets/')
            if key in result:
                raise ValueError('Duplicate selection append member')
            result[key] = raw
        module_key = 'prototype/public/'+module
        module_raw = (ROOT/'tools/preview'/module).read_bytes()
        if sha(module_raw) != MODULES[module]:
            raise ValueError('Frozen candidate renderer source differs')
        result[module_key] = module_raw
        extensions.append({'kind': kind, 'url': '/assets/'+namespace+'/overlay.json'})
    old = json.loads(previous['game-data/converted/source-creation-stage/manifest.json'])
    if old['format'] != 'oc2-source-creation-preview-delivery-v1':
        raise ValueError('Original stage predecessor differs')
    profile = {**old, 'format': FORMAT, 'extensions': extensions,
               'originalStaticInstances': 151, 'originalDryChunks': 192,
               'originalWaterSurfaceChunks': 152, 'originalWetFloorRestored': True}
    result['game-data/converted/source-creation-stage/manifest-v2.json'] = encoded(profile)
    if set(previous) & set(result):
        raise ValueError('Scene append cannot overwrite an existing runtime file')
    return result


def package(output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists():
        raise ValueError('Fresh ignored release output required')
    if sha(BASE.read_bytes()) != BASE_SHA:
        raise ValueError('Current complete private runtime differs')
    original, _ = inspect(BASE)
    files = safe_members(BASE)
    files.pop('bundle-manifest.json')
    added = additions(files)
    files.update(added)
    manifest = copy.deepcopy(original)
    manifest['files'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(files.items())}
    manifest['selectionStageExtensions'] = {
        'format': FORMAT, 'baseArchiveSHA256': BASE_SHA, 'existingMembersPreserved': len(original['files']),
        'addedFiles': len(added), 'originalStaticInstances': 151, 'originalDryChunks': 192,
        'originalWaterSurfaceChunks': 152, 'wetFloorRestored': True,
        'stages': ['CharacterChooseRace'], 'playableRacesChanged': False, 'localSavesImported': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name, raw in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
                m = tarfile.TarInfo(name); m.size = len(raw); m.mode = 0o600
                archive.addfile(m, io.BytesIO(raw))
    output.chmod(0o600)
    inspect(output)
    receipt = {'archive': str(output), 'sha256': sha(output.read_bytes()), 'bytes': output.stat().st_size,
               'files': len(files), 'localSavesImported': False, **manifest['selectionStageExtensions']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.output)))
