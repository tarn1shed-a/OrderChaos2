"""Four original Creature default/message replays, never activity producers.

Uses the frozen real parser/factory harness. Resource preparation, network and
live server inputs remain the explicitly named boundaries of that harness.
"""
import argparse
import json
from pathlib import Path

from tutorial_npc_resource_resolve_library_candidate import ROOT, RAW, digest, json_write, private_path

ENTRIES = (750, 970, 971, 747)
AREA = RAW/'tutorial-npc-admission-20261115'
LIBRARY = RAW/'tutorial-npc-resource-resolve-library-20261114/candidate-v1'
SO = RAW/'ghidra-mcp-20261110/input/libOrderChaos2.so'


def resources():
    """References to immutable reviewed resources, no appearance/idle decision."""
    from tutorial_npc_resource_resolve_library_package import validate
    validate(LIBRARY)
    library = json.loads((LIBRARY/'library.json').read_text())
    rows = []
    for entry in ENTRIES:
        meta = next(e for e in library['entries'] if e['entry'] == entry)
        manifest_path = LIBRARY/meta['manifest']
        manifest = json.loads(manifest_path.read_text())
        row = next(e for e in manifest['entries'] if e['entry'] == entry)
        model_path = manifest_path.parent/row['model']
        model = json.loads(model_path.read_text())
        bindings = model.get('animationBinding', model.get('sourceNativeBinding'))
        rows.append({'entry': entry, 'name': meta['sourceName'],
            'defaultDisplay': meta['defaultDisplay'], 'defaultModel': meta['defaultModel'],
            'family': meta['family'], 'manifest': meta['manifest'], 'model': meta['model'],
            'preview': meta['preview'], 'sourceModel': model['source'],
            'modelFile': digest(model_path), 'manifestFile': digest(manifest_path),
            'idleDurationSeconds': row['idleDuration'], 'clipNames': [c.get('name') for c in model['clips']],
            'rigNodeCount': len(model.get('rig', {}).get('nodes', [])),
            'animationBinding': bindings, 'sourceAnimation': row.get('sourceAnimation'),
            'materialCount': len(row['materials']), 'knownGaps': meta['knownGaps'],
            'turnOrInteractionAnimationSelection': None,
            'animationScope': row.get('animationScope', 'Reviewed original idle only; active state selection unknown'),
            'actualGUID': None, 'appearanceObserved': False, 'activityAdmissionProvided': False})
    return {'format': 'oc2-npc-admission-resources-v1', 'entries': rows,
            'libraryRelativePath': str(LIBRARY.relative_to(ROOT)),
            'libraryFile': digest(LIBRARY/'library.json'), 'liveActor': False,
            'resourceLookupCreatesActorOrStartsAnimation': False}


def extended_snapshot(p):
    row = p.snapshot_creature(); a = p.creature_actor
    row['original291'] = p.r(a+0x291, 'B')[0]
    row['secondarySelected4c'] = bool(p.r(a+0x4c, 'B')[0])
    row['primaryWrapperPointer'] = p.r(a+0x38, 'Q')[0]
    return row


