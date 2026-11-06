import json
import struct
import unittest
from pathlib import Path

from skill_attachments import (decode_ftable,adapt_socket_nodes,recover_skill_attachments,
                               EFFECT_TABLE,STATE_TABLE,REFERENCE_MODEL)
from resource_packs import DEFAULT_SOURCE,ResourceArchive
from bdae_convert import BDAE
from bdae_skin import read_nodes
from bdae_animation import BDAEAnimation


def table(columns,types,rows):
    schema=('CREATE TABLE `test` (\n'+',\n'.join('  `'+name+'` int' for name in columns)+'\n)\0').encode()
    schema+=b'\0'*(-len(schema)%4)
    ids_at=44+len(schema);types_at=ids_at+len(rows)*4;rows_at=types_at+len(types)+1
    stride=sum(6 if kind=='s' else 4 for kind in types);strings_at=rows_at+stride*len(rows)
    header=struct.pack('<8s9I',b'FTABLE\0\0',0x100000,len(rows),len(columns),ids_at,types_at,rows_at,stride,strings_at,0)
    records=bytearray();strings=bytearray()
    for row in rows:
        for name,kind in zip(columns,types):
            value=row[name]
            if kind=='s':
                raw=value.encode();records.extend(struct.pack('<IH',strings_at+len(strings),len(raw)));strings.extend(raw+b'\0')
            else: records.extend(struct.pack('<'+kind.replace('u','I'),value))
    return bytearray(header+schema+struct.pack('<'+'I'*len(rows),*[r[columns[0]] for r in rows])+types.encode()+b'\0'+records+strings)


def node(name,parent=-1):
    return {'name':name+'-node','aliases':[name],'parent':parent,'position':[.1,.2,.3],
            'quaternion':[0,0,0,1],'scale':[1.1,1.1,1.1]}


def nodes():
    reference=[node('Weapon_R'),node('Weapon_L'),node('Bip01_Spine1'),node('Dummy_R_Hand',0),node('Dummy_L_Hand',1),node('Dummy_Chest',2)]
    target=[node('Bip01_Spine1'),node('Weapon_L'),node('Weapon_R')]
    return reference,target


def sample_tables():
    effects=[]
    for id in [464,234,994,65]:
        effects.append({'id':id,'editName':'effect'+str(id),'pathName':'effects/test.beff','scaleX':0 if id!=65 else 0x43480000,
                        'scaleY':0 if id!=65 else 0x43160000,'scaleZ':0 if id!=65 else 0x43480000,
                        'missileType':int(id==234),'missileNum':int(id==234),'missileSpeed':0.0})
    states=[]
    for id in [728,729,1584,137]:
        states.append({'id':id,'editName':'state'+str(id),'casterRHandEff':464 if id==728 else 0,'casterLHandEff':464 if id==728 else 0,
                       'targetChestEff':234 if id==729 else 994 if id==1584 else 0,'targetGroundEff':65 if id==137 else 0,
                       'casterPreAnim':385 if id==137 else 0,'casterLoopAnim':43 if id==728 else 0})
    return {EFFECT_TABLE:table(list(effects[0]),'ussuuuuuf',effects),STATE_TABLE:table(list(states[0]),'usuuuuuu',states)}


