"""Audit real ZIP-wrapped original BDAE members for hidden script containers.

Only BDAE entries from the existing source index are opened. Normal model data
is classified by source format, not by extension alone; its content is not
re-searched. Unexpected members are length/CRC checked before any byte search.
No extraction, runtime, save, network or deployment action is performed.
"""
import argparse
import collections
import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path, PurePosixPath

from resource_packs import DEFAULT_SOURCE, index, read_entry, normalize_resource_name

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-bdae-20261115'
NATIVE_MODEL_MEMBERS = {'little_endian_not_quantized.bdae', 'little_endian_quantized.bdae'}
NEEDLES = ('tutorial_quest202', 'tutorial_npc972_ai', 'tutorial_obj188_trigger',
           'tutorial_obj190_khalin_hammer', 'Skill240_OnSkillHit', 'Skill228_OnSkillHit')
sha = lambda data: hashlib.sha256(data).hexdigest()


def name_hits(data):
    return [{'name': n, 'encoding': enc, 'offset': at}
            for n in NEEDLES for enc in ('ascii', 'utf-16-le', 'utf-16-be')
            if (at := data.find(n.encode(enc))) >= 0]


def local_record(data, info, central_start):
    at = info.header_offset
    if at < 0 or at + 30 > central_start:
        raise ValueError('ZIP local header outside member region')
    magic, version, flags, method, tm, date, crc, cs, us, nl, el = struct.unpack_from('<4s5H3I2H', data, at)
    if magic != b'PK\x03\x04':
        raise ValueError('ZIP local header signature mismatch')
    name_at, payload = at + 30, at + 30 + nl + el
    if payload > central_start:
        raise ValueError('ZIP local name/extra outside member region')
    name = data[name_at:name_at + nl].decode('utf-8' if flags & 0x800 else 'cp437')
    if name != info.orig_filename or method != info.compress_type or flags != info.flag_bits:
        raise ValueError('ZIP local/central name, method or flags disagree')
    if flags & 1:
        raise ValueError('Encrypted original ZIP is not decoded by guessing')
    if cs == 0xffffffff or us == 0xffffffff:
        raise ValueError('ZIP64 local sizes require a separately audited format branch')
    descriptor_bytes = 0
    end = payload + info.compress_size
    if end > central_start:
        raise ValueError('ZIP compressed member overlaps central directory')
    if flags & 8:
        # The descriptor may carry a signature; its three values are mandatory.
        descriptor_at = end + (4 if data[end:end + 4] == b'PK\x07\x08' else 0)
        if descriptor_at + 12 > central_start:
            raise ValueError('Truncated ZIP data descriptor')
        expected = (info.CRC, info.compress_size, info.file_size)
        if struct.unpack_from('<3I', data, descriptor_at) != expected:
            raise ValueError('ZIP descriptor disagrees with central metadata')
        descriptor_bytes = descriptor_at + 12 - end
        if (crc not in (0, info.CRC) or cs not in (0, info.compress_size)
                or us not in (0, info.file_size)):
            raise ValueError('ZIP descriptor local sizes disagree')
    elif (crc, cs, us) != (info.CRC, info.compress_size, info.file_size):
        raise ValueError('ZIP local/central CRC or sizes disagree')
    if method == 0 and info.compress_size != info.file_size:
        raise ValueError('Stored ZIP member has unequal lengths')
    return {'headerStart': at, 'payloadStart': payload, 'payloadEnd': end,
            'extentEnd': end + descriptor_bytes, 'descriptorBytes': descriptor_bytes,
            'localExtraBytes': el, 'centralExtraBytes': len(info.extra),
            'centralMemberCommentBytes': len(info.comment)}


def bres_header(data, declared_size):
    if len(data) < 16 or data[:8] != b'BRES\xfe\xff\0\0':
        return False
    header, length = struct.unpack_from('<II', data, 8)
    return header == 64 and length == declared_size


def payload_shape(data):
    """Recognize actual magic only; never infer code from a filename alone."""
    if data.startswith(b'\x1bLua'):
        return 'Lua-bytecode-magic'
    if data.startswith(b'\x1bLJ'):
        return 'LuaJIT-bytecode-magic'
    if data.startswith(b'PK\x03\x04'):
        return 'nested-ZIP-magic'
    if data.startswith((b'FWS', b'CWS')):
        return 'SWF-magic'
    if data.startswith(b'BRES'):
        return 'BRES-family'
    if data.lstrip().startswith((b'{', b'[')):
        return 'JSON-like-text-only'
    if data.lstrip().startswith(b'<'):
        return 'XML-like-text-only'
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return 'unknown-binary'
    if '\0' not in text and all(c.isprintable() or c in '\r\n\t' for c in text):
        return 'UTF8-text-only'
    return 'unknown-binary'


