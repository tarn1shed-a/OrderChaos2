"""Inventory indexed table coordinates without selecting a tutorial spawn.

This is a name-bounded search, not proof that every possible position source
has been decoded. Full rows and schemas stay in an ignored local report.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from tutorial_map_geometry import local_output


def inventory():
    source = Sources(DEFAULT_SOURCE)
    reports, errors, count = [], [], 0
    for name in sorted(source.lookup):
        if not name.lower().endswith('.tbl'):
            continue
        raw = source.read(name)
        count += 1
        if len(raw) < 44 or raw[:8] != b'FTABLE\0\0':
            errors.append({'file': name, 'reason': 'not observed FTABLE'})
            continue
        ids_at, = struct.unpack_from('<I', raw, 20)
        if not 44 <= ids_at <= len(raw):
            raise ValueError('Source schema span differs: ' + name)
        if ids_at == 44:
            errors.append({'file': name, 'reason': 'no embedded SQL schema; '
                           'not classified by coordinate-name search'})
            continue
        fields = re.findall(r'^\s*`([^`]+)`\s+',
                            raw[44:ids_at].split(b'\0')[0].decode('utf-8'), re.M)
        low = {f.lower(): f for f in fields}
        triples = [[low[f], low[f[:-1]+'y'], low[f[:-1]+'z']]
                   for f in low if f.endswith('x') and
                   f[:-1]+'y' in low and f[:-1]+'z' in low]
        if not triples:
            continue
        maps = [f for f in fields if f.lower().replace('_', '') in ('map', 'mapid')]
        report = {'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                  'coordinateFields': triples, 'mapFields': maps,
                  'recordCount': struct.unpack_from('<I', raw, 12)[0]}
        if maps and report['recordCount']:
            # The observed first column is checked against the physical ID index.
            # A different schema must fail instead of silently matching wrong rows.
            rows = decode_ftable(raw, fields[0])['rows']
            report['map5Records'] = [
                {k: r[k] for k in dict.fromkeys(
                    [fields[0], *maps, *(f for t in triples for f in t)])}
                for r in rows if any(r[m] == 5 for m in maps)]
        reports.append(report)
    return {'tblFilesRead': count, 'coordinateTables': reports,
            'nonFTABLEOrReadErrors': errors, 'originalFirstEntryKnown': False,
            'scope': 'Indexed .tbl paths; observed FTABLE coordinate-name triples '
                     'and map/map_id names only. No hidden script or binary-layout '
                     'absence claim; no coordinate chosen as player spawn.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = local_output(args.output)
    result = inventory()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'tablesRead': result['tblFilesRead'],
                      'coordinateTables': len(result['coordinateTables']),
                      'unclassifiedTables': len(result['nonFTABLEOrReadErrors']),
                      'firstEntryKnown': False}))
