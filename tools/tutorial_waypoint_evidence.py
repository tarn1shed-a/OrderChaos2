"""Source waypoint chains and cached lookup evidence; never chooses a spawn."""
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path
from skill_attachments import decode_ftable

SOURCE_SHA = 'a28bbe03a7a8e0da5b3dcdb0cad641b5a783e66e7406a11223be5e0746623db9'


def chains(rows):
    """Follow explicit IDs; preserve loops, terminal duplicates and dangling links."""
    groups = defaultdict(list)
    for row in rows:
        groups[row['first_wp_id']].append(row)
    result = []
    for first, members in sorted(groups.items()):
        lookup = {r['id']: r for r in members}
        if len(lookup) != len(members):
            raise ValueError('Duplicate waypoint record ID')
        order, seen, at = [], set(), first
        while at and at in lookup and at not in seen:
            seen.add(at)
            order.append(at)
            at = lookup[at]['next_wp_id']
        result.append({'first': first, 'count': len(members), 'order': order,
                       'termination': 'zero' if at == 0 else 'loop' if at in seen else 'missing',
                       'nextAfterTraversal': at, 'unvisited': sorted(set(lookup)-seen),
                       'positions': [[lookup[k][f] for f in ('x', 'y', 'z')] for k in order]})
    return result


def source_evidence():
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    source = Sources(DEFAULT_SOURCE)
    raw = source.read('tables/way_points.tbl')
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Original waypoint table differs')
    table = decode_ftable(raw, 'id')
    if table['verification']['rowStride'] != 76 or table['physicalTypes'] != 'uuuuuuufffuuuuuufuu':
        raise ValueError('Original scalar record layout differs')
    selected = [r for r in table['rows'] if r['map_id'] == 5]
    routes = chains(selected)
    creatures = decode_ftable(source.read('tables/creature_spawns.tbl'), 'id')['rows']
    source_refs = [r for r in creatures if r['waypoint_id']]
    starts = {r['first_wp_id'] for r in selected}
    direct = [r['id'] for r in source_refs if r['waypoint_id'] in starts]
    all_point_refs = [r['id'] for r in source_refs
                      if r['waypoint_id'] in {p['id'] for p in selected}]
    giver = [r for r in creatures if r['map'] == 5 and r['entry'] == 750]
    ids_at, types_at, rows_at, stride = struct.unpack_from('<4I', raw, 20)
    del ids_at, types_at
    records = {r['id']: raw[rows_at+i*stride:rows_at+(i+1)*stride]
               for i, r in enumerate(table['rows']) if r['map_id'] == 5}
    control_index = next(i for i, r in enumerate(table['rows']) if r['map_id'] != 5)
    control = table['rows'][control_index]
    records[control['id']] = raw[rows_at+control_index*stride:rows_at+(control_index+1)*stride]
    return {'source': table['verification'], 'map5Rows': len(selected), 'chains': routes,
            'flags': {f: dict(Counter(r[f] for r in selected))
                      for f in ('valid', 'phasing_id', 'delay', 'disappear', 'y_move')},
            'allCreatureWaypointReferences': len(source_refs),
            'map5CreatureWaypointReferences': sum(r['map'] == 5 for r in source_refs),
            'directReferencesToTheseHeads': direct,
            'directReferencesToAnySelectedPoint': all_point_refs,
            'giver750': [{'id': r['id'], 'position': [r[k] for k in
                         ('position_x', 'position_y', 'position_z')]} for r in giver],
            'controlRecord': {'id': control['id'], 'map': control['map_id']},
            'actualPathActorAndTriggerKnown': False, 'originalFirstEntryKnown': False}, records


def probe(runtime):
    from analyze_native_resources import NativeImage
    from native_waypoint_probe import NativeWaypointProbe
    source, records = source_evidence()
    cfg = json.loads((Path(runtime)/'prototype/native-physics.json').read_text())
    image = NativeImage(Path(cfg['library']).read_bytes())
    engine = NativeWaypointProbe(image)
    text = image.elf.get_section_by_name('.text')
    direct_callers = []
    for index, (word,) in enumerate(struct.iter_unpack('<I', text.data())):
        if word & 0x7c000000 != 0x14000000:
            continue
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        address = int(text['sh_addr'])+index*4
        if address+delta*4 == 0xc99230:
            direct_callers.append(hex(address))
    engine.records(records)
    cases = []
    for identifier, raw in sorted(records.items()):
        out = engine.lookup(identifier)
        if out['found'] != 1 or out['record'] != raw:
            raise ValueError('Original lookup did not copy the exact source row')
        cases.append({'id': identifier, 'copiedBytes': 76,
                      'recordSHA256': hashlib.sha256(out['record']).hexdigest(), 'calls': out['calls']})
    missing = []
    for identifier in (0, 0x7fffffff):
        out = engine.lookup(identifier)
        if out['found'] or out['record'] != bytes([0xa5])*76 or out['calls']:
            raise ValueError('Missing lookup overwrote output')
        missing.append(identifier)
    uncached = engine.lookup(4768, cached=False)
    if uncached['calls'] != [{'kind': 'uncached-boundary-not-executed'}]:
        raise ValueError('Original uncached delegation differs')
    # Explicit counterfactual cache record. It is never written to source/runtime.
    varied = bytearray(records[4768])
    struct.pack_into('<I', varied, 4, 0)       # valid
    struct.pack_into('<II', varied, 20, 999, 777)  # map_id, phasing_id
    engine.records({4768: bytes(varied)})
    varied_out = engine.lookup(4768)
    if varied_out['found'] != 1 or varied_out['record'] != varied:
        raise ValueError('Original cached lookup unexpectedly filtered the record')
    engine.records({})
    empty = engine.lookup(4768)
    if empty['found'] or empty['record'] != bytes([0xa5])*76:
        raise ValueError('Empty original cache overwrote output')
    return {'source': source,
            'nativeLookup': {'constructorFragment': '0xc8b61c..0xc8b64c',
                             'managerTableOffset': '0x38', 'recordBytes': 76,
                             'accessor': '0xc99230', 'lookup': '0xc9fa18',
                             'lookupVtableSlot': '0x242a008+0x18',
                             'directBOrBLToAccessor': direct_callers,
                             'callScanScope': 'All aligned .text B/BL encodings only; '
                                              'does not exclude indirect or dynamic access.'},
            'originalCachedLookups': cases, 'missingIDs': missing,
            'emptyCachePreservesOutput': True,
            'uncachedCalls': uncached['calls'],
            'explicitSyntheticFlagsCopiedWithoutFiltering': {'valid': 0, 'map_id': 999, 'phasing_id': 777},
            'gameplayChanged': False,
            'scope': 'Original c99230/c9fa18 instructions; host balanced 49-row cache, '
                     'memory and memcpy; uncached loader only recorded, no path activation, '
                     'server script, actual Android cache or original entry message.'}


if __name__ == '__main__':
    import argparse
    from tutorial_map_geometry import local_output
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--runtime', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    out = local_output(args.output)
    report = probe(args.runtime)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'map5Rows': report['source']['map5Rows'],
                      'chains': len(report['source']['chains']),
                      'originalRowCopies': len(report['originalCachedLookups']),
                      'originalFirstEntryKnown': False}))