class SkillAttachmentTests(unittest.TestCase):
    def test_ftable_exact_extents_ids_and_string_spans(self):
        data=table(['id','name','value'],'usf',[{'id':7,'name':'example','value':1.25}]);parsed=decode_ftable(data)
        self.assertEqual(parsed['rows'],[{'id':7,'name':'example','value':1.25}])
        custom=table(['map_id','name'],'us',[{'map_id':17,'name':'world'}])
        self.assertEqual(decode_ftable(custom,id_column='map_id')['rows'][0]['map_id'],17)
        rows_at=struct.unpack_from('<I',data,28)[0]
        bad=bytearray(data);struct.pack_into('<I',bad,rows_at,8)
        with self.assertRaisesRegex(ValueError,'ID index'):decode_ftable(bad)
        bad=bytearray(data);struct.pack_into('<I',bad,rows_at+4,len(data)+100)
        with self.assertRaisesRegex(ValueError,'string span'):decode_ftable(bad)
        for bad in [data[:40],data[:-1]]:
            with self.assertRaises(ValueError):decode_ftable(bad)
        bad=bytearray(data);struct.pack_into('<I',bad,32,999)
        with self.assertRaises(ValueError):decode_ftable(bad)

    def test_source_slots_and_packed_float_scale_become_explicit_metadata(self):
        source,target=nodes();tables=sample_tables()
        result=recover_skill_attachments(tables.__getitem__,source,target,[node('Dummy_Chest')])
        self.assertEqual(result['effects']['fireCast']['slots'],['casterRHand','casterLHand'])
        self.assertEqual(result['effects']['fireHit']['slot'],'targetChest')
        self.assertEqual(result['effects']['fireCast']['scale'],[1,1,1])
        self.assertEqual(result['effects']['frostHit']['scale'],[2,1.5,2])
        self.assertAlmostEqual(result['effects']['frostHit']['particleScale'],5.5/3)
        self.assertEqual(result['effects']['frostHit']['groundOffset'],.1)
        self.assertEqual(result['slots']['targetChest']['rotationMode'],'owner-facing')
        self.assertFalse(result['slots']['targetChest']['inheritRotation'])
        self.assertEqual(result['slots']['casterRHand']['rotationMode'],'dummy')
        self.assertEqual(result['models']['wolf']['nativeSockets']['Dummy_Chest']['node'],0)

    def test_socket_nodes_preserve_source_trs_and_target_parents_without_changing_skin_indices(self):
        source,target=nodes();before=json.dumps(target);new=adapt_socket_nodes(source,target)
        self.assertEqual([n['parent'] for n in new],[2,1,0])
        self.assertEqual(json.dumps(target),before)
        self.assertEqual(new[0]['scale'],[1.1]*3)
        self.assertTrue(new[0]['attachmentOrigin']['animated']);self.assertFalse(new[2]['attachmentOrigin']['animated'])
        self.assertEqual(adapt_socket_nodes(source,target+[node('Dummy_Chest')])[-1]['name'],'Dummy_L_Hand-node')

    def test_reject_missing_ambiguous_parents_and_mismatched_source_slot(self):
        source,target=nodes()
        with self.assertRaisesRegex(ValueError,'compatible'):adapt_socket_nodes(source,target[:2])
        with self.assertRaisesRegex(ValueError,'Ambiguous'):adapt_socket_nodes(source,target+[node('Weapon_R')])
        tables=sample_tables();parsed=decode_ftable(tables[STATE_TABLE]);row=parsed['rows'][0];row['casterLHandEff']=999
        tables[STATE_TABLE]=table(list(row),'usuuuuuu',parsed['rows'])
        with self.assertRaisesRegex(ValueError,'reference mismatch'):recover_skill_attachments(tables.__getitem__,source,target,[])

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(),'Original tables and models are local-only')
    def test_original_tables_model_dummies_and_animated_hand_channels(self):
        root=Path(__file__).resolve().parents[1];extracted=root/'game-data/extracted'
        reference=read_nodes(BDAE(extracted/REFERENCE_MODEL))
        player=read_nodes(BDAE(extracted/'model/npc/creature/humanoid/forest_elf/forest_elf.bdae'))
        wolf=read_nodes(BDAE(extracted/'model/npc/creature/beast/wolf/wolf.bdae'))
        result=recover_skill_attachments(ResourceArchive(DEFAULT_SOURCE/'tables.bin').read,reference,player,wolf)
        self.assertEqual([r['sourceStateIds'] for r in result['effects'].values()],[[728],[729],[1584],[137]])
        self.assertAlmostEqual(result['effects']['frostHit']['scale'][0],1.99968505859375)
        self.assertEqual(len(result['models']['player']['appendNodes']),3)
        self.assertIn('Dummy_Chest',result['models']['wolf']['nativeSockets'])
        channels=BDAEAnimation(extracted/'model/npc/character/elf/female/anim/animations.bdae').channels()
        names={c['node'] for c in channels if c['node'].startswith('Dummy_')}
        self.assertEqual(names,{'Dummy_R_Hand-node','Dummy_L_Hand-node'})


if __name__=='__main__': unittest.main()
