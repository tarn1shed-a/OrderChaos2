"""Append the verified tutorial material-group DTO without replacing old files."""
import argparse
import copy
import gzip
import io
import json
import tarfile
from pathlib import Path
from creation_preview_delivery import ROOT, sha, encoded, safe_members
from runtime_delta import inspect

BASE = ROOT/'analysis/raw/selection-stage-release-20261115/complete-v3.tar.gz'
BASE_SHA = '94a42293c46b0ce9bef15a45b84bd8ad1c5a01ab389f5f303693e836cffcbe53'
APPEND = ROOT/'analysis/raw/tutorial-terrain-grouping-20261115/v2/tutorial-terrain-groups-append-v1.tar.gz'
APPEND_SHA = 'f704d7fad8ff998574d077a83a874262527f6a0e8ec67564622c2dacf5fe6379'
MEMBER = 'assets/source-tutorial-terrain-groups/overlay.json'
PAYLOAD_SHA = 'f83b00a3aadeea233f0e86a9ad0a05c1475a2ecc61052be8dab403cc59822ec0'


def validate_profile(p):
    if (p.get('format') != 'oc2-tutorial-terrain-native-material-groups-v2'
            or p.get('world') != 'tutorial' or p.get('mapId') != 5
            or p.get('profile') != 'APK_Default'
            or [p.get(k) for k in ('changedChunks', 'changedDry', 'changedWet')] != [2178, 1789, 389]
            or any(p.get(k) is not False for k in ('sourceGeometryChanged', 'sourceLightingChanged', 'savesChanged'))
            or not p.get('source35127cMaterialTransfer')
            or p.get('copyEvidence', {}).get('fullOriginal35127cExecuted') is not True
            or p.get('copyEvidence', {}).get('memberIndexFieldsUnchanged') is not True
            or sum(len(t['chunks']) for t in p.get('tiles', [])) != 2178):
        raise ValueError('Verified original tutorial material transfer required')


def package(output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists():
        raise ValueError('Fresh ignored release output required')
    if sha(BASE.read_bytes()) != BASE_SHA or sha(APPEND.read_bytes()) != APPEND_SHA:
        raise ValueError('Frozen original runtime or append differs')
    original, _ = inspect(BASE)
    files = safe_members(BASE); files.pop('bundle-manifest.json')
    members = safe_members(APPEND)
    assets = {k: v for k, v in members.items() if k.startswith('assets/')}
    if set(assets) != {MEMBER} or sha(assets[MEMBER]) != PAYLOAD_SHA:
        raise ValueError('Only the reviewed material-group DTO may be appended')
    validate_profile(json.loads(assets[MEMBER]))
    added = {'game-data/converted/'+MEMBER.removeprefix('assets/'): assets[MEMBER]}
    if set(added) & set(files): raise ValueError('Existing runtime member cannot be replaced')
    files.update(added); manifest = copy.deepcopy(original)
    manifest['files'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(files.items())}
    manifest['tutorialRepresentativeMaterials'] = {
        'baseArchiveSHA256': BASE_SHA, 'appendArchiveSHA256': APPEND_SHA,
        'sourceGroupRepresentativeCopies': True, 'existingMembersPreserved': len(original['files']),
        'addedFiles': 1, 'materialBindingsChanged': 2178, 'geometryChanged': False,
        'lightingChanged': False, 'physicsChanged': False, 'localSavesImported': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name, raw in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
                m = tarfile.TarInfo(name); m.size = len(raw); m.mode = 0o600
                archive.addfile(m, io.BytesIO(raw))
    output.chmod(0o600); inspect(output)
    receipt = {'archive': str(output), 'sha256': sha(output.read_bytes()), 'bytes': output.stat().st_size,
               'files': len(files), **manifest['tutorialRepresentativeMaterials']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    print(json.dumps(package(p.parse_args().output)))
