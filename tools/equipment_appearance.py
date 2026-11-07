"""Join selected original player body/garments without inventing skin weights.

Archive lookup/CRC checking belongs to extract(path). The source table chain,
exact bone aliases and rest matrices are checked here; body hiding and rigid
weapon grip alignment are explicitly web presentation choices.
"""
import copy
import hashlib
import math
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bdae_character import convert_character, aliases
from bdae_skin import recover_skin, read_nodes, compose
from skill_attachments import decode_ftable

BASE_MODEL = 'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'
ANIMATION = 'model/npc/character/elf/female/anim/animations.bdae'
TABLES = {'items': ('tables/items.tbl', 'entry'),
          'display': ('tables/itemdisplayinfo.tbl', 'ID'),
          'models': ('tables/itemmodeldata.tbl', 'ID')}
FOUNDATION = (
    'model/item/armor/8_underwear/oc2_elf_f_underwear_bra.bdae',
    'model/item/armor/8_underwear/oc2_elf_f_underwear_briefs.bdae',
)
SELECTED = {
    'trainingSword': {'entry': 200230, 'modelId': 253, 'slot': 'mainHand',
        'path': 'model/item/weapon/1_sword/oc2_sword_10_august_spatha/oc2_sword_10_august_spatha.bdae',
        'icon': 'august_spatha.png', 'hideParts': []},
    'linenArmor': {'entry': 100422, 'modelId': 817, 'slot': 'chest',
        'path': 'model/item/armor/3_chest/oc2_elf_f_light_1_faith_chest.bdae',
        'icon': 'faith_chest.png',
        'hideParts': ['chest', 'shoulder', 'upper_arm', 'waist', 'hip', 'thigh', 'knee', 'crus'],
        'attached': {'entry': 100140, 'modelId': 818,
            'path': 'model/item/armor/5_leg/oc2_elf_f_light_1_faith_leg.bdae'}},
    'travelerBoots': {'entry': 100423, 'modelId': 828, 'slot': 'feet',
        'path': 'model/item/armor/6_feet/oc2_elf_f_light_1_faith_feet.bdae',
        'icon': 'faith_feet.png', 'hideParts': ['foot']},
}


def inverse_matrix(matrix):
    """Invert a finite column-major 4x4 matrix; never replace singular data."""
    if len(matrix) != 16 or not all(math.isfinite(v) for v in matrix):
        raise ValueError('Invalid weapon grip matrix')
    rows = [[matrix[col*4+row] for col in range(4)] + [float(row == col) for col in range(4)] for row in range(4)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) < 1e-10: raise ValueError('Singular weapon grip matrix')
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        rows[column] = [value/scale for value in rows[column]]
        for row in range(4):
            if row == column: continue
            scale = rows[row][column]
            rows[row] = [value-scale*other for value, other in zip(rows[row], rows[column])]
    return [rows[row][4+col] for col in range(4) for row in range(4)]


def validate_equipment_references(tables):
    """Selected display ids are same-key matches; zero displayid fallback is unproven."""
    result = {}
    for key, selection in SELECTED.items():
        chain = []
        for specification in [selection, *([selection['attached']] if 'attached' in selection else [])]:
            entry, model_id = specification['entry'], specification['modelId']
            item = tables['items'].get(entry, {}); display = tables['display'].get(entry, {}); model = tables['models'].get(model_id, {})
            if item.get('displayid') != 0 or display.get('ModelElfFemale') != model_id or model.get('ModelPath') != specification['path']:
                raise ValueError(f'Original equipment model reference mismatch: {key}/{entry}')
            if specification is selection and display.get('Icon') != selection['icon']:
                raise ValueError(f'Original equipment icon reference mismatch: {key}')
            if specification is selection and item.get('attached_item', 0) != selection.get('attached', {}).get('entry', 0):
                raise ValueError(f'Original attached equipment reference mismatch: {key}')
            chain.append({'itemEntry': entry, 'itemDisplayId': item['displayid'], 'displayID': entry,
                'modelField': 'ModelElfFemale', 'modelID': model_id, 'path': model['ModelPath'],
                'Flags0': model['Flags0'], 'Flags1': model['Flags1'],
                'displayTextureOverride': display.get('TextureElfFemaleDiffuse', ''),
                'linkMode': 'same-key-item-display; exact-ModelElfFemale-to-itemmodeldata'})
        result[key] = chain
    return result


def merge_piece(result, source, source_skin=None, *, item=None, attachment=None, source_path=None):
    """Keep original vertices and bindings, only relocate material/mesh indices."""
    material_offset, mesh_offset = len(result['materials']), len(result['meshes'])
    materials=copy.deepcopy(source['materials'])
    if source_path:
        for material in materials:material['sourceModel']=source_path
    result['materials'].extend(materials)
    indices = []
    for mesh in source['meshes']:
        value = copy.deepcopy(mesh)
        if 'material' in value: value['material'] += material_offset
        for group in value.get('groups', []): group['material'] += material_offset
        if item: value['appearanceItem'] = item
        if attachment: value['attachment'] = copy.deepcopy(attachment)
        indices.append(len(result['meshes'])); result['meshes'].append(value)
    if source_skin:
        for skin in source_skin['skins']:
            value = copy.deepcopy(skin); value['mesh'] += mesh_offset
            result['rig']['skins'].append(value)
    return indices


