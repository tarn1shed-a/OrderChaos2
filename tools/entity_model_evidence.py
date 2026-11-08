"""Join original EntityConfig records to native binding and model-slot consumers.

This is a research instrument, not a scene loader. Full input-derived records
stay in ignored analysis/raw; no live device, successful load or draw is assumed.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from device_instance_evidence import level_inputs, verify_native as verify_device
from map_loading_evidence import Sources
from map_selection_evidence import inventory
from scene_model_slots import verify_native as verify_slots

ROOT = Path(__file__).resolve().parents[1]
ENTITY = 'world/tutorial/EntityConfig.xml'
ROUTINES = {
    0x4c92d4: (24, '443e9401a60bb4c5878999f46fb79c952be4cdf05504a853fd3368cfa7fa8dd5'),
    0x4c937c: (992, '95bd34b8de9f5d3d0e0b803c9bf3457c7d601c289b73553fe8a21e8d507ef48e'),
    0x4c975c: (2076, 'eb9e67aa33dcff7137d98381b5bd32889a1555a73af4770000ffb5f218d60a31'),
    0x4ca580: (216, '50105c0e17f6a92b55284708efbfd32bd8abf96313a0c8eac3b89c5696315029'),
    0x4ca658: (56, 'eae16df82a8a7c6f1b364ffb6e6377d34d11501d0ce3bad08c6b4ece757e100e'),
    0x1aaaed0: (72, 'c33d052379c1d90d808f4c4df9a3ce1b8314e3ccf51c036aa1babccb196c84ff'),
    0x1aab1cc: (144, 'fb303314627f8047cb492d6b4abf9057592a3bbf18d72bc713a94ed03c67af9d'),
    0x1aab2b0: (140, '4d7eca5565df01757495d9009da78a9f2c1ee19573fd1be7c66aaf63ed78d9bd'),
    0x1aab9a4: (120, 'bd06e3b0332cd7b07e28ee5e9a253050f5f131f358ecd414a386b07dbd6da737'),
    0x1aaba78: (156, '0daa7c0ce0b839f07c74e5e725ee49955fa9fa264a4eedf350e5ee57661f7aa4'),
}
CALLS = {0x33ec34: 0x4ca580, 0x1aabaf0: 0x2a0c90}
CALLER_SLICE = (0xa61e7c, 56, 'a43c8a50356ee9899b98f68ff6da14137b43e8f0d5d7d90e19383b811fe29109')


def verify_native(image):
    verify_device(image)
    verify_slots(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original EntityConfig routine changed: {at:#x}')
    for at, target in CALLS.items():
        word, = struct.unpack('<I', image.read(at, 4))
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if word & 0xfc000000 != 0x94000000 or at+delta*4 != target:
            raise ValueError('Original EntityConfig call changed')
    at, size, digest = CALLER_SLICE
    if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
        raise ValueError('Original static model caller slice changed')
    if image.read(0x250a8a8, 1) != b'\1':
        raise ValueError('Original cull override initial gate differs')
    return {'additionalRoutines': len(ROUTINES), 'additionalCallEdges': len(CALLS),
            'staticCallerSlices': 1,
            'overrideGateELFInitialByte': 1, 'originalProcessExecuted': False}


def distance_experiments(image, distances):
    from native_model_slot_probe import NativeModelSlotProbe
    p = NativeModelSlotProbe(image)
    result = []
    for outer in distances:
        for current in (0, 1, 2):
            edge = outer+(8 if current < 2 else 0)
            for distance in (edge-1, edge):
                inputs = dict(center=[0, 0, 0], position=[distance, 0, 0], radius=0,
                              scale160=1, config18=10, current=current, config28=2,
                              override168=outer, override_enabled=True,
                              direction_enabled=False, projection_enabled=False)
                requested = p.select(**inputs)
                result.append({'explicitInputs': inputs, 'emittedRequest': requested,
                               'nextRequestedSlot': current if requested is None else requested})
    return result


def analyze(image, source, probe=False):
    native = verify_native(image)
    sources = Sources(source)
    levels, overrides, entity = level_inputs(sources)
    inv = inventory(sources)
    records = [dict(row, itm=f['path'], recordIndex=i) for f in inv['buildingFiles']
               for i, row in enumerate(f['records'])]
    models, rows = [], []
    for model in entity.findall('Item/Model'):
        name = model.attrib['name']
        lower = name[:-5]+'_l.bdae'
        candidates = sources.candidates(name)
        if len(candidates) != 1:
            raise ValueError('Scoped base model is missing or ambiguous')
        sources.read(name)  # Verify original bytes/CRC and retain source proof.
        models.append({'sourceAttributes': dict(model.attrib),
                       'baseLocalCandidates': len(candidates),
                       'lowerPath': lower, 'lowerLocalCandidates': len(sources.candidates(lower))})
        for instance in model.findall('Instance'):
            ident = int(instance.attrib['id'])
            matching = [r for r in records if r['id'] == ident and r['model'] == name]
            if len(matching) != 1:
                raise ValueError('Scoped entity ID/model does not join exactly one original ITM record')
            rows.append({'model': name, 'sourceAttributes': dict(instance.attrib),
                         'sourceRecord': matching[0]})
    result = {'format': 'oc2-entity-model-evidence-v1', 'native': native,
              'sources': sources.proofs, 'models': models, 'instances': rows,
              'gaps': ['Actual device/configuration, resident tiles and current camera are unobserved.',
                       'Original XML tokenization and VFS are adapted; DOM accessors and field reader execute.',
                       'Loaded bounds, original worker completion, render admission and complete unload lifetime remain open.',
                       'Local pack candidates are not proof of the complete original mounted filesystem.',
                       'Stored device/lodlevel/phasing fields have no demonstrated effect in the identified binding fragment.'],
              'appliedToGame': False}
    if not probe:
        return result
    from native_entity_model_probe import NativeEntityModelProbe
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_model_slot_probe import NativeModelSlotProbe
    p = NativeEntityModelProbe(image)
    parsed = p.load(sources.read(ENTITY))
    result['originalReaderResults'] = parsed
    query, gate = NativeDeviceInstanceProbe(image), NativeDeviceInstanceProbe(image)
    query.configure_levels(levels, overrides)
    gate.level_delegate = query.lookup
    for row in rows:
        record = row['sourceRecord']
        ident = record['id']
        row['boundObject168'] = p.bind(row['model'], ident)
        row['queriedModelLevel'] = query.lookup(row['model'], ident)
        gate.load_itm(sources.read(record['itm']))
        row['admissionByExplicitLayer'] = {layer: gate.admission(record['recordIndex'], 2, layer)
                                            for layer in range(5)}
    requests = []
    for model in models:
        name = model['sourceAttributes']['name']
        for config in (0, 1, 2):
            initial = p.static_initial(config)
            request = p.fresh(name, initial['requestedSlot'], initial['forceSingleSlot'],
                              lambda n: bool(sources.candidates(n)))
            requests.append({'model': name, 'explicitForceModelLodLevel': config,
                             'originalStaticCallerIncomingSlot': initial['incomingSlot'], 'initialRequest': initial,
                             'freshRequest': request})
    state = NativeModelSlotProbe(image)
    hidden = state.transition(0, 0, [True, True], 2)
    pointers = list(state.read(state.SELF+0x98, '2Q'))
    result['experiments'] = {
        'freshRequests': requests,
        'distances': distance_experiments(image, sorted({r['boundObject168'] for r in rows})),
        'sentinelTransition': {'explicitLoadedSlots': [True, True], 'result': hidden,
                               'modelRequestCalls': state.loads,
                               'loadedSlotPointersStillPresent': [bool(v) for v in pointers]},
        'inputsAreFixtures': True, 'originalXMLTokenizerExecuted': False,
        'originalXMLFieldReaderExecuted': True, 'resourceTaskOrRendererExecuted': False}
    return result


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--probe', action='store_true')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/entity-chain-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full original-derived records must stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source, args.probe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'models': len(result['models']),
                      'instances': len(result['instances']), 'appliedToGame': False}))


if __name__ == '__main__':
    main()
