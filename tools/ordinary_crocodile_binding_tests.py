"""Original crocodile assembly/float-rig controls; no sampler rerun or game VM."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import ordinary_crocodile_binding_probe as probe

PUBLIC = '--public-only' in sys.argv or os.environ.get('PUBLIC_ONLY') == '1'
if '--public-only' in sys.argv:
    sys.argv.remove('--public-only')
CPU = probe.AREA / 'cpu-final-v1'
RIG = probe.AREA / 'rig-final-v1'
PRIVATE = not PUBLIC and (CPU / 'binding-v1.json').is_file() and (RIG / 'descriptor.json').is_file()
read = lambda p: json.loads(p.read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


class PublicImport(unittest.TestCase):
    def test_native_imports_are_lazy(self):
        result = subprocess.run([sys.executable, '-S', '-c',
            "import sys;sys.path.insert(0,'tools');import ordinary_crocodile_binding_probe;"
            "assert 'unicorn'not in sys.modules;assert 'capstone'not in sys.modules"],
            cwd=probe.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(PRIVATE, 'Private original assets/CPU receipt unavailable or public-only')
class OriginalBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = read(CPU / 'binding-v1.json')
        cls.construction = read(CPU / 'construction-v1.json')
        cls.rig = read(RIG / 'rig.json')
        cls.descriptor = read(RIG / 'descriptor.json')

    def test_real_camera_empty_descriptor_branch_does_not_drop_bip01(self):
        from bdae_convert import BDAE
        from ordinary_crocodile_animation_probe import MODEL
        from analyze_native_resources import NativeImage
        source = BDAE(probe.RESOURCES / MODEL)
        self.assertEqual(source.section(124)[0], 0)
        static = probe.camera_lookup_source(NativeImage(probe.SO.read_bytes()))
        self.assertEqual(static, read(probe.AREA / 'camera-source-final-v1/source-v1.json'))
        self.assertEqual(self.proof['assembledRoots'], ['Bip01-node', 'Direct001.Target-node'])
        self.assertEqual([c['kind'] for c in self.proof['cameraCalls']],
                         ['actual-original-camera-section-lookup'])
        tree = {n['name']: n for n in self.construction['nativeTree']}
        self.assertEqual(tree['Camera01']['vptr'], tree['Bip01']['vptr'])
        self.assertEqual(tree['Camera01']['vptr'], '0x2460890')
        self.assertFalse(self.proof['cameraAttachmentResourceConstructed'])

    def test_every_original_bone_points_to_real_world_storage_and_original_inverse(self):
        bones = self.construction['boneBindings']
        skin = self.rig['skins'][0]
        self.assertEqual(len(bones), 27)
        self.assertEqual(len({b['actualNativeWorldPointer'] for b in bones}), 27)
        for i, bone in enumerate(bones):
            self.assertGreater(bone['actualNativeNode'], 0)
            self.assertEqual(bone['actualNativeWorldPointer'], bone['actualNativeNode'] + 0x28)
            self.assertEqual(bone['actualInverseMatrix'], skin['inverseBindMatrices'][i])
            self.assertEqual(bone['alias'], skin['boneNames'][i])
            self.assertEqual(bone['sourceNodeIndex'], skin['boneNodes'][i])
        self.assertLess(self.proof['maximumNativeRestPaletteError'], .002)

    def test_rig_has_original_float32_weights_and_literal_four_joint_bytes(self):
        from bdae_convert import BDAE
        from ordinary_crocodile_animation_probe import MODEL
        reader = BDAE(probe.RESOURCES / MODEL)
        count, table = reader.section(188)
        self.assertEqual(count, 1)
        wrapper = reader.rel(table + 16)
        body = reader.q(wrapper + 8) + ((reader.u(wrapper + 4) & 0xffffff) - 1) * 8
        source = reader.q(body + 104)
        self.assertEqual(reader.q(body + 112), 1266 * 20)
        self.assertEqual(reader.u(body + 176), 4)
        weights = b''.join(reader.b[source + i * 20 + 4:source + (i + 1) * 20] for i in range(1266))
        joints = b''.join(reader.b[source + i * 20:source + i * 20 + 4] for i in range(1266))
        skin = self.rig['skins'][0]
        self.assertEqual(struct.pack('<5064f', *skin['skinWeights']), weights)
        self.assertEqual(bytes(skin['skinIndices']), joints)
        self.assertEqual(hashlib.sha256(weights).hexdigest(), self.descriptor['literalWeightBytesSHA256'])
        self.assertEqual(hashlib.sha256(joints).hexdigest(), self.descriptor['literalJointBytesSHA256'])
        self.assertTrue(any(0 < w < 1 and w != round(w * 255) / 255 for w in skin['skinWeights']))
        self.assertLess(max(skin['skinIndices']), 27)

    def test_source_nodes_and_attachments_survive_export_exactly(self):
        from bdae_convert import BDAE
        from ordinary_crocodile_animation_probe import MODEL
        from scene_flags_evidence import literal_nodes
        reader = BDAE(probe.RESOURCES / MODEL)
        self.assertEqual(read(RIG / 'source-model.json'), reader.parse())
        self.assertEqual(self.rig['nodes'], literal_nodes(reader))
        self.assertEqual(len(self.rig['nodes']), 37)
        self.assertEqual(self.construction['sourceAttachments'], [n['attachments'] for n in self.rig['nodes']])
        camera = next(n for n in self.rig['nodes'] if n['name'] == 'Camera01-node')
        self.assertEqual(camera['attachments'], [{'kind': 1, 'reference': '#Camera01-camera'}])
        self.assertEqual(self.rig['nodes'][36]['attachments'],
                         [{'kind': 2, 'reference': '#Object007-mesh-skin'}])
        self.assertFalse(self.proof['sourceNodesOrAttachmentsModified'])
        self.assertFalse(self.proof['identityFallbackSupplied'])
        self.assertFalse(self.proof['meshGPUOrGameActorConstructed'])

    def test_finite_original_samples_drive_every_setter_palette_and_vertex(self):
        from bdae_character import aliases
        from bdae_skin import multiply
        from tutorial_npc_binding_probe import world_matrices, host_vertices
        original = read(probe.EVIDENCE)
        positions = read(RIG / 'source-model.json')['meshes'][0]['positions']
        skin = self.rig['skins'][0]
        skin_input = {'indices': [skin['skinIndices'][i:i + 4] for i in range(0, 5064, 4)],
                      'weights': [skin['skinWeights'][i:i + 4] for i in range(0, 5064, 4)]}
        pose_export = read(RIG / 'finite-poses.json')
        self.assertEqual([c['absoluteMs'] for c in self.proof['cases']], [34993.0, 35123, 36600.0])
        for actual, exported in zip(self.proof['cases'], pose_export['poses']):
            source = next(c for c in original['cases'] if c['absoluteMs'] == actual['absoluteMs'])
            self.assertEqual(len(actual['setters']), 44)
            self.assertEqual(len(actual['actualPalette']), 27)
            self.assertEqual(len(actual['nativePositionOnlyVertices']), 1266 * 3)
            self.assertEqual(exported['originalSamples'], source['samples'])
            self.assertEqual(exported['originalPalette'], actual['actualPalette'])
            self.assertEqual(exported['originalPositionOnlyVertices'], actual['nativePositionOnlyVertices'])
            nodes = copy.deepcopy(self.rig['nodes'])
            lookup = aliases(nodes)
            for sample in source['samples']:
                nodes[lookup[sample['node']]][{1: 'position', 5: 'quaternion'}[sample['type']]] = sample['value']
            world = world_matrices(nodes)
            # Non-skin ancestor and camera setters must affect their real
            # world matrices too; palette-only checks cannot prove this.
            native_world = {row['name']: row['matrix'] for row in actual['actualWorldTree'] if row['name']}
            self.assertEqual(len(native_world), 36)  # Only the separate mesh root is unconstructed.
            for name, matrix in native_world.items():
                self.assertLess(max(abs(a - b) for a, b in zip(matrix, world[lookup[name]])), .002, name)
            palette = [multiply(world[index], inv) for index, inv in zip(skin['boneNodes'], skin['inverseBindMatrices'])]
            vertices = host_vertices(skin_input, positions, palette)
            self.assertEqual(max(abs(a - b) for a, b in zip(vertices, actual['nativePositionOnlyVertices'])),
                             actual['maximumVertexError'])
            self.assertLess(actual['maximumVertexError'], .002)
            self.assertLess(actual['maximumPaletteError'], .002)
        self.assertNotEqual(self.proof['cases'][0]['nativePositionOnlyVertices'],
                            self.proof['cases'][1]['nativePositionOnlyVertices'])
        self.assertFalse(pose_export['newContinuousClipOrTimingRule'])

    def test_wrong_or_failed_proof_is_not_admitted_to_export(self):
        for field, value in [('nativeSHA256', '0' * 64), ('maximumNativeRestPaletteError', math.nan),
                             ('identityFallbackSupplied', True), ('sourceCameraDescriptorCount', 1)]:
            with tempfile.TemporaryDirectory(dir=probe.AREA, prefix='negative-control-') as directory:
                directory = Path(directory)
                changed = copy.deepcopy(self.proof)
                changed[field] = value
                path = directory / 'wrong.json'
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    probe.export_rig(path, directory / 'out')
                self.assertFalse((directory / 'out').exists())

    def test_parent_evidence_sources_and_frozen_readers_stay_unchanged(self):
        for row in read(probe.AREA / 'protected-v1.json'):
            self.assertEqual(digest(probe.ROOT / row['path']), row['sha256'], row['path'])
        for path, row in self.descriptor['files'].items():
            self.assertEqual(digest(RIG / path), row['sha256'])
        self.assertEqual(self.descriptor['nativeProof']['sha256'], digest(CPU / 'binding-v1.json'))
        self.assertFalse(self.proof['lootCombatOrQuestApproved'])
        self.assertFalse(self.descriptor['gameActorMaterialOrRenderAdmission'])


if __name__ == '__main__':
    unittest.main()
