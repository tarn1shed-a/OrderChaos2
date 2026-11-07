import json
import unittest
from pathlib import Path
from native_cast import movement_policy,MOVEMENT_BITS
from skill_attachments import decode_ftable
from resource_packs import ResourceArchive,DEFAULT_SOURCE

ROOT=Path(__file__).resolve().parents[1]
class NativeCastTests(unittest.TestCase):
    def test_stop_and_moving_interrupt_are_separate_phase_specific_bits(self):
        for stage,(stop,interrupt) in MOVEMENT_BITS.items():
            self.assertEqual(movement_policy(1<<stop,stage),{'stopOnEnter':True,'interruptOnMove':False})
            self.assertEqual(movement_policy(1<<interrupt,stage),{'stopOnEnter':False,'interruptOnMove':True})
            self.assertEqual(movement_policy(0,stage,0x40),{'stopOnEnter':True,'interruptOnMove':False})
    def test_real_spell_words_do_not_treat_nonzero_as_a_global_interrupt_boolean(self):
        self.assertTrue(movement_policy(0x1250a4a1,1)['interruptOnMove'])
        self.assertFalse(movement_policy(0x21294264,1)['interruptOnMove'])
        self.assertFalse(movement_policy(0x12492492,2)['stopOnEnter'])
    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(),'Original spell tables remain local')
    def test_source_fields_and_packed_native_rune_movement_offset(self):
        a=ResourceArchive(DEFAULT_SOURCE/'tables.bin');d=decode_ftable(a.read('tables/skill_runes.tbl'))
        offset=0;offsets={}
        for name,kind in zip(d['columns'],d['physicalTypes']):offsets[name]=offset;offset+=8 if kind=='s' else 4
        self.assertEqual(offsets['moveinterrupt'],0x48);self.assertEqual(offsets['chantTime'],0x5c);self.assertEqual(offsets['channelTime'],0x64)
        rows={r['id']:r for r in d['rows']};self.assertEqual(rows[2368]['chantTime'],2000);self.assertEqual(rows[376]['coolDownTime'],20000)
        self.assertEqual(rows[360]['channelTime'],1500);self.assertEqual(rows[360]['channelIntervalTime'],300)
    @unittest.skipUnless((ROOT/'game-data/converted/gameplay/native.json').is_file(),'Converted spells remain local')
    def test_recovered_stage_clips_and_cooldowns_match_actual_model_without_alias_loss(self):
        p=json.loads((ROOT/'game-data/converted/gameplay/native.json').read_text());model=json.loads((ROOT/'game-data/converted/models/elf-female.json').read_text())
        spells=p['casting']['spells'];clips={c['name']:c for c in model['clips']}
        self.assertEqual(p['casting']['serverWaitExtraMs'],5000);self.assertEqual(spells['fireball']['sourceSkillId'],17)
        self.assertEqual(spells['frost_blast']['visuals']['2']['pre']['clip'],'skill_frost_blast')
        for s in spells.values():
            for v in s['visuals'].values():
                for k in ['pre','loop']:
                    if k in v:
                        c=clips[v[k]['clip']];self.assertEqual(c['sourceName'],v[k]['sourceRange'])
                        self.assertAlmostEqual(c['duration']*1000,v[k]['durationMs'])
                        self.assertGreater(v[k]['durationMs'],0)
        self.assertIn('skill_fireball',clips);self.assertIn('skill_frost_blast',clips)
if __name__=='__main__':unittest.main()
