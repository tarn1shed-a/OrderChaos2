"""Export a private, source-bounded 750 appearance candidate for review.

No map placement, live ObjectCreate, quest marker, GUID or character save is
created. The source default table branch is an explicit asset-review input.
"""
import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bdae_skin import recover_skin, read_nodes
from bdae_character import aliases
from bdae_animation import BDAEAnimation
from bdae_attributes import primitive_bindings, verify_native as verify_attributes
from character_materials import read_material_record, EFFECTS, SHADER_SHA256
from equipment_appearance import merge_piece
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from texture_decode import decode
from tutorial_map_geometry import local_output
from tutorial_npc_inventory import audit
from tutorial_npc_native_probe import recover, TutorialNPCVisibilityProbe

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'model/npc/character/human/male/oc2_human_m_body_01.bdae'
ANIMATION = 'model/npc/character/human/male/anim/animations.bdae'
FORMAT = 'oc2-tutorial-npc750-source-candidate-v1'


def source_tangent_basis(reader, data):
    """Retain source semantics22/18, including the chest's extra UV stream.

    Native 12db930 maps source22 to runtime bit18/tangent0; its next loop maps
    source18 to runtime bit22/binormal0. Never generate tangents from UVs.
    """
    count,table=reader.section(180)
    if count!=len(data['meshes']):raise ValueError('Source mesh order differs')
    for n,mesh in enumerate(data['meshes']):
        wrapper=reader.rel(table+n*24+20)
        at=reader.q(wrapper+8)+((reader.u(wrapper+4)&0xffffff)-1)*8
        attr_count=reader.u(at+16); primitive_count=reader.u(at+96);primitives=reader.rel(at+100)
        bindings=[primitive_bindings(reader,primitives+i*88,attr_count) for i in range(primitive_count)]
        for semantic,name in [(22,'sourceTangents'),(18,'sourceBinormals')]:
            indices={b.get(semantic) for b in bindings}
            if len(indices)!=1 or None in indices:raise ValueError('Missing/ambiguous source tangent semantic')
            index=indices.pop()
            stride=reader.u(reader.rel(at+20)+index*4);offset=reader.u(reader.rel(at+28)+index*4)
            kind=reader.u(reader.rel(at+36)+index*4);width=reader.u(reader.rel(at+44)+index*4)
            vertex=reader.q(at+64);size=reader.q(at+72)
            if kind!=6 or width!=3 or offset+12>stride or (mesh['vertexCount']-1)*stride+offset+12>size:
                raise ValueError('Unsupported source tangent stream')
            values=[round(value,7) for i in range(mesh['vertexCount']) for value in reader.unpack('3f',vertex+i*stride+offset)]
            if name in mesh and mesh[name]!=values:raise ValueError('Existing source tangent disagrees')
            mesh[name]=values
            mesh.setdefault('sourceTangentBindings',{})[name]={'sourceSemantic':semantic,'attributeIndex':index,
                'stride':stride,'offset':offset,'components':3,'generated':False}
    return data