def inspect_zip(data):
    if not data.startswith(b'PK\x03\x04'):
        raise ValueError('Only original ZIP local-header magic is admitted')
    result = {'memberCount': 0, 'members': [], 'anomalies': [], 'anomalyHits': [],
              'ordinaryModelBodySearchPerformed': False}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > 10000:
            raise ValueError('Unbounded or empty original model ZIP')
        if len({i.orig_filename for i in infos}) != len(infos):
            raise ValueError('Duplicate central names are not silently selected')
        spans = []
        for info in infos:
            local = local_record(data, info, archive.start_dir)
            spans.append((local['headerStart'], local['extentEnd']))
            row = {'name': info.orig_filename, 'method': info.compress_type,
                'bytes': info.file_size, 'compressedBytes': info.compress_size,
                'CRC32': f'{info.CRC:08x}', 'flags': info.flag_bits, 'local': local,
                'localCentralMatched': True, 'decodedCRCValidated': False}
            # The ordinary stored model payload can be recognized in place.
            # No whole-model literal/script search is repeated.
            head = data[local['payloadStart']:min(local['payloadStart'] + 16, local['payloadEnd'])]
            ordinary = (info.orig_filename in NATIVE_MODEL_MEMBERS and info.compress_type == 0
                        and bres_header(head, info.file_size))
            if ordinary:
                row['classification'] = 'original-named-BRES-model'
            elif info.is_dir() and info.file_size == 0:
                row['classification'] = 'directory'
            else:
                # Do not call .bdae or .nfo harmless without checking real bytes.
                decoded = archive.read(info)  # stdlib verifies decoded length and CRC.
                if len(decoded) != info.file_size:
                    raise ValueError('Inner ZIP decoded length mismatch')
                row['decodedCRCValidated'] = True
                row['decodedSHA256'] = sha(decoded)
                row['shape'] = payload_shape(decoded)
                row['hits'] = name_hits(decoded)
                if (info.orig_filename in NATIVE_MODEL_MEMBERS
                        and bres_header(decoded, info.file_size)):
                    row['classification'] = 'original-named-BRES-model-compressed'
                elif info.orig_filename == 'version.nfo' and decoded == b'0,0,0,946':
                    row['classification'] = 'observed-model-version-text'
                else:
                    row['classification'] = 'unexpected-member'
                    result['anomalies'].append(row)
                if row['hits']:
                    result['anomalyHits'].append(row)
            result['members'].append(row)
        spans.sort()
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            raise ValueError('Overlapping original ZIP members')
        result['memberCount'] = len(infos)
        result['ZIPCommentBytes'] = len(archive.comment)
        result['centralDirectoryStart'] = archive.start_dir
        result['unreferencedPreCentralBytes'] = (spans[0][0]
            + sum(b[0] - a[1] for a, b in zip(spans, spans[1:]))
            + archive.start_dir - spans[-1][1])
        result['allMemberLocalCentralNamesMethodsSizesCRCAndRangesMatched'] = True
    return result


def tutorial_priority(entries):
    sources = [ROOT / 'analysis/raw/creation-stage-transform-20261115/entry-runtime/game-data/converted/source-tutorial-inside/manifest.json',
               ROOT / 'analysis/raw/tutorial-quest-mvp-20261114/chain-evidence.json']
    models, proofs = set(), []
    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.lower().endswith('.bdae'):
            models.add(normalize_resource_name(node))
    for path in sources:
        data = path.read_bytes()
        walk(json.loads(data))
        proofs.append({'path': str(path.relative_to(ROOT)), 'SHA256': sha(data)})
    resolved = {normalize_resource_name(e['path']) for e in entries} & models
    return models, {'sourceProofs': proofs, 'explicitReferenceCount': len(models),
        'resolvedUniquePaths': len(resolved), 'unresolvedReferenceNames': sorted(models - resolved),
        'boundary': 'Prioritizes these actual manifest/table references only; not an assertion of all live tutorial actor selection'}


