"""Create a checksummed private migration archive, without copying any save.

Only reviewed runtime text, the converted asset tree and explicitly referenced
original collision inputs are allowed. Existing runtime/configs remain untouched.
"""
import argparse
import ast
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'analysis/raw/showcase-20261110/running-preview'
CONTAINER = Path('/opt/oc2')
DEST = CONTAINER / 'analysis/raw/portable/running-preview'
INPUT_KEYS = ('terrain', 'collision', 'terrainLighting', 'swimming', 'diving',
              'animationBlending', 'stopQueue', 'layerQueue')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def python_closure():
    pending, found = ['source_physics_worker'], set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        file = ROOT / 'tools' / (name + '.py')
        if not file.is_file():
            continue
        found.add(name)
        for node in ast.walk(ast.parse(file.read_text())):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for module in modules:
                base = module.split('.')[0]
                if (ROOT / 'tools' / (base + '.py')).is_file():
                    pending.append(base)
    return sorted('tools/' + name + '.py' for name in found)


def payload(entry_assets=None):
    identity = json.loads((ROOT / 'tools/local_mvp_runtime.json').read_text())
    files = {}

    def add(name, raw):
        if name in files:
            raise ValueError('Duplicate migration path: ' + name)
        files[name] = raw

    for name, expected in identity['files'].items():
        file = RUNTIME / name
        if not file.is_relative_to(RUNTIME) or file.is_symlink():
            raise ValueError('Unsafe reviewed runtime path')
        raw = file.read_bytes()
        if digest(raw) != expected:
            raise ValueError('Unreviewed runtime change: ' + name)
        add(name, raw)
    converted = RUNTIME / 'game-data/converted'
    for file in sorted(converted.rglob('*')):
        if file.is_symlink():
            raise ValueError('Converted assets cannot contain symlinks')
        if file.is_file():
            add(file.relative_to(RUNTIME).as_posix(), file.read_bytes())
    if entry_assets is not None:
        overlay=Path(entry_assets).resolve()
        if not any(overlay.is_relative_to(ROOT/p)for p in ['analysis/raw','game-data','backups']):
            raise ValueError('Recovered entry assets must come from an ignored folder')
        proof=json.loads((overlay/'entry.json').read_text())
        if proof.get('format')!='oc2-source-entry-ui-v1':raise ValueError('Unknown recovered entry profile')
        expected={'entry.json',*(v['url'].rsplit('/',1)[-1]for v in proof['windows'].values()),*(v['url'].rsplit('/',1)[-1]for v in proof['assets'].values())}
        if {p.name for p in overlay.iterdir()}!=expected:raise ValueError('Unlisted entry asset or missing drawing')
        for file in sorted(overlay.iterdir()):
            if file.is_symlink()or not file.is_file()or file.suffix not in ('.json','.svg','.png'):raise ValueError('Unsafe entry asset')
            add('game-data/converted/source-entry/'+file.name,file.read_bytes())
    config = json.loads((RUNTIME / 'prototype/native-physics.json').read_text())
    if config['nativeSHA256'] != identity['nativeSHA256']:
        raise ValueError('Original native identity differs')
    raw = Path(config['library']).read_bytes()
    if digest(raw) != identity['nativeSHA256']:
        raise ValueError('Original library differs')
    add('native-inputs/library.so', raw)
    config['library'] = str(DEST / 'native-inputs/library.so')
    for key in INPUT_KEYS:
        name = 'native-inputs/' + key + '.json'
        add(name, Path(config[key]).read_bytes())
        config[key] = str(DEST / name)
    for name, item in sorted(config['sourceFiles'].items()):
        raw = Path(item['path']).read_bytes()
        if digest(raw) != item['sha256']:
            raise ValueError('Original PHY differs: ' + name)
        target = 'native-inputs/phy/' + digest(raw) + '.phy'
        if target not in files:
            add(target, raw)
        item['path'] = str(DEST / target)
    config.update(python='/opt/venv/bin/python', worker=str(CONTAINER / 'tools/source_physics_worker.py'),
                  config=str(DEST / 'prototype/native-physics.json'))
    # sourceFiles is complete, so the unused original full archive path is removed.
    config.pop('source', None)
    add('prototype/native-physics.json', json.dumps(config, sort_keys=True, indent=2).encode())
    python_files = {name: digest((ROOT / name).read_bytes()) for name in python_closure()}
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines())
    if not set(python_files).issubset(tracked):
        raise ValueError('A physics dependency is not a reviewed tracked source')
    manifest = {'format': 'oc2-private-runtime-v1', 'runtimeIdentity': identity,
                'pythonFiles': python_files, 'localSavesImported': False,
                'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'files': {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in sorted(files.items())}}
    return files, manifest


def package(output,entry_assets=None):
    output = Path(output).resolve()
    if not any(output.is_relative_to(ROOT / name) for name in ['backups', 'analysis/raw']):
        raise ValueError('Migration archives must stay in ignored backups/ or analysis/raw/')
    if output.exists():
        raise ValueError('Preserve existing migration archives; choose a new filename')
    files, manifest = payload(entry_assets)
    files['bundle-manifest.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as archive:
        for name, raw in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(raw))
    output.chmod(0o600)
    receipt = {'archive': str(output), 'sha256': digest(output.read_bytes()), 'bytes': output.stat().st_size,
               'files': len(manifest['files']), 'expandedBytes': sum(v['bytes'] for v in manifest['files'].values()),
               'reviewedRuntimeFiles': len(manifest['runtimeIdentity']['files']), 'pythonModules': len(manifest['pythonFiles']),
               'localSavesImported': False}
    output.with_suffix(output.suffix + '.receipt.json').write_text(json.dumps(receipt, indent=2))
    return receipt


def build_context(archive, destination):
    """Allowlisted private Railway CLI context, never the repository root."""
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    if not destination.is_relative_to(ROOT / 'backups/deployment') or destination.exists():
        raise ValueError('Use a new ignored backups/deployment/ context directory')
    receipt = json.loads(archive.with_suffix(archive.suffix + '.receipt.json').read_text())
    if digest(archive.read_bytes()) != receipt['sha256']:
        raise ValueError('Migration archive differs from its receipt')
    with tarfile.open(archive, 'r:gz') as packed:
        manifest = json.load(packed.extractfile('bundle-manifest.json'))
    sources = ['Dockerfile', '.dockerignore', '.railway/railway.ts',
               'tools/local_mvp_runtime.json', 'tools/requirements-native.txt', 'tools/requirements-resources.txt',
               'deploy/bootstrap.py', 'deploy/server.mjs', 'deploy/package.json', 'deploy/package-lock.json',
               'deploy/acceptance.mjs', 'deploy/physics_acceptance.py', 'tools/preview/map-runtime-inside-overlay.mjs', *python_closure()]
    sources += ['deploy/prepare_delivery.mjs', 'deploy/static_delivery.mjs',
                'deploy/delivery_boot.mjs', 'deploy/delivery_worker.mjs', 'deploy/delivery_audit.mjs',
                'deploy/stage_runtime.mjs', 'deploy/stage_plan.mjs', 'deploy/staged_scene.mjs', 'deploy/streaming_window.mjs']
    # Presentation host modules are versioned with the image, separate from the
    # unchanged private archive's physics-host hash set.
    sources += ['tools/head_name_evidence.py','tools/native_font_draw.py','tools/source_name_worker.py']
    sources=sorted(set(sources)|{'deploy/'+p.name for p in (ROOT/'deploy').iterdir()if p.is_file()and p.suffix in ('.mjs','.css')}|{'deploy/admin.html','deploy/admin.js'})
    if manifest['pythonFiles'] != {name: digest((ROOT / name).read_bytes()) for name in python_closure()}:
        raise ValueError('Physics host modules changed since packing')
    destination.mkdir(parents=True, mode=0o700)
    for name in sources:
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, output)
    shutil.copyfile(archive, destination / 'deploy/private-runtime.tar.gz')
    (destination / 'deploy/private-runtime.tar.gz').chmod(0o600)
    return {'context': str(destination), 'bundleSHA256': receipt['sha256'], 'privateBundleIncluded': True,
            'sourceFiles': len(sources), 'localSavesImported': False,
            'fileSHA256': {name: digest((destination / name).read_bytes()) for name in sources}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'backups/deployment/oc2-runtime-20261113.tar.gz')
    parser.add_argument('--context', type=Path, help='Prepare a private CLI build context from the existing archive')
    parser.add_argument('--entry-assets', type=Path, help='Append a verified recovered entry overlay without changing the existing runtime')
    args = parser.parse_args()
    if args.context:
        result = build_context(args.output, args.context)
        args.context.with_suffix('.receipt.json').write_text(json.dumps(result, indent=2))
    else:
        result = package(args.output,args.entry_assets)
    print(json.dumps(result, indent=2))
