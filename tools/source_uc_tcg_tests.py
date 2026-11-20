"""Host configuration contract; no original game code or saved actors."""
import builtins
from contextlib import contextmanager
import os
import platform
import unittest
from unittest.mock import patch

import source_uc_tcg as setting


@contextmanager
def value(text):
    with patch.dict(os.environ):
        os.environ.pop(setting.ENVIRONMENT, None)
        if text is not None:
            os.environ[setting.ENVIRONMENT] = text
        yield


class ConfigurationBoundary(unittest.TestCase):
    def test_unset_and_zero_do_not_inspect_object_or_import_backend(self):
        class Unusable:
            def __getattribute__(self, name):
                raise AssertionError('Default path must not inspect a Uc')
        original = builtins.__import__
        def no_backend(name, *args, **kwargs):
            if name == 'unicorn' or name.startswith('unicorn.'):
                raise AssertionError('Default path imported the backend')
            return original(name, *args, **kwargs)
        for text in [None, '0']:
            with self.subTest(value=text), value(text), patch('builtins.__import__', no_backend):
                self.assertIsNone(setting.configure_uc_tcg_before_init(Unusable()))

    def test_noncanonical_numbers_and_uint32_wrap_are_rejected(self):
        for text in ['', '00', '01', '-1', '+2097152', ' 2097152', '2097152 ',
                     '2.0', '0x200000', '1048575', '2147483649', '4294967296',
                     '9999999999999999999999999999999']:
            with self.subTest(value=text), value(text), self.assertRaises(ValueError):
                setting.configure_uc_tcg_before_init(object())

    def test_plain_object_cannot_receive_native_setting(self):
        with value('2097152'), self.assertRaises(ValueError):
            setting.configure_uc_tcg_before_init(object())


LINUX_X86 = platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64')


@unittest.skipUnless(LINUX_X86, 'Actual Linux amd64 required; no emulated platform admission')
class ActualBackend(unittest.TestCase):
    def new(self):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        return Uc(UC_ARCH_ARM64, UC_MODE_ARM)

    def test_actual_early_setting_then_initialization_and_duplicate_refusal(self):
        uc = self.new()
        with value('2097152'):
            receipt = setting.configure_uc_tcg_before_init(uc)
            self.assertEqual(receipt['requestedBytes'], 2097152)
            self.assertIs(receipt['readbackPerformed'], False)
            self.assertIs(receipt['effectiveAllocationOrMemorySavingsMeasured'], False)
            # The getter is deliberately AFTER setting; it initializes here.
            self.assertEqual(uc.ctl_get_tcg_buffer_size(), 2097152)
            self.assertEqual(list(uc.mem_regions()), [])
            with self.assertRaises(ValueError):
                setting.configure_uc_tcg_before_init(uc)

    def test_original_api_error_is_not_a_silent_default(self):
        from unicorn import Uc, UcError, UC_ERR_ARG
        uc = self.new()
        with value('2097152'), patch.object(Uc, 'ctl_set_tcg_buffer_size', side_effect=UcError(UC_ERR_ARG)):
            with self.assertRaises(UcError):
                setting.configure_uc_tcg_before_init(uc)
        self.assertFalse(hasattr(uc, setting._MARKER))

    def test_wrong_version_is_refused_before_setting(self):
        import unicorn
        uc = self.new()
        with value('2097152'), patch.object(unicorn, '__version__', 'unreviewed'), self.assertRaises(ValueError):
            setting.configure_uc_tcg_before_init(uc)
        self.assertFalse(hasattr(uc, setting._MARKER))


if __name__ == '__main__':
    unittest.main()
