"""Private750/970 source weapon mounts, with checked original sampler addressing.

The two frozen body candidates are byte-checked inputs. Native state fixtures
choose mounts; this does not choose an actual actor's posture or animation.
"""
import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bdae_skin import read_nodes,compose
from bdae_character import aliases
from character_materials import read_material_record,SCALARS,EFFECTS,SHADER_SHA256
from scene_sampling import material_samplers,effect_profile_samplers
from scene_texture_sampling import verify_native as verify_sampling
from scene_render_state import effect_render_state
from texture_decode import decode
from tutorial_npc_candidate import source_tangent_basis
from tutorial_npc_additional_candidate import original_material as additional_material
from tutorial_npc_weapon_probe import recover,WeaponMountProbe
from tutorial_map_geometry import local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-tutorial-npc-weapon-candidate-v1'
DEFAULT750=ROOT/'analysis/raw/tutorial-npc-recovery-20261114/candidate-v3'
DEFAULT970=ROOT/'analysis/raw/tutorial-npc-additional-20261114/candidate-v2'


def checked_tree(directory,expected_format):
    directory=local_output(directory);metadata=json.loads((directory/'package-files.json').read_text())
    if metadata['format']!=expected_format or metadata['privateOnly']is not True:raise ValueError('Wrong frozen body input')
    for name,record in metadata['files'].items():
        path=directory/name
        if path.is_symlink()or not path.resolve().is_relative_to(directory)or not path.is_file():raise ValueError('Unsafe frozen body input')
        raw=path.read_bytes()
        if record!={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}:raise ValueError('Frozen body candidate changed')
    return metadata


def original_sampling(reader,name,extract,temporary):
    rows=[r for r in material_samplers(reader)if r['material']==name]
    if len(rows)!=1:raise ValueError('Source sampler material is ambiguous')
    row=rows[0];fx_path=Path(temporary)/row['effectPath'];fx_path.write_bytes(extract(row['effectPath']))
    fx=BDAE(fx_path);extras={s:8 for s in SCALARS}
    extras.update({k:10 for k in['skinColorHair','skinColorSkin','skinColorEye']})
    profiles=effect_profile_samplers(fx,extra_properties=extras)
    if profiles['effectName']!=row['effectName'][1:]:raise ValueError('Source sampler FX identity differs')
    first=profiles['profiles'][0]['samplers']
    if first!=profiles['profiles'][1]['samplers']or set(first)!=set(row['samplers']):raise ValueError('Source sampler profiles disagree')
    result={}
    for key,sampler in row['samplers'].items():
        # Skip-setter is not a mode. This result applies to a fresh POT source
        # texture's checked Repeat default, not a mutated live texture cache.
        effect_expected={'addressU':1 if key in['diffusePal','specularPal','specularPalBack']else None,
            'addressV':None,'minFilter':None,'magFilter':None}
        if first[key]['texture']is not None or first[key]['request']!=effect_expected:
            raise ValueError('Unreviewed effect sampler request')
        expected={'addressU':2 if key in['diffusePal','specularPal','specularPalBack']else None,
            'addressV':None,'minFilter':None,'magFilter':None}
        if sampler['request']!=expected:raise ValueError('Unreviewed NPC sampler request')
        raw=extract(sampler['texture']);image=decode(raw);w,h=image.size
        if any(v<=0 or v&(v-1)for v in[w,h]):raise ValueError('NPC fresh Repeat branch requires original POT dimensions')
        result[key]={'source':sampler['texture'],'sourceSHA256':hashlib.sha256(raw).hexdigest(),
            'sourceRequest':sampler['request'],'sourceEffectProfiles':profiles,
            'width':w,'height':h,'addressU':expected['addressU']or 0,'addressV':0,
            'scope':'Fresh source POT texture default and material request; later live cache mutation unknown'}
    return result,effect_render_state(fx)


