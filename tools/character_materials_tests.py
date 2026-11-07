import copy
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bdae_convert import BDAE
from character_materials import (read_material_record, recover_color_choices,
    recover_character_materials, COLOR_TABLE, VERTEX_SHADER, FRAGMENT_SHADER,
    SCALARS, SHADER_SHA256)
from resource_packs import ResourceArchive, DEFAULT_SOURCE
from skill_icons_tests import ftable

MODEL = 'model/test-body.bdae'
EFFECT = 'lt_cull_pal_normal_skin_solid.bdae'


def source_model(*, bad_scalar=False, bad_sampler=False):
    raw = bytearray(8192)
    raw[:8] = b'BRES\xfe\xff\0\0'
    struct.pack_into('<II', raw, 8, 64, len(raw)); struct.pack_into('<Q', raw, 40, 64)
    pool = 2300
    def string(value):
        nonlocal pool
        at = pool; value = value.encode()+b'\0'; raw[at:at+len(value)] = value; pool += len(value); return at
    struct.pack_into('<Q', raw, 64, string('0,0,0,946'))
    def section(offset, count, table): struct.pack_into('<Ii', raw, 64+offset, count, table-(64+offset+4))
    section(148, 7, 768); section(172, 1, 512)
    for offset,value in [(0,'body'),(8,EFFECT),(16,'#'+Path(EFFECT).stem+'-fx')]: struct.pack_into('<Q',raw,512+offset,string(value))
    fields = ['texture','normalMap','maskMap','diffusePal','specularPal','specularPalBack','skinColorMask',*SCALARS,
              Path(EFFECT).stem+'-fx-profile_GLES2/CurrentTechnique']
    struct.pack_into('<Ii',raw,512+32,len(fields),1024-(512+36))
    for index,field in enumerate(fields):
        prop,value = 1024+index*32,1600+index*32
        struct.pack_into('<Q',raw,prop,string(field)); struct.pack_into('<II',raw,prop+16,17 if index<7 else 8 if field in SCALARS else 28,1)
        struct.pack_into('<i',raw,prop+28,value-(prop+28))
        if index<7:
            target = 768+index*32
            struct.pack_into('<i',raw,value,target-value)
            filename = '../outside.tga' if bad_sampler and index==0 else field+'.tga'
            struct.pack_into('<Q',raw,target+16,string('texture/'+filename))
        elif field in SCALARS: struct.pack_into('<f',raw,value,float('nan') if bad_scalar and field=='ambientIntensity' else .7)
        else: struct.pack_into('<I',raw,value,2)
    return bytes(raw)


def source_effect():
    raw=bytearray(2048);raw[:8]=b'BRES\xfe\xff\0\0'
    struct.pack_into('<II',raw,8,64,len(raw));struct.pack_into('<Q',raw,40,64);struct.pack_into('<Q',raw,64,400)
    raw[400:412]=b'0,0,0,946\0\0\0'
    struct.pack_into('<Ii',raw,64+164,1,512-(64+168));struct.pack_into('<Q',raw,512,600)
    values=[Path(EFFECT).stem+'-fx',VERTEX_SHADER,FRAGMENT_SHADER,'RIM_LIGHT','SKIN_COLOR']
    at=600
    for value in values:
        encoded=value.encode()+b'\0';raw[at:at+len(encoded)]=encoded;at+=len(encoded)
    return bytes(raw)


def color_table():
    return ftable([('ID','u'),('Elf_Female_Hair','s'),('Elf_Female_Skin','s')],
        [{'ID':index,'Elf_Female_Hair':'16771561,16771561','Elf_Female_Skin':'0,0' if index==6 else '15335401,13155248'} for index in range(1,7)])


