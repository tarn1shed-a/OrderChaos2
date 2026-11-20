"""Explicit readable-gather transport atop the frozen V2 path materializer.

Body recipes, source clocks, values, queue and normal worker code do not change.
This module never prepares an engine or grants world/collection readiness.
"""
import importlib
import importlib.util
import json
from pathlib import Path
from world_air_delivery_v2 import portable as base

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'analysis/raw/portable/running-preview'
PREFIX = 'native-inputs/world-gather-v1/'
PLAN = PREFIX + 'projection.json'


def read_plan():
    if base.ROOT.resolve() != ROOT.resolve() or base.RUNTIME.resolve() != RUNTIME.resolve():
        raise ValueError('Exact installed V2 path projection core required')
    plan = json.loads(base.inside(PLAN).read_text())
    if plan.get('format') != 'oc2-common-gather-readable-path-append-v1':
        raise ValueError('Explicit frozen readable-gather delivery required')
    entry = plan['entry']
    if entry.get('key') != 'common-eight-gather-reader' or entry.get('workerTarget') != 'tools/world_gather_delivery_v1/worker.py' or entry.get('module') != 'source_own_gather_runtime_v1.worker' or entry.get('export') != 'start' or entry['modulePin']['target'] != 'tools/source_own_gather_runtime_v1/worker.py':
        raise ValueError('Only the explicit pinned readonly source entry is supported')
    pin = plan['baseProjection']
    if pin['target'] != base.PLAN or base.sha(base.inside(pin['target'])) != pin['sha256']:
        raise ValueError('Frozen V2 recipes/code projection differs')
    for target, pin in plan['rootFiles'].items():
        if base.sha(base.inside(target, ROOT)) != pin['sha256']:
            raise ValueError('Pinned readable-gather import/support bytes differ: ' + target)
    return plan


def materialize(python, keys, entry_key):
    plan = read_plan()
    if entry_key != plan['entry']['key']:
        raise ValueError('Explicit readable-gather entry required; V2 remains its own default')
    legacy = base.materialize(python, keys, 'source-runtime')
    cfg = base.validate_config(legacy)
    folder = base.inside(PREFIX + 'derived/' + entry_key)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('rpc-' + '-'.join(keys) + '.json')
    projected = {**cfg, 'worker': str(base.inside(plan['entry']['workerTarget'], ROOT)), 'config': str(path)}
    raw = base.encoded(projected)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('Existing readable-gather transport differs')
    path.write_bytes(raw)
    return path


def validate_config(config):
    plan = read_plan()
    path = Path(config).resolve()
    if not path.is_relative_to(base.inside(PREFIX + 'derived/' + plan['entry']['key'])):
        raise ValueError('Only this explicit readable-gather derived transport is accepted')
    cfg = json.loads(path.read_text())
    if set(cfg) != {'format', 'bodies', 'python', 'worker', 'config'} or not isinstance(cfg['bodies'], dict) or not cfg['bodies']:
        raise ValueError('Exact original shared RPC envelope required')
    keys = list(cfg['bodies'])
    old = base.inside(base.PREFIX + 'derived/source-runtime/rpc-' + '-'.join(keys) + '.json')
    expected = base.validate_config(old)
    expected = {**expected, 'worker': str(base.inside(plan['entry']['workerTarget'], ROOT)), 'config': str(path)}
    if cfg != expected:
        raise ValueError('Readable-gather transport changed beyond its two declared locations')
    return cfg


def run(config, actual_worker):
    cfg = validate_config(config)
    plan = read_plan()
    if cfg['worker'] != str(Path(actual_worker).resolve()):
        raise ValueError('Actual readable-gather transport entry differs')
    entry = plan['entry']
    module_path = base.inside(entry['modulePin']['target'], ROOT)
    if base.sha(module_path) != entry['modulePin']['sha256']:
        raise ValueError('Frozen outer source worker differs')
    spec = importlib.util.find_spec(entry['module'])
    if spec is None or spec.origin is None or Path(spec.origin).resolve() != module_path:
        raise ValueError('Readable-gather import leaves its exact frozen code closure')
    module = importlib.import_module(entry['module'])
    if Path(module.__file__).resolve() != module_path:
        raise ValueError('Loaded readable-gather source provenance differs')
    return getattr(module, entry['export'])(config)
