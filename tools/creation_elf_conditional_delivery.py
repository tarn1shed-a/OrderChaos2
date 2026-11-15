"""Add exact conditional Elf2046 preview without replacing frozen eight bodies."""
import argparse
import copy
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'analysis/raw/creation-elf-conditional-20261115'
CANDIDATE = RAW/'candidate-v1/elf-male'
BASE_STATIC = ROOT/'analysis/raw/creation-race-preview-20261115/qa-static-eight-v2'
PROFILE_NAME = 'game-data/converted/source-creation-stage/manifest-conditional-v1.json'
PROFILE_URL = '/assets/source-creation-stage/manifest-conditional-v1.json'
CONTRACT_SHA = '51a825509778cec34f72369b3a57cb2cbcec2d5102954f2b5eb2b0ebc2c3dc3e'
MANIFEST_SHA = '0d307cf99c49c86877659ee395907d7649cad2eecc3edbbe2de49c26b036fa59'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()+b'\n'


def payload():
    original = json.loads((BASE_STATIC/'game-data/converted/source-creation-stage/manifest-races-v1.json').read_text())
    if (original['format'] != 'oc2-source-creation-preview-delivery-v4' or
            sorted(original['previews']) != ['0:0', '0:1', '1:0', '1:1', '2:1', '3:0', '3:1', '4:0'] or
            original['allNineRacePreviewsRestored'] is not False):
        raise ValueError('Exact frozen eight-body stage required')
    manifest_raw = (CANDIDATE/'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    if (sha(manifest_raw) != MANIFEST_SHA or manifest['creationPreviewAdmitted'] is not False or
            manifest['appearanceComplete'] is not False or not manifest['hostConditionalDisplay'] or
            manifest['retainedSourceMaterial']['contractSHA256'] != CONTRACT_SHA):
        raise ValueError('Exact source-only conditional candidate required')
    checks = json.loads((CANDIDATE/'package-files.json').read_text())['files']
    closure = {'manifest.json', manifest['model'].lstrip('/')}
    closure.update(p.lstrip('/') for m in manifest['materials'] for p in m['samplers'].values())
    files = {}
    for name in sorted(closure):
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
            raise ValueError('Unsafe conditional source resource')
        if name != 'manifest.json' and not name.startswith('assets/'):
            raise ValueError('Only runtime source model/image closure is permitted')
        raw = (CANDIDATE/name).read_bytes()
        if checks.get(name) != {'bytes': len(raw), 'sha256': sha(raw)}:
            raise ValueError('Frozen source candidate differs')
        files['game-data/converted/source-creation-elf-conditional-v1/'+name] = raw
    profile = copy.deepcopy(original)
    profile.update(format='oc2-source-creation-preview-delivery-v5', originalAndroidFinalAppearanceKnown=False,
        conditionalOriginalPreviews=[{'key': '2:0', 'contractSHA256': CONTRACT_SHA, 'appearanceComplete': False,
            'sourceRequestSucceeded': False, 'displayOnlyAfterHostReady': True}])
    profile['previews']['2:0'] = {'baseURL': '/assets/source-creation-elf-conditional-v1/'}
    profile['additionalOriginalPreviews'].append({'key': '2:0', 'bodyKey': 'elf-male', 'display': 2046, 'model': 33})
    profile['additionalOriginalPreviews'].sort(key=lambda row: row['key'])
    files[PROFILE_NAME] = encoded(profile)
    files['prototype/public/character_creation_race_preview_v2.mjs'] = (ROOT/'tools/preview/character_creation_preview_proposal.mjs').read_bytes()
    files['prototype/public/creation_elf_source_ready.mjs'] = (ROOT/'tools/preview/creation_elf_source_ready.mjs').read_bytes()
    if any((BASE_STATIC/name).exists() for name in files):
        raise ValueError('Append would replace an existing eight-body input')
    return files, profile


def package(output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists():
        raise ValueError('Use a new ignored conditional append')
    files, profile = payload()
    manifest = {'format': 'oc2-elf-conditional-preview-append-v1', 'profileURL': PROFILE_URL,
        'candidateManifestSHA256': MANIFEST_SHA, 'contractSHA256': CONTRACT_SHA,
        'files': {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(files.items())},
        'oldEightBodyInputsReplaced': False, 'oldPublicProposalReplaced': False,
        'allNineRacePreviewsRestored': False, 'appearanceComplete': False,
        'sourceGPUObserved': False, 'localSavesImported': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name, raw in sorted({**files, 'conditional-preview-append.json': encoded(manifest)}.items()):
                item = tarfile.TarInfo(name)
                item.size, item.mode = len(raw), 0o600
                archive.addfile(item, io.BytesIO(raw))
    output.chmod(0o600)
    receipt = {**manifest, 'archive': str(output), 'sha256': sha(output.read_bytes()), 'bytes': output.stat().st_size}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(receipt))
    return receipt


def prepare_qa(output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists():
        raise ValueError('Use a new ignored conditional QA root')
    files, profile = payload()
    shutil.copytree(BASE_STATIC, output)
    for name, raw in files.items():
        target = output/name
        if target.exists():
            raise ValueError('Conditional QA cannot replace the old eight-body files')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output/'qa-static.json').write_bytes(encoded({'format': 'oc2-original-race-preview-static-qa-v1',
        'profileURL': PROFILE_URL, 'additionalOriginalPreviews': profile['additionalOriginalPreviews'],
        'conditionalOriginalPreviews': profile['conditionalOriginalPreviews'],
        'eightBodyStaticSource': str(BASE_STATIC), 'originalEightBodyBytesPreserved': True,
        'savesImported': False, 'serverStarted': False}))
    return {'directory': str(output), 'profileURL': PROFILE_URL,
            'conditionalOriginalPreviews': profile['conditionalOriginalPreviews']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qa-static', action='store_true')
    args = parser.parse_args()
    result = prepare_qa(args.output) if args.qa_static else package(args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
