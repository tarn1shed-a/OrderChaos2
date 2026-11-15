"""Export source NPC2079 and object467 assets for the explicit quest461 adapter.

Original default appearance/geometry/material/idle inputs only. Activity IDs,
quest progress, proximity policy and rewards belong to the compatibility server.
No original resource, save, shared runtime or deployment is modified.
"""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT/'analysis/raw/plain-quest-feasibility-20261115'
BASE = 'model/npc/character/human/male/oc2_human_m_body_01.bdae'
STATIC = 'model/scene_dawnwatch_002/sub_industry/ind_other_parts006.bdae'
SPARSE = {
    'oc2_human_m_light_19_dark_moon_hand.bdae': '_5_-_Default',
    'oc2_human_m_light_19_dark_moon_feet.bdae': '_7_-_Default',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sparse_material(reader, name, get_reader, image):
    from character_materials import read_material_record, SCALARS, SAMPLERS
    from tutorial_npc_final_pair_probe import scalar_default_execution
    try:
        return read_material_record(reader, name)
    except ValueError:
        if SPARSE.get(reader.path.name) != name:
            raise
    count, table = reader.section(172)
    matches = [table+i*80 for i in range(count) if reader.string(reader.q(table+i*80)) == name]
    if len(matches) != 1:
        raise ValueError('Sparse dark-moon material identity differs')
    row = matches[0]
    effect, effect_name = reader.string(reader.q(row+8)), reader.string(reader.q(row+16))
    if effect != 'lt_cull_pal_normal_solid.bdae' or effect_name != '#lt_cull_pal_normal_solid-fx':
        raise ValueError('Sparse dark-moon effect differs')
    count, props = reader.u(row+32), reader.rel(row+36)
    values, samplers, seen, technique = {}, {}, set(), None
    texture_count, texture_table = reader.section(148)
    for index in range(count):
        at = props+32*index
        field, kind = reader.string(reader.q(at)), reader.u(at+16)
        value = reader.rel(at+28)
        if field in seen or reader.u(at+20) != 1:
            raise ValueError('Sparse material property/count differs')
        seen.add(field)
        if field in SCALARS:
            number = reader.unpack('f', value)[0]
            if kind != 8 or not math.isfinite(number) or not 0 <= number <= 16:
                raise ValueError('Sparse scalar type/range differs')
            values[field] = number
        elif field in SAMPLERS:
            pointer = reader.rel(value)
            if kind != 17 or not texture_table <= pointer < texture_table+texture_count*32 or (pointer-texture_table) % 32:
                raise ValueError('Sparse material sampler reference differs')
            samplers[field] = reader.string(reader.q(pointer+16))
        elif field.endswith('/CurrentTechnique'):
            if kind != 28:
                raise ValueError('Sparse technique type differs')
            technique = reader.named_technique(value)
        else:
            raise ValueError('Uncovered sparse dark-moon property')
    if set(values) != set(SCALARS[:3]) or set(samplers) != set(SAMPLERS) or technique is None:
        raise ValueError('Sparse dark-moon exact property set differs')
    fx = get_reader(effect)
    count, table = fx.section(164)
    if count != 1 or fx.string(fx.q(table)) != effect_name[1:]:
        raise ValueError('Sparse source FX identity differs')
    defaults = []
    for field in (32, 36):
        profile = fx.rel(table+field)
        count, props = fx.u(profile+8), fx.rel(profile+12)
        values_fx = {}
        for index in range(count):
            at = props+index*32
            key = fx.string(fx.q(at))
            if key not in SCALARS:
                continue
            if key in values_fx or fx.u(at+8) != 8 or fx.u(at+16) != 1 or fx.unpack('2I', fx.rel(at+20)) != (1, 0):
                raise ValueError('Sparse source FX scalar declaration differs')
            number = fx.unpack('f', fx.rel(at+24))[0]
            if not math.isfinite(number) or not 0 <= number <= 16:
                raise ValueError('Sparse source FX scalar default differs')
            values_fx[key] = number
        if set(values_fx) != set(SCALARS):
            raise ValueError('Sparse source FX scalar set differs')
        defaults.append(values_fx)
    if defaults[0] != defaults[1]:
        raise ValueError('Sparse source FX profiles disagree')
    proof = scalar_default_execution(image, defaults[0], values)
    return {'effectPath': effect, 'effectName': effect_name, 'scalars': proof['result'],
            'samplers': samplers, 'sourceMaterialRecordOffset': row,
            'sourceTechniqueName': technique['name'], 'sourceTechniqueValueWord0': technique['valueWord0'],
            'missingMaterialScalars': list(SCALARS[3:]), 'scalarDefaultInheritance': proof}


def build(output, source_path, library):
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from bdae_character import aliases
    from equipment_appearance import merge_piece
    from character_materials import EFFECTS, SCALARS, SHADER_SHA256
    from tutorial_npc_robe_probe import RobeProbe
    from tutorial_npc_catalog_probe import CatalogVisibilityProbe
    from tutorial_npc_catalog_ut_probe import OverrideProbe
    from tutorial_npc_soldier_probe import strict_original_skin
    from tutorial_npc_final_pair_probe import source_or_native_default_basis, boot_palette_address_execution
    from scene_sampling import material_samplers, effect_profile_samplers
    from scene_render_state import effect_render_state
    from scene_flags_evidence import literal_nodes
    from texture_decode import decode
    from skill_attachments import decode_ftable

    output = Path(output).resolve()
    if not output.is_relative_to(AREA.resolve()) or output.exists():
        raise ValueError('Choose a new private ordinary-quest asset output')
    image = NativeImage(Path(library).read_bytes())
    class OrdinarySources(Sources):
        def __init__(self, root):
            self.archive_choices = {}
            super().__init__(root)

        def candidates(self, name):
            rows = super().candidates(name)
            if len(rows) <= 1:
                return rows
            if name != 'texture/lightmap.tga' or {r['pack'] for r in rows} != {'res_t.bin', 'res_t_upd10.bin'}:
                raise ValueError('Unclosed ordinary actor archive ambiguity: '+name)
            if name not in self.archive_choices:
                from native_missing_records import MissingRecordProbe
                class Probe(MissingRecordProbe):
                    def call(self, address, registers, **options):
                        if address == 0x54bc84:
                            at = self.alloc(len(name)+1)
                            self.uc.mem_write(at, name.encode()+b'\0')
                            registers = {**registers, 'X1': at}
                        return super().call(address, registers, **options)
                result = Probe(image).fresh_archives({p.name for p in Path(self.root).glob('*.bin')}, {r['pack'] for r in rows})
                if result['order'] != ['res_t_upd%d.bin' % n for n in range(10, 16)]+['res_t.bin'] or result['selected'] != 'res_t_upd10.bin':
                    raise ValueError('Original cold res_t lightmap selection differs')
                self.archive_choices[name] = {'originalArchiveTrace': result, 'selected': result['selected'],
                                              'freshMount': True, 'emptyNameCache': True, 'otherProvidersEmpty': True,
                                              'actualAndroidVFSObserved': False}
            return [r for r in rows if r['pack'] == self.archive_choices[name]['selected']]
    source = OrdinarySources(source_path)
    probe = RobeProbe(image, source)
    selection = probe.entry_selection(2079)
    if selection['result']['selectedDisplayAtD60'] != 2044:
        raise ValueError('Original NPC2079 default display differs')
    parts = probe.parts(2044)
    if parts['modelId'] != 1 or any(parts['slots'][n] for n in (7, 8, 15, 16)):
        raise ValueError('NPC2079 model/unnamed/weapon branch differs')
    requests = [probe.part_resource(n, parts['slots'][n], parts['slots'][0]) for n in range(7)]
    requests += [probe.part_resource(n, parts['slots'][n], parts['slots'][0]) for n in range(9, 15) if parts['slots'][n]]
    output.mkdir(parents=True)
    assets = output/'assets/source-ordinary-quest-actors'
    assets.mkdir(parents=True)
    readers, textures, sampling_proofs = {}, {}, []

    def write(name, value):
        path = assets/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n')
        return '/assets/source-ordinary-quest-actors/'+name

    def get_reader(path):
        if path not in readers:
            target = output/'original-resources'/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(path))
            readers[path] = BDAE(target)
        return readers[path]

    def texture(path):
        if path not in textures:
            raw = source.read(path)
            url = '/assets/source-ordinary-quest-actors/textures/'+sha(raw)+'.png'
            target = output/url[1:]
            target.parent.mkdir(parents=True, exist_ok=True)
            decoded = decode(raw)
            decoded.save(target)
            textures[path] = {'url': url, 'source': path, 'sourceSHA256': sha(raw), 'size': list(decoded.size)}
        return textures[path]['url']

    def sampling(reader, name):
        matches = [r for r in material_samplers(reader) if r['material'] == name]
        if len(matches) != 1:
            raise ValueError('NPC source sampler material ambiguous')
        row = matches[0]
        fx = get_reader(row['effectPath'])
        extras = {k: 8 for k in SCALARS}
        extras.update({k: 10 for k in ('skinColorHair', 'skinColorSkin', 'skinColorEye')})
        profiles = effect_profile_samplers(fx, extra_properties=extras)
        if profiles['effectName'] != row['effectName'][1:] or profiles['profiles'][0]['samplers'] != profiles['profiles'][1]['samplers']:
            raise ValueError('NPC effect sampler profiles differ')
        result = {}
        for key, sampler in row['samplers'].items():
            request = sampler['request']
            fx_request = profiles['profiles'][0]['samplers'][key]
            if any(request[k] is not None for k in ('addressV', 'minFilter', 'magFilter')) or request['addressU'] not in (None, 1, 2):
                raise ValueError('Uncovered ordinary-NPC sampler request')
            if fx_request != {'texture': None, 'request': {'addressU': 1 if key in ('diffusePal', 'specularPal', 'specularPalBack') else None,
                                                         'addressV': None, 'minFilter': None, 'magFilter': None}}:
                raise ValueError('NPC source effect sampling differs')
            raw = source.read(sampler['texture'])
            width, height = decode(raw).size
            if any(v <= 0 or v & (v-1) for v in (width, height)):
                raise ValueError('Only source POT texture defaults covered')
            result[key] = {'source': sampler['texture'], 'sourceSHA256': sha(raw),
                           'addressU': request['addressU'] or 0, 'addressV': 0,
                           'sourceRequest': request, 'width': width, 'height': height}
            if request['addressU'] == 1:
                result[key]['nativeEnum1Evidence'] = boot_palette_address_execution(image)
        return result, effect_render_state(fx)

    base_reader = get_reader(BASE)
    data = source_or_native_default_basis(base_reader, base_reader.parse(), image)
    data['source'] = BASE
    data['rig'] = strict_original_skin(base_reader, data, external_nodes=literal_nodes(base_reader))
    for material in data['materials']:
        material['sourceModel'] = BASE
    visibility = CatalogVisibilityProbe(image)
    names = [m['name'].removesuffix('-mesh') for m in data['meshes']]
    mapping = visibility.bind_original_parts(names)
    if set(mapping.values()) != set(names):
        raise ValueError('NPC2079 base body parts differ')
    mesh_policy, changes, garments = dict(enumerate(names)), [], []
    models = {r['ID']: r for r in decode_ftable(source.read('tables/itemmodeldata.tbl'), 'ID')['rows']}
    for request in requests:
        slot, path = request['slot'], request.get('path')
        if slot < 7 and not path:
            changes.append(visibility.feature_request(slot, None))
            continue
        if not path or request['sourceResourceCandidates'] != 1:
            raise ValueError('NPC2079 requested source missing')
        reader = get_reader(path)
        piece = source_or_native_default_basis(reader, reader.parse(), image)
        skin = strict_original_skin(reader, piece, external_nodes=data['rig']['nodes'])
        for material in piece['materials']:
            material['sourceOriginalSamplerPaths'] = dict(material['samplers'])
            material['sourceRequestedSamplerOverrides'] = {}
            for channel, stem in enumerate(request.get('textureOverrides') or []):
                if not stem:
                    continue
                proof = OverrideProbe(image).request(list(material['samplers']), channel, stem)
                boundary = proof['reachedBoundary']
                if boundary is None:
                    raise ValueError('Original yellow override did not reach request boundary')
                key = proof['originalConsumerCalls'][0]['sampler']
                source.read(boundary['path'])
                material['samplers'][key] = boundary['path']
                material['sourceRequestedSamplerOverrides'][key] = {'path': boundary['path'], 'proof': proof}
                if key == 'texture':
                    material['diffuse'] = boundary['path']
        indices = merge_piece(data, piece, skin, source_path=path)
        if slot < 7:
            marker = 'feature:'+str(slot)
            changes.append(visibility.feature_request(slot, marker))
            mesh_policy.update({i: marker for i in indices})
        else:
            keys = [r['id'] for r in request['tableLookups'] if r['table'] == 'itemmodeldata' and r['found']]
            if len(keys) != 1 or models[keys[0]]['ModelPath'] != path:
                raise ValueError('NPC2079 original garment/model lookup differs')
            row = models[keys[0]]
            mask = visibility.apply_item_mask(row['Flags0'], row['Flags1'])
            garments.append({'slot': slot, 'itemKey': request['inputValue'], 'sourceModel': row,
                             'meshIndices': indices, 'originalRemappedMask': str(mask)})
    visible = visibility.visibility()
    active = [i for i in range(len(data['meshes'])) if i not in mesh_policy or visible[mesh_policy[i]]]
    animation = BDAEAnimation(get_reader(BASE.rsplit('/', 1)[0]+'/anim/animations.bdae').path)
    node_map = aliases(data['rig']['nodes'])
    clips = animation.parse(['idle'])['clips']
    if any(t['node'] not in node_map for c in clips for t in c['tracks']):
        raise ValueError('NPC2079 idle has an unbound original node')
    data['clips'] = [{**c, 'tracks': [{**t, 'node': node_map[t['node']]} for t in c['tracks']]} for c in clips]
    used = {g['material'] for i, mesh in enumerate(data['meshes']) if i in active for g in mesh['groups']}
    material_profiles, inactive = [], []
    for index, material in enumerate(data['materials']):
        reader = get_reader(material['sourceModel'])
        record = sparse_material(reader, material['name'], get_reader, image)
        if index not in used:
            inactive.append({'index': index, 'sourceModel': material['sourceModel'], 'samplers': record['samplers']})
            continue
        if record['samplers'] != material.get('sourceOriginalSamplerPaths', material['samplers']):
            raise ValueError('NPC2079 material source sampler identity differs')
        addresses, fx = sampling(reader, material['name'])
        for key, override in material.get('sourceRequestedSamplerOverrides', {}).items():
            raw = source.read(override['path'])
            width, height = decode(raw).size
            if any(v <= 0 or v & (v-1) for v in (width, height)) or addresses[key]['addressU'] != 0:
                raise ValueError('Uncovered source yellow override sampling')
            addresses[key] = {**addresses[key], 'source': override['path'], 'sourceSHA256': sha(raw), 'width': width, 'height': height}
        defines, state = EFFECTS[record['effectPath']], fx['profiles'][0]['state']
        if state != fx['profiles'][1]['state'] or state['blendEnabled']:
            raise ValueError('NPC2079 source render-state branch not covered')
        for profile in fx['profiles']:
            for stage, filename in (('vertexShader', 'lt_pal_normal_vs.glsl'), ('fragmentShader', 'lt_pal_normal_fs.glsl')):
                if profile[stage]['file'] != filename or set(profile[stage]['defines']) != set(defines) or sha(source.read(filename)) != SHADER_SHA256[filename]:
                    raise ValueError('NPC2079 source shader relationship differs')
        urls = {key: texture(path) for key, path in material['samplers'].items()}
        material_profiles.append({'index': index, **{k: v for k, v in record.items() if k != 'samplers'},
                                  'samplers': urls, 'addressing': addresses, 'defines': defines,
                                  'alphaTest': .5 if 'ALPHA_TEST' in defines else 0,
                                  'doubleSided': not state['cullEnabled'], 'sourceEffectProfiles': fx})
        sampling_proofs.append({'materialIndex': index, 'sourceModel': material['sourceModel'], 'addresses': addresses})
    colors = {key: [(value >> shift & 255)/255 for shift in (0, 8, 16)] for key, value in
              (('skin', parts['sourceColorAt9c']), ('hair', parts['sourceColorAta0']))}
    data.update({'format': 'bdae946-character-v1', 'visibleMeshIndices': active})
    npc = {'entry': 2079, 'sourceName': '斯潘纳', 'defaultDisplay': 2044,
           'model': write('npc2079.json', data), 'materials': material_profiles,
           'materialSlotCount': len(data['materials']), 'inactiveMaterials': inactive,
           'visibleMeshIndices': active, 'colors': colors, 'idleDuration': clips[0]['duration'],
           'sourceScalePercent': 100, 'sourceProtoScale': 1.0, 'sourceWorldUnitsPreserved': True}
    npc['sourceSpawns'] = [r for r in decode_ftable(source.read('tables/creature_spawns.tbl'), 'id')['rows']
                          if r['entry'] == 2079 and r['map'] == 1]
    if len(npc['sourceSpawns']) != 1 or npc['sourceSpawns'][0]['id'] != 6598:
        raise ValueError('NPC2079 original placement changed')
    npc['materialInterface'] = 'createNPC2079({materialFactory}) accepts synchronous host material factory; omitted uses the frozen independent palette review light, not original map light'
    # Generic source scene material readers, rather than character palette rules.
    from scene_collision import apply_scene_transforms
    from scene_texture_sampling import recover_scene_sampling
    from scene_alpha import recover_scene_alpha
    from scene_culling import recover_scene_culling
    from scene_baked_lighting import recover_model_lighting
    reader = get_reader(STATIC)
    static = reader.parse()
    static['source'] = STATIC
    apply_scene_transforms(reader, static)
    static['sceneSampling'] = recover_scene_sampling(source.read, reader, static, allow_repeat_override=True)
    static['sceneAlpha'] = recover_scene_alpha(source.read, reader, static)
    static['sceneCulling'] = recover_scene_culling(source.read, reader, static)
    static['sceneBakedLighting'] = recover_model_lighting(reader, static, allow_repeat_override=True)
    for material in static['materials']:
        material['diffuseAsset'] = texture(material['samplers']['texture'])
        material['lightmapAsset'] = texture(material['samplers']['lightMap'])
    obj = {'entry': 467, 'model': write('static467.json', static), 'sourceModel': STATIC,
           'sourceLightmapBinding': 'Unmodified BDAE default texture/lightmap.tga; no AITM/DAT instance-atlas override supplied',
           'sourceDisplayScaleRaw': 0, 'sourceInstanceScale': [1, 1, 1],
           'scope': 'Asset local geometry/materials only; source actor attribute scale remains a host integration boundary'}
    obj['allSourceMap1Spawns'] = [r for r in decode_ftable(source.read('tables/staticobject_spawns.tbl'), 'id')['rows']
                                if r['Entry'] == 467 and r['map'] == 1]
    obj['sourcePhase0Phasing0Manual0Candidates'] = [r for r in obj['allSourceMap1Spawns']
                                                   if r['phase'] == 0 and r['phasing_id'] == 0 and r['manual_spawn'] == 0]
    if len(obj['allSourceMap1Spawns']) != 14 or len(obj['sourcePhase0Phasing0Manual0Candidates']) != 11:
        raise ValueError('Object467 original phase placement count changed')
    profile = {'format': 'oc2-ordinary-quest-actors-v1', 'questId': 461, 'npc': npc, 'object': obj,
               'textures': textures, 'coldArchiveChoices': source.archive_choices, 'actualOriginalActivityObserved': False,
               'runtimeActivityAndPolicy': 'Explicit compatibility host, not recovered original server rules',
               'noSaveAccess': True}
    write('profile.json', profile)
    write('source-proofs-private.json', source.proofs)
    write('native-selection-private.json', {'selection': selection, 'parts': parts, 'requests': requests,
          'idle': probe.idle(2079, 2044), 'garments': garments, 'visibilityChanges': changes,
          'visibleNames': visible, 'samplingProofs': sampling_proofs})
    for name in ('source-ordinary-quest-actors.mjs', 'source-npc-final-pair-material.js', 'source-npc-material.js', 'scene-sampling.js'):
        shutil.copyfile(ROOT/'tools/preview'/name, output/name)
    shared = ROOT/'analysis/raw/played-species-routing-20261115/immutable-inputs/prototype/public'
    for name in ('scene-baked-lighting.js', 'scene-alpha.js', 'scene-culling.js'):
        shutil.copyfile(shared/name, output/name)
    records = {str(p.relative_to(output)): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
               for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'package-files.json').write_text(json.dumps({'format': profile['format'], 'privateOnly': True,
                                                       'files': records}, ensure_ascii=False, indent=2)+'\n')
    return profile


if __name__ == '__main__':
    from resource_packs import DEFAULT_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--library', type=Path, default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    args = parser.parse_args()
    profile = build(args.output, args.source, args.library)
    print(json.dumps({'output': str(args.output), 'npc': profile['npc']['entry'], 'object': profile['object']['entry'],
                      'visibleMeshes': len(profile['npc']['visibleMeshIndices']), 'sourceTextures': len(profile['textures'])}))
