import hashlib
import io
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from skill_icons import (decode_localized_names, recover_skill_icons, SELECTION,
    PROTO_TABLE, RUNE_TABLE, STATE_TABLE, EFFECT_TABLE, NAME_TABLES, ICON_PACK)


def ftable(fields, rows, localized=False):
    schema_fields = [('ID', 'u'), ('EN', 's'), ('SC', 's')] if localized else fields
    schema = ('CREATE TABLE `test` (\n' + ',\n'.join(
        f'  `{name}` int' for name, _ in schema_fields) + '\n)\0').encode()
    count = len(rows)
    ids_at = 44 + len(schema)
    types_at = ids_at + count * 4
    rows_at = types_at + len(fields) + 1
    stride = sum(6 if kind == 's' else 4 for _, kind in fields)
    pool_at = rows_at + count * stride
    records, pool = bytearray(), bytearray()
    for row in rows:
        for name, kind in fields:
            value = row[name]
            if kind == 's':
                raw = value.encode('utf-8')
                size = len(raw) + 1 if localized and raw else len(raw)
                records.extend(struct.pack('<IH', pool_at + len(pool), size))
                pool.extend(raw + b'\0')
            else:
                records.extend(struct.pack('<I', value))
    header = b'FTABLE\0\0' + struct.pack('<9I', 0x100000, count, len(fields),
        ids_at, types_at, rows_at, stride, pool_at, 0)
    return header + schema + struct.pack('<' + 'I' * count,
        *(row[fields[0][0]] for row in rows)) + ''.join(k for _, k in fields).encode() + b'\0' + records + pool


def fixtures():
    states, effects, protos, runes = {}, {}, [], []
    slots = ['casterRHandEff', 'casterLHandEff', 'targetChestEff', 'targetGroundEff']
    state_fields = ['chantState', 'releaseState','channellingState']
    for expected in SELECTION.values():
        protos.append({'skillId': expected['skillId'], 'editName': expected['editName'], 'rune0': expected['runeId']})
        rune = {'id': expected['runeId'], 'icon': expected['icon'], 'nameStrId': expected['nameStrId'],
                **{field: 0 for field in state_fields}}
        for field, state_id, links in expected['links']:
            rune[field] = state_id
            state = states.setdefault(state_id, {'id': state_id, **{slot: 0 for slot in slots}})
            for slot, effect_id, path in links:
                state[slot] = effect_id
                effects[effect_id] = {'id': effect_id, 'pathName': path}
        runes.append(rune)
    result = {
        PROTO_TABLE: ftable([('skillId','u'),('editName','s'),('rune0','u')], protos),
        RUNE_TABLE: ftable([('id','u'),('icon','s'),('nameStrId','u'),
                            *[(field,'u') for field in state_fields]], runes),
        STATE_TABLE: ftable([('id','u'),*[(slot,'u') for slot in slots]], list(states.values())),
        EFFECT_TABLE: ftable([('id','u'),('pathName','s')], list(effects.values())),
    }
    for locale, (path, _) in NAME_TABLES.items():
        result[path] = ftable([('ID','u'),('text','s')], [
            {'ID':3263,'text':'奥术飞弹' if locale=='zh' else 'Arcane Missile'},
            {'ID':3279,'text':'炎爆术' if locale=='zh' else 'Fireburst'},
            {'ID':3287,'text':'霜爆术' if locale=='zh' else 'Arctic Blast'},
        ], localized=True)
    for index, expected in enumerate(SELECTION.values()):
        output = io.BytesIO()
        Image.new('RGBA',(96,96),(220,index*120,10,255)).save(output,format='PNG')
        result['ui/icons/'+expected['icon']] = output.getvalue()
    return result


