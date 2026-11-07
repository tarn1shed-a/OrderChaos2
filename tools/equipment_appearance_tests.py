import copy
import math
import unittest

from bdae_convert import BDAE
from bdae_skin import compose, multiply, recover_skin
from equipment_appearance import (BASE_MODEL, ANIMATION, SELECTED, FOUNDATION,
    convert_equipment_character, validate_equipment_references, merge_piece, inverse_matrix)
from resource_packs import ResourceArchive, DEFAULT_SOURCE


def reference_tables():
    tables = {'items': {}, 'display': {}, 'models': {}}
    for selection in SELECTED.values():
        for spec in [selection, *([selection['attached']] if 'attached' in selection else [])]:
            tables['items'][spec['entry']] = {'displayid': 0, 'attached_item': spec.get('attached', {}).get('entry', 0)}
            tables['display'][spec['entry']] = {'ModelElfFemale': spec['modelId'], 'Icon': spec.get('icon', ''), 'TextureElfFemaleDiffuse': '_d'}
            tables['models'][spec['modelId']] = {'ModelPath': spec['path'], 'Flags0': 123, 'Flags1': 456}
    return tables


class EquipmentAppearanceTests(unittest.TestCase):
    def test_grip_inverse_preserves_source_transform_without_replacing_bad_matrices(self):
        matrix = compose([.3, -.2, .1], [0, math.sin(.3), 0, math.cos(.3)], [1, 2, .5])
        product = multiply(matrix, inverse_matrix(matrix))
        self.assertLess(max(abs(value-float(i%5 == 0)) for i, value in enumerate(product)), 1e-12)
        with self.assertRaisesRegex(ValueError, 'Singular'): inverse_matrix([0.0]*16)
        with self.assertRaisesRegex(ValueError, 'Invalid'): inverse_matrix([float('nan')]*16)

    def test_model_chain_rejects_foreign_variant_path_and_missing_attached_lower_garment(self):
        tables = reference_tables(); result = validate_equipment_references(tables)
        self.assertEqual([row['itemEntry'] for row in result['linenArmor']], [100422, 100140])
        self.assertEqual(result['travelerBoots'][0]['displayTextureOverride'], '_d')
        changes = [lambda data: data['display'][100423].update(ModelElfFemale=817),
                   lambda data: data['models'][817].update(ModelPath='model/foreign.bdae'),
                   lambda data: data['items'][100422].update(attached_item=0),
                   lambda data: data['display'][200230].update(Icon='foreign.png')]
        for change in changes:
            data = copy.deepcopy(tables); change(data)
            with self.assertRaisesRegex(ValueError, 'reference mismatch'): validate_equipment_references(data)

    def test_merge_only_remaps_material_mesh_indices_and_never_rewrites_source_vertices_or_weights(self):
        target = {'materials': [{'name': 'body'}], 'meshes': [{'name': 'body-mesh'}], 'rig': {'skins': []}}
        source = {'materials': [{'name': 'cloth', 'diffuse': 'original.tga'}],
            'meshes': [{'name': 'cloth-mesh', 'positions': [1, 2, 3], 'material': 0,
                        'groups': [{'start': 0, 'count': 3, 'material': 0}]}]}
        skin = {'skins': [{'mesh': 0, 'boneNodes': [2, 5], 'skinWeights': [.8, .2], 'skinIndices': [0, 1]}]}
        before = copy.deepcopy((source, skin))
        self.assertEqual(merge_piece(target, source, skin, item='linenArmor'), [1])
        self.assertEqual(target['meshes'][1]['material'], 1)
        self.assertEqual(target['meshes'][1]['groups'][0]['material'], 1)
        self.assertEqual(target['rig']['skins'][0]['mesh'], 1)
        self.assertEqual(target['rig']['skins'][0]['boneNodes'], [2, 5])
        self.assertEqual(target['rig']['skins'][0]['skinWeights'], [.8, .2])
        target['meshes'][1]['positions'][0] = 999
        self.assertEqual((source, skin), before)

    @unittest.skipUnless(all((DEFAULT_SOURCE/name).is_file() for name in ('res_npc.bin', 'res_a.bin', 'res_item.bin', 'tables.bin')), 'Original body and gear remain local-only')
    def test_original_modular_body_foundation_attached_skirt_and_shared_bind_matrices(self):
        import tempfile
        from pathlib import Path
        packs = {name: ResourceArchive(DEFAULT_SOURCE/name) for name in ('res_npc.bin', 'res_a.bin', 'res_item.bin', 'tables.bin')}
        def extract(path):
            pack = 'tables.bin' if path.startswith('tables/') else 'res_item.bin' if path.startswith('model/item/') else 'res_a.bin' if path == ANIMATION else 'res_npc.bin'
            return packs[pack].read(path)
        data = convert_equipment_character(extract); appearance = data['appearance']
        self.assertEqual(data['source'], BASE_MODEL)
        self.assertEqual(len(data['meshes']), 20); self.assertEqual(len(data['rig']['skins']), 19)
        self.assertEqual(len(appearance['foundationMeshIndices']), 2)
        self.assertEqual(len(appearance['items']['linenArmor']['meshIndices']), 2)
        self.assertTrue(set(appearance['foundationMeshIndices']) <= set(appearance['items']['linenArmor']['hideBaseMeshIndices']))
        self.assertFalse(appearance['provenance']['nativeBodyFlagMeaningRestored'])
        self.assertEqual(set(clip['name'] for clip in data['clips']), {'idle','walk_forward','attack','hurt','death','skill_fireball','skill_frost_blast'})
        weapon = data['meshes'][appearance['items']['trainingSword']['meshIndices'][0]]
        self.assertEqual(data['rig']['nodes'][weapon['attachment']['node']]['name'], 'Weapon_R-node')
        identity = multiply(weapon['attachment']['sourceGripMatrix'], weapon['attachment']['matrix'])
        self.assertLess(max(abs(value-float(i%5 == 0)) for i, value in enumerate(identity)), 1e-10)
        with tempfile.TemporaryDirectory() as td:
            for key in ('linenArmor', 'travelerBoots'):
                item = appearance['items'][key]
                for index, record in zip(item['meshIndices'], item['sourceReferences']):
                    path = Path(td)/'original.bdae'; path.write_bytes(extract(record['path']))
                    reader = BDAE(path); original = reader.parse(); original_skin = recover_skin(reader, original, external_nodes=data['rig']['nodes'])['skins'][0]
                    converted_skin = next(skin for skin in data['rig']['skins'] if skin['mesh'] == index)
                    self.assertEqual(data['meshes'][index]['positions'], original['meshes'][0]['positions'])
                    self.assertEqual(converted_skin['skinWeights'], original_skin['skinWeights'])
                    self.assertEqual(converted_skin['inverseBindMatrices'], original_skin['inverseBindMatrices'])
                    self.assertLess(converted_skin['verification']['maximumRestBindShapeError'], 1e-5)


if __name__ == '__main__': unittest.main()