def export(image, source, output, *, three):
    output = local_output(output)
    if output.exists():
        raise ValueError('Existing candidate is preserved; choose a new output')
    verify_attributes(image)
    inventory, selection = audit(source), recover(image, source)
    row = next(r for r in inventory['creatures'] if r['entry'] == 750)
    if (row['appearance']['creaturedisplayinfo_id'] != 741 or
            selection['parts']['modelId'] != 1 or selection['defaultIdle']['request'] != 'idle' or
            selection['parts']['slots'][:3] != [2,2,1]):
        raise ValueError('Source 750 relationship differs; retrace before exporting')
    sources = Sources(source)
    visibility = TutorialNPCVisibilityProbe(image)
    output.mkdir(parents=True)
    assets = output/'assets'; assets.mkdir()
    files = {}
    def write(name, value):
        path = output/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, separators=(',',':'), allow_nan=False)+'\n')
        return '/'+name
    def extract(path, temporary):
        target = Path(temporary)/path; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(sources.read(path))
        return target
    def texture(path):
        if path in files: return files[path]
        raw = sources.read(path); image = decode(raw)
        name = 'assets/'+hashlib.sha256(raw).hexdigest()+'.png'
        image.save(output/name)
        files[path] = '/'+name
        return files[path]
    with tempfile.TemporaryDirectory(prefix='oc2-npc-source-') as temporary:
        base = extract(MODEL, temporary)
        reader = BDAE(base); result = source_tangent_basis(reader,reader.parse()); result['source'] = MODEL
        result['rig'] = recover_skin(reader, result)
        for material in result['materials']: material['sourceModel'] = MODEL
        animation_file = extract(ANIMATION, temporary)
        source_animation = BDAEAnimation(animation_file)
        decoded = source_animation.parse(['idle'])
        node_map = aliases(result['rig']['nodes'])
        source_nodes = read_nodes(reader)
        if len(source_nodes) != len(result['rig']['nodes']):
            raise ValueError('Original source rest/skeleton mismatch')
        clips = []
        for clip in decoded['clips']:
            tracks=[]
            for track in clip['tracks']:
                if track['node'] not in node_map:
                    raise ValueError('Original idle contains an unbound source node')
                tracks.append({**copy.deepcopy(track), 'node':node_map[track['node']]})
            clips.append({**clip, 'tracks':tracks})
        result['clips'] = clips
        body_names = [mesh['name'].removesuffix('-mesh') for mesh in result['meshes']]
        mapping = visibility.bind_source_names(body_names)
        if set(mapping.values()) != set(body_names):
            raise ValueError('Original body names do not bind exactly to source part slots')
        mesh_policy = {i:name for i,name in enumerate(body_names)}
        paths = [MODEL]
        for feature in selection['features']:
            if feature['localCandidates'] != 1:
                raise ValueError('Original feature filename missing or ambiguous')
            path = feature['path']; piece_reader = BDAE(extract(path,temporary)); piece = source_tangent_basis(piece_reader,piece_reader.parse())
            skin = recover_skin(piece_reader,piece,external_nodes=result['rig']['nodes'])
            if len(piece['meshes']) != 1 or len(skin['skins']) != 1:
                raise ValueError('Only verified one-mesh source feature selection is in scope')
            marker = 'feature:'+str(feature['kind'])
            visibility.replace_feature(feature['kind'], marker)
            indices = merge_piece(result,piece,skin,source_path=path)
            mesh_policy.update({i:marker for i in indices});paths.append(path)
        item_displays = decode_ftable(sources.read('tables/itemdisplayinfo.tbl'),'ID')
        item_models = decode_ftable(sources.read('tables/itemmodeldata.tbl'),'ID')
        by_display={r['ID']:r for r in item_displays['rows']};by_model={r['ID']:r for r in item_models['rows']}
        garments=[]
        for slot in [11,14]:
            display_id=selection['parts']['slots'][slot]
            display=by_display[display_id]; model=by_model[display['ModelHumanMale']]
            if any(display['TextureHumanMale'+suffix] for suffix in ['Diffuse','Normal','Mask']):
                raise ValueError('Uncovered nonempty source garment texture override')
            path=model['ModelPath'];piece_reader=BDAE(extract(path,temporary));piece=source_tangent_basis(piece_reader,piece_reader.parse())
            skin=recover_skin(piece_reader,piece,external_nodes=result['rig']['nodes'])
            indices=merge_piece(result,piece,skin,source_path=path)
            mask=visibility.apply_item_mask(model['Flags0'],model['Flags1'])
            garments.append({'partSlot':slot,'itemDisplayId':display_id,'model':model,
                              'remappedMask':str(mask),'meshIndices':indices})
            paths.append(path)
        visible=visibility.visibility()
        active=[i for i in range(len(result['meshes'])) if i not in mesh_policy or visible[mesh_policy[i]]]
        materials=[]
        readers={path:BDAE(Path(temporary)/path) for path in paths}
        for i,material in enumerate(result['materials']):
            record=read_material_record(readers[material['sourceModel']],material['name'])
            if record['samplers'] != material['samplers']:
                raise ValueError('Original material samplers differ')
            effect=record['effectPath'];effect_reader=BDAE(extract(effect,temporary))
            for shader,sha in SHADER_SHA256.items():
                if hashlib.sha256(sources.read(shader)).hexdigest()!=sha:
                    raise ValueError('Original character shader identity differs')
                if shader.encode()+b'\0' not in effect_reader.b:
                    raise ValueError('Original effect shader link missing')
            defines=EFFECTS[effect]
            for define in defines:
                if define.encode()+b'\0' not in effect_reader.b:
                    raise ValueError('Original effect define link missing')
            materials.append({'index':i,**{k:v for k,v in record.items() if k!='samplers'},
                              'defines':defines,'samplers':{k:texture(v) for k,v in record['samplers'].items()},
                              'alphaTest':.5 if 'ALPHA_TEST' in defines else 0,
                              'doubleSided':not effect.startswith('lt_cull_')})
        result.update({'format':'bdae946-character-v1','sourceNPC':{
            'format':FORMAT,'entry':750,'defaultDisplayId':741,'extraDisplayId':608,
            'visibleMeshIndices':active,'nativePartNames':mapping,'nativeVisibleNames':visible,
            'garments':garments,'bodyNameBindingIsHostSceneLookup':True,
            'weaponNotAssembled':True,'liveAppearanceSelection':False},
            'animationBinding':{'source':ANIMATION,'sourceSHA256':sources.proofs[ANIMATION]['sha256'],
                'sourceRange':next(r for r in source_animation.ranges() if r['name']=='idle'),
                'originalTrackValuesPreserved':True,'sourceDefaultRequestCPU':selection['defaultIdle'],
                'browserClockAndLoopAreReviewAdapter':True},
            'warnings':['Independent source default appearance candidate; not a production/live NPC.',
                        'Source part choice and two-channel hiding execute; resource completion and scene handles are host boundaries.',
                        'No actual GUID, activity, transform, quest state, interaction marker or weapon posture is manufactured.',
                        'Camera, neutral light, WebGL, skinning renderer and idle review clock/loop are browser adapters.']})
        write('assets/npc750.json',result)
    # SkinColor/HairColor are decoded from the source extra row. The source
    # 9d4c48 fragment passes low byte first, then +8 and +16; no RGB24 guess.
    parts=selection['parts']
    color=lambda n:[(n>>shift&255)/255 for shift in (0,8,16)]
    manifest={'format':FORMAT,'name':row['name'],'entry':750,'model':'/assets/npc750.json',
              'materials':materials,'visibleMeshIndices':active,
              'colors':{'skin':color(parts['sourceColorAt9c']),'hair':color(parts['sourceColorAta0'])},
              'evidence':{'inventory':'inventory-private.json','native':'native-selection-private.json'},
              'liveActor':False,'worldPlacement':None,'runtimeGUID':None,'questAvailability':None,
              'reviewScope':'Original default appearance candidate; world and current server state remain unknown.'}
    write('manifest.json',manifest)
    write('inventory-private.json',inventory);write('native-selection-private.json',selection)
    write('visibility-private.json',{'partNames':mapping,'visibleNames':visible,
        'sceneEvents':visibility.scene_events,'garments':garments,
        'executed':['3202ec..3203e8','32165c..321abc','9d6d10..9d6d58','321350'],
        'sceneLookupAndAttachDetachAreHostBoundaries':True,'resourceCompletionExecuted':False})
    write('sources-private.json',sources.proofs)
    for name in ['source-npc-preview.js','source-npc-material.js']:
        shutil.copyfile(ROOT/'tools/preview'/name,output/name)
    for name in ['three.module.js','three.core.js']:
        shutil.copyfile(three/name,output/name)
    (output/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>NPC 750 原资源独立审阅</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;height:100%;background:#14191d;color:#e8e7df;font:15px system-ui}canvas{display:block;width:100%;height:100%}aside{position:absolute;top:24px;left:24px;max-width:340px;pointer-events:none}h1{font-size:22px;margin:0 0 12px}p{line-height:1.5;color:#bec8c8}.tag{color:#d5b982;font-size:12px}footer{position:absolute;bottom:20px;left:24px;color:#97a7aa;font-size:12px}#status{white-space:pre-line}</style><canvas></canvas><aside><div class="tag">原资源 · 独立外观审阅</div><h1>750</h1><p id="status">读取原模型与材质…</p></aside><footer>拖动旋转 · 滚轮缩放 · 独立 idle 审阅；未接入地图、交互或任务状态</footer><script type="module" src="/source-npc-preview.js"></script></html>''')
    records={str(path.relative_to(output)):{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(output.rglob('*')) if path.is_file()}
    write('package-files.json',{'format':FORMAT,'files':records,'privateOnly':True,
                                'publicSourceFiles':[str(Path(__file__).relative_to(ROOT))]})
    return {'output':str(output),'files':len(records)+1,'meshes':len(result['meshes']),
            'visibleMeshes':len(active),'materials':len(materials),'textures':len(files),
            'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    cli.add_argument('--three',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    print(json.dumps(export(NativeImage(args.native.read_bytes()),args.source,args.output,three=args.three)))
