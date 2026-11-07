"""Recover three table-bounded elf-female hairstyles on the original player rig.

The filename recipe was checked against ARM64 3.1.3a function 0x9d88b0.
No native code is executed; the build reads original tables and model files.
"""
import hashlib
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bdae_skin import recover_skin
from skill_attachments import decode_ftable

BASE_MODEL = 'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'
FEATURE_TABLE = 'tables/race_features.tbl'
RACE, GENDER, FACE_INDEX = 1, 1, 0
HAIR_INDICES = (1, 2, 3)
NATIVE_RECIPE = {
    'buildSHA256': '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4',
    'function': '0x9d88b0', 'featurePathTable': '0x2422200',
    'raceNameTable': '0x24221c0', 'genderNameTable': '0x24221f0',
    'formatAddress': '0x1e64841', 'format': '%s%s_%s_%s_%03d',
    'suffixFormat': '_%03d', 'extension': '.bdae', 'featureType': 1,
    'featurePrefix': '7_hair/hair', 'raceName': 'elf', 'genderName': 'female',
    'nativeExecution': False,
}


def hair_model_path(hair_index, face_index=FACE_INDEX):
    if hair_index not in HAIR_INDICES or face_index != FACE_INDEX:
        raise ValueError('Unsupported verified elf-female hair/face selection')
    return f'model/item/armor/7_hair/hair_elf_female_{face_index:03d}_{hair_index:03d}.bdae'


def validate_feature_row(rows):
    selected = [row for row in rows if row.get('race') == RACE and row.get('gender') == GENDER]
    if len(selected) != 1:
        raise ValueError('Missing or ambiguous original elf-female race feature row')
    row = selected[0]
    if (row.get('id') != 4 or row.get('face') != 3 or row.get('hair') != 3 or
            row.get('hair_begin') != 1 or row.get('hair_color') != 6 or row.get('skin_color') != 6):
        raise ValueError('Original elf-female feature range changed')
    return row


def recover_character_hair(extract, result):
    """Append validated original meshes/materials/skins; return appearance.hair.

    extract(path) returns CRC-checked original bytes or a Path. The caller embeds
    the returned profile in result['appearance']['hair']; these meshes must not
    also be included in baseMeshIndices because only one style is visible.
    """
    from equipment_appearance import merge_piece
    if result.get('source') != BASE_MODEL or not result.get('rig', {}).get('nodes'):
        raise ValueError('Original hair requires the verified elf-female player body')
    loaded = {}
    def raw(path):
        if path not in loaded:
            source = extract(path)
            loaded[path] = bytes(source) if isinstance(source, (bytes, bytearray, memoryview)) else Path(source).read_bytes()
        return loaded[path]
    table = decode_ftable(raw(FEATURE_TABLE), 'id')
    feature = validate_feature_row(table['rows'])
    pending = []
    with tempfile.TemporaryDirectory(prefix='oc2-hair-source-') as temporary:
        for hair_index in HAIR_INDICES:
            path = hair_model_path(hair_index)
            source = Path(temporary)/Path(path).name; source.write_bytes(raw(path))
            reader = BDAE(source); model = reader.parse()
            skin = recover_skin(reader, model, external_nodes=result['rig']['nodes'])
            expected = f'texture/hair_elf_female_000_{hair_index:03d}_d.tga'
            if (len(model['meshes']) != 1 or len(model['materials']) != 1 or len(skin['skins']) != 1 or
                    model['materials'][0].get('diffuse') != expected or
                    model['materials'][0].get('samplers', {}).get('skinColorMask') != 'texture/hair_all_race_m.tga'):
                raise ValueError('Original hair mesh/material/skin selection differs')
            pending.append((hair_index, path, model, skin))
    # No partial mutation if a later selected model is missing or invalid.
    styles, all_indices = {}, []
    for hair_index, path, model, skin in pending:
        material_start = len(result['materials'])
        mesh_indices = merge_piece(result, model, skin, source_path=path)
        identifier = f'hair{hair_index}'
        styles[identifier] = {
            'id': identifier, 'label': f'发型 {hair_index}', 'sourceHairIndex': hair_index,
            'sourceFaceIndex': FACE_INDEX, 'sourcePath': path, 'sourcePack': 'res_item.bin',
            'sourceSHA256': hashlib.sha256(loaded[path]).hexdigest(),
            'meshIndices': mesh_indices,
            'materialIndices': list(range(material_start, len(result['materials']))),
            'sourceMeshNames': [mesh['name'] for mesh in model['meshes']],
            'binding': 'original-external-skin-to-player-bone-aliases',
            'maximumRestBindShapeError': max(s['verification']['maximumRestBindShapeError'] for s in skin['skins']),
        }
        all_indices.extend(mesh_indices)
    return {
        'format': 'oc2-character-hair-v1', 'race': RACE, 'gender': GENDER, 'faceIndex': FACE_INDEX,
        'defaultStyle': 'hair1', 'styles': styles, 'allMeshIndices': all_indices,
        'provenance': {
            'featureTable': {'path': FEATURE_TABLE, 'pack': 'tables.bin', 'row': feature, **table['verification']},
            'sources': {path: {'pack': 'tables.bin' if path == FEATURE_TABLE else 'res_item.bin',
                'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()} for path, value in loaded.items()},
            'nativeFilenameRecipe': NATIVE_RECIPE,
            'originalVerticesAndWeightsPreserved': True, 'sourceRigRestBindingVerified': True,
            'webChoice': 'fixed original face variant 0; hairstyle IDs/labels/default selection are web choices',
            'limitations': [
                'The native source recipe and race_features bound the three selected original paths; no original creation UI or character-server protocol runs here.',
                'Face, ear and other race/gender variants are outside this selection.',
                'Some source mesh names are reused across different hair files; source path and hash identify a style, not its exported mesh name.',
                'Hair tint, normal and material maps are retained as original samplers and applied by the separate character material profile.'],
        },
    }
