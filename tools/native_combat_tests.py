import json,tempfile,unittest
from pathlib import Path
from native_combat import descriptor_fields,recover_combat,recover_protocol,DESCRIPTORS
from resource_packs import ResourceArchive,DEFAULT_SOURCE,index
ROOT=Path(__file__).resolve().parents[1]

class NativeCombatTests(unittest.TestCase):
    def test_descriptor_numbers_types_and_rejection_of_truncation(self):
        raw=b'\x0a\x04Test\x12\x09\x0a\x01x\x18\x01\x20\x02\x28\x0d'
        self.assertEqual(descriptor_fields(raw),{'name':'Test','fields':[{'name':'x','number':1,'label':2,'type':13}]})
        for broken in [raw[:-1],b'\x80'*11,b'\x0a\x7fTest',b'\x00',b'\x01',b'']:
            with self.assertRaises(ValueError):descriptor_fields(broken)
        with self.assertRaises(ValueError):descriptor_fields(raw+raw[6:])

    @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').exists(),'Native sample stays local')
    def test_pinned_native_protocol_distinguishes_server_damage_and_buff_lifetimes(self):
        from analyze_native_resources import NativeImage
        image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());p=recover_protocol(image)
        self.assertEqual(set(p),set(DESCRIPTORS))
        damage={f['name']:f for f in p['SMSG_Skill_DmgLog']['fields']}
        self.assertEqual((damage['attack_dmg']['number'],damage['attack_dmg']['type']),(6,1))
        self.assertEqual((damage['targetCurHp']['number'],damage['targetCurHp']['type']),(8,5))
        fields={f['name']:f['number'] for f in p['SMSG_Skill_AddBuff']['fields']}
        self.assertEqual((fields['remain_duration'],fields['duration_max'],fields['stack_count']),(5,6,7))
        class Changed:
            def read(self,a,n):return bytes(n)
        with self.assertRaisesRegex(ValueError,'retrace'):recover_protocol(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').exists(),'Original combat tables stay local')
    def test_exact_selected_records_descriptions_display_coefficients_and_base_stats(self):
        # Resolve archive namespaces exactly like the bounded builder.
        rows=index(DEFAULT_SOURCE);archives={};wanted={'tables.bin','ui_icon_1.bin','ui_icon_2.bin'}
        def extract(path):
            candidates=[r for r in rows if r['path']==path and r['pack'] in wanted]
            self.assertEqual(len(candidates),1,path);pack=candidates[0]['pack']
            if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
            return archives[pack].read(path)
        with tempfile.TemporaryDirectory() as temp:
            p=recover_combat(extract,temp)
            self.assertEqual(p['auras']['burn']['id'],22);self.assertEqual(p['auras']['freeze']['runeId'],80)
            self.assertEqual(p['auras']['freeze']['visuals']['buffState'],136)
            self.assertEqual(p['spells']['fireball']['displayCoefficients']['dot_hitCount'],5)
            self.assertEqual(p['spells']['arcane_missile']['damageAttribute'],16)
            self.assertEqual(p['spells']['frost_blast']['events'][0]['scriptFunc'],'Skill94_OnSkillHit')
            self.assertEqual(p['baseAttributes'][0]['hp_mg'],314)
            self.assertEqual(len(p['baseAttributes']),90)
            self.assertEqual(len(list((Path(temp)/'ui').glob('buff-*.png'))),4)
            self.assertTrue(any('candidate' in s for s in p['limitations']))

if __name__=='__main__':unittest.main()
