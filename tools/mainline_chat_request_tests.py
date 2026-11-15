"""Original request boundaries; never a mainline completion/eligibility test."""
import os
import struct
import unittest

from mainline_chat_request_probe import ChatRequestProbe, SO, run, source


class InputBoundaryTests(unittest.TestCase):
    def test_unreviewed_or_out_of_width_inputs_rejected_before_execution(self):
        p = object.__new__(ChatRequestProbe)
        for guid in (-1, 1 << 64, True, '2337'):
            with self.assertRaises(ValueError):
                p.constructor(guid)
        for button in (1, 3, 14, True, -1, 1 << 32):
            with self.assertRaises(ValueError):
                p.dispatch(button, 1)
        for button in (0, 15, True):
            with self.assertRaises(ValueError):
                p.count_slice(1, 1, fallthrough_button=button)
        with self.assertRaises(ValueError):
            p.list_slice(1, blocked=0, has_vector=True, nonempty=True)


@unittest.skipUnless(SO.is_file() and not os.getenv('OC2_MAINLINE_CHAT_PUBLIC_ONLY'),
                     'Original private ARM64 sample is not shipped')
class OriginalRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(SO.read_bytes())
        cls.report = run(cls.image)

    def test_original_descriptor_is_one_required_actor_guid(self):
        self.assertEqual(self.report['source']['requestSchema'], {
            'name': 'C2GS_GetChatMenuList', 'fields': [
                {'name': 'creature_guid', 'number': 1, 'label': 2, 'type': 4}]})
        self.assertFalse(self.report['runtimeEnabled'])
        self.assertFalse(self.report['savesAccessed'])

    def test_original_constructor_and_serializer_preserve_guid_width(self):
        for row in self.report['constructors'][:5]:
            value = int(row['controls']['guid'])
            encoded = bytearray([8])
            rest = value
            while rest >= 128:
                encoded.append((rest & 127) | 128)
                rest >>= 7
            encoded.append(rest)
            expected = struct.pack('<I', len(encoded)) + encoded
            self.assertEqual(len(row['packets']), 1)
            packet = row['packets'][0]
            self.assertEqual(packet['opcode'], 0x9a)
            self.assertEqual(packet['guid'], str(value))
            self.assertEqual(bytes.fromhex(packet['framedHex']), expected)
            self.assertFalse(packet['transportExecuted'])

    def test_actual_socket_gates_emit_nothing(self):
        for row in self.report['constructors'][5:]:
            self.assertEqual(row['packets'], [])
            self.assertIsNone(row['serverReply'])

    def test_button_dispatch_does_not_confuse_chat_and_interaction(self):
        expected = {0: [0x21], 2: [0x9a], 15: [0x9a]}
        for row in self.report['buttonControls']:
            b = row['controls']['buttonVirtual490']
            self.assertEqual([p['opcode'] for p in row['packets']], expected.get(b, []))
            self.assertFalse(row['controls']['eligibilityRecovered'])

    def test_count_gate_is_not_a_whole_interaction_predicate(self):
        for row in self.report['countSlices']:
            c = row['controls']
            should_send = c['computedCountSupplied'] >= 2 or c['fallthroughButtonVirtual490'] == 2
            self.assertEqual([p['opcode'] for p in row['packets']], [0x9a] if should_send else [])
            self.assertEqual(row['stopBoundaries'], ['0x9e5b30'])
            self.assertFalse(c['fullCallerExecuted'])

    def test_original_list_empty_and_blocked_branches(self):
        for i, row in enumerate(self.report['listSlices']):
            self.assertEqual([p['opcode'] for p in row['packets']], [0x9a] if i == 0 else [])
            self.assertFalse(row['taskAcceptedOrAdvanced'])

    def test_changed_original_bytes_rejected(self):
        image = self.image

        class Changed:
            routine = image.routine

            def read(self, address, length):
                raw = image.read(address, length)
                return bytes([raw[0] ^ 1]) + raw[1:] if address == 0x5a11c8 else raw

        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            source(Changed())


if __name__ == '__main__':
    unittest.main()