def run(source, output):
    output = output.resolve()
    if not output.is_relative_to(ROOT / 'analysis/raw'):
        raise ValueError('Full original directories and findings must remain private')
    output.mkdir(parents=True, exist_ok=True)
    all_entries = index(source)
    entries = [e for e in all_entries if e['path'].lower().endswith('.bdae') and not e['path'].endswith('/')]
    priority, proof = tutorial_priority(entries)
    entries.sort(key=lambda e: (normalize_resource_name(e['path']) not in priority, e['pack'], e['header_offset']))
    rows, errors = [], []
    for entry in entries:
        row = {'pack': entry['pack'], 'path': entry['path'], 'headerOffset': entry['header_offset'],
            'currentTutorialReference': normalize_resource_name(entry['path']) in priority}
        try:
            data = read_entry(entry, source)
            row.update({'outerBytes': len(data), 'outerSHA256': sha(data), 'outerCRCValidated': True,
                        'head8': data[:8].hex()})
            if data.startswith(b'PK\x03\x04'):
                row['outerClass'] = 'real-ZIP'
                row['ZIP'] = inspect_zip(data)
            elif bres_header(data[:16], len(data)):
                row['outerClass'] = 'raw-BRES-already-in-old-scan'
            else:
                row['outerClass'] = 'unsupported-original-format'
                errors.append({'pack': entry['pack'], 'path': entry['path'], 'reason': 'No supported ZIP/BRES magic; not decoded by guessing'})
        except (ValueError, RuntimeError, UnicodeDecodeError, zipfile.BadZipFile, NotImplementedError, EOFError) as error:
            row['failure'] = str(error)
            errors.append({'pack': entry['pack'], 'path': entry['path'], 'reason': str(error)})
        rows.append(row)
    members = [m for r in rows if 'ZIP' in r for m in r['ZIP']['members']]
    anomalies = [{'pack': r['pack'], 'path': r['path'], 'member': m}
                 for r in rows if 'ZIP' in r for m in r['ZIP']['anomalies']]
    anomaly_matrix = collections.Counter((a['member']['name'], a['member']['shape'],
        a['member']['bytes'], a['member']['decodedSHA256']) for a in anomalies)
    report = {'format': 'tutorial-script-bdae-inner-directory-v1', 'scope': {
            'originalIndexedRecords': len(all_entries), 'selectedOuterBDAE': len(entries),
            'original39665BodySearchRerun': False, 'scriptSearchInOrdinaryBRESBodies': False,
            'noOtherOuterExtensionsInspected': True}, 'tutorialPriority': proof,
        'summary': {'outerClasses': dict(collections.Counter(r.get('outerClass', 'failure') for r in rows)),
            'perPack': dict(collections.Counter(r['pack'] for r in rows)),
            'innerMembers': len(members), 'innerMethods': dict(collections.Counter(m['method'] for m in members)),
            'innerClassifications': dict(collections.Counter(m['classification'] for m in members)),
            'innerPayloadsCRCValidated': sum(m['decodedCRCValidated'] for m in members),
            'currentTutorialOuterRecords': sum(r['currentTutorialReference'] for r in rows),
            'nonemptyZIPComments': sum(bool(r['ZIP']['ZIPCommentBytes']) for r in rows if 'ZIP' in r),
            'unreferencedPreCentralBytes': sum(r['ZIP']['unreferencedPreCentralBytes'] for r in rows if 'ZIP' in r),
            'localExtraBytes': sum(m['local']['localExtraBytes'] for m in members),
            'centralExtraBytes': sum(m['local']['centralExtraBytes'] for m in members),
            'centralMemberCommentBytes': sum(m['local']['centralMemberCommentBytes'] for m in members),
            'anomalyNameHits': sum(bool(a['member']['hits']) for a in anomalies),
            'anomalies': len(anomalies), 'errors': len(errors)},
        'anomalyContentMatrix': [{'name': name, 'shape': shape, 'bytes': size,
            'decodedSHA256': digest, 'count': count}
            for (name, shape, size, digest), count in sorted(anomaly_matrix.items())],
        'anomalies': anomalies, 'errors': errors, 'rows': rows,
        'scriptBodyRecovered': False, 'gameRuntimeSaveOrDeploymentChanges': False,
        'limits': ['Directory/schema inventory cannot prove absence of unnamed/obfuscated behavior in BRES',
            'Original model caller 117f010 selects named little-endian model members; no quest script execution inferred',
            'Unsupported encryption/ZIP64/format errors remain explicit rather than transformed',
            'Only supplied original source directory; Android external/internal mounts remain outside scope']}
    (output / 'audit-v1.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output / 'audit-v1.json'), 'summary': report['summary'],
                      'tutorialPriority': proof, 'errors': errors[:8], 'anomalyNames': sorted({a['member']['name'] for a in anomalies})}, ensure_ascii=False))
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=RAW)
    args = cli.parse_args()
    run(args.source, args.output)


if __name__ == '__main__':
    main()
