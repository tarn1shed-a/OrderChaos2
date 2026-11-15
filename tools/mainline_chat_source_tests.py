"""Original-source regressions; no quest/server/window fixture is installed."""
import unittest

from mainline_chat_source import SO, source, selection_controls


@unittest.skipUnless(SO.is_file(), 'Original ARM64 source remains private')
class OriginalChatFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(SO.read_bytes())
        cls.record = source(cls.image)

    def test_received_text_ids_are_independent_required_fields(self):
        messages = self.record['messages']
        for name, identity in (('GS2C_ChatMenuInfo', 'menu_id'),
                               ('GS2C_ChatMenuOptionInfo', 'option_id')):
            fields = messages[name]['fields']
            self.assertEqual([(v['name'], v['label']) for v in fields[:2]],
                             [(identity, 2), ('text_id', 2)])
        self.assertEqual([(f['name'], f['label']) for f in
                          messages['GS2C_ChatMenuList']['fields']],
                         [('menus', 3), ('is_list', 1), ('guid', 1)])
        self.assertEqual([f['name'] for f in
                          messages['C2GS_ChatMenuSelectOption']['fields']],
                         ['option_id', 'giver_guid'])

    def test_modified_source_is_rejected(self):
        original = self.image

        class Damaged:
            def read(self, address, size):
                raw = bytearray(original.read(address, size))
                raw[0] ^= 1
                return bytes(raw)

        with self.assertRaisesRegex(ValueError, 'descriptor differs'):
            source(Damaged())

    def test_original_window_selection_including_presence_and_actor_gates(self):
        controls = selection_controls(self.image)
        self.assertEqual([v['eventBoundary']['constructor'] for v in controls],
                         ['0x64121c', '0x64121c', '0x644fd8', '0x64121c',
                          '0x64121c', '0x6448b0', '0x64121c', '0x6448b0',
                          '0x644fd8', '0x64121c'])
        self.assertEqual([v['virtualMaskReads'] for v in controls],
                         [0, 0, 0, 0, 1, 1, 1, 1, 1, 0])
        self.assertEqual([v['originalHelperCount'] for v in controls],
                         [None, None, None, None, 0, 2, 2, 2, 0, None])
        self.assertTrue(all(v['eventConstructed'] is False for v in controls))
        # A zero-page reply reaches the constructor boundary; this does not
        # certify usable content, UI readiness, dialogue completion or approval.
        self.assertEqual(controls[0]['eventBoundary']['integerArguments'][:2], [0, 0])
        self.assertEqual(controls[2]['eventBoundary']['integerArguments'][:2], [1, 0])


if __name__ == '__main__':
    unittest.main()
