import random
import unittest
from pathlib import Path

from scene_sky_material import (FORMAT, ROUTINES, RELOCATIONS, analyze_material,
                                classification_word, static_submissions, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class SkyStaticClassificationTests(unittest.TestCase):
    def test_context_extracts_bits16_through47_and_rejects_non_uint64(self):
        self.assertEqual(classification_word(0xffff123456789abc), 0x12345678)
        self.assertEqual(classification_word(1 << 47), 0x80000000)
        self.assertEqual(classification_word(1 << 48), 0)
        self.assertEqual(classification_word(0xffff), 0)
        for value in (True, -1, 1 << 64, 1.0):
            with self.assertRaises(ValueError): classification_word(value)

    def test_static_mesh_consumer_preserves_parts_and_optional_code8(self):
        self.assertEqual(static_submissions(2, 0)['submissions'], [{'part': 1, 'code': 3}, {'part': 2, 'code': 3}])
        self.assertEqual(static_submissions(0, 0x4000), {'submissions': [], 'cleanupParts': [], 'returnWord': 1})
        self.assertEqual(len(static_submissions(64, 0x4000)['submissions']), 128)
        for count in (True, -1, 65):
            with self.assertRaises(ValueError): static_submissions(count)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_static_classifier_runs_with_full_uint64_contexts(self):
        from analyze_native_resources import NativeImage
        from native_sky_material_probe import NativeSkyMaterialProbe
        p = NativeSkyMaterialProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x119700c)
        for context in [0, 0xffff123456789abc, 1 << 47, 1 << 48, (1 << 64)-1]+[rng.getrandbits(64) for _ in range(96)]:
            count = rng.randrange(12); flags = rng.getrandbits(32)
            actual = p.static_submit(count, flags, context)
            self.assertEqual(actual.pop('staticClassificationCalls'), count)
            self.assertEqual(actual, static_submissions(count, flags))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_root_attachment_propagates_context_to_stable_subtrees(self):
        from analyze_native_resources import NativeImage
        from native_sky_material_probe import NativeSkyMaterialProbe
        p = NativeSkyMaterialProbe(NativeImage(NATIVE.read_bytes()))
        for count in range(9):
            for gate in (False, True):
                result = p.attach(count, gate)
                self.assertEqual(result['rootContext'], result['scene'])
                self.assertEqual(result['childContexts'], [result['scene']]*count)
                self.assertEqual(result['rootParent'], result['parent'])
                self.assertEqual(result['parentChildren'], [result['root']+8]*2)
                self.assertEqual(result['rootReferences'], 101)
                self.assertEqual(result['lockCalls'], [0x1502ff4, 0x1502cf0, 0x1502fc0, 0x1503330])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_missing_wrapper_node_or_parent_keeps_tree_and_references_unchanged(self):
        from analyze_native_resources import NativeImage
        from native_sky_material_probe import NativeSkyMaterialProbe
        p = NativeSkyMaterialProbe(NativeImage(NATIVE.read_bytes()))
        for model, parent in ((False, True), (True, False), (False, False)):
            result = p.attach(2, model_present=model, parent_present=parent)
            self.assertEqual(result['rootContext'], 0)
            self.assertEqual(result['childContexts'], [0, 0])
            self.assertEqual(result['rootParent'], 0)
            self.assertEqual(result['parentChildren'], [result['parent']+0xf0]*2)
            self.assertEqual(result['rootReferences'], 100)
            self.assertEqual(result['lockCalls'], [])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_code_virtual_targets_and_queue_entries_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read, elf = image.read, image.elf
        for target in [*ROUTINES, 0x1f37cbc, 0x1f37cd0]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read
        rels = [dict(r.entry) for r in elf.get_section_by_name('.rela.dyn').iter_relocations()]
        class ChangedSection:
            def __init__(self, target): self.target = target
            def iter_relocations(self):
                for row in rels:
                    yield {**row, 'r_addend': row['r_addend'] ^ 1} if row['r_offset'] == self.target else row
        class ChangedELF:
            def __init__(self, target): self.target = target
            def __getattr__(self, name): return getattr(elf, name)
            def get_section_by_name(self, name):
                return ChangedSection(self.target) if name == '.rela.dyn' else elf.get_section_by_name(name)
        for target in RELOCATIONS:
            image.elf = ChangedELF(target)
            with self.assertRaises(ValueError): verify_native(image)
        image.elf = elf

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/model are local only')
    def test_report_corrects_attachment_receiver_without_claiming_final_queue(self):
        from analyze_native_resources import NativeImage
        from resource_packs import ResourceArchive, index, normalize_resource_name
        from scene_sky import MODEL
        from scene_sky_draw import analyze_scene
        from scene_sky_frame import analyze_frame
        image = NativeImage(NATIVE.read_bytes())
        entry, = [e for e in index(SOURCE) if normalize_resource_name(e['path']) == MODEL]
        report = analyze_material(image, ResourceArchive(SOURCE/entry['pack']).read(MODEL))
        self.assertEqual(report['format'], FORMAT)
        self.assertEqual(report['classification']['constantResult'], 16)
        self.assertFalse(report['classification']['dependsOnMaterialAtThisSlot'])
        self.assertTrue(report['classification']['queueStillExaminesMaterial'])
        self.assertEqual(report['attachmentCorrection']['parentRootVptr'], '0x2486960')
        self.assertEqual(report['context']['initialSubmissionDelegate'], 'scene itself at12f1f40')
        self.assertFalse(report['appliedAsLiveState'])
        self.assertFalse(analyze_scene(image)['attachment']['tutorialSkyAttachmentPath'])
        self.assertIn('parent root', analyze_frame(image)['sceneAttachment']['receiverCorrection'])


if __name__ == '__main__': unittest.main()
