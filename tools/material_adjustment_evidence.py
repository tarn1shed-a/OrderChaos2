"""Join original material declarations and per-instance option consumers."""
import argparse
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bres_world_bounds_evidence import inner_bres
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources
from mesh_scene_evidence import verify_native as verify_mesh
from scene_lightmaps import source_names, read_records, object_records
from scene_sampling import material_samplers
from resource_packs import read_entry

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0x327160: (572, '7fa56bf748483bd7c354a9f078ba6366d4e762b65250ec2cfc0033ae3e34af8c'),
    0x33abb8: (784, '5d26abddd59dba88cc3ac17fbbd40631cbba89bafc422276593c1d8228f1d6c6'),
    0x33b854: (3092, '8d7808518b96e36d43a5bffadbf9e4fa87b42f9361573b99bc5dd9d6b72f2119'),
    0x13649ac: (8, 'ccd9a1b80b77a7a279e3d48dbcee6b4e4f1594f0506ae5ff14908fd4eab094b4'),
    0x13649b4: (8, '1840908233751555ed3d4d67c13d42f94e496a4f7993bd56a6817a428e4d32bc'),
    0x550f08: (104, '202cb4b869cb9856cf7ee8b36553948e5444395d70b7b1344a125a6e64684869'),
    0x550db4: (304, 'af05094c3125860cf47388d00c83df1bb236039612d1b9692470d8cdc6dcda4e'),
    0x3cf0b8: (292, 'db8e346c748c6c824e2cf28fbbe4aa6fedc2802d21cae80ef7dd5eb81ca6ee45'),
}


