"""Versioned transport addition for each explicit actor's original model queue.

The reviewed worker and its original physics are not edited. A SHA-guarded copy
selects the already verified SourceSpeciesQueue only with a local pinned profile.
"""
import hashlib
import json
import sys
from pathlib import Path
import source_physics_worker
from source_species_queue import SourceSpeciesQueue

WORKER_SHA256 = '736784c9841b0c771cf311459f4dbcd449fedab1ce88e0b931ac07f44d6b9e32'


def load_species_profiles(engine, cfg, root):
    value = cfg.get('sourceSpeciesProfiles')
    if not value:
        return {}
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
    raw = Path(source_physics_worker.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != WORKER_SHA256:
        raise ValueError('Reviewed physics worker identity differs')
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
    replace("            elif op=='forget':engine.actors.pop(data['identity'],None);result=True",
            "            elif op=='forget':forget_source_actor(engine,data['identity']);result=True")
    return source


def start(config):
    namespace = dict(vars(source_physics_worker))
    namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,
                     load_species_profiles=load_species_profiles,
                     bind_source_reset=bind_source_reset,
                     forget_source_actor=forget_source_actor)
    exec(compile(staged_worker_source(), source_physics_worker.__file__, 'exec'), namespace)
    namespace['start'](config)


if __name__ == '__main__':
    start(sys.argv[1])