def run(library):
    from analyze_native_resources import NativeImage
    from tutorial_quest_creature_probe import native_probe_type, packet_fixture
    from tutorial_npc_native_probe import TutorialNPCProbe
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    image = NativeImage(library.read_bytes()); Base = native_probe_type()

    class C(Base):
        def __init__(self, *args, **kwargs):
            self.ingress_prefix_count = 0
            super().__init__(*args, **kwargs)

        def call(self, address, *args, **kwargs):
            if address == 0xa3f8b8 and getattr(self, 'creature_parse', False):
                # Execute the actual incoming handler prefix as well as parser.
                # The frozen harness still records/stops at manager entry, then
                # runs that original manager explicitly. No socket is supplied.
                self.ingress_prefix_count += 1
                address = 0x589dd8
            return super().call(address, *args, **kwargs)

    constructor = C(image); ctor = constructor.construct_only_fixture(poison=True)
    ctor['snapshot'] = extended_snapshot(constructor)
    rows = []
    for entry in ENTRIES:
        p = C(image)
        inputs = {'guid': 0x40a00001234, 'entry': entry,
                  'position': (0, 0, 0), 'direction': (0, 0, 1)}
        raw = packet_fixture(**inputs)
        parsed = p.parse_creature_packet(raw); p.consume_creature_packet()
        default = extended_snapshot(p); gates = p.qualify_and_emit_creature()
        # Original existing-object path consumes new quest/property fields;
        # an entry in the update does not rerun this object's initialization.
        values = [0]*73; values[72] = 4
        update_entry = ENTRIES[(ENTRIES.index(entry)+1) % len(ENTRIES)]
        authored_update = packet_fixture(**{**inputs, 'entry': update_entry},
            values=values, quest_status=6, quest_type=1,
            interactives=[[202, 1, 1, 99, True]])
        p.parse_creature_packet(authored_update); p.consume_creature_packet(update=True)
        updated = extended_snapshot(p); updated_gates = p.qualify_and_emit_creature()
        p.parse_creature_packet(packet_fixture(**inputs)); p.consume_creature_packet(update=True)
        omitted = extended_snapshot(p)
        idle = TutorialNPCProbe(image, Sources(DEFAULT_SOURCE)).idle(entry, default['selectedDisplay'])
        rows.append({'entry': entry, 'packetHex': raw.hex(), 'parser': parsed,
            'freshMessage': default, 'withoutModel': gates,
            'updateEntryFixture': update_entry, 'updatePacketHex': authored_update.hex(),
            'explicitUpdate': updated, 'withoutModelAfterUpdate': updated_gates,
            'omittedFieldsUpdate': omitted, 'originalIdleRequest': idle,
            'originalReceiveHandlerPrefixExecutions': p.ingress_prefix_count,
            'originalServerActivity': False, 'displayOrInteractionAdmitted': False})
    evidence = []
    for address in (0x5809a8, 0x589dd8, 0xa3f8b8):
        meta, asm = image.routine(address)
        evidence.append({'address': hex(address), 'bytes': meta['size'],
            'sha256': __import__('hashlib').sha256(image.read(address, meta['size'])).hexdigest(),
            'instructions': asm})
    return {'format': 'oc2-npc-original-admission-evidence-v1', 'library': digest(library),
        'constructor': ctor, 'descriptorProofs': p.descriptor_proofs, 'cases': rows,
        'receiveRegistration': {'opcode': 6, 'registration': '0x5809a8',
            'keyStore': '0x580f5c', 'handlerStore': '0x580f58',
            'handler': '0x589dd8', 'parser': '0xa3f8b8', 'manager': '0xa3700c',
            'registrationFunctionExecuted': False, 'socketDispatcherExecuted': False,
            'sameHandlerForCreateOrExistingGuid': True}, 'originalRoutineEvidence': evidence,
        'sourceBoundary': {'originalServerObjectCreateObserved': False,
            'phaseOrManualSpawnInObjectCreatureSchema': False,
            'staticSpawnAppearancePolicyRecovered': False,
            'modelNormalReturnAndActorAssociationObserved': False,
            'firstOfferOrQuestApprovalRecovered': False},
        'hostBoundaries': ['All incoming GUID/location/values/quest fields are authored test inputs, not captured activity.',
            'Factory/parser/manager and original default selection execute; table packing, services, C++/AS storage and transmission retain frozen harness boundaries.',
            'Resource preparation9ddb9c is not executed; no wrapper/node or successful model completion is inserted.',
            'Native idle request is recorded from explicit default-display input, not an activity animation choice.',
            'No phase/manual_spawn decision is derived from static data or absent protocol fields.'],
        'productionChanged': False, 'savesAccessed': False, 'actorsCreatedInGame': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library', type=Path, default=SO)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--resources', type=Path)
    args = cli.parse_args(); out = private_path(args.output)
    if out.exists() or (args.resources and private_path(args.resources).exists()):
        cli.error('Preserve existing evidence')
    json_write(out, run(args.library))
    if args.resources: json_write(private_path(args.resources), resources())
    print(json.dumps({'report': str(out), 'productionChanged': False}))