def export(image,source,output,body750=DEFAULT750,body970=DEFAULT970):
    output=local_output(output)
    if output.exists():raise ValueError('Existing candidate is preserved')
    verify_sampling(image)
    dependency750=checked_tree(body750,'oc2-tutorial-npc750-source-candidate-v1')
    dependency970=checked_tree(body970,'oc2-tutorial-npc-additional-candidate-v1')
    evidence=recover(image,source);sources=Sources(source)
    output.mkdir(parents=True);(output/'assets').mkdir()
    def write(name,value):
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');return '/'+name
    def asset(directory,url):
        source_path=directory/url.lstrip('/');target=output/url.lstrip('/')
        raw=source_path.read_bytes()
        if target.exists()and target.read_bytes()!=raw:raise ValueError('Conflicting source asset')
        target.write_bytes(raw);return url
    original750=json.loads((body750/'manifest.json').read_text())
    original970=next(e for e in json.loads((body970/'manifest.json').read_text())['entries']if e['entry']==970)
    entries=[];mounts=[]
    with tempfile.TemporaryDirectory(prefix='oc2-npc-weapon-')as temporary:
        readers={}
        def reader(path):
            if path not in readers:
                p=Path(temporary)/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sources.read(path));readers[path]=BDAE(p)
            return readers[path]
        for original,base,row in zip([original750,original970],[body750,body970],evidence['entries']):
            entry=row['entry'];body=json.loads((base/original['model'].lstrip('/')).read_text())
            materials=copy.deepcopy(original['materials'])
            for m in materials:
                for url in m['samplers'].values():asset(base,url)
                source_material=body['materials'][m['index']]
                source_model=source_material.get('sourceModel',body['source'])
                source_reader=reader(source_model)
                addresses,fx=original_sampling(source_reader,source_material['name'],sources.read,temporary)
                if set(addresses)!=set(m['samplers'])or fx['effectName']!=m['effectName'][1:]:raise ValueError('Frozen body material/source identity differs')
                for key,address in addresses.items():
                    if m['samplers'][key]!='/assets/'+address['sourceSHA256']+'.png':raise ValueError('Frozen body texture/source identity differs')
                if m['doubleSided']==fx['profiles'][0]['state']['cullEnabled']:raise ValueError('Frozen source culling disagreement')
                m['addressing']=addresses;m['sourceEffectProfiles']=fx
            body_url=asset(base,original['model'])
            paths={r['path']for w in row['weapons']for r in w['resources']}
            if len(paths)!=1:raise ValueError('Only one verified source weapon per NPC is in scope')
            weapon_path=paths.pop();wr=reader(weapon_path);weapon=source_tangent_basis(wr,wr.parse())
            if wr.section(188)[0]!=0 or len(weapon['meshes'])!=1:raise ValueError('Expected one original rigid weapon mesh')
            weapon['sourceNodes']=read_nodes(wr);weapon['source']=weapon_path
            node_map=aliases(weapon['sourceNodes']);mesh_alias=weapon['meshes'][0]['name'].removesuffix('-mesh')
            mesh_node=weapon['sourceNodes'][node_map[mesh_alias]]
            if mesh_node['parent']!=-1 or any(abs(v-e)>1e-7 for v,e in zip(compose(mesh_node['position'],mesh_node['quaternion'],mesh_node['scale']),[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])):
                raise ValueError('Weapon mesh needs an original source-node transform branch')
            wm=[]
            for i,m in enumerate(weapon['materials']):
                # The staff uses the same exact cull/trans FX independently
                # checked for747; keep its identity rather than aliasing it.
                count,table=wr.section(172)
                material_at=next(table+j*80 for j in range(count)if wr.string(wr.q(table+j*80))==m['name'])
                effect=wr.string(wr.q(material_at+8))
                if effect=='lt_cull_pal_normal_trans.bdae':
                    record=additional_material(wr,m['name']);record['samplers']=record.pop('sourceSamplers');defines=['ALPHA_TEST','RIM_LIGHT']
                else:record=read_material_record(wr,m['name']);defines=EFFECTS[record['effectPath']]
                addresses,fx=original_sampling(wr,m['name'],sources.read,temporary)
                for profile in fx['profiles']:
                    for stage,shader in [('vertexShader','lt_pal_normal_vs.glsl'),('fragmentShader','lt_pal_normal_fs.glsl')]:
                        if profile[stage]['file']!=shader or hashlib.sha256(sources.read(shader)).hexdigest()!=SHADER_SHA256[shader]:raise ValueError('Weapon shader differs')
                urls={}
                for key,path in record['samplers'].items():
                    raw=sources.read(path);url='/assets/'+hashlib.sha256(raw).hexdigest()+'.png';decode(raw).save(output/url.lstrip('/'));urls[key]=url
                state=fx['profiles'][0]['state']
                if state!=fx['profiles'][1]['state']or state['blendEnabled']:raise ValueError('Unreviewed weapon FX state')
                wm.append({'index':i,**{k:v for k,v in record.items()if k!='samplers'},'samplers':urls,
                    'defines':defines,'alphaTest':.5 if'ALPHA_TEST'in defines else 0,
                    'doubleSided':not state['cullEnabled'],'addressing':addresses,'sourceEffectProfiles':fx})
            modes=[]
            for w in row['weapons']:
                if len(w['resources'])!=1:raise ValueError('Expected exactly one selected weapon')
                resource=w['resources'][0];mount=WeaponMountProbe(image).attachment(body['rig']['nodes'],weapon['sourceNodes'],resource['slot'],resource['positionAnchor'])
                modes.append({'armedParameter':w['armed'],'resourceRequest':resource,'mount':mount});mounts.append({'entry':entry,**modes[-1]})
            default_armed=row['postureFixtures'][0]['weaponRequests'][0]['armedParameter']
            entries.append({'entry':entry,'name':original['name'],'model':body_url,'materials':materials,
                'colors':original750['colors']if entry==750 else {'skin':[1,1,1],'hair':[1,1,1]},
                'visibleMeshIndices':original['visibleMeshIndices'],'idleDuration':body['clips'][0]['duration'],
                'weapon':{'itemKey':row['extra']['MainHand'],'model':write('assets/weapon'+str(row['extra']['MainHand'])+'.json',weapon),
                    'materials':wm,'modes':modes,'reviewDefaultArmedParameter':default_armed,
                    'reviewDefaultInputs':{'kindProperty0':0x40a,'stateByte5a0':0},'actualPosture':None},
                'animationScope':'Previously verified idle only; weapon-ready animation selection not recovered',
                'liveActor':False,'actualGUID':None,'worldPlacement':None,'questAvailability':None})
    for name in['three.module.js','three.core.js']:shutil.copyfile(body750/name,output/name)
    shutil.copyfile(ROOT/'tools/preview/source-npc-material.js',output/'source-npc-material.js')
    for name in['source-npc-weapon-preview.js','source-npc-weapon-material.js']:shutil.copyfile(ROOT/'tools/preview'/name,output/name)
    chest=json.loads((body750/'assets/npc750.json').read_text())['meshes'][16]
    audit={'negativeUVertices':sum(u<0 for u in chest['uvs'][::2]),'chestVertices':chest['vertexCount'],
        'frozenViewerDefault':'Three TextureLoader ClampToEdge; source negative U collapsed to texture border',
        'newSourceAddressing':'Fresh POT source Repeat U/V; palette U retains original explicit Clamp to Edge',
        'sourceUVVerticesNormalsTangentsTexturesColorsAndLightChanged':False,
        'nativeSamplerEvidence':'scene_sampling + scene_texture_sampling checked original 146d33c/146d4a8 constructors,146f58c setter and skip255 loader',
        'currentAndroidCacheAndGPUObserved':False}
    write('manifest.json',{'format':FORMAT,'entries':entries,'liveActor':False,
        'scope':'Source weapon mounts under explicit armed0/1 fixtures; idle and current actor posture remain separate',
        'reviewAdapters':['WebGL skeleton and formula rewrite','Fixed neutral review light/camera','Idle browser loop'],
        'samplingScope':'Original fresh POT addressing only; filter/mip/anisotropy and later cache remain review boundaries'})
    write('native-private.json',evidence);write('mounts-private.json',mounts);write('sampling-private.json',audit)
    write('sources-private.json',sources.proofs)
    write('dependencies-private.json',{'750':dependency750,'747970':dependency970,'bodyBytesChanged':False})
    (output/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>750 / 970 原武器挂点审阅</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;height:100%;background:#14191d;color:#e5e7e6;font:14px system-ui}canvas{display:block;width:100%;height:100%}aside{position:absolute;left:24px;top:24px;max-width:360px}small{color:#c9b388}h1{font-size:22px}p{white-space:pre-line;color:#bec8c8;line-height:1.5}button{background:#26373f;color:#e8e7df;border:1px solid #53666c;border-radius:4px;padding:8px;margin:3px;cursor:pointer}button[aria-pressed=true]{border-color:#cfb075}footer{position:absolute;left:24px;bottom:20px;color:#96a7ab;font-size:12px}</style><canvas></canvas><aside><small>原资源 · 独立武器与采样审阅</small><h1>750 / 970</h1><div id="choices"></div><div id="postures"></div><div id="diagnostics"></div><p id="status">读取原资源…</p></aside><footer>拖动旋转 · 滚轮缩放 · 活动姿态、完整武器动作和任务状态仍未知</footer><script type="module" src="/source-npc-weapon-preview.js"></script></html>''')
    records={str(p.relative_to(output)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(output.rglob('*'))if p.is_file()}
    write('package-files.json',{'format':FORMAT,'privateOnly':True,'files':records})
    return {'output':str(output),'entries':[r['entry']for r in entries],'files':len(records)+1,'productionChanged':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--body750',type=Path,default=DEFAULT750)
    cli.add_argument('--body970',type=Path,default=DEFAULT970);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();print(json.dumps(export(NativeImage(args.native.read_bytes()),args.source,args.output,args.body750,args.body970)))
