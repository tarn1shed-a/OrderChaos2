"""Original227 crocodile bones plus intact Camera01 attachment, no mesh GPU.

Reuse frozen original sampler outputs at three times. Execute the original
camera-section lookup, node/property setters/world/palette and affine scatter.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/ordinary-crocodile-binding-20261116'
RESOURCES = ROOT / 'analysis/raw/ordinary-quest-neighbors-20261116/candidate-v2/original-resources'
EVIDENCE = ROOT / 'analysis/raw/quest227-parent-20261116/croc-native-final-v1/evidence.json'
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def camera_lookup_source(image):
    """File-backed relocation/dispatch only; never construct a camera resource."""
    import struct
    table, slot = 0x1f2ea94, 0x2416430 + 0x150
    dispatch = table + struct.unpack('<i', image.read(table, 4))[0]
    relocations = [r for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()
                   if r['r_offset'] == slot]
    if dispatch != 0x111dffc or len(relocations) != 1 or relocations[0]['r_addend'] != 0x112b580:
        raise ValueError('Original camera kind1 dispatch/factory relocation differs')
    return {'nativeSHA256': sha(image.data), 'kind': 1, 'dispatchTable': hex(table),
            'dispatchIndex': 0, 'dispatchTarget': hex(dispatch),
            'sourceCountRead': '111e014:LDRSW [resourceInfo+0x7c]',
            'emptyCountBranch': '111e020:CMP count,1;111e024:B.LT 1120978',
            'explicitResearchFactoryVptr': '0x2416430', 'factoryVirtualSlot': hex(slot),
            'slotRelocationTarget': hex(relocations[0]['r_addend']),
            'factoryExecutedInThisStaticReceipt': False,
            'factoryEntryObservedInCPUProof': False}


def binding_type():
    from ordinary_crocodile_animation_probe import probe_type
    from tutorial_npc_binding_probe import BindingProbe, verify
    base = probe_type()

    class CrocodileBinding(base):
        palette_case = BindingProbe.palette_case
        vertices = BindingProbe.vertices

        def __init__(self, image, reader, skin):
            verify(image)
            super().__init__(image, skin)
            self.reader = reader
            self.nodes_source = skin['nodes']
            self.camera_calls = []
            self.node_calls = []
            self.source_attachments_unchanged = True
            from unicorn import UC_HOOK_CODE
            for pc in (0x111dae0, 0x111dffc, 0x111ed70, 0x111ed74, 0x118455c, 0x112b580):
                self.uc.hook_add(UC_HOOK_CODE, self.observe_binding, begin=pc, end=pc)
            self.loaded = self.load(reader.b)
            info = self.loaded['info']
            self.source_camera_count = reader.section(124)[0]
            self.loaded_camera_count = self.r(info + 0x7c, 'I')[0]
            if self.source_camera_count != self.loaded_camera_count or self.source_camera_count != 0:
                raise ValueError('Original crocodile empty camera section differs')
            self.pair = self.resource_pair(self.loaded)
            self.holder = self.alloc(8)
            self.invoke(0x112ba70, X1=self.pair, X8=self.holder)
            self.root = self.r(self.holder, 'Q')[0]
            scene = info + 0xe0 + self.r(info + 0xe0, 'i')[0]
            first = scene + 20 + self.r(scene + 20, 'i')[0]

            def attachment_kinds(record):
                kinds = []
                count = self.r(record + 80, 'I')[0]
                table = record + 84 + self.r(record + 84, 'i')[0]
                for i in range(count):
                    kinds.append(self.r(table + i * 8, 'I')[0])
                count = self.r(record + 72, 'I')[0]
                children = record + 76 + self.r(record + 76, 'i')[0]
                for i in range(count):
                    kinds += attachment_kinds(children + i * 96)
                return kinds

            self.assembled_roots = []
            self.unconstructed_mesh_roots = []
            for i in range(self.r(scene + 16, 'I')[0]):
                record = first + i * 96
                name = self.c(self.r(record, 'Q')[0]).decode()
                kinds = attachment_kinds(record)
                if any(kind != 1 for kind in kinds):
                    if name != 'Object007-node' or kinds != [2]:
                        raise ValueError('Unexpected source attachment; do not prune the tree')
                    self.unconstructed_mesh_roots.append({'name': name, 'sourceAttachmentKinds': kinds,
                        'sourceRecordDeletedOrModified': False, 'meshGPUConstructed': False})
                    continue
                out = self.alloc(8)
                self.invoke(0x111dae0, X0=self.pair, X1=self.alloc(16), X2=record, X3=self.holder, X8=out)
                if not self.r(out, 'Q')[0]:
                    raise ValueError('Original source node construction returned empty')
                self.invoke(self.r(self.r(self.root, 'Q')[0] + 0xd0, 'Q')[0], X0=self.root, X1=out)
                self.assembled_roots.append(name)
            self.propagate()
            self.rest_tree = self.tree(self.root)
            self.native_nodes = {row['name']: row['nativeProbeAddress'] for row in self.rest_tree}
            for node in self.nodes_source:
                matches = {self.native_nodes[n] for n in (node['name'], *node['aliases']) if n in self.native_nodes}
                if len(matches) > 1:
                    raise ValueError('Ambiguous original alias')
                if matches:
                    address = matches.pop()
                    for alias in (node['name'], *node['aliases']):
                        self.native_nodes[alias] = address
            if 'Camera01-node' not in self.native_nodes or not self.camera_calls:
                raise ValueError('Actual original camera TRS node/section lookup missing')
            if any(c['kind'] != 'actual-original-camera-section-lookup' for c in self.camera_calls):
                raise ValueError('Do not manufacture a camera resource for the empty source section')
            record = info + 0xc0 + self.r(info + 0xc0, 'i')[0]
            wrapper = record + 16 + self.r(record + 16, 'i')[0]
            stream, vt = self.alloc(16), self.alloc(32)
            self.w(stream, 'Q', vt)
            self.w(vt + 0x10, 'Q', 0x30000108)
            self.controller_body = self.invoke(0x117c40c, X0=wrapper, X1=stream, W2=0)
            self.context = self.alloc(0x40)
            self.w(self.context, 'I', 1)
            self.provider = self.alloc(0x50)
            self.invoke(0x11985fc, X0=self.provider, X1=self.controller_body, X2=self.context)
            self.w(self.provider + 0x18, 'Q', self.root)
            self.invoke(0x119c21c, X0=self.provider)
            count = self.r(self.controller_body + 0x50, 'I')[0]
            vector = self.r(self.context + 8, 'Q')[0]
            self.bone_pointers = [self.r(vector + i * 8, 'Q')[0] for i in range(count)]
            if count != 27 or count != len(skin['bones']) or any(not p for p in self.bone_pointers):
                raise ValueError('Actual original bone lookup missing; no identity fallback')
            self.inverse = self.controller_body + 4 + self.r(self.controller_body + 4, 'i')[0]
            self.palette = self.alloc(count * 64)
            for i, bone in enumerate(skin['bones']):
                if self.bone_pointers[i] != self.native_nodes[bone['alias']] + 0x28:
                    raise ValueError('Original named bone pointer differs')
                if list(self.r(self.inverse + i * 64, '16f')) != bone['inverse']:
                    raise ValueError('Relocated original inverse changed')
            self.rest_palette = self.palette_case()

        def observe_binding(self, uc, pc, size, data):
            if pc == 0x111dae0:
                record = self.get('X2')
                self.node_calls.append(self.c(self.r(record, 'Q')[0]).decode())
            elif pc == 0x111dffc:
                info = self.loaded['info']
                self.camera_calls.append({'kind': 'actual-original-camera-section-lookup',
                    'pc': hex(pc), 'loadedCameraCount': self.r(info + 0x7c, 'I')[0],
                    'sourceDescriptorCount': self.source_camera_count,
                    'cameraResourceFactoryEntered': False})
            elif pc == 0x111ed70:
                record = self.get('X2')
                self.camera_calls.append({'kind': 'original-camera-factory-call', 'pc': hex(pc),
                    'factoryTarget': hex(self.get('X9')), 'sourceCameraName': self.c(self.r(record, 'Q')[0]).decode()})
            elif pc == 0x111ed74:
                camera = self.r(self.get('SP') + 0x138, 'Q')[0]
                self.camera_calls.append({'kind': 'original-camera-factory-return', 'pointer': camera,
                    'vptr': hex(self.r(camera, 'Q')[0]) if camera else None})
            elif pc == 0x118455c:
                self.camera_calls.append({'kind': 'original-camera-registration', 'camera': self.get('X1')})
            elif pc == 0x112b580:
                self.camera_calls.append({'kind': 'actual-original-camera-constructor-factory-entered',
                    'pc': hex(pc), 'outputStorage': self.get('X8')})

        def hook(self, uc, pc, size, data):
            if pc == 0x111b8c4:
                raise ValueError('Mesh resource/GPU path outside camera/bone scope; no success fabricated')
            return super().hook(uc, pc, size, data)

        def apply_original_samples(self, case):
            if len(case['samples']) != len(self.channels):
                raise ValueError('Exact original sample/property correspondence required')
            setters = []
            for channel, sample in zip(self.channels, case['samples']):
                if any(channel[k] != sample[k] for k in ('node', 'type', 'sourceSkinBone')):
                    raise ValueError('Frozen original sample targets differ')
                value = sample['value']
                if len(value) != (4 if channel['type'] == 5 else 3) or not all(math.isfinite(v) for v in value):
                    raise ValueError('Original finite sample width required')
                output = self.alloc(16)
                self.w(output, str(len(value)) + 'f', *value)
                setter = self.r(self.r(channel['object'], 'Q')[0] + 0x98, 'Q')[0]
                self.invoke(setter, X0=channel['object'], X1=output, X2=self.native_nodes[channel['node']])
                setters.append({'node': channel['node'], 'type': channel['type'], 'setter': hex(setter)})
            self.propagate()
            return {'absoluteMs': case['absoluteMs'], 'setters': setters,
                'actualWorldTree': self.tree(self.root), 'actualPalette': self.palette_case()}

    return CrocodileBinding


def run(output):
    from analyze_native_resources import NativeImage
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from bdae_character import aliases
    from bdae_skin import multiply
    from tutorial_npc_binding_probe import controller, world_matrices, host_vertices
    from ordinary_crocodile_animation_probe import MODEL, ANIMATION, SOURCE_SHAS
    output = Path(output).resolve()
    if not output.is_relative_to(AREA) or output.exists():
        raise ValueError('New scoped ignored output required')
    output.mkdir(parents=True)
    write = lambda name, value: (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    image = NativeImage(SO.read_bytes())
    for name, expected in SOURCE_SHAS.items():
        if sha((RESOURCES / name).read_bytes()) != expected:
            raise ValueError('Original crocodile resource differs')
    original_samples = json.loads(EVIDENCE.read_text())
    if original_samples['sourceSHA256'] != SOURCE_SHAS or original_samples['boneCount'] != 27:
        raise ValueError('Existing frozen original sampler proof differs')
    reader = BDAE(RESOURCES / MODEL)
    data = reader.parse()
    skin = controller(reader, data)
    if len(skin['bones']) != 27 or data['meshes'][0]['vertexCount'] != 1266:
        raise ValueError('Exact original controller/geometry required')
    cls = binding_type()
    probe = cls.__new__(cls)
    try:
        cls.__init__(probe, image, reader, skin)
    except Exception as error:
        write('construction-failure-v1.json', {'error': str(error), 'sourceNodesDeleted': False,
            'identityOrResourceSuccessSupplied': False, 'cameraCalls': getattr(probe, 'camera_calls', []),
            'nodeCalls': getattr(probe, 'node_calls', []), 'tree': getattr(probe, 'rest_tree', []),
            'nativeNodeNames': list(getattr(probe, 'native_nodes', {})),
            'PC': hex(probe.get('PC')), 'LR': hex(probe.get('X30'))})
        raise
    expected_rest_world = world_matrices(skin['nodes'])
    expected_rest_palette = [multiply(expected_rest_world[b['node']], b['inverse']) for b in skin['bones']]
    rest_error = max(abs(a - b) for row, expected in zip(probe.rest_palette, expected_rest_palette) for a, b in zip(row, expected))
    if rest_error > .002:
        raise ValueError('Original rest palette differs; no replacement rest pose')
    write('construction-v1.json', {'sourceNodeCount': len(skin['nodes']), 'sourceBoneCount': len(skin['bones']),
        'assembledRoots': probe.assembled_roots, 'unconstructedMeshRoots': probe.unconstructed_mesh_roots,
        'cameraCalls': probe.camera_calls, 'nativeTree': probe.rest_tree,
        'all27BonePointersNonzero': all(probe.bone_pointers), 'sourceAttachments': [n['attachments'] for n in skin['nodes']],
        'boneBindings': [{'alias': bone['alias'], 'sourceNodeIndex': bone['node'],
            'actualNativeWorldPointer': probe.bone_pointers[i], 'actualNativeNode': probe.native_nodes[bone['alias']],
            'actualInverseMatrix': list(probe.r(probe.inverse + i * 64, '16f'))} for i, bone in enumerate(skin['bones'])],
        'nativeRestPalette': probe.rest_palette, 'maximumNativeRestPaletteError': rest_error,
        'originalCameraResourceBoundary': {'sourceDescriptorCount': probe.source_camera_count,
            'loadedDescriptorCount': probe.loaded_camera_count, 'genericCameraTRSNodeActuallyConstructed': True,
            'cameraAttachmentResourceConstructed': False, 'sourceReferenceRetained': '#Camera01-camera'}})
    probe.prepare_animation(BDAEAnimation(RESOURCES / ANIMATION))
    positions = data['meshes'][0]['positions']
    cases = []
    for case in [original_samples['cases'][i] for i in (0, 2, 4)]:
        actual = probe.apply_original_samples(case)
        nodes = copy.deepcopy(skin['nodes'])
        by_name = aliases(nodes)
        for sample in case['samples']:
            nodes[by_name[sample['node']]][{1: 'position', 5: 'quaternion'}[sample['type']]] = sample['value']
        world = world_matrices(nodes)
        expected_palette = [multiply(world[bone['node']], bone['inverse']) for bone in skin['bones']]
        palette_error = max(abs(a - b) for row, expected in zip(actual['actualPalette'], expected_palette) for a, b in zip(row, expected))
        actual_vertices = probe.vertices(positions)
        expected_vertices = host_vertices(skin, positions, expected_palette)
        vertex_error = max(abs(a - b) for a, b in zip(actual_vertices, expected_vertices))
        if palette_error > .002 or vertex_error > .002:
            raise ValueError('Original setter/world/palette/scatter differs; no tolerance widening')
        cases.append({**actual, 'nativePositionOnlyVertices': actual_vertices,
            'maximumPaletteError': palette_error, 'maximumVertexError': vertex_error})
    functions = {}
    for address in (0x111dae0, 0x112b580, 0x1113fd4, 0x118455c, 0x119c21c, 0x1362320, 0x119bd7c):
        metadata, asm = image.routine(address)
        (output / (hex(address) + '.asm')).write_text('\n'.join(asm) + '\n')
        functions[hex(address)] = {'bytes': metadata['size'], 'sha256': sha(image.read(address, metadata['size']))}
    result = {'format': 'oc2-original-crocodile-binding-v1', 'nativeSHA256': sha(image.data),
        'sourceSHA256': SOURCE_SHAS, 'reusedSamplerProof': {'path': str(EVIDENCE.relative_to(ROOT)), 'sha256': sha(EVIDENCE.read_bytes()),
            'originalProperties': 44, 'newSamplesExecuted': 0, 'appliedOriginalCases': 3},
        'sourceNodeCount': len(skin['nodes']), 'boneCount': 27, 'vertices': 1266,
        'maximumNativeRestPaletteError': rest_error,
        'cameraCalls': probe.camera_calls, 'sourceCameraDescriptorCount': probe.source_camera_count,
        'genericCameraTRSNodeActuallyConstructed': True, 'cameraAttachmentResourceConstructed': False,
        'assembledRoots': probe.assembled_roots,
        'unconstructedMeshRoots': probe.unconstructed_mesh_roots, 'cases': cases, 'functions': functions,
        'sourceNodesOrAttachmentsModified': False, 'inverseOrWeightsModified': False, 'identityFallbackSupplied': False,
        'meshGPUOrGameActorConstructed': False, 'lootCombatOrQuestApproved': False,
        'boundaries': ['Original camera-section lookup executes and finds the source-declared zero camera descriptors. Generic Camera01 TRS node is real; no camera attachment resource is manufactured.',
            'SourceObject007 mesh attachment remains in source and is not constructed; no mesh resource/GPU success is supplied.',
            'Frozen original44-property samples are reused, then original setters/world27-bone lookup/palette/1266 position scatter execute.',
            'Allocator/string/stream/locks/libm and output descriptors remain existing named host ABI; no new identity matrices.',
            'No shared runtime, renderer, service, save, Git write or deployment.']}
    write('binding-v1.json', result)
    return result


def export_rig(binding_report, output):
    """Portable source float rig + finite proven poses; no new native run."""
    import struct
    from bdae_convert import BDAE
    from tutorial_npc_binding_probe import controller
    from ordinary_crocodile_animation_probe import MODEL, SOURCE_SHAS, NATIVE_SHA
    binding_report = Path(binding_report).resolve()
    output = Path(output).resolve()
    if not binding_report.is_relative_to(AREA) or not output.is_relative_to(AREA) or output.exists():
        raise ValueError('Owned existing CPU proof and new scoped rig output required')
    proof = json.loads(binding_report.read_text())
    if (proof['format'] != 'oc2-original-crocodile-binding-v1' or proof['nativeSHA256'] != NATIVE_SHA
            or proof['boneCount'] != 27 or proof['vertices'] != 1266 or proof['sourceSHA256'] != SOURCE_SHAS
            or proof['sourceNodesOrAttachmentsModified'] or proof['inverseOrWeightsModified']
            or proof['identityFallbackSupplied'] or proof['sourceCameraDescriptorCount'] != 0
            or not proof['genericCameraTRSNodeActuallyConstructed'] or proof['cameraAttachmentResourceConstructed']):
        raise ValueError('Exact original bound crocodile proof required')
    if (proof['reusedSamplerProof']['sha256'] != sha(EVIDENCE.read_bytes())
            or [c['absoluteMs'] for c in proof['cases']] != [34993.0, 35123, 36600.0]):
        raise ValueError('Frozen original finite sampler correspondence differs')
    errors = [proof['maximumNativeRestPaletteError'],
              *(c[k] for c in proof['cases'] for k in ('maximumPaletteError', 'maximumVertexError'))]
    if any(not math.isfinite(v) or not 0 <= v <= .002 for v in errors):
        raise ValueError('Original CPU comparison did not pass')
    reader = BDAE(RESOURCES / MODEL)
    if sha(reader.path.read_bytes()) != SOURCE_SHAS[MODEL]:
        raise ValueError('Source body changed')
    data = reader.parse()
    skin = controller(reader, data)
    if skin['maximumInfluences'] != 4 or len(skin['indices']) != 1266:
        raise ValueError('Original4-float influences required')
    count, table = reader.section(188)
    if count != 1:
        raise ValueError('Exact original controller required')
    wrapper = reader.rel(table + 16)
    prefix = reader.u(wrapper + 4) & 0xffffff
    body = reader.q(wrapper + 8) + (prefix - 1) * 8
    source = reader.q(body + 104)
    literal_weights = b''.join(reader.b[source + i * 20 + 4:source + i * 20 + 20] for i in range(1266))
    packed_weights = struct.pack('<' + str(1266 * 4) + 'f', *(v for row in skin['weights'] for v in row))
    literal_indices = b''.join(reader.b[source + i * 20:source + i * 20 + 4] for i in range(1266))
    packed_indices = bytes(v for row in skin['indices'] for v in row)
    if literal_weights != packed_weights or literal_indices != packed_indices:
        raise ValueError('Do not normalize, quantize or replace inactive influences')
    rig = {'nodes': skin['nodes'], 'skins': [{'mesh': 0, 'name': data['meshes'][0]['name'] + '-skin',
        'attachmentNode': skin['attachmentNode'], 'boneNames': [b['alias'] for b in skin['bones']],
        'boneNodes': [b['node'] for b in skin['bones']], 'inverseBindMatrices': [b['inverse'] for b in skin['bones']],
        'bindShapeMatrix': skin['bindShapeMatrix'], 'skinIndices': list(packed_indices),
        'skinWeights': [v for row in skin['weights'] for v in row],
        'verification': {'sourceFloatWeightsRetainedAfterStrictValidation': True,
            'sourceIndicesRetainedByteForByte': True, 'normalizationApplied': False,
            'inverseOrPoseCorrectionApplied': False, 'originalCPUComparisonTolerance': .002,
            'maximumWeightSumError': skin['maximumWeightSumError'],
            'restEqualsBindDiagnosticError': max(b['restEqualsBindDiagnosticError'] for b in skin['bones']),
            'maximumNativeRestPaletteError': proof['maximumNativeRestPaletteError'],
            'maximumNativePaletteError': max(c['maximumPaletteError'] for c in proof['cases']),
            'maximumNativeVertexError': max(c['maximumVertexError'] for c in proof['cases'])}}],
        'quaternionConvention': 'XYZW', 'matrixConvention': 'column-major', 'coordinateSystem': 'Y_UP'}
    sampler = json.loads(EVIDENCE.read_text())
    poses = []
    for case in proof['cases']:
        original = next(c for c in sampler['cases'] if c['absoluteMs'] == case['absoluteMs'])
        poses.append({'absoluteMs': case['absoluteMs'], 'originalSamples': original['samples'],
            'originalPalette': case['actualPalette'], 'originalPositionOnlyVertices': case['nativePositionOnlyVertices'],
            'continuousClipInvented': False})
    output.mkdir(parents=True)
    write = lambda name, value: (output / name).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    write('rig.json', rig)
    write('source-model.json', data)  # Exact existing parser result; no format relabelling/material invention.
    write('finite-poses.json', {'format': 'oc2-original-crocodile-finite-pose-controls-v1', 'poses': poses,
        'originalCameraAttachmentConstructed': False, 'sourceCameraTRSNodeRetained': True,
        'newContinuousClipOrTimingRule': False})
    descriptor = {'format': 'oc2-original-crocodile-rig-data-v1', 'model': 'source-model.json', 'rig': 'rig.json',
        'finitePoses': 'finite-poses.json', 'sourceModelSHA256': SOURCE_SHAS[MODEL],
        'nativeProof': {'path': str(binding_report.relative_to(ROOT)), 'sha256': sha(binding_report.read_bytes())},
        'sourceVertices': 1266, 'sourceNodes': 37, 'sourceSkinBones': 27, 'floatWeightsPerVertex': 4,
        'literalWeightBytesSHA256': sha(literal_weights), 'literalJointBytesSHA256': sha(literal_indices),
        'cameraBoundary': 'Original camera section0; actual generic Camera01 TRS node exists; no camera resource success supplied',
        'files': {name: {'bytes': (output / name).stat().st_size, 'sha256': sha((output / name).read_bytes())}
            for name in ('source-model.json', 'rig.json', 'finite-poses.json')},
        'gameActorMaterialOrRenderAdmission': False, 'noOriginalResourceOrFrozenSamplerChanged': True}
    write('descriptor.json', descriptor)
    return descriptor


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--export-rig', type=Path)
    p.add_argument('--inspect-camera', action='store_true')
    args = p.parse_args()
    if args.inspect_camera:
        from analyze_native_resources import NativeImage
        output = args.output.resolve()
        if not output.is_relative_to(AREA) or output.exists():
            raise ValueError('New scoped ignored output required')
        r = camera_lookup_source(NativeImage(SO.read_bytes()))
        output.mkdir(parents=True)
        (output / 'source-v1.json').write_text(json.dumps(r, indent=2) + '\n')
        print(json.dumps(r))
    elif args.export_rig:
        r = export_rig(args.export_rig, args.output)
        print(json.dumps({'nodes': r['sourceNodes'], 'bones': r['sourceSkinBones'], 'vertices': r['sourceVertices'],
            'literalFloatWeightsRetained': True, 'newNativeRuns': 0}))
    else:
        r = run(args.output)
        print(json.dumps({'bones': r['boneCount'], 'vertices': r['vertices'], 'cameraCalls': r['cameraCalls'],
            'paletteErrors': [c['maximumPaletteError'] for c in r['cases']], 'vertexErrors': [c['maximumVertexError'] for c in r['cases']]}))
