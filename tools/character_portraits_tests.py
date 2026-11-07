import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from resource_packs import ResourceArchive,DEFAULT_SOURCE
from character_portraits import (decode_abc_metadata,decode_gauge_abc,source_portrait_slot,
    recover_character_portraits,_head,GAUGE_SWF,MODEL_TABLE,DISPLAY_TABLE,PLAYER_MODEL,WOLF_MODEL)


def u30(value):
    output=bytearray()
    while value>=128:output.append((value&127)|128);value>>=7
    output.append(value);return bytes(output)


def abc(identifiers,component='Model3D'):
    strings=['','Common.gluicEx.components.ui',*dict.fromkeys([component,*identifiers])]
    pool=b'\x01\x01\x01'+u30(len(strings))
    for value in strings[1:]:
        raw=value.encode('utf-8');pool+=u30(len(raw))+raw
    pool+=b'\x02\x16\x01\x01\x02\x07\x01'+u30(strings.index(component))
    return struct.pack('<HH',16,46)+pool+b'\0'


def rect(bounds):
    width=max(max(value.bit_length()+1 for value in bounds),1)
    bits=f'{width:05b}'+''.join(f'{value&((1<<width)-1):0{width}b}' for value in bounds)
    bits+='0'*(-len(bits)%8)
    return int(bits,2).to_bytes(len(bits)//8,'big')


def tag(kind,payload=b''):
    return struct.pack('<H',(kind<<6)|min(len(payload),63))+(struct.pack('<I',len(payload)) if len(payload)>=63 else b'')+payload


def swf(identifiers,component='Model3D'):
    matrix=b'\x02\0'
    def place(child,name=None):
        return tag(26,bytes([0x26 if name else 6])+struct.pack('<HH',1,child)+matrix+(name.encode()+b'\0' if name else b''))
    def sprite(identifier,placement):
        return tag(39,struct.pack('<HH',identifier,1)+placement+tag(1)+tag(0))
    body=rect([0,1,0,1])+struct.pack('<HH',24*256,1)
    body+=tag(2,struct.pack('<H',6)+rect([0,960,0,960])+b'\x01\0\x66\0\0\0\0\0')
    body+=sprite(7,place(6))+sprite(8,place(7,'objImage'))+sprite(114,place(8,'playerIcon'))
    body+=tag(76,struct.pack('<HH',1,114)+b'Window_PlayerGauges\0')
    body+=tag(300,struct.pack('<I',1)+b'\0'+abc(identifiers,component))+tag(0)
    return b'FWS\x0a'+struct.pack('<I',len(body)+8)+body


def ftable(fields,rows):
    schema=('CREATE TABLE `test` (\n'+',\n'.join(f' `{name}` int' for name,kind in fields)+'\n)\0').encode()
    ids_at=44+len(schema);types_at=ids_at+len(rows)*4;rows_at=types_at+len(fields)+1
    stride=sum(6 if kind=='s' else 4 for name,kind in fields);pool_at=rows_at+len(rows)*stride
    records=bytearray();pool=bytearray()
    for row in rows:
        for name,kind in fields:
            if kind=='s':
                raw=row[name].encode();records+=struct.pack('<IH',pool_at+len(pool),len(raw));pool+=raw+b'\0'
            else:records+=struct.pack('<I',row[name])
    return (b'FTABLE\0\0'+struct.pack('<9I',0x100000,len(rows),len(fields),ids_at,types_at,rows_at,stride,pool_at,0)
            +schema+struct.pack('<'+'I'*len(rows),*(row[fields[0][0]] for row in rows))
            +''.join(kind for name,kind in fields).encode()+b'\0'+records+pool)


def fixtures():
    return {
        GAUGE_SWF:swf(['playerIcon','Model3D','targetGuid','TARGET_TYPE_PLAYER','Hero_GetTargetInfo','TYPE_MODEL','initWithGuid']),
        'ui/Flash/Gauges2.swf':swf(['vehicleIcon','Model3D','Hero_GetHeroInfo','TYPE_MODEL','initWithGuid']),
        'ui/Flash/EnemyGauges.swf':swf(['m_enemyIcon','Icon','Hero_GetTargetInfo',
            'ui/icons/userinterface/elite_head.png','ui/icons/userinterface/dungeon_elite_head.png'],'Icon'),
        MODEL_TABLE:ftable([('ID','u'),('ModelPath','s')],[
            {'ID':335,'ModelPath':PLAYER_MODEL},{'ID':12,'ModelPath':'model/npc/creature/beast/wolf/wolf_skin.bdae'}]),
        DISPLAY_TABLE:ftable([('ID','u'),('Model','u'),('Icon','s')],[{'ID':1,'Model':335,'Icon':''}]),
        PLAYER_MODEL:b'fake-player-model',WOLF_MODEL:b'fake-wolf-model',
    }


def nodes(alias):
    return [{'name':'root','aliases':[],'parent':-1,'position':[0,0,0],'quaternion':[0,0,0,1],'scale':[1,1,1]},
            {'name':alias+'-node','aliases':[alias],'parent':0,'position':[0,1,0],'quaternion':[0,0,0,1],'scale':[1,1,1]}]


class CharacterPortraitTests(unittest.TestCase):
    def test_bounded_abc_pool_identifies_model3d_without_executing_or_inventing_traits(self):
        raw=abc(['playerIcon','initWithGuid'])
        result=decode_abc_metadata(raw)
        self.assertIn('Common.gluicEx.components.ui::Model3D',result['multinames'])
        self.assertIn('playerIcon',result['strings'])
        self.assertEqual(result['unparsedMethodBytes'],1)
        self.assertIn('unresolved',result['proofScope'])
        for invalid in (raw[:8],b'\0\0\0\0'+raw[4:],struct.pack('<HH',16,46)+b'\xff'*6):
            with self.assertRaises(ValueError):decode_abc_metadata(invalid)

    def test_named_slot_chain_proves_dynamic_solid_placeholder_instead_of_static_bitmap(self):
        source,_=decode_gauge_abc(swf(['playerIcon','Model3D']))
        proof=source_portrait_slot(source)
        self.assertEqual(proof['spriteIds'],[8,7]);self.assertEqual(proof['placeholderShapeId'],6)
        self.assertEqual(proof['placeholderPixels'],[48,48]);self.assertFalse(proof['staticBitmapPortrait'])
        del source['records'][7]
        with self.assertRaises(ValueError):source_portrait_slot(source)

    def test_head_binding_keeps_wolf_bip001_distinct_and_rejects_ambiguous_aliases(self):
        self.assertEqual(_head(nodes('Bip001_Head'),'Bip001_Head')['headNodeIndex'],1)
        with self.assertRaises(ValueError):_head(nodes('Bip001_Head'),'Bip01_Head')
        data=nodes('Bip01_Head');data.append(dict(data[1]))
        with self.assertRaises(ValueError):_head(data,'Bip01_Head')

    def test_profile_preserves_role_and_model_identity_limits(self):
        source=fixtures()
        with tempfile.TemporaryDirectory() as td,mock.patch('character_portraits._model_nodes',side_effect=lambda raw:
                nodes('Bip01_Head' if raw==source[PLAYER_MODEL] else 'Bip001_Head')):
            profile=recover_character_portraits(source.__getitem__,td)
            self.assertEqual(profile['format'],'oc2-character-portraits-v1')
            self.assertEqual(profile['models']['player']['sourceModelTableIds'],[335])
            self.assertEqual(profile['models']['targetWolf']['sourceModelTableIds'],[])
            self.assertEqual(profile['models']['targetWolf']['headNode'],'Bip001_Head')
            self.assertEqual(profile['models']['targetWolf']['mode'],'source-model-web-framing')
            self.assertFalse(profile['provenance']['swfExecution'])
            self.assertIn('elite/status',profile['sourceComponents']['enemyTarget']['role'])
            self.assertEqual(json.loads((Path(td)/'ui/portraits.json').read_text())['models'],profile['models'])

    def test_missing_model3d_or_changed_static_icon_mapping_does_not_silently_export(self):
        for path,before,after in [(GAUGE_SWF,b'Model3D',b'Model2D'),(MODEL_TABLE,b'forest_elf.bdae',b'forest_bad.bdae')]:
            source=fixtures();self.assertEqual(len(before),len(after));source[path]=source[path].replace(before,after)
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):recover_character_portraits(source.__getitem__,td)
                self.assertFalse((Path(td)/'ui/portraits.json').exists())
        source=fixtures();source[DISPLAY_TABLE]=ftable([('ID','u'),('Model','u'),('Icon','s')],
            [{'ID':1,'Model':335,'Icon':'different.png'}])
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'static icon'):recover_character_portraits(source.__getitem__,td)

    @unittest.skipUnless(all((DEFAULT_SOURCE/name).is_file() for name in ('ui.bin','tables.bin','res_npc.bin')),
                         'Original SWF/tables/models remain local-only')
    def test_real_gauge_pools_named_slot_model335_and_exact_head_nodes(self):
        packs={name:ResourceArchive(DEFAULT_SOURCE/name) for name in ('ui.bin','tables.bin','res_npc.bin')}
        def extract(path):
            return packs['ui.bin' if path.startswith('ui/') else 'tables.bin' if path.startswith('tables/') else 'res_npc.bin'].read(path)
        with tempfile.TemporaryDirectory() as td:
            profile=recover_character_portraits(extract,td)
            self.assertEqual(profile['models']['player']['headNodeIndex'],28)
            self.assertEqual(profile['models']['targetWolf']['headNodeIndex'],16)
            self.assertEqual(profile['models']['player']['sourceModelTableIds'],[335])
            self.assertEqual(profile['models']['targetWolf']['sourceModelTableIds'],[])
            self.assertEqual(profile['sourceComponents']['selectedPlayer']['namedSlot']['spriteIds'],[8,7])
            self.assertIn('web adaptation',profile['provenance']['cameraAndLighting'])


if __name__=='__main__':unittest.main()
