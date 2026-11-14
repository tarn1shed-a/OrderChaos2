"""Versioned append for the original selection material-group copy correction.

The initial v2 and all its resources are retained as evidence. A new v3 profile
routes the existing floor constructor to a separately verified native-copy DTO.
"""
import argparse
import copy
import gzip
import io
import json
import re
import tarfile
from pathlib import Path
from creation_preview_delivery import ROOT, sha, encoded, safe_members
from runtime_delta import inspect

BASE = ROOT/'analysis/raw/selection-stage-release-20261115/complete-v2.tar.gz'
BASE_SHA = '38b1a3b0c7b68fc7adb74325f927490b130f46b70e74960e826f83c71c97cfe5'
FORMAT = 'oc2-source-creation-preview-delivery-v3'
PROFILE = 'game-data/converted/source-creation-stage/manifest-v3.json'
OVERLAY = 'assets/source-selection-water-floor-groups/overlay.json'


def revised_stage(old):
    if (old.get('format') != 'oc2-source-creation-preview-delivery-v2'
            or old.get('mapId') != 7 or old.get('createsPlayableRole') is not False
            or [e['kind'] for e in old.get('extensions', [])] !=
               ['dry', 'flowers', 'grass', 'waterfalls', 'waterSurface', 'wetFloor']):
        raise ValueError('Verified previous selection profile required')
    result = copy.deepcopy(old)
    result['format'] = FORMAT
    result['originalGroupRepresentativeMaterialCopies'] = True
    result['extensions'][-1]['url'] = '/'+OVERLAY
    return result


def package(append, expected_sha, output):
    append, output = Path(append).resolve(), Path(output).resolve()
    if (not output.is_relative_to(ROOT/'analysis/raw') or output.exists()
            or not append.is_relative_to(ROOT/'analysis/raw') or not re.fullmatch('[0-9a-f]{64}', expected_sha)):
        raise ValueError('Explicit frozen private append and new ignored output required')
    if sha(BASE.read_bytes()) != BASE_SHA or sha(append.read_bytes()) != expected_sha:
        raise ValueError('Frozen source archive differs')
    original, _ = inspect(BASE)
    files = safe_members(BASE); files.pop('bundle-manifest.json')
    members = safe_members(append)
    assets = {k: v for k, v in members.items() if k.startswith('assets/')}
    if set(assets) != {OVERLAY}:
        raise ValueError('Material copy correction must not replace shader/art/geometry')
    floor = json.loads(assets[OVERLAY])
    if (floor.get('world') != 'selection' or floor.get('mapId') != 7
            or floor.get('nativeFinalLayerGroups') is not True
            or floor.get('nativeGroupRepresentativeMaterials') is not True
            or floor.get('priorFloorV4SHA256') != sha(files['game-data/converted/source-selection-water-floor/overlay.json'])
            or [(r['tile'], r['chunk'], r['representativeChunk']) for r in floor.get('correctedMaterialGroups', [])] !=
               [([-39, -3], [3, 2], [2, 2]), ([-39, -3], [4, 2], [2, 2]), ([-40, -2], [0, 1], [0, 0])]):
        raise ValueError('Original selection group correction missing')
    added = {'game-data/converted/'+OVERLAY.removeprefix('assets/'): assets[OVERLAY],
             PROFILE: encoded(revised_stage(json.loads(files['game-data/converted/source-creation-stage/manifest-v2.json'])))}
    if set(added) & set(files):
        raise ValueError('Existing runtime member cannot be replaced')
    files.update(added); manifest = copy.deepcopy(original)
    manifest['files'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(files.items())}
    manifest['selectionGroupMaterialCorrection'] = {
        'format': FORMAT, 'baseArchiveSHA256': BASE_SHA, 'appendSHA256': expected_sha,
        'sourceGroupRepresentativeCopies': True, 'existingMembersPreserved': len(original['files']),
        'addedFiles': 2, 'originalStaticInstances': 151, 'localSavesImported': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name, raw in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
                m = tarfile.TarInfo(name); m.size = len(raw); m.mode = 0o600
                archive.addfile(m, io.BytesIO(raw))
    output.chmod(0o600); inspect(output)
    receipt = {'archive': str(output), 'sha256': sha(output.read_bytes()), 'bytes': output.stat().st_size,
               'files': len(files), 'localSavesImported': False, **manifest['selectionGroupMaterialCorrection']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--append', type=Path, required=True)
    p.add_argument('--append-sha', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); print(json.dumps(package(a.append, a.append_sha, a.output)))
