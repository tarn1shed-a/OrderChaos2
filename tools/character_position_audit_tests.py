"""Memory-only audit checks; optional reviewed source, never saved characters."""
import unittest
from pathlib import Path

from character_position_audit_probe import run_fixtures,REVIEWED,NODE


@unittest.skipUnless(Path(NODE).is_file(),'Node unavailable')
class PositionAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=run_fixtures(include_reviewed=False)

    def test_backup_precedes_only_resources_replacement_and_other_fields_survive(self):
        sample=self.report['returnSuccess'];self.assertEqual(sample['calls'],['backup','flush'])
        self.assertTrue(sample['onlyResourcesChanged']);self.assertTrue(sample['otherRoleUnchanged']);self.assertTrue(sample['updatedAtUnchanged'])

    def test_credentials_active_and_closing_sockets_and_failure_rollbacks(self):
        cases=self.report['returnNegatives'];self.assertEqual({c['mode']for c in cases},{'wrongToken','wrongId','wrongAnchor','active','closing','backupFailure','flushFailure','missingSupport'})
        self.assertTrue(all(c['rejected']and c['recordUnchanged']for c in cases))

    def test_target_helper_uses_y_plus_five_support_input_not_a_first_spawn_claim(self):
        target=self.report['entryTarget'];self.assertEqual(target['supportCalls'],[[-2594,-64,141]])
        self.assertEqual(target['position']['groundY'],135.72999572753906);self.assertFalse(self.report['realRoleFilesOpened']);self.assertFalse(self.report['networkOrResetRequestsSent'])


@unittest.skipUnless(Path(NODE).is_file()and(REVIEWED/'prototype/game/character-store.mjs').is_file(),'Private reviewed runtime is unavailable')
class ReviewedPositionConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=run_fixtures()

    def test_selected_reviewed_code_identities_match_manifest(self):
        self.assertEqual(len(self.report['reviewedSourceSHA256']),4);self.assertFalse(self.report['realRoleFilesOpened'])

    def test_falling_updates_horizontal_position_and_keeps_last_height_until_landing(self):
        cases={c['name']:c for c in self.report['savePosition']['cases']}
        self.assertEqual(cases['falling']['after'],{'x':44,'y':55,'groundY':172})
        self.assertEqual(cases['landed']['after']['groundY'],132);self.assertEqual(cases['swimming']['after']['groundY'],130)
        self.assertEqual(cases['nonfiniteHeight']['after']['groundY'],130)
        self.assertTrue(self.report['savePosition']['unchangedDoesNotTouch']);self.assertTrue(self.report['savePosition']['campUnchanged'])

    def test_record_identity_not_name_or_request_profession_owns_position(self):
        identity=self.report['identity'];self.assertTrue(identity['credentialRestoreIgnoresRequestNameAndProfession']);self.assertTrue(identity['duplicateNamesCreateDifferentIds']);self.assertTrue(identity['restoredFlag'])

    def test_literal_join_restoration_and_missing_dead_or_outside_cases(self):
        cases={c['name']:c for c in self.report['join']['cases']}
        self.assertEqual(cases['savedHeight']['calls'][-1],{'method':'restoreHeight','height':172})
        for name in ['savedNoHeight','dead','outsideBounds','fresh']:self.assertEqual([c['method']for c in cases[name]['calls']],['place'])
        self.assertEqual(cases['dead']['player']['x'],9);self.assertEqual(cases['outsideBounds']['player']['x'],9)
        self.assertEqual(cases['legacyHeightConsumer']['calls'][-1]['arguments'],[88,165,172.5])

    def test_close_of_old_socket_cannot_overwrite_new_session_position_or_remove_it(self):
        samples=self.report['sessions'];self.assertEqual(samples['closeCases'],[
            {'sameSocket':True,'calls':['savePosition','flush'],'identityStillActive':False},
            {'sameSocket':False,'calls':[],'identityStillActive':True}])
        self.assertTrue(samples['activeGuardRejectsSameIdAcrossRoomAndClosingState']);self.assertTrue(samples['otherIdAllowed'])


if __name__=='__main__':unittest.main()
