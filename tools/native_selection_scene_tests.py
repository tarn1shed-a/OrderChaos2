"""Execute original selection instructions with explicitly supplied boundaries."""
from pathlib import Path
import unittest

NATIVE = Path(__file__).resolve().parents[1]/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


@unittest.skipUnless(NATIVE.is_file(), 'Private original ARM64 input is unavailable')
class SelectionSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from native_selection_scene import NativeSelectionScene
        cls.probe = NativeSelectionScene(NativeImage(NATIVE.read_bytes()))

    def test_source_decimal_configuration_is_consumed_as_integer(self):
        self.assertEqual(self.probe.config_integer('5.5'), 5)
        self.assertEqual(self.probe.config_integer('0x10'), 16)

    def test_original_default_requires_no_consumed_character(self):
        self.assertEqual(self.probe.config_integer('bad', 9), 9)
        self.assertEqual(self.probe.config_integer('', 9), 9)
        self.assertEqual(self.probe.config_integer('0', 9), 0)

    def test_switch_hides_previous_and_shows_selected(self):
        result = self.probe.switch_existing(1, 0)
        self.assertEqual(result['selectedIndex'], 1)
        self.assertEqual(result['notifications'], [
            {'object': 0, 'visible': 0, 'secondArgument': 1},
            {'object': 1, 'visible': 1, 'secondArgument': 1}])
        self.assertFalse(result['modelOrGPUCreated'])

    def test_switch_without_previous_does_not_fabricate_hide(self):
        result = self.probe.switch_existing(0, None)
        self.assertEqual(result['notifications'], [
            {'object': 0, 'visible': 1, 'secondArgument': 1}])

    def test_new_or_purchase_slot_is_not_an_existing_character(self):
        with self.assertRaises(ValueError):
            self.probe.switch_existing(-1)
        with self.assertRaises(ValueError):
            self.probe.switch_existing(2)


if __name__ == '__main__':
    unittest.main()
