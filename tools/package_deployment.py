"""Create a checksummed private migration archive, without copying any save.

Only reviewed runtime text, the converted asset tree and explicitly referenced
original collision inputs are allowed. Existing runtime/configs remain untouched.
"""
import argparse
import ast
import gzip
import hashlib
import importlib.util
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


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def python_closure(entry='source_physics_worker'):
    pending, found = [entry], set()
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


def _runtime_transport():
    """Use the build helper's one strict portable declaration validator."""
    path = ROOT / 'deploy/runtime_transport.py'
    spec = importlib.util.spec_from_file_location('oc2_private_runtime_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_runtime_transport(archive, destination, transport_plan):
    """Replace only a context's checked duplicate gzip with full-XZ transport.

    The canonical archive is read-only. Build-time reconstruction uses the same
    helper/schema and leaves the existing bootstrap gzip path unchanged.
    """
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    plan_path = Path(transport_plan)
    if plan_path.is_symlink() or not plan_path.is_file():
        raise ValueError('Use a regular full-XZ declaration file')
    plan_path = plan_path.resolve()
    source = plan_path.with_name('private-runtime.tar.xz')
    if source.is_symlink() or not source.is_file():
        raise ValueError('Full-XZ input must be the declaration adjacent regular file')
    if not destination.is_relative_to(ROOT / 'backups/deployment') or not destination.is_dir():
        raise ValueError('Only an existing private deployment context can be transported')
    if archive.is_relative_to(destination) or not archive.is_file():
        raise ValueError('The canonical archive must remain outside the context')
    helper = _runtime_transport()
    plan = helper.read_plan(plan_path)
    raw_plan = plan_path.read_bytes()
    helper.verify_file(plan_path, {'sha256': digest(raw_plan), 'bytes': len(raw_plan)})
    helper.verify_file(archive, plan['canonicalGzip'])
    helper.verify_file(source, plan['xz'])
    deploy = destination / 'deploy'
    bundled, sidecar = deploy / 'private-runtime.tar.gz', deploy / 'private-runtime.sha256'
    if deploy.is_symlink() or bundled.is_symlink() or sidecar.is_symlink():
        raise ValueError('Private context transport targets must be regular files')
    helper.verify_file(bundled, plan['canonicalGzip'])
    old_sidecar = sidecar.read_bytes()
    if old_sidecar != (plan['canonicalGzip']['sha256'] + '  private-runtime.tar.gz\n').encode():
        raise ValueError('Context gzip sidecar differs from the canonical input')
    copied_helper = deploy / 'runtime_transport.py'
    if (not copied_helper.is_file() or copied_helper.is_symlink() or
            file_digest(copied_helper) != file_digest(ROOT / 'deploy/runtime_transport.py')):
        raise ValueError('Context transport helper differs from reviewed source')
    target, declaration = deploy / 'private-runtime.tar.xz', deploy / 'private-runtime.transport.json'
    temporary_sidecar = deploy / 'private-runtime.sha256.transport-new'
    if any(path.exists() or path.is_symlink() for path in (target, declaration, temporary_sidecar)):
        raise ValueError('Existing transport outputs are preserved')
    created, sidecar_changed = [], False
    result = {'format': 'oc2-private-runtime-xz-context-v1',
              'declarationSHA256': digest(raw_plan), 'canonicalGzip': plan['canonicalGzip'],
              'xz': plan['xz'], 'tar': plan['tar'], 'storedGzip': plan['storedGzip'],
              'canonicalArchiveWritten': False, 'duplicateContextGzipRemoved': True,
              'localSavesImported': False}
    try:
        with source.open('rb') as incoming, target.open('xb') as output:
            created.append(target)
            shutil.copyfileobj(incoming, output)
        target.chmod(0o600)
        helper.verify_file(target, plan['xz'])
        with declaration.open('xb') as output:
            created.append(declaration)
            output.write(raw_plan)
        declaration.chmod(0o600)
        with temporary_sidecar.open('xb') as output:
            created.append(temporary_sidecar)
            output.write((plan['storedGzip']['sha256'] + '  private-runtime.tar.gz\n').encode())
        temporary_sidecar.chmod(0o600)
        temporary_sidecar.replace(sidecar)
        sidecar_changed = True
        # Last operation: only the context duplicate is removed. The source
        # canonical gzip and its receipt are never opened for writing.
        bundled.unlink()
    except Exception:
        if sidecar_changed:
            sidecar.write_bytes(old_sidecar)
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return result


def build_context(archive, destination, transport_plan=None):
    """Allowlisted private Railway CLI context, never the repository root."""
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    if not destination.is_relative_to(ROOT / 'backups/deployment') or destination.exists():
        raise ValueError('Use a new ignored backups/deployment/ context directory')
    receipt = json.loads(archive.with_suffix(archive.suffix + '.receipt.json').read_text())
    if file_digest(archive) != receipt['sha256']:
        raise ValueError('Migration archive differs from its receipt')
    with tarfile.open(archive, 'r:gz') as packed:
        manifest = json.load(packed.extractfile('bundle-manifest.json'))
    sources = ['Dockerfile', '.dockerignore', '.railway/railway.ts',
               'tools/local_mvp_runtime.json', 'tools/requirements-native.txt', 'tools/requirements-resources.txt',
               'deploy/bootstrap.py', 'deploy/runtime_transport.py', 'deploy/server.mjs', 'deploy/package.json', 'deploy/package-lock.json',
               'deploy/acceptance.mjs', 'deploy/physics_acceptance.py', 'tools/preview/map-runtime-inside-overlay.mjs', 'tools/preview/character-panel-runtime-overlay.mjs', 'tools/preview/character-hotbar-overlay.mjs', 'tools/preview/source-scene-effect-overlay.mjs', 'tools/preview/source-scene-effect-fire10-overlay.mjs', 'deploy/character_hotbar.mjs', *python_closure()]
    sources += ['tools/preview/source-tutorial-sky-overlay.mjs']
    sources += ['tools/preview/tutorial_terrain_grouping_policy.js']
    sources += ['tools/preview/quest_journal_program.mjs','tools/preview/quest_journal_widgets.mjs']
    sources += ['tools/preview/'+name+'.mjs' for name in ['ordinary-quest461-gather','ordinary-quest461-gather-browser','ordinary-quest461-gather-pose','ordinary-quest461-gather-events','source-property-math-v1','source-world-layer-compose-v1','source-world-track-queue-v1','source-gather-controller-v1']]
    sources += ['tools/creation_class_stage/stage_switch.mjs','tools/creation_class_stage/actor_v2.mjs','tools/creation_class_stage/actor_v3.mjs','tools/creation_class_stage/material_v2.mjs']
    sources += ['tools/creation_class_stage/actor_v6.mjs', 'tools/creation_batch/geometry_core.mjs', 'tools/creation_batch/contracts.mjs', 'tools/creation_batch/stage_adapters_v1.mjs', 'tools/creation_batch/stage_adapter_core_v1.mjs', 'tools/creation_batch/stage_guard.mjs', 'tools/creation_batch/source_capabilities_v1.mjs']
    sources += ['tools/creation_batch/'+name+'.mjs' for name in ['stage_batch_guard', 'stage_adapters_all_v1', 'stage_adapters_v5', 'typed_armor_root']]
    sources += ['tools/creation_control/'+name+'.mjs' for name in ['source_pose_applier_v1','source_pose_writer_v1','legacy_actor_pose_v1']]
    sources += ['deploy/creation_control/race_actor_pose_v1.mjs']
    sources += ['deploy/world_admission/'+name+'.mjs' for name in ['contracts','pending','first_pose','gate','human_female']]
    sources += ['deploy/world_route/'+name+'.mjs' for name in ['assembly','route','eight_domain','selector']]
    # Optional original human composition code. Its private inputs/configuration
    # are not activated or appended to the unchanged base runtime archive.
    sources += python_closure('source_human_pose_worker')
    source_world = ROOT / 'tools/source_world_python.json'
    if source_world.exists():
        code = json.loads(source_world.read_text())
        if code.get('format') != 'oc2-source-world-python-closure-v1':
            raise ValueError('Unknown source-world Python closure')
        for name, expected in code['files'].items():
            path = Path(name)
            if (not name.startswith('tools/') or path.suffix != '.py' or
                    '..' in path.parts or path.is_absolute() or
                    file_digest(ROOT / path) != expected):
                raise ValueError('Unreviewed source-world Python input')
        sources += ['tools/source_world_python.json', *code['files']]
    sources += ['deploy/prepare_delivery.mjs', 'deploy/static_delivery.mjs',
                'deploy/delivery_boot.mjs', 'deploy/delivery_worker.mjs', 'deploy/delivery_audit.mjs',
                'deploy/stage_runtime.mjs', 'deploy/stage_plan.mjs', 'deploy/staged_scene.mjs', 'deploy/streaming_window.mjs']
    # Presentation host modules are versioned with the image, separate from the
    # unchanged private archive's physics-host hash set.
    sources += ['tools/head_name_evidence.py','tools/native_font_draw.py','tools/source_name_worker.py']
    sources=sorted(set(sources)|{'deploy/'+p.name for p in (ROOT/'deploy').iterdir()if p.is_file()and p.suffix in ('.mjs','.css')}|{'deploy/admin.html','deploy/admin.js'})
    if manifest['pythonFiles'] != {name: file_digest(ROOT / name) for name in python_closure()}:
        raise ValueError('Physics host modules changed since packing')
    destination.mkdir(parents=True, mode=0o700)
    for name in sources:
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, output)
    bundled = destination / 'deploy/private-runtime.tar.gz'
    shutil.copyfile(archive, bundled)
    bundled.chmod(0o600)
    if file_digest(bundled) != receipt['sha256']:
        raise ValueError('Copied private image archive differs from its receipt')
    # BuildKit must reject a corrupt COPY before a private image is published.
    (destination / 'deploy/private-runtime.sha256').write_text(receipt['sha256'] + '  private-runtime.tar.gz\n')
    result = {'context': str(destination), 'bundleSHA256': receipt['sha256'], 'privateBundleIncluded': True,
              'sourceFiles': len(sources), 'localSavesImported': False,
              'fileSHA256': {name: file_digest(destination / name) for name in sources}}
    if transport_plan is not None:
        transport = apply_runtime_transport(archive, destination, transport_plan)
        result.update(bundleSHA256=transport['storedGzip']['sha256'],
                      canonicalBundleSHA256=receipt['sha256'], archiveTransport=transport)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'backups/deployment/oc2-runtime-20261113.tar.gz')
    parser.add_argument('--context', type=Path, help='Prepare a private CLI build context from the existing archive')
    parser.add_argument('--entry-assets', type=Path, help='Append a verified recovered entry overlay without changing the existing runtime')
    parser.add_argument('--transport-plan', type=Path, help='Use the exact adjacent full-XZ declaration in a new CLI context')
    args = parser.parse_args()
    if args.transport_plan is not None and not args.context:
        parser.error('--transport-plan requires --context; existing archives are not repackaged')
    if args.context:
        result = build_context(args.output, args.context, args.transport_plan)
        args.context.with_suffix('.receipt.json').write_text(json.dumps(result, indent=2))
    else:
        result = package(args.output,args.entry_assets)
    print(json.dumps(result, indent=2))
