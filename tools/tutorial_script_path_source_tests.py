"""Immediate branch coverage and original native input-path controls."""
import struct
import unittest

from tutorial_script_path_source_probe import SO, direct_branches


class BranchCoverageTests(unittest.TestCase):
    def test_backward_bl_and_tail_b_are_both_found_without_ghidra_functions(self):
        target, base = 0xc99370, 0xc99380
        raw = struct.pack('<III', 0x94000000 | ((target-base)//4 & 0x3ffffff),
                          0x14000000 | ((target-base-4)//4 & 0x3ffffff), 0xd503201f)

        class Section:
            def data(self): return raw
            def __getitem__(self, name):
                if name != 'sh_addr': raise KeyError(name)
                return base

        class ELF:
            def get_section_by_name(self, name):
                if name != '.text': raise KeyError(name)
                return Section()

        class Image:
            elf = ELF()

        r = direct_branches(Image())
        self.assertEqual(r['targets'][hex(target)], [
            {'at': hex(base), 'branch': 'BL'}, {'at': hex(base+4), 'branch': 'B'}])
        self.assertFalse(r['indirectCallsOrAliasesExcluded'])


@unittest.skipUnless(SO.is_file(), 'Original native library remains private')
class OriginalPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_script_path_source_probe import run
        cls.r = run()

    def test_getters_and_setters_preserve_three_explicit_directory_inputs(self):
        rows = self.r['directories']
        self.assertEqual([r['managerOffset'] for r in rows], [8, 0x10, 0x18])
        self.assertTrue(all(r['sourceAndDestinationEqual'] for r in rows))
        self.assertFalse(self.r['actualAndroidPreferencesOrStreamObserved'])

    def test_complete_resolver_uses_data_root_without_open_or_new_flags(self):
        rows = self.r['pathControls']
        self.assertEqual([r['resolvedFixturePath'] for r in rows],
                         ['/research-data/InitialFeed.dat', '/research-data/initialfeed.dat'])
        self.assertTrue(all(r['completeOriginalResolverExecuted'] for r in rows))
        self.assertTrue(all(r['returnedFlags'] == 0 and not r['originalOpenRequested'] for r in rows))
        self.assertFalse(self.r['originalPayloadOrQuestScriptRecovered'])
        self.assertFalse(self.r['gameOrSaveOrProductionAccessed'])

    def test_original_factory_registration_never_replaces_an_existing_pointer(self):
        rows = self.r['factoryRegisterOnlyIfEmptyControls']
        self.assertEqual([r['accepted'] for r in rows], [1, 0, 0])
        self.assertEqual([r['storedPointer'] for r in rows], ['0x12345000'] * 3)
        self.assertTrue(all(not r['pointeeDereferenced'] for r in rows))

    def test_binary_direct_branch_scan_confirms_the_finite_getter_inventory(self):
        r = self.r['directBranches']
        self.assertEqual(r['textBytes'], 28641180)
        self.assertEqual(len(r['targets']['0xc99370']), 14)
        self.assertEqual(r['targets']['0xc994c8'], [])
        self.assertEqual(r['targets']['0xc993f8'], [{'at': '0x5b7e00', 'branch': 'BL'}])
        self.assertEqual(r['targets']['0x1542094'], [])
        self.assertEqual(r['targets']['0x10f75d4'], [])
        self.assertFalse(r['indirectCallsOrAliasesExcluded'])


if __name__ == '__main__':
    unittest.main()
