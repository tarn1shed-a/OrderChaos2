"""Versioned transport addition for each explicit actor's original model queue.

The historical SHA keeps its exact projection. Current installed worker bytes
are checked against the shared source declaration before an exact projection.
Original physics and optional pinned model profiles are not replaced.
"""
import hashlib
import json
import sys
from pathlib import Path

WORKER_SHA256 = '736784c9841b0c771cf311459f4dbcd449fedab1ce88e0b931ac07f44d6b9e32'


def load_species_profiles(engine, cfg, root):
    value = cfg.get('sourceSpeciesProfiles')
    if not value:
        return {}
    from source_species_queue import SourceSpeciesQueue
    if not isinstance(engine, SourceSpeciesQueue) or set(value) != {'path', 'sha256'}:
        raise ValueError('Explicit source queue and pinned profiles required')
    path = Path(value['path']).resolve()
    if not path.is_relative_to(root/'analysis/raw') or path.is_symlink():
        raise ValueError('Source model profiles must stay in the private runtime')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != value['sha256']:
        raise ValueError('Source model profile bytes differ')
    profiles = json.loads(raw)
    if not isinstance(profiles, dict) or not profiles or len(profiles) > 10:
        raise ValueError('Verified model profile collection required')
    for key, profile in profiles.items():
        if key != profile.get('key'):
            raise ValueError('Source model profile key differs')
        engine.register_species(profile)
    return {'sourceSpeciesKeys': sorted(profiles), 'sourceSpeciesProfileSHA256': value['sha256']}


def bind_source_reset(engine, data):
    identity = data['identity']
    profiles = getattr(engine, 'species_profiles', {})
    actors = getattr(engine, 'species_actors', {})
    if 'species' not in data:
        if identity in actors:
            raise ValueError('An existing source actor cannot become the legacy model')
        return
    key = data['species']
    if not isinstance(key, str) or key not in profiles:
        raise ValueError('Source actor model is unavailable')
    if identity in actors:
        if actors[identity] != key:
            raise ValueError('An existing actor model cannot be replaced')
        return
    engine.bind_species(identity, key)


def forget_source_actor(engine, identity):
    engine.actors.pop(identity, None)
    if hasattr(engine, 'species_actors'):
        engine.species_actors.pop(identity, None)


def staged_worker_source():
    path = Path(__file__).with_name('source_physics_worker.py')
    raw = path.read_bytes()
    legacy = hashlib.sha256(raw).hexdigest() == WORKER_SHA256
    if not legacy:
        # This is the same installed declaration verified by bootstrap. Never
        # derive an expected identity from the worker bytes being admitted.
        declaration = json.loads(path.with_name('source_world_python.json').read_text())
        files = declaration.get('files') if isinstance(declaration, dict) else None
        if (not isinstance(declaration, dict) or
                declaration.get('format') != 'oc2-source-world-python-closure-v1' or
                not isinstance(files, dict)):
            raise ValueError('Reviewed source world declaration differs')
        for target, actual in (
                ('tools/source_physics_worker.py', raw),
                ('tools/source_species_worker.py', Path(__file__).read_bytes())):
            expected = files.get(target)
            if (type(expected) is not str or len(expected) != 64 or
                    any(c not in '0123456789abcdef' for c in expected) or
                    hashlib.sha256(actual).hexdigest() != expected):
                raise ValueError('Reviewed current worker identity differs: ' + target)
    source = raw.decode()

    def replace(before, after):
        nonlocal source
        if source.count(before) != 1:
            raise ValueError('Source species worker anchor differs')
        source = source.replace(before, after)

    replace('        engine_type=SourceLayerQueue',
            "        engine_type=SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue")
    replace("    for line in sys.stdin:",
            "    if cfg.get('sourceSpeciesProfiles') and not cfg.get('layerQueue'):raise ValueError('Original model queues required')\n"
            "    summary.update(load_species_profiles(engine,cfg,root))\n    for line in sys.stdin:")
    replace("                identity=data['identity'];position=data['position']",
            "                bind_source_reset(engine,data)\n                identity=data['identity'];position=data['position']")
    if legacy:
        replace("            elif op=='forget':engine.actors.pop(data['identity'],None);result=True",
                "            elif op=='forget':forget_source_actor(engine,data['identity']);result=True")
    else:
        replace("            elif op=='forget':\n"
                "                engine.actors.pop(data['identity'],None);result=True\n"
                "                if not engine.actors:reclaim_guest_pages(engine.uc)",
                "            elif op=='forget':\n"
                "                forget_source_actor(engine,data['identity']);result=True\n"
                "                if not engine.actors:reclaim_guest_pages(engine.uc)")
    return source


def start(config):
    import source_physics_worker
    from source_species_queue import SourceSpeciesQueue
    namespace = dict(vars(source_physics_worker))
    namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,
                     load_species_profiles=load_species_profiles,
                     bind_source_reset=bind_source_reset,
                     forget_source_actor=forget_source_actor)
    exec(compile(staged_worker_source(), source_physics_worker.__file__, 'exec'), namespace)
    namespace['start'](config)


if __name__ == '__main__':
    start(sys.argv[1])
