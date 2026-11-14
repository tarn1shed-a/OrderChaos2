"""Validate the actual envelope/reader controls without declaring decoded data."""
import unittest

from tutorial_script_initialfeed_probe import SO, SOURCE


@unittest.skipUnless(SO.is_file() and SOURCE.is_file(), 'Original InitialFeed and native library remain private')
class InitialFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_script_initialfeed_probe import run
        cls.r, _ = run()

    def test_original_envelope_success_and_distinct_validation_failures(self):
        r = self.r['fixtureControls']
        self.assertEqual(r['validEnvelopeReturn'], 0)
        self.assertTrue(r['payloadEqual'])
        self.assertEqual((r['wrongDigestReturn'], r['wrongLengthReturn']), (-4, -3))

    def test_both_real_header_branches_leave_the_supplied_file_unclassified(self):
        rows = self.r['originalReadHeaderControls']
        self.assertEqual([r['explicitFlag40000'] for r in rows], [False, True])
        self.assertEqual([r['firstFourBytesChanged'] for r in rows], [False, True])
        self.assertTrue(all(r['remainingBytesUnchanged'] and r['bytesReturned'] == 1084 for r in rows))
        self.assertTrue(all(r['completeEnvelopeReturn'] == -3 and r['appendedNulEnvelopeReturn'] == -3 for r in rows))
        self.assertFalse(self.r['actualInitialFeedDecoded'])
        self.assertFalse(self.r['actualContentClassifiedAsConfiguration'])
        self.assertFalse(self.r['sourceContract']['activeFactoryProviderPathsFlagsOrReadBytesObserved'])
        self.assertFalse(self.r['sourceContract']['runtimeKeyInitializationObserved'])
        self.assertFalse(self.r['networkOrSaveOrRuntimeChanged'])

    def test_original_key_is_file_backed_without_a_proven_external_dependency(self):
        from tutorial_script_initialfeed_key_probe import run
        r = run()
        self.assertTrue(r['key']['fileBackedInitialValueConfirmed'])
        self.assertEqual(r['key']['section'], '.data')
        self.assertEqual(r['dynamicRelocationDestinationsOverlappingKey'], [])
        self.assertEqual(r['dynamicRelocationAliasesIntoKey'], [])
        self.assertEqual([x['at'] for x in r['codeReferences']['materializedKeyAddresses']],
                         ['0xecbdc0', '0xecc03c'])
        self.assertTrue(r['nativeKeyAccessControl']['keyUnchanged'])
        self.assertTrue(r['nativeKeyAccessControl']['allObservedAccessesReadOnly'])
        self.assertFalse(r['conclusion']['differentRuntimeKeyProvenRequired'])
        self.assertFalse(r['conclusion']['actualInitialFeedDecoded'])
        self.assertFalse(r['networkOrSaveOrRuntimeChanged'])


if __name__ == '__main__':
    unittest.main()