def verify_native(image):
    verify_mesh(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original material adjustment method changed: {at:#x}')
    if hashlib.sha256(image.read(0x33e86c, 0x98)).hexdigest() != '9e1561160819a409e7bbcdbfc648071e538e9b60383f934685e5898c4394e945':
        raise ValueError('Original post-adjustment attachment consumer changed')
    return {'additionalRoutines': len(ROUTINES), 'postCallFragmentPinned': True,
            'callerUsesMaterialReturnAsAttachGate': False, 'GPUCompletionObserved': False}


def candidates(sources, name):
    result = []
    for entry in sources.candidates(name):
        raw = read_entry(entry, sources.root)
        result.append({'pack': entry['pack'], 'path': entry['path'], 'bytes': len(raw),
                       'crc32': f"{entry['crc']:08x}", 'sha256': hashlib.sha256(raw).hexdigest()})
    if len(result) == 1:
        sources.read(name)
    return result


def source_materials(raw, sources):
    with tempfile.TemporaryDirectory(prefix='oc2-material-declarations-') as tmp:
        path = Path(tmp)/'model.bdae'
        path.write_bytes(raw)
        reader = BDAE(path)
        result = material_samplers(reader)
        count, table = reader.section(172)
        for i in range(count):
            row = result[i]
            row['effectCandidates'] = candidates(sources, row['effectPath'])
            for value in row['samplers'].values():
                value['candidates'] = candidates(sources, value['texture'])
            at = table+i*80
            size, props = reader.u(at+32), reader.rel(at+36)
            row['namedTechniques'] = []
            for j in range(size):
                prop = props+j*32
                if reader.u(prop+16) == 28:
                    row['namedTechniques'].append({'property': reader.string(reader.q(prop)),
                                                  **reader.named_technique(reader.rel(prop+28))})
        return result


def source_atlases(sources, record):
    slots = []
    for slot in (0, 1):
        name = source_names('tutorial', *record['tile'], slot=slot)['record']
        if len(sources.candidates(name)) != 1:
            slots.append({'slot': slot, 'recordPath': name, 'recordUnresolved': True})
            continue
        table = read_records(sources.read(name))
        rows = object_records(table, record['id'])
        requests = []
        for row in rows:
            texture = source_names('tutorial', *record['tile'], slot=slot,
                                   atlas=row['atlasIndex'])['texture']
            requests.append({'sourceRecord': row, 'texture': texture,
                             'candidates': candidates(sources, texture)})
        slots.append({'slot': slot, 'recordPath': name, 'requests': requests,
                      'textureLoadedInOriginalProcess': 'unobserved'})
    return slots


def analyze(image, source):
    from native_material_adjustment_probe import NativeMaterialAdjustmentProbe
    inputs = entity_inputs(image, source, probe=False)
    sources = Sources(source)
    world = sources.read('world/tutorial.wld')
    models, instances = [], []
    for model in inputs['models']:
        name = model['sourceAttributes']['name']
        original = sources.read(name)
        declarations = source_materials(original, sources)
        models.append({'model': name, 'materials': declarations})
        p = NativeMaterialAdjustmentProbe(image)
        for item in inputs['instances']:
            if item['model'] != name:
                continue
            rec = item['sourceRecord']
            itm = sources.read(rec['itm'])
            raw_record = itm[24+76*rec['recordIndex']:24+76*(rec['recordIndex']+1)]
            if struct.unpack_from('<I', raw_record, 4)[0] != rec['id']:
                raise ValueError('Original material-instance identity differs')
            row = {'id': rec['id'], 'model': name, 'atlasSlots': source_atlases(sources, rec),
                   'sourceITMWord64': struct.unpack_from('<I', raw_record, 64)[0],
                   'conditionalSlots': []}
            for slot in (0, 1):
                root = p.scene(p.load(inner_bres(original), string_pool=False)['info'])
                p.w(0x25277d0, 'I', 1)  # Explicit object-visibility fixture.
                trs = p.itm_transform(raw_record, rec['tile'], world[40:52])
                p.finish(root, trs, name, slot=slot)
                initial_stamp = p.r(root+0x148, 'I')[0]
                option_cases = []
                for config in (1, 2):
                    shadow = p.source_shadow_field(raw_record, config)
                    for present in (False, True):
                        p.atlas_presence_fixture(slot, present)
                        for fading in (False, True):
                            result = p.adjustment(slot, fading, options_only=True)
                            option_cases.append({'explicitConfig40': config,
                                                 'explicitAtlasPointerPresent': present,
                                                 'explicitFading': fading, 'sourceShadowConsumer': shadow,
                                                 'result': result})
                # Fresh assembled-root path; no texture/GPU success is supplied.
                config = 1 if slot == 0 else 2
                p.source_shadow_field(raw_record, config)
                p.atlas_presence_fixture(slot, True)
                p.w(0x250aee4, 'B', 0)  # Explicit macro-constructor environment switch.
                cold = p.adjustment(slot)
                if not cold['boundary'] or cold['boundary']['kind'] != 'materialPreparationNotExecuted':
                    raise ValueError('Expected real preparation boundary, not invented completion')
                row['conditionalSlots'].append({'slot': slot, 'assembledRootInitialStamp': initial_stamp,
                                                 'optionCases': option_cases,
                                                 'firstPreparation': cold})
            instances.append(row)
    return {'format': 'oc2-material-adjustment-evidence-v1', 'native': verify_native(image),
            'models': models, 'instances': instances, 'sources': inputs['sources'] | sources.proofs,
            'scope': {'optionAndCacheConsumersExecuteOriginalCode': True,
                      'atlasPointerPresenceIsFixture': True, 'activeConfigurationObserved': False,
                      'oldMeshStorageAdapterRetained': True, 'materialRebuildExecuted': False,
                      'shaderOrGPUResultSupplied': False, 'renderedFrameObserved': False},
            'gaps': ['Actual texture loading/mount precedence and active configuration remain unobserved.',
                     'Original material-list preparation and device-dependent rebuild remain incomplete.',
                     'An original adjustment return word is not a rendered-frame completion result.',
                     'The twelve are source associations, not a proven simultaneous display set.'],
            'appliedToGame': False}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/material-admission-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Complete source-derived records stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'instances': len(result['instances']), 'models': len(result['models']),
                      'callerUsesReturnAsAttachGate': False, 'GPUCompletionObserved': False}))


if __name__ == '__main__':
    main()
