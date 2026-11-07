import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from character_hair import (BASE_MODEL, FEATURE_TABLE, hair_model_path,
    recover_character_hair, validate_feature_row)
from resource_packs import ResourceArchive, DEFAULT_SOURCE
from skill_icons_tests import ftable


def feature():
    return {'id': 4, 'race': 1, 'gender': 1, 'face': 3, 'hair': 3,
            'hair_begin': 1, 'hair_color': 6, 'skin_color': 6}


def fixtures():
    result = {FEATURE_TABLE: ftable([(key, 'u') for key in feature()], [feature()])}
    for index in (1, 2, 3): result[hair_model_path(index)] = bytes([index])
    return result


def body():
    return {'source': BASE_MODEL, 'meshes': [{'name': 'body-mesh'}], 'materials': [{'name': 'body'}],
            'rig': {'nodes': [{'name': 'Head', 'aliases': ['Bone34'], 'parent': -1}], 'skins': []}}


class FakeModel:
    def __init__(self, path): self.index = Path(path).read_bytes()[0]
    def parse(self):
        return {'meshes': [{'name': 'source-hair-mesh', 'positions': [1, 2, 3], 'material': 0,
            'groups': [{'start': 0, 'count': 3, 'material': 0}]}],
            'materials': [{'name': 'source-hair-material',
                'diffuse': f'texture/hair_elf_female_000_{self.index:03d}_d.tga',
                'samplers': {'skinColorMask': 'texture/hair_all_race_m.tga'}}]}


def skin(reader, model, *, external_nodes):
    return {'nodes': external_nodes, 'skins': [{'mesh': 0, 'boneNodes': [0], 'skinWeights': [1.0],
        'skinIndices': [0], 'inverseBindMatrices': [[1.0]*16],
        'verification': {'maximumRestBindShapeError': 0.0}}]}


class CharacterHairTests(unittest.TestCase):
    def test_feature_ranges_and_native_filename_recipe_keep_face_and_hair_indices_distinct(self):
        self.assertEqual(validate_feature_row([feature()])['hair_begin'], 1)
        self.assertEqual(hair_model_path(2), 'model/item/armor/7_hair/hair_elf_female_000_002.bdae')
        for value in (0, 4, -1):
            with self.assertRaises(ValueError): hair_model_path(value)
        with self.assertRaises(ValueError): hair_model_path(1, face_index=1)
        for rows in ([], [feature(), feature()], [{**feature(), 'hair_begin': 0}], [{**feature(), 'gender': 0}]):
            with self.assertRaises(ValueError): validate_feature_row(rows)

    def test_profiles_keep_original_skin_and_material_identity_without_always_visible_hair(self):
        source = fixtures(); result = body(); original = copy.deepcopy(result)
        with mock.patch('character_hair.BDAE', FakeModel), mock.patch('character_hair.recover_skin', skin):
            profile = recover_character_hair(source.__getitem__, result)
        self.assertEqual(set(profile['styles']), {'hair1', 'hair2', 'hair3'})
        self.assertEqual(profile['allMeshIndices'], [1, 2, 3]); self.assertEqual(profile['defaultStyle'], 'hair1')
        self.assertEqual(result['meshes'][0], original['meshes'][0])
        for index in (1, 2, 3):
            entry = profile['styles'][f'hair{index}']
            self.assertEqual(entry['meshIndices'], [index]); self.assertEqual(entry['materialIndices'], [index])
            self.assertEqual(result['materials'][index]['sourceModel'], hair_model_path(index))
            self.assertEqual(result['rig']['skins'][index-1]['skinWeights'], [1.0])
            self.assertEqual(result['rig']['skins'][index-1]['mesh'], index)
        self.assertFalse(profile['provenance']['nativeFilenameRecipe']['nativeExecution'])

    def test_failed_later_source_or_wrong_body_cannot_partially_append_hair(self):
        source = fixtures(); source[hair_model_path(3)] = b'\x04'
        result = body(); before = copy.deepcopy(result)
        with mock.patch('character_hair.BDAE', FakeModel), mock.patch('character_hair.recover_skin', skin):
            with self.assertRaisesRegex(ValueError, 'selection differs'): recover_character_hair(source.__getitem__, result)
        self.assertEqual(result, before)
        with self.assertRaisesRegex(ValueError, 'player body'): recover_character_hair(source.__getitem__, {**body(), 'source': 'foreign.bdae'})

    @unittest.skipUnless(all((DEFAULT_SOURCE/name).is_file() for name in ('tables.bin', 'res_item.bin', 'res_npc.bin', 'res_a.bin')),
                         'Original hairstyle and player resources remain local-only')
    def test_real_source_three_external_skins_and_exact_original_vertices(self):
        from bdae_convert import BDAE
        from bdae_skin import recover_skin
        from equipment_appearance import ANIMATION
        from bdae_character import convert_character
        packs = {name: ResourceArchive(DEFAULT_SOURCE/name) for name in ('tables.bin', 'res_item.bin', 'res_npc.bin', 'res_a.bin')}
        def extract(path):
            pack = 'tables.bin' if path.startswith('tables/') else 'res_item.bin' if path.startswith('model/item/') else 'res_a.bin' if path == ANIMATION else 'res_npc.bin'
            return packs[pack].read(path)
        with tempfile.TemporaryDirectory() as td:
            model_path=Path(td)/'body.bdae'; model_path.write_bytes(extract(BASE_MODEL))
            animation_path=Path(td)/'animations.bdae'; animation_path.write_bytes(extract(ANIMATION))
            result=convert_character(model_path, animation_path, model_path); result['source']=BASE_MODEL
        start = len(result['meshes'])
        profile = recover_character_hair(extract, result)
        self.assertEqual(len(result['meshes']), start+3)
        self.assertEqual([result['meshes'][index]['vertexCount'] for index in profile['allMeshIndices']], [150, 380, 140])
        for entry in profile['styles'].values():
            index = entry['meshIndices'][0]
            with tempfile.TemporaryDirectory() as td:
                path = Path(td)/'source.bdae'; path.write_bytes(extract(entry['sourcePath']))
                reader = BDAE(path); model = reader.parse(); original_skin = recover_skin(reader, model, external_nodes=result['rig']['nodes'])['skins'][0]
            merged_skin = next(s for s in result['rig']['skins'] if s['mesh'] == index)
            self.assertEqual(result['meshes'][index]['positions'], model['meshes'][0]['positions'])
            self.assertEqual(merged_skin['skinWeights'], original_skin['skinWeights'])
            self.assertEqual(merged_skin['inverseBindMatrices'], original_skin['inverseBindMatrices'])
            self.assertLess(entry['maximumRestBindShapeError'], 1e-5)


if __name__ == '__main__': unittest.main()
