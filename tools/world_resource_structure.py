"""Group supplied world and creature references before restoring instances.

Only explicit table/path/header relations are inventoried. Default appearance
candidates and stored spawns are not claims about active server actors.
Full original rows and resource lists must remain in ignored analysis/raw.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct

from map_loading_evidence import Sources, read_world_container
from map_restoration_inventory import group_world_records
from resource_packs import DEFAULT_SOURCE, normalize_resource_name
from skill_attachments import decode_ftable
from terrain_convert import read_instances, read_tile

ROOT = Path(__file__).resolve().parents[1]


class SourceBuffer:
    def __init__(self, name, raw):
        self.stem = Path(name).stem
        self.raw = raw

    def read_bytes(self):
        return self.raw


def audit(source):
    sources = Sources(source)
    tables = {}
    for name, key in [('map_info', 'map_id'), ('creature_spawns', 'id'),
                      ('creature_proto', 'entry'), ('creature_appearance', 'entry'),
                      ('creaturedisplayinfo', 'ID'), ('creaturemodeldata', 'ID'),
                      ('creaturedisplayinfoextra', 'ID')]:
        tables[name] = decode_ftable(sources.read('tables/' + name + '.tbl'), key)
    entries = [row for rows in sources.lookup.values() for row in rows]
    groups = group_world_records(entries)
    worlds, referenced_worlds = [], defaultdict(set)
    for world, group in groups.items():
        terrain_versions, placement_versions, placement_types = Counter(), Counter(), Counter()
        errors, placements, terrain_files, models = [], [], [], set()
        container_path = 'world/' + world + '.wld'
        try:
            container = read_world_container(sources.read(container_path))
        except (ValueError, IndexError, struct.error) as error:
            container = {'error': str(error)}
        for path in group['paths']:
            if not path.endswith(('.trn', '.itm')):
                continue
            try:
                raw = sources.read(path)
                if len(raw) < 8:
                    raise ValueError('Truncated original header')
                version = struct.unpack_from('<I', raw, 4)[0]
                if path.endswith('.trn'):
                    if raw[:4] != b'ATIL':
                        raise ValueError('Terrain suffix has another original magic')
                    terrain_versions[version] += 1
                    # Keep variants that do not meet the old parser separate.
                    # Never rewrite their names/headers to force acceptance.
                    tile = read_tile(SourceBuffer(path, raw))
                    terrain_files.append({'path': path, 'tile': [tile['x'], tile['z']],
                                          'version': tile['version'], 'textureReferences': tile['textures']})
                else:
                    if raw[:4] != b'AITM':
                        raise ValueError('Placement suffix has another original magic')
                    placement_versions[version] += 1
                    rows = read_instances(SourceBuffer(path, raw))
                    placement_types.update(row['sourceType'] for row in rows)
                    models.update(row['model'] for row in rows)
                    placements.append({'path': path, 'rows': rows})
            except (ValueError, IndexError, struct.error) as error:
                errors.append({'path': path, 'reason': str(error)})
        for model in models:
            referenced_worlds[model].add(world)
        worlds.append({'world': world, 'container': container,
                       'mapDefinitionIDs': [r['map_id'] for r in tables['map_info']['rows']
                                            if normalize_resource_name(r['file']) == container_path],
                       'filesBySuffix': group['filesBySuffix'],
                       'terrainHeaderVersions': dict(terrain_versions),
                       'placementHeaderVersions': dict(placement_versions),
                       'placementTypes': dict(placement_types),
                       'decodedTerrain': terrain_files, 'decodedPlacements': placements,
                       'modelReferences': sorted(models), 'decodeGaps': errors})
    indexed = {name: {r[key]: r for r in tables[name]['rows']}
               for name, key in [('creature_proto', 'entry'), ('creature_appearance', 'entry'),
                                 ('creaturedisplayinfo', 'ID'), ('creaturemodeldata', 'ID'),
                                 ('creaturedisplayinfoextra', 'ID')]}
    defaults, missing, models_used = [], [], defaultdict(list)
    for entry, appearance in sorted(indexed['creature_appearance'].items()):
        display = indexed['creaturedisplayinfo'].get(appearance['creaturedisplayinfo_id'])
        model = indexed['creaturemodeldata'].get(display['Model']) if display else None
        if model is None:
            missing.append({'entry': entry, 'displayID': appearance['creaturedisplayinfo_id'],
                            'reason': 'Referenced display or Model row absent'})
            continue
        extra_id = display['ExtraDisplayInformation']
        extra = indexed['creaturedisplayinfoextra'].get(extra_id) if extra_id else None
        row = {'entry': entry, 'hasPrototype': entry in indexed['creature_proto'],
               'displayID': display['ID'], 'modelID': model['ID'], 'path': model['ModelPath'],
               'extraID': extra_id, 'extraPresent': extra_id == 0 or extra is not None,
               'modelArchiveCandidates': len(sources.lookup.get(normalize_resource_name(model['ModelPath']), [])),
               'modelEffects': {k: v for k, v in model.items() if k.startswith('eff_mod_eff') and v},
               'activeAppearanceKnown': False}
        defaults.append(row)
        models_used[model['ModelPath']].append(entry)
    spawns = tables['creature_spawns']['rows']
    extra_defaults = sum(r['extraID'] != 0 for r in defaults)
    summary = {'worldGroups': len(worlds), 'mapDefinitions': len(tables['map_info']['rows']),
               'worlds': [{'world': r['world'], 'mapDefinitionIDs': r['mapDefinitionIDs'],
                           'terrainVersions': r['terrainHeaderVersions'],
                           'placementVersions': r['placementHeaderVersions'],
                           'terrainDecoded': len(r['decodedTerrain']),
                           'placementFilesDecoded': len(r['decodedPlacements']),
                           'placementRows': sum(len(p['rows']) for p in r['decodedPlacements']),
                           'placementTypes': r['placementTypes'], 'models': len(r['modelReferences']),
                           'decodeGaps': len(r['decodeGaps'])} for r in worlds],
               'worldModelReferences': len(referenced_worlds),
               'worldModelsReusedAcrossGroups': sum(len(v) > 1 for v in referenced_worlds.values()),
               'creaturePrototypeRows': len(tables['creature_proto']['rows']),
               'creatureAppearanceRows': len(tables['creature_appearance']['rows']),
               'creatureModelConfigurationRows': len(tables['creaturemodeldata']['rows']),
               'creatureSpawnRows': len(spawns), 'creatureSpawnMaps': len({r['map'] for r in spawns}),
               'defaultCandidatesResolved': len(defaults), 'defaultReferenceGaps': len(missing),
               'defaultCandidateModelPaths': len(models_used),
               'defaultModelPathsReusedByTemplates': sum(len(v) > 1 for v in models_used.values()),
               'defaultsReferencingExtraAssembly': extra_defaults,
               'defaultsWithoutExtraAssembly': len(defaults) - extra_defaults,
               'spawnRowsWithExplicitDisplayReference': sum(r['displayid'] != 0 for r in spawns)}
    return {'format': 'oc2-world-creature-shared-reference-audit-v1', 'summary': summary,
            'sourceProofs': sources.proofs,
            'worlds': worlds, 'sharedWorldModelReferences': {k: sorted(v) for k, v in referenced_worlds.items() if len(v) > 1},
            'creatureDefaultCandidates': defaults, 'creatureReferenceGaps': missing,
            'creatureModelsToTemplates': dict(models_used),
            'storedCreatureSpawns': spawns,
            'limits': ['References and parser coverage only; not active actors, original VFS winners or rendered maps.',
                       'Creature templates include enemies; counts are not a number of restored friendly NPCs.',
                       'Appearance defaults, spawn display references and runtime server messages remain distinct.',
                       'No appearance, quest, phase, spawn, loot, map permission or save state is invented.',
                       'Unrecognized variants remain named gaps; no parser guard is weakened.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'analysis/raw') or output.exists():
        raise ValueError('New ignored analysis/raw output required')
    report = audit(args.source)
    raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)
    output.chmod(0o600)
    print(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(), 'summary': report['summary']}, ensure_ascii=False))
