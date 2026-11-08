import copy
import random
import unittest
from pathlib import Path

from scene_sky_mesh import (FORMAT, MODEL, MESH_VPTR, ROUTINES, RELOCATIONS,
                            analyze_mesh, source_nodes, submission_decision, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class SkyMeshTests(unittest.TestCase):
    def test_source_codes_and_one_based_parts_are_not_draw_order(self):
        result = submission_decision([0, 4, 5, 16, 3, 8], 0x4000)
        self.assertEqual(result, {'submissions': [{'part': 2, 'code': 3}, {'part': 2, 'code': 8},
                                                  {'part': 4, 'code': 3}, {'part': 4, 'code': 8}],
                                  'cleanupParts': [2], 'returnWord': 1})
        self.assertEqual(submission_decision([4], 0x2000)['submissions'], [{'part': 1, 'code': 3}])

    def test_missing_mesh_or_driver_skips_even_when_classification_would_submit(self):
        for mesh, driver in [(False, True), (True, False), (False, False)]:
            self.assertEqual(submission_decision([4, 5, 16], 0x4000, mesh, driver),
                             {'submissions': [], 'cleanupParts': [], 'returnWord': 1})

    def test_research_input_guards_reject_ambiguous_states(self):
        for values, flags in [([True], 0), ([-1], 0), ([1 << 32], 0), ([4]*65, 0), ([], True), ([], -1)]:
            with self.assertRaises(ValueError): submission_decision(values, flags)
        with self.assertRaises(ValueError): submission_decision([], mesh_present=1)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_factory_initializes_self_delegate_and_mesh_reference(self):
        from analyze_native_resources import NativeImage
        from native_sky_mesh_probe import NativeSkyMeshProbe
        probe = NativeSkyMeshProbe(NativeImage(NATIVE.read_bytes()))
        for present in (True, False):
            result = probe.construct(present)
            self.assertEqual(result['vptr'], MESH_VPTR)
            self.assertEqual(result['delegate'], probe.BASE)
            self.assertEqual(result['mesh'], probe.BASE+0x4000 if present else 0)
            self.assertEqual(result['output'], probe.BASE)
            self.assertEqual(result['nodeReferences'], 1)
            self.assertEqual(result['meshReferences'], 101 if present else 100)
            self.assertEqual(result['mode'], 2)
            self.assertEqual(result['allocationBytes'], [0x190])
            self.assertEqual(result['matrixCallbacks'], 1)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_self_route_and_complete_submission_consumer(self):
        from analyze_native_resources import NativeImage
        from native_sky_mesh_probe import NativeSkyMeshProbe
        probe = NativeSkyMeshProbe(NativeImage(NATIVE.read_bytes()))
        rng = random.Random(0x1132bc8)
        for _ in range(120):
            values = [rng.choice([0, 3, 4, 5, 8, 16, 0xffffffff]) for _ in range(rng.randrange(10))]
            flags = rng.getrandbits(32); mesh = bool(rng.randrange(2)); driver = bool(rng.randrange(2))
            result = probe.submit(values, flags, mesh, driver, context_word=rng.getrandbits(32))
            self.assertEqual(result.pop('delegateCalls'), 1)
            self.assertEqual(result, submission_decision(values, flags, mesh, driver))
        # Gate failure must prevent the delegate even for valid geometry.
        result = probe.submit([4, 16], 0x4000, gate=False)
        self.assertEqual(result['delegateCalls'], 0)
        self.assertEqual(result['submissions'], [])
        self.assertEqual(result['cleanupParts'], [])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_all_creation_fingerprints_and_relocations_fail_closed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in ROUTINES:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        def changed_jump(at, size):
            raw = read(at, size)
            return bytes([raw[0] ^ 1])+raw[1:] if at == 0x1f2ea9c else raw
        image.read = changed_jump
        with self.assertRaises(ValueError): verify_native(image)
        image.read = read
        self.assertEqual(verify_native(image)['relocations'], len(RELOCATIONS))
        elf = image.elf
        original_relocs = [dict(r.entry) for r in elf.get_section_by_name('.rela.dyn').iter_relocations()]
        class RelocationSection:
            def __init__(self, target): self.target = target
            def iter_relocations(self):
                for row in original_relocs:
                    yield {**row, 'r_addend': row['r_addend'] ^ 1} if row['r_offset'] == self.target else row
        class ChangedELF:
            def __init__(self, target): self.target = target
            def __getattr__(self, name): return getattr(elf, name)
            def get_section_by_name(self, name):
                return RelocationSection(self.target) if name == '.rela.dyn' else elf.get_section_by_name(name)
        for target in RELOCATIONS:
            image.elf = ChangedELF(target)
            with self.assertRaises(ValueError): verify_native(image)
        image.elf = elf

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/model are local only')
    def test_local_source_references_and_report_boundaries(self):
        from analyze_native_resources import NativeImage
        from resource_packs import ResourceArchive, index, normalize_resource_name
        from bdae_convert import BDAE
        import tempfile
        entries = [e for e in index(SOURCE) if normalize_resource_name(e['path']) == MODEL]
        self.assertEqual(len(entries), 1)
        raw = ResourceArchive(SOURCE/entries[0]['pack']).read(MODEL)
        image = NativeImage(NATIVE.read_bytes()); report = analyze_mesh(image, raw)
        self.assertEqual(report['format'], FORMAT)
        self.assertFalse(report['appliedAsLiveState'])
        self.assertTrue(report['native']['defaultDelegateIsSelf'])
        self.assertEqual(report['source']['instanceType'], 6)
        nodes = report['source']['nodes']
        self.assertEqual([n['name'] for n in nodes], ['VisualSceneNode', 'sky001-node'])
        self.assertEqual(nodes[1]['attachments'][0]['reference'], '#sky001-mesh')
        self.assertEqual(nodes[1]['attachments'][0]['nodeFactorySlot'], 0x158)
        self.assertNotEqual(nodes[1]['field0x58'], 0)
        self.assertEqual(nodes[1]['field0x5c'], 0)
        self.assertEqual(nodes[1]['transformFactorySlot'], 0x140)
        with self.assertRaises(ValueError): analyze_mesh(image, raw[:-1])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'source.bdae'; path.write_bytes(raw); reader = BDAE(path)
            _, table = reader.section(220); node = reader.rel(table+20)+96
            corrupted = copy.copy(reader); corrupted.b = bytearray(reader.b)
            import struct
            attachment = reader.rel(node+84)
            struct.pack_into('<I', corrupted.b, attachment, 99)
            with self.assertRaises(ValueError): source_nodes(corrupted)
            corrupted.b = bytearray(reader.b)
            struct.pack_into('<I', corrupted.b, node+72, 65)
            with self.assertRaises(ValueError): source_nodes(corrupted)
            corrupted.b = bytearray(reader.b)
            _, instances = reader.section(276)
            struct.pack_into('<I', corrupted.b, instances, 3)
            with self.assertRaises(ValueError): source_nodes(corrupted)


if __name__ == '__main__': unittest.main()