class CharacterMaterialTests(unittest.TestCase):
    def test_typed_source_material_properties_are_checked_without_replacing_missing_maps(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'model.bdae';path.write_bytes(source_model())
            record=read_material_record(BDAE(path),'body')
            self.assertEqual(record['effectPath'],EFFECT);self.assertEqual(len(record['samplers']),7)
            self.assertAlmostEqual(record['scalars']['ambientIntensity'],.7)
            for raw,pattern in [(source_model(bad_scalar=True),'scalar'),(source_model(bad_sampler=True),'texture path')]:
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,pattern): read_material_record(BDAE(path),'body')

    def test_color_pairs_keep_secondary_value_uninterpreted_and_disable_zero_skin(self):
        colors,proof=recover_color_choices(color_table())
        self.assertEqual(proof['rows'],6)
        self.assertEqual(colors['skin']['color1']['sourcePair'],[15335401,13155248])
        self.assertEqual(colors['skin']['color1']['selection'],'first-value-web-selection')
        self.assertFalse(colors['skin']['color6']['enabled']);self.assertTrue(colors['hair']['color6']['enabled'])
        invalid=color_table().replace(b'15335401,13155248',b'99999999,13155248')
        with self.assertRaisesRegex(ValueError,'RGB24'): recover_color_choices(invalid)

    def test_profile_links_source_identity_effect_and_shader_version_and_exports_only_metadata(self):
        source={MODEL:source_model(),EFFECT:source_effect(),COLOR_TABLE:color_table(),VERTEX_SHADER:b'test vertex evidence',FRAGMENT_SHADER:b'test fragment evidence'}
        hashes={key:hashlib.sha256(source[key]).hexdigest() for key in (VERTEX_SHADER,FRAGMENT_SHADER)}
        data={'materials':[{'name':'body','sourceModel':MODEL}]}
        with mock.patch.dict(SHADER_SHA256,hashes):
            profile=recover_character_materials(source.__getitem__,data,lambda path:'/assets/textures/'+Path(path).stem+'.png')
            material=profile['materials'][0]
            self.assertEqual(profile['format'],'oc2-character-materials-v1');self.assertFalse(material['doubleSided']);self.assertEqual(material['alphaTest'],0)
            self.assertEqual(profile['defaults']['neutralIdentityEye'],[0,0,0]);self.assertFalse(profile['defaults']['nativeColorDefaultsRecovered'])
            self.assertEqual(len(material['samplers']),7)
            source[FRAGMENT_SHADER]+=b'changed'
            with self.assertRaisesRegex(ValueError,'shader formula version'): recover_character_materials(source.__getitem__,data,lambda path:'/assets/map.png')
        self.assertEqual(data,{'materials':[{'name':'body','sourceModel':MODEL}]})

    @unittest.skipUnless(all((DEFAULT_SOURCE/name).is_file() for name in ('res_npc.bin','res_item.bin','res.bin','tables.bin')), 'Original materials stay local-only')
    def test_real_base_gear_and_hair_materials_reference_crc_checked_source_scalars_and_shaders(self):
        paths = [
            ('model/npc/character/elf/female/oc2_elf_f_body_01.bdae','res_npc.bin'),
            ('model/item/armor/8_underwear/oc2_elf_f_underwear_bra.bdae','res_item.bin'),
            ('model/item/armor/8_underwear/oc2_elf_f_underwear_briefs.bdae','res_item.bin'),
            ('model/item/armor/3_chest/oc2_elf_f_light_1_faith_chest.bdae','res_item.bin'),
            ('model/item/armor/5_leg/oc2_elf_f_light_1_faith_leg.bdae','res_item.bin'),
            ('model/item/armor/6_feet/oc2_elf_f_light_1_faith_feet.bdae','res_item.bin'),
            ('model/item/weapon/1_sword/oc2_sword_10_august_spatha/oc2_sword_10_august_spatha.bdae','res_item.bin'),
            ('model/item/armor/0_head/hair_elf_female_000_001.bdae','res_item.bin'),
        ]
        # Hair path is discovered in the exact archive index below, not guessed.
        packs={name:ResourceArchive(DEFAULT_SOURCE/name) for name in ('res_npc.bin','res_item.bin','res.bin','tables.bin')}
        from resource_packs import index
        hair=[entry['path'] for entry in index(DEFAULT_SOURCE) if entry['pack']=='res_item.bin' and Path(entry['path']).name=='hair_elf_female_000_001.bdae']
        self.assertEqual(len(hair),1);paths[-1]=(hair[0],'res_item.bin')
        def extract(path):
            pack = 'tables.bin' if path.startswith('tables/') else 'res_item.bin' if path.startswith('model/item/') else 'res_npc.bin' if path.startswith('model/') else 'res.bin'
            return packs[pack].read(path)
        data={'materials':[]}
        with tempfile.TemporaryDirectory() as td:
            for source,pack in paths:
                path=Path(td)/'model.bdae';path.write_bytes(packs[pack].read(source))
                for material in BDAE(path).parse()['materials']:
                    material=copy.deepcopy(material);material['sourceModel']=source;data['materials'].append(material)
            profile=recover_character_materials(extract,data,lambda path:'/assets/textures/'+Path(path).stem+'.png')
        body=profile['materials'][0]
        self.assertAlmostEqual(body['scalars']['ambientIntensity'],.7)
        self.assertAlmostEqual(body['scalars']['specularIntensity'],.6)
        skirt=next(material for material in profile['materials'] if material['sourceModel'].endswith('faith_leg.bdae'))
        self.assertTrue(skirt['doubleSided']);self.assertEqual(skirt['alphaTest'],0)
        self.assertEqual(profile['materials'][-1]['alphaTest'],.5);self.assertTrue(profile['materials'][-1]['doubleSided'])
        self.assertFalse(profile['provenance']['nativeColorPairApplicationRecovered'])
        self.assertEqual(profile['colors']['hair']['color1']['sourcePair'],[16771561,16771561])


if __name__=='__main__': unittest.main()
