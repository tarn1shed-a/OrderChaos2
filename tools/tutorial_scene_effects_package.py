"""Check and bundle the isolated source fire/smoke candidate, never production."""
import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, FORMAT, FOCUS, output_path


def checked_candidate(candidate):
    candidate = Path(candidate).resolve()
    if not candidate.is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Original effect assets must remain private')
    audit = json.loads((candidate/'audit.json').read_text())
    manifest = json.loads((candidate/'manifest.json').read_text())
    if (manifest.get('format') != FORMAT or manifest.get('source') != FOCUS or
            manifest.get('placementCount') != 43 or manifest.get('insertIntoDefaultScene') is not False or
            manifest.get('automaticRestart') is not False or manifest.get('wholeMapAccepted') is not False):
        raise ValueError('Only the explicitly conditional source candidate')
    for name, digest in audit['files'].items():
        if Path(name).name != name or hashlib.sha256((candidate/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Candidate checksum differs: '+name)
    runtime = [manifest['effect'], manifest['placements'], 'manifest.json']
    runtime.extend(row['file'] for row in manifest['textures'].values())
    if len(runtime) != 6 or len(set(runtime)) != 6 or any(Path(n).name != n for n in runtime):
        raise ValueError('Unexpected runtime payload')
    if any(n not in audit['files'] for n in runtime):
        raise ValueError('Unverified runtime payload')
    return candidate, manifest, runtime


def package(candidate, destination):
    candidate, _, runtime = checked_candidate(candidate)
    destination = output_path(destination)
    payload = {'public/source-scene-effects/'+name: (candidate/name).read_bytes() for name in runtime}
    payload['public/source-scene-effect-preview.js'] = (ROOT/'tools/preview/source-scene-effect-preview.js').read_bytes()
    payload['private-evidence/audit.json'] = (candidate/'audit.json').read_bytes()
    checksums = {name: hashlib.sha256(raw).hexdigest() for name, raw in payload.items()}
    index = {'format': FORMAT, 'files': checksums, 'resourceGroupsInventoried': 14,
        'placementsInventoried': 92, 'conditionalCandidatePlacements': 43,
        'automaticDefaultSceneInsertion': False, 'productionDeployIncluded': False,
        'wholeMapAccepted': False,
        'runtimeDependencies': ['particle-renderer.js', 'particle-simulation.js', 'procedural-effects.js'],
        'limits': ['Private evidence must not be served as game UI.',
            'Host must supply reviewed admitted tiles, camera, decoded maps and an explicit elapsed clock.',
            'No original engine resource callback, RNG stream, audio or full distance manager is claimed.']}
    payload['package.json'] = (json.dumps(index, ensure_ascii=False, indent=2)+'\n').encode()
    destination.mkdir(parents=True)
    archive = destination/'tutorial-scene-fire-smoke.tar'
    with tarfile.open(archive, 'w') as tar:
        for name, raw in sorted(payload.items()):
            item = tarfile.TarInfo(name); item.size = len(raw); item.mode = 0o644; item.mtime = 0
            tar.addfile(item, io.BytesIO(raw))
    proof = {'archive': archive.name, 'bytes': archive.stat().st_size,
        'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': checksums,
        'packageIndexSHA256': hashlib.sha256(payload['package.json']).hexdigest()}
    (destination/'sha256.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--candidate', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    print(json.dumps(package(args.candidate, args.output), ensure_ascii=False))
