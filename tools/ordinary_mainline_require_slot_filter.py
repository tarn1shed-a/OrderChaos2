"""Filter frozen DataManager provenance for the named chat-require slot.

Does not rerun the address-flow search or scan arbitrary object offsets.
Original-source instruction checks are limited to the retained target call and
the ten already-saved residual getter bodies. No CPU/UI/task execution.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'analysis/raw/tutorial-script-manager-inline-20261115'
PINS = {
    'address-flow-v1.json': '0d34aabcfb462fbfd1ba07d4de49617ecadb37ddbb7928884484ca0ad290bfea',
    'address_flow_audit.py': 'c031dbc014f78b02d714e58c6e1bba032abe74b5027f85823ec14a36f557ac5e',
    'residual23-forward-audit-v1.json': 'e8f9b1cd15d32b9ed7adbe7732cf0dde721bc8d3b57efd509ce50efe46a93ca1',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit():
    for name, digest in PINS.items():
        if sha((OLD/name).read_bytes()) != digest:
            raise ValueError('Preserve the frozen original provenance input: '+name)
    report = json.loads((OLD/'address-flow-v1.json').read_text())
    residual = json.loads((OLD/'residual23-forward-audit-v1.json').read_text())
    fields, calls = [], []
    events = Counter()
    for routine in report['results']:
        for event in routine['events']:
            events[event['type']] += 1
            if event['type'] in ('managerFieldRead', 'managerFieldWrite') and event['offset'] == 0x290:
                fields.append({'routine': routine['start'], **event})
            if (event['type'] == 'callWithManagerProvenance'
                    and event.get('target') == '0xc99488'
                    and event.get('arguments', {}).get('x0') == ['manager', 0]):
                calls.append({'routine': routine['start'], 'routineSHA256': routine['sha256'], **event})
    from analyze_native_resources import NativeImage
    image = NativeImage((ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes())
    if report['nativeSHA256'] != sha(image.data):
        raise ValueError('Original image does not match the frozen provenance')
    getters = []
    for address, entry in residual['actualCalleeBodies'].items():
        start = int(address, 16)
        metadata, lines = image.routine(start)
        normalized = lambda text: ' '.join(text.split())
        if (metadata['start'] != address or metadata['size'] != 8
                or [normalized(s) for s in lines] != [normalized(s) for s in entry['lines']]):
            raise ValueError('Saved residual getter differs from original instructions')
        first = next(image.disassembler.disasm(image.read(start, 8), start))
        match = re.fullmatch(r'x0, \[x0, #(0x[0-9a-f]+)\]', first.op_str)
        if first.mnemonic != 'ldr' or not match:
            raise ValueError('Residual callee is not the previously verified direct table getter')
        offset = int(match.group(1), 16)
        getters.append({'address': address, 'managerOffset': hex(offset),
                        'rawSHA256': sha(image.read(start, 8)), 'targets290': offset == 0x290})
    for call in calls:
        metadata, _ = image.routine(int(call['routine'], 16))
        start = int(metadata['start'], 16)
        if sha(image.read(start, metadata['size'])) != call['routineSHA256']:
            raise ValueError('Original retained caller differs')
        ins = next(image.disassembler.disasm(image.read(int(call['pc'], 16), 4), int(call['pc'], 16)))
        if (ins.mnemonic, ins.op_str) != ('bl', '#0xc99488'):
            raise ValueError('Retained target is not the actual original getter call')
    if (len(residual['points']) != 23 or len(getters) != 10 or fields
            or [(x['routine'], x['pc']) for x in calls] != [('0x3e7638', '0x3e76a8')]
            or any(x['targets290'] for x in getters)):
        raise ValueError('Frozen slot290 classification changed; review before extending scope')
    return {'format': 'oc2-chat-require-frozen-slot-filter-v1',
            'sourcePins': PINS, 'originalNativeSHA256': sha(image.data),
            'oldCoverage': {key: report[key] for key in (
                'seedRoutineCount', 'ghidraGlobalReferenceCount', 'resolvedGlobalReads',
                'resolvedGlobalWrites', 'unresolvedGhidraReferences', 'additionalGlobalAccesses')},
            'oldRetainedRoutines': len(report['results']), 'oldRetainedEventCounts': dict(events),
            'oldDataIncludesAllModeledFieldOffsets': True,
            'oldStdoutSummaryOnlyFiltered178And2d0': True,
            'slot290FieldAccesses': fields,
            'slot290GetterCallsWithActualManagerSource': calls,
            'residual23': {'method': residual['method'],
                           'directTargets': dict(Counter(p['nextDirectCallee'] for p in residual['points'])),
                           'originalGetterBodiesRechecked': getters},
            'knownConsumer': '3e7638 metadata helper, already in old14 quests-getter callers; require.step only COW cleanup',
            'newActualConsumerCandidates': [],
            'limitationsInheritedUnchanged': report['limitations'],
            'scope': [
                'Only frozen provenance events from actual DataManager global2528dc8 and saved residual paths.',
                'No address-flow rerun, arbitrary-offset search, new global scan or Ghidra query.',
                'Zero additional retained +290 reads is a finite static coverage result, not whole-program absence.',
                'Getter call results, indirect paths and aliases outside the original model remain unproven.',
                'No original predicate, task208 approval, server state or dialogue content is produced.'
            ], 'originalCPUExecuted': False, 'UIUsed': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'analysis/raw').resolve()) or output.exists():
        cli.error('Use a new ignored analysis/raw output; preserve frozen results')
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'retainedDirect290Reads': len(result['slot290FieldAccesses']),
                      'knownGetterCalls': len(result['slot290GetterCallsWithActualManagerSource']),
                      'originalResidualGettersRechecked': 10, 'newConsumerCandidates': 0}))