def convert_equipment_character(extract):
    """extract(path)->verified Path/bytes; return one reusable character dictionary."""
    with tempfile.TemporaryDirectory(prefix='oc2-equipment-reader-') as temporary:
        cache, paths = {}, {}
        def load(path):
            if path not in cache:
                source = extract(path)
                if isinstance(source, (bytes, bytearray, memoryview)):
                    cache[path] = bytes(source)
                    target = Path(temporary)/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(cache[path])
                else:
                    target = Path(source); cache[path] = target.read_bytes()
                paths[path] = target
            return paths[path]
        tables, table_verification = {}, {}
        for key, (path, identifier) in TABLES.items():
            parsed = decode_ftable(load(path).read_bytes(), identifier)
            tables[key] = {row[identifier]: row for row in parsed['rows']}
            table_verification[path] = parsed['verification']
        references = validate_equipment_references(tables)
        result = convert_character(load(BASE_MODEL), load(ANIMATION), load(BASE_MODEL), profile='player')
        result['source'] = BASE_MODEL
        for material in result['materials']:material['sourceModel']=BASE_MODEL
        result['animationBinding'].update(source=ANIMATION, restSource=BASE_MODEL)
        base_count = len(result['meshes'])
        part_indices = {mesh['name'].removesuffix('-mesh'): index for index, mesh in enumerate(result['meshes'])}
        if len(part_indices) != base_count or not {'chest', 'foot', 'head', 'hip'} <= set(part_indices):
            raise ValueError('Original player body part mesh names changed')
        base_indices = list(range(base_count)); foundation_indices = []
        def garment(path, item=None):
            reader = BDAE(load(path)); model = reader.parse()
            skin = recover_skin(reader, model, external_nodes=result['rig']['nodes'])
            if len(skin['skins']) != len(model['meshes']):
                raise ValueError('Equipment garment has an unskinned mesh')
            return merge_piece(result, model, skin, item=item, source_path=path)
        for path in FOUNDATION:
            foundation_indices.extend(garment(path))
        base_indices.extend(foundation_indices)
        items = {}; base_aliases = aliases(result['rig']['nodes'])
        for key, selection in SELECTED.items():
            mesh_indices = []
            for record in references[key]:
                if key != 'trainingSword':
                    mesh_indices.extend(garment(record['path'], key)); continue
                reader = BDAE(load(record['path'])); model = reader.parse()
                if reader.section(188)[0] != 0: raise ValueError('Selected weapon unexpectedly has skin data')
                weapon_nodes = read_nodes(reader); grip_aliases = aliases(weapon_nodes)
                if 'Weapon_R' not in base_aliases or 'Dummy_Grip' not in grip_aliases:
                    raise ValueError('Original weapon hand/grip node missing')
                grip = weapon_nodes[grip_aliases['Dummy_Grip']]
                if grip['parent'] != -1: raise ValueError('Selected weapon grip is no longer a root transform')
                grip_matrix = compose(grip['position'], grip['quaternion'], grip['scale'])
                attachment = {'node': base_aliases['Weapon_R'], 'matrix': inverse_matrix(grip_matrix),
                    'sourceBoneAlias': 'Weapon_R', 'sourceGripAlias': 'Dummy_Grip',
                    'sourceGripMatrix': grip_matrix,
                    'mode': 'source-nodes-web-grip-alignment', 'nativeAttachPipelineRestored': False}
                mesh_indices.extend(merge_piece(result, model, item=key, attachment=attachment, source_path=record['path']))
            hide = []
            for part in selection['hideParts']:
                if part not in part_indices: raise ValueError(f'Body coverage mesh missing: {part}')
                hide.append(part_indices[part])
            if key == 'linenArmor': hide.extend(foundation_indices)
            items[key] = {'slot': selection['slot'], 'meshIndices': mesh_indices,
                'hideBaseMeshIndices': hide, 'sourceReferences': references[key],
                'bodyCoverageMode': 'web-mapping-of-exact-source-part-names'}
        result['appearance'] = {'format': 'oc2-equipment-appearance-v1', 'baseModelPath': BASE_MODEL,
            'baseMeshIndices': base_indices, 'bodyPartMeshIndices': part_indices,
            'foundationMeshIndices': foundation_indices, 'foundationPaths': list(FOUNDATION), 'items': items,
            'provenance': {'tables': table_verification,
                'sources': {path: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'pack': 'tables.bin' if path.startswith('tables/') else 'res_item.bin' if path.startswith('model/item/') else 'res_a.bin' if path == ANIMATION else 'res_npc.bin'}
                    for path, raw in cache.items()},
                'skinBinding': 'exact-source-bone-aliases; base-rest-times-source-inverse-bind-checked',
                'originalVertexDataPreserved': True, 'nativeBodyFlagMeaningRestored': False,
                'nativeZeroDisplayFallbackVerified': False, 'hairSelectionRecovered': False,
                'textureOverrideMode': 'original-model-diffuse-sampler; empty and _d display overrides are not guessed',
                'limitations': ['Original ModelElfFemale/model-path links are verified; zero items.displayid uses a same-key match whose native fallback is unresolved.',
                    'Original itemmodeldata Flags0/Flags1 are retained but not decoded. Covered base parts and foundation visibility are explicit web mappings.',
                    'The sword uses original Weapon_R and inverse Dummy_Grip transforms with a web attachment convention; the original complete attachment pipeline is not restored.',
                    'Original diffuse textures are used; normal/specular/skin-color palettes, hair selection and the complete original shader are not restored.',
                    'The previous forest-elf NPC is not used as the wearable player body. Local item stats and inventory rules are unchanged.']}}
        result['warnings'].append('Equipment visibility/rigid grip alignment are web adaptations; original garment geometry, skin weights and source diffuse samplers are retained.')
        return result
