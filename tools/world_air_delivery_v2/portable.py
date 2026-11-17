"""Path projection only for the frozen shared own-air loaders.

The immutable recipe includes explicit isolated source context. It is not an
original server default and this module neither advances an actor nor grants
world/creation readiness. Install under tools/world_air_delivery_v2/.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'analysis/raw/portable/running-preview'
PREFIX = 'native-inputs/world-own-air-v2/'
PLAN = PREFIX + 'projection.json'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(name, root=RUNTIME):
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Private relative projected path required')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Projection escapes its private root')
    return path


def read_plan():
    plan = json.loads(inside(PLAN).read_text())
    if plan.get('format') != 'oc2-world-own-air-path-projection-v1':
        raise ValueError('Reviewed own-air path projection required')
    return plan


def project(recipe, plan, python, key, entry_key):
    paths = {row['original']: str(inside(row['target'])) for row in plan['resources']}

    def walk(value):
        if isinstance(value, str):
            return paths.get(value, value)
        if isinstance(value, list):
            return [walk(x) for x in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    result = walk(recipe)
    # Historical self-path/interpreter/worker are transport locations only.
    for name, value in (
        ('config', str(inside(PREFIX + 'derived/' + entry_key + '/' + key + '.json'))),
        ('python', python),
        ('worker', str(inside(plan['entries'][entry_key]['workerTarget'], ROOT))),
    ):
        if name in result:
            result[name] = value
    return result


def validate_sources(plan):
    seen = set()
    for row in plan['resources']:
        if row['original'] in seen or sha(inside(row['target'])) != row['sha256']:
            raise ValueError('Immutable own resource or unique source mapping differs')
        seen.add(row['original'])
    for name, row in plan['code'].items():
        if sha(inside(name, ROOT)) != row['sha256']:
            raise ValueError('Pinned common loader code differs: ' + name)
    for row in plan['bodies'].values():
        if sha(inside(row['recipe'])) != row['recipeSHA256']:
            raise ValueError('Frozen own body recipe differs')
    workers = set()
    for entry in plan.get('entries', {}).values():
        if entry['workerTarget'] in workers or entry.get('export') != 'start':
            raise ValueError('Unique explicit frozen start entries required')
        workers.add(entry['workerTarget'])
        expected_module = 'tools/' + entry['module'].replace('.', '/') + '.py'
        if entry['modulePin']['path'] != expected_module or expected_module not in plan['code'] or sha(inside(expected_module, ROOT)) != entry['modulePin']['sha256']:
            raise ValueError('Frozen runtime module/code identity differs')
    # Preserve this original fixed reader, rather than changing its algorithm.
    fixed = plan['fixedModelPathIndex']
    if sha(inside(fixed['target'], ROOT)) != fixed['sha256']:
        raise ValueError('Original fixed body model-path index differs')


def materialize(python, keys, entry_key):
    plan = read_plan()
    if entry_key not in plan.get('entries', {}):
        raise ValueError('Explicit frozen runtime entry required; no default startup')
    if not isinstance(python, str) or not Path(python).is_absolute():
        raise ValueError('Actual interpreter path required')
    if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys) or any(k not in plan['bodies'] or not plan['bodies'][k]['nativePortableEligible'] for k in keys):
        raise ValueError('Explicit unique supported body subset required; no default prewarm')
    validate_sources(plan)
    bodies = {}
    for key in keys:
        row = plan['bodies'][key]
        recipe = json.loads(inside(row['recipe']).read_text())
        path = inside(PREFIX + 'derived/' + entry_key + '/' + key + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        value = encoded(project(recipe, plan, python, key, entry_key))
        if path.exists() and path.read_bytes() != value:
            raise ValueError('Existing derived config differs; choose a fresh private root')
        path.write_bytes(value)
        bodies[key] = {'path': str(path), 'sha256': sha(path)}
    path = inside(PREFIX + 'derived/' + entry_key + '/rpc-' + '-'.join(keys) + '.json')
    result = {'format': 'oc2-shared-own-air-rpc-v1', 'bodies': bodies,
              'python': python, 'worker': str(inside(plan['entries'][entry_key]['workerTarget'], ROOT)), 'config': str(path)}
    value = encoded(result)
    if path.exists() and path.read_bytes() != value:
        raise ValueError('Existing derived RPC differs')
    path.write_bytes(value)
    return path


def validate_config(config):
    plan = read_plan()
    validate_sources(plan)
    path = Path(config).resolve()
    if not path.is_relative_to(inside(PREFIX + 'derived')):
        raise ValueError('Only explicit new derived RPC configurations are accepted')
    cfg = json.loads(path.read_text())
    if set(cfg) != {'format', 'bodies', 'python', 'worker', 'config'} or cfg['format'] != 'oc2-shared-own-air-rpc-v1' or not cfg['bodies']:
        raise ValueError('Exact projected RPC envelope required')
    entry_key = next((key for key, entry in plan.get('entries', {}).items() if cfg['worker'] == str(inside(entry['workerTarget'], ROOT))), None)
    if entry_key is None or cfg['config'] != str(path) or not Path(cfg['python']).is_absolute():
        raise ValueError('Actual projected transport locations required')
    for key, pin in cfg['bodies'].items():
        if key not in plan['bodies'] or not plan['bodies'][key]['nativePortableEligible'] or set(pin) != {'path', 'sha256'}:
            raise ValueError('Unknown own body recipe')
        expected_path = inside(PREFIX + 'derived/' + entry_key + '/' + key + '.json')
        if pin['path'] != str(expected_path) or sha(expected_path) != pin['sha256']:
            raise ValueError('Derived own config path/hash differs')
        recipe = json.loads(inside(plan['bodies'][key]['recipe']).read_text())
        actual = json.loads(expected_path.read_text())
        if actual != project(recipe, plan, cfg['python'], key, entry_key):
            raise ValueError('Own source context or data changed beyond path projection')
        def pinned_paths(value):
            if isinstance(value, dict):
                if 'path' in value and 'sha256' in value:
                    source = Path(value['path']).resolve()
                    if not source.is_relative_to(RUNTIME.resolve()) or sha(source) != value['sha256']:
                        raise ValueError('Pinned body input leaves the verified portable resource closure')
                for child in value.values():
                    pinned_paths(child)
            elif isinstance(value, list):
                for child in value:
                    pinned_paths(child)
        pinned_paths(actual)
    return cfg


def run(config, actual_worker):
    """Dispatch only to a frozen code-closure entry, never a user module path."""
    import importlib
    import importlib.util
    cfg = validate_config(config)
    if cfg['worker'] != str(Path(actual_worker).resolve()):
        raise ValueError('Actual child entry differs from projected worker')
    plan = read_plan()
    entry = next(row for row in plan['entries'].values() if str(inside(row['workerTarget'], ROOT)) == cfg['worker'])
    module_path = inside(entry['modulePin']['path'], ROOT)
    if sha(module_path) != entry['modulePin']['sha256']:
        raise ValueError('Frozen runtime start provider differs')
    spec = importlib.util.find_spec(entry['module'])
    if spec is None or spec.origin is None or Path(spec.origin).resolve() != module_path:
        raise ValueError('Runtime import would leave its exact pinned code closure')
    module = importlib.import_module(entry['module'])
    if Path(module.__file__).resolve() != module_path:
        raise ValueError('Loaded runtime module provenance differs')
    return getattr(module, entry['export'])(config)