class SkillIconTests(unittest.TestCase):
    def test_localized_rows_use_physical_two_columns_and_include_nul_length(self):
        data = ftable([('ID','u'),('text','s')], [
            {'ID':10,'text':'火球'}, {'ID':11,'text':''}, {'ID':12,'text':'Arctic Blast'}], localized=True)
        decoded = decode_localized_names(data,'SC')
        self.assertEqual(decoded['values'],{10:'火球',11:'',12:'Arctic Blast'})
        self.assertEqual(decoded['verification']['rowStride'],10)
        self.assertEqual(decoded['verification']['sourceSHA256'], hashlib.sha256(data).hexdigest())
        with self.assertRaises(ValueError):
            decode_localized_names(data,'FR')

    def test_localization_rejects_bad_index_bounds_utf8_and_terminator(self):
        raw = ftable([('ID','u'),('text','s')],[{'ID':10,'text':'火球'}], localized=True)
        _, _, _, ids, _, rows, _, pool, _ = struct.unpack_from('<9I', raw, 8)
        variants=[]
        data=bytearray(raw);struct.pack_into('<I',data,ids,11);variants.append(data)
        data=bytearray(raw);struct.pack_into('<I',data,rows+4,pool-1);variants.append(data)
        data=bytearray(raw);struct.pack_into('<H',data,rows+8,65535);variants.append(data)
        data=bytearray(raw);data[-1]=65;variants.append(data)
        data=bytearray(raw);data[pool]=0;variants.append(data)
        data=bytearray(raw);data[pool]=255;variants.append(data)
        for data in variants:
            with self.subTest(data=data[:44]):
                with self.assertRaises(ValueError):
                    decode_localized_names(data,'SC')

    def test_verified_source_links_copy_full_png_bytes_without_guessing_atlas(self):
        source=fixtures()
        with tempfile.TemporaryDirectory() as td:
            profile=recover_skill_icons(source.__getitem__,td)
            self.assertEqual(profile['format'],'oc2-skill-icons-v1')
            self.assertEqual(set(profile['icons']),{'fireball','frost_blast','arcane_missile'})
            self.assertFalse(profile['provenance']['completeOriginalPlayerSkills'])
            fire=profile['icons']['fireball'];ice=profile['icons']['frost_blast']
            self.assertEqual(fire['sourceSkill']['id'],17)
            self.assertEqual(fire['sourceRune']['id'],68)
            self.assertEqual(fire['sourceNames']['zh']['value'],'炎爆术')
            self.assertEqual(ice['effectLinks'][0]['stateId'],137)
            self.assertEqual(ice['effectLinks'][0]['effects'][0]['effectId'],65)
            self.assertEqual(ice['sourceNames']['en']['value'],'Arctic Blast')
            for key, icon in profile['icons'].items():
                output=Path(td)/icon['url'].removeprefix('/assets/')
                self.assertEqual(output.read_bytes(),source[icon['sourcePath']])
                self.assertEqual(icon['sourceRect'],[0,0,96,96])
                self.assertEqual(icon['sourcePack'],ICON_PACK)
                self.assertEqual(icon['sourceSHA256'],hashlib.sha256(output.read_bytes()).hexdigest())

    def test_recovery_refuses_icon_or_effect_chain_mismatch(self):
        for path, old, new in [(RUNE_TABLE,b'skill/fire_blast.png',b'skill/fake_blast.png'),
                              (EFFECT_TABLE,b'scorcher_default_cast_hand_loop',b'scorcher_default_fake_hand_loop')]:
            source=fixtures();self.assertIn(old,source[path]);source[path]=source[path].replace(old,new)
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(ValueError,'reference mismatch'):
                    recover_skill_icons(source.__getitem__,td)
                self.assertFalse((Path(td)/'ui/skill-icons.json').exists())

    def test_recovery_refuses_unverified_image_dimensions(self):
        source=fixtures();output=io.BytesIO()
        Image.new('RGBA',(48,48)).save(output,format='PNG')
        source['ui/icons/skill/fire_blast.png']=output.getvalue()
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'dimensions'):
                recover_skill_icons(source.__getitem__,td)

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file() and
                         (DEFAULT_SOURCE/ICON_PACK).is_file(),'Original tables/icons remain local-only')
    def test_real_crc_checked_tables_and_full_resolution_pngs(self):
        packs={name:ResourceArchive(DEFAULT_SOURCE/name) for name in ('tables.bin',ICON_PACK)}
        def extract(path):
            return packs[ICON_PACK if path.startswith('ui/') else 'tables.bin'].read(path)
        with tempfile.TemporaryDirectory() as td:
            profile=recover_skill_icons(extract,td)
            self.assertEqual(profile['icons']['fireball']['sourceNames']['zh']['value'],'炎爆术')
            self.assertEqual(profile['icons']['frost_blast']['sourceNames']['zh']['value'],'霜爆术')
            for icon in profile['icons'].values():
                original=extract(icon['sourcePath'])
                output=(Path(td)/icon['url'].removeprefix('/assets/')).read_bytes()
                self.assertEqual(original,output)
                with Image.open(io.BytesIO(output)) as image:
                    self.assertEqual(image.size,(96,96));self.assertEqual(image.mode,'RGBA')


if __name__=='__main__':
    unittest.main()
