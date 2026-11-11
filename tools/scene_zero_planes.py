"""Recover source non-lightmapped planes with proven zero alpha in every mip.

Only the successful source-texture/default split branch is admitted. All its
color fragments discard; unknown RGB lighting and complete queue order are not
invented. Original resources remain local.
"""
import hashlib,io,json,struct,tempfile,zipfile
from pathlib import Path
from bdae_convert import BDAE
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_collision import apply_scene_transforms
from scene_sampling import material_samplers
from scene_alpha import texture_alpha,verify_native as verify_alpha
from scene_culling import cull_state,positive_affine
from scene_render_state import SHADERS,effect_render_state,verify_native as verify_state
from scene_texture_sampling import recover_scene_sampling,texture_dimensions
from tutorial_map_geometry import local_output

FORMAT='oc2-source-zero-alpha-planes-v1'
MODEL='model/scene/plane.bdae';EFFECT='ut_trans.bdae';TEXTURE='texture/plane.tga'
EFFECT_SHA='0789bcd628e8763dc7c1c92984c7160cd0f3bee8a248f9a091fad2eb0617a70a'
ROUTINES={
 0x114dd1c:(600,'9a77d4d5e4db7e6cbadde627c1536847f186cc710c96b0b884959bdd8ea28954'),
 0x1433a54:(720,'017a4df001994ac192ecb39d35186a935731d38af9137710f5b93098fe971620'),
 0x1433e74:(336,'a918ff5f8d6d8e1671768108c5e3c3edffc618dddef45c0785bbdb75ef6d816b'),
 0x1437070:(380,'e5943805685fef484e2791280519713004c94d306675dd88103f99ee250ca6e0'),
 0x1415b44:(2336,'70ad22b0af79cfb57533aec1523441fa29c10564ffb641b185a0e24b874fbdd8'),
}


def verify_native(image):
    verify_alpha(image);verify_state(image)
    for at,(size,digest)in ROUTINES.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original plane state consumer changed')
    rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rel.get(0x249c0d0)!=0x1f4ccb3 or image.read(0x249c0d8,4)!=struct.pack('<I',67)or image.read(0x1f4ccb3,9)!=b'alpharef\0':raise ValueError('Original alpha reference semantic differs')
    return {'routines':len(ROUTINES),'semantic':67,'originalGPUObserved':False}


def native_state(image,source):
    from source_physics import SourcePhysics
    verify_native(image)
    class Probe(SourcePhysics):
        def __init__(self,image):self.gl=[];super().__init__(image)
        def hook(self,uc,a,n,d):
            if a in self.imports and self.imports[a].startswith('gl'):
                name=self.imports[a];self.gl.append({'name':name,'arguments':[self.get('W0'),self.get('W1')],**({'value':self.gf('S0')}if name=='glUniform1f'else{})});self.set('PC',self.get('X30'))
            else:super().hook(uc,a,n,d)
    v=Probe(image);src=v.alloc(88);out=v.alloc(28);driver=v.alloc(0x3000)
    if len(source)!=88:raise ValueError('Original plane state needs88 bytes')
    v.uc.mem_write(src,source);v.call(0x114dd1c,{'X0':out,'X1':src});translated=bytes(v.uc.mem_read(out,28))
    # 1437070 subtracts38 for program parameters; state object is driver+38.
    # Start with a different cached reference to verify the original copy.
    v.uc.mem_write(driver+0x38+0x48c,translated);v.w(driver+0x508,'f',.5);v.call(0x1433a54,{'X0':driver+0x38,'X1':out});reference=v.r(driver+0x508,'f')[0]
    v.set('X19',driver);v.set('W28',7);v.uc.emu_start(0x1415ffc,0x14161ac,count=12)
    upload=[r for r in v.gl if r['name']=='glUniform1f']
    if reference!=0 or len(upload)!=1 or upload[0]['value']!=reference:raise ValueError('Original plane alpha reference needs further recovery')
    return {'state28':translated.hex(),'alphaReference':reference,'nativeCPU':True,'glCallsRecordedNotExecuted':v.gl,'compiledProgramAndQueueFlagsObserved':False}



def queue_boundaries(image,translated_state):
    """Execute original queue consumers with declared program-flag fixtures.

    The actual compiled program bit6 is unknown. Keep both outcomes rather
    than choosing a plane queue or inventing ordering in the preview.
    """
    from native_sky_assembly_probe import NativeSkyAssemblyProbe
    result=[]
    for flags in(0,0x40):
        p=NativeSkyAssemblyProbe(image)
        p.assemble([{'name':'tech0','passes':[{'state':translated_state,'programWordE2':flags,'programByteDF':0}]}],effect_name='ut_trans-fx')
        result.append({'programWordE2Fixture':flags,'actualProgramFlagsObserved':False,**p.enqueue(0)})
    return result


def all_mip_zero_alpha(raw):
    import texture2ddecoder
    info=texture_dimensions(raw)
    if info['container']!='ZIP-PVR2-split':raise ValueError('Plane requires original split-red alpha')
    levels=[]
    with zipfile.ZipFile(io.BytesIO(raw))as z:
        b=z.read('alpha.pvr');at=52
        for i in range(info['fileMipLevels']):
            w,h=max(1,info['width']>>i),max(1,info['height']>>i);size=((w+3)//4)*((h+3)//4)*8
            rgba=texture2ddecoder.decode_etc1(b[at:at+size],w,h);red=rgba[2::4]
            if len(red)!=w*h or any(red):raise ValueError('Nonzero original alpha needs actual RGB/queue branch; no zero specialization')
            levels.append({'level':i,'width':w,'height':h,'alphaRange':[0,0],'alphaSHA256':hashlib.sha256(red).hexdigest()});at+=size
        if at!=len(b):raise ValueError('Incomplete source alpha mip chain')
    return levels


def source_material(reader):
    n,t=reader.section(172)
    if n!=1 or reader.string(reader.q(t+8))!=EFFECT or reader.string(reader.q(t+16))!='#ut_trans-fx'or reader.q(t+24)!=0 or reader.u(t+32)!=2:raise ValueError('Only the original single-texture plane material')
    technique=None;seen=set()
    for j in range(2):
        a=reader.rel(t+36)+j*32;name=reader.string(reader.q(a));kind=reader.u(a+16)
        if name in seen or reader.u(a+20)!=1 or reader.unpack('2I',reader.rel(a+24))!=(1,0):raise ValueError('Original plane property shape differs')
        seen.add(name)
        if name=='texture':
            if kind!=17:raise ValueError('Original plane texture type differs')
        elif name=='ut_trans-fx-profile_GLES2/CurrentTechnique'and kind==28:technique=reader.named_technique(reader.rel(a+28))
        else:raise ValueError('Unexpected plane shader argument')
    if technique is None or technique['name']!='tech0':raise ValueError('Original plane technique differs')
    records=material_samplers(reader)
    if len(records)!=1 or set(records[0]['samplers'])!={'texture'}or records[0]['samplers']['texture']['texture']!=TEXTURE:raise ValueError('Plane is not a lightmapped material')
    return technique


def recover(extract,reader,data,image):
    technique=source_material(reader);levels=all_mip_zero_alpha(extract(TEXTURE))
    for name,digest in SHADERS.items():
        if hashlib.sha256(extract(name)).hexdigest()!=digest:raise ValueError('Original plane shader changed')
    with tempfile.TemporaryDirectory()as td:
        p=Path(td)/'fx.bdae';p.write_bytes(extract(EFFECT));fx=BDAE(p)
        if hashlib.sha256(fx.b).hexdigest()!=EFFECT_SHA:raise ValueError('Original plane FX differs')
        state=effect_render_state(fx);proof=[];_,t=fx.section(164)
        for profile in state['profiles']:
            if profile['technique']!='tech0'or any(profile[s]['file']!=file or profile[s]['defines']!={'ALPHA_TEST':''}for s,file in(('vertexShader','ut_common_vs.glsl'),('fragmentShader','ut_common_fs.glsl'))):raise ValueError('Unknown non-lightmapped shader branch')
            prof=fx.rel(t+profile['sourcePointerField']);tech=fx.rel(prof+4);ps=fx.rel(tech+12);proof.append(native_state(image,fx.b[ps+72:ps+160]))
        if cull_state(state['profiles'],'tech0')is not False or proof[0]['state28']!=proof[1]['state28']:raise ValueError('Plane profiles disagree')
    if not data['meshes']:raise ValueError('Source plane geometry missing')
    for m in data['meshes']:positive_affine(m['sourceNodeTransform']['matrix'])
    mat=data['materials'][0];data['sceneSampling']=recover_scene_sampling(extract,reader,data,effect_hashes={EFFECT:EFFECT_SHA})
    data['sceneAlpha']={'format':'oc2-scene-alpha-v1','materials':[{'index':0,'name':mat['name'],'texture':TEXTURE,'effectPath':EFFECT,'sourceTechnique':technique,'resolvedTechniqueIndex':0,'rule':'discard-less-equal','reference':0,'sourceAlpha':texture_alpha(extract(TEXTURE))}]}
    data['sceneCulling']={'format':'oc2-scene-culling-v1','projectionRule':'target-y-inversion-compensated-by-front-face-xor','transformScope':'positive-affine-source-nodes-and-world-instances','materials':[{'index':0,'name':mat['name'],'texture':TEXTURE,'effectPath':EFFECT,'technique':'tech0','cullEnabled':False,'cullFace':'BACK','frontFaceBeforeTarget':'CCW'}]}
    data['sourceZeroPlane']={'format':FORMAT,'model':MODEL,'effect':EFFECT,'texture':TEXTURE,'textureSHA256':hashlib.sha256(extract(TEXTURE)).hexdigest(),'alphaReference':0,'allMipAlphaZero':True,'mips':levels,'lightMapConsumed':False,'shaderSHA256':SHADERS,'native':proof,'splitBranch':'fresh-project-default-0x800;successful-original-texture','actualOriginalDeviceObserved':False,'colorAndDepthWrites':False,'fullQueueOrderRecovered':False,'rgbLightingRestored':False,'scope':'All fragments discard before RGB lighting. Constant-discard specialization only; no new light or draw-order rule.'}


def export(runtime,output):
    from analyze_native_resources import NativeImage
    from terrain_convert import read_instances
    from texture_decode import decode
    runtime,output=map(local_output,(runtime,output));output.mkdir(parents=True,exist_ok=True);assets=runtime/'game-data/converted';source=Sources(DEFAULT_SOURCE)
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());image=NativeImage(Path(cfg['library']).read_bytes());manifest=json.loads((assets/'source-map-dynamic-wind/manifest.json').read_text());selection=json.loads((assets/manifest['sourceSelection']['url'].removeprefix('/assets/')).read_text())
    if selection['profile']!='APK_Default':raise ValueError('Explicit source default profile required')
    before=sum(len(m['instances'])for m in manifest['scenery']);prefix='/assets/source-map-zero-planes/'
    rows=[r for r in selection['instances']if r.get('requestedModel')==MODEL and r['admission']=='admittedBeforeTypeFactory']
    if len(rows)!=31:raise ValueError('Expected original31 selected planes')
    with tempfile.TemporaryDirectory()as td:
        p=Path(td)/'model.bdae';model_raw=source.read(MODEL);p.write_bytes(model_raw);reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse());recover(source.read,reader,data,image);data['source']=MODEL;instances=[];tiles={}
        for row in rows:
            tile=tuple(row['tile'])
            if tile not in tiles:
                p=Path(td)/'tile.itm';p.write_bytes(source.read(f'world/tutorial/items/{tile[0]:04d}_{tile[1]:04d}.itm'));tiles[tile]=read_instances(p)
            matches=[i for i in tiles[tile]if i['id']==row['id']]
            if len(matches)!=1 or any(matches[0][k]!=row[k]for k in('model','position','quaternion','scale','tile','sourceType')):raise ValueError('Plane selection differs from original ITM')
            instances.append({**matches[0],'flags':2})
    if len({(tuple(i['tile']),i['id'])for i in instances})!=31:raise ValueError('Duplicate original plane identity')
    def write(name,value):(output/name).write_text(json.dumps(value,separators=(',',':'),ensure_ascii=False));return prefix+name
    name=hashlib.sha256(model_raw).hexdigest()+'.json';model_url=write(name,data);texture_raw=source.read(TEXTURE);png=hashlib.sha256(texture_raw).hexdigest()+'.png';decode(texture_raw).save(output/png);manifest['textures'][TEXTURE]=prefix+png
    manifest['scenery'].append({'url':model_url,'model':MODEL,'vertices':sum(m['vertexCount']for m in data['meshes']),'triangles':sum(m['triangleCount']for m in data['meshes']),'instances':instances})
    keys={(i['id'],MODEL)for i in instances};old=selection['preview']['omitted'];selection['preview']['omitted']=[r for r in old if(r['id'],r['path'])not in keys]
    if len(old)-len(selection['preview']['omitted'])!=31:raise ValueError('Plane omissions not uniquely matched')
    selection['preview'].update(nonLightmappedInstances=31,zeroAlphaInstances=31,sceneInstances=before+31,scope='Original placements;31 proven zero-alpha color-pass instances. Historical displayedInstances counts lightmap-bound instances, not visible pixels.')
    manifest['sourceSelection']['url']=write('selection.json',selection)
    audit={'format':FORMAT,'added':[{'tile':i['tile'],'id':i['id'],'model':MODEL,'position':i['position']}for i in instances],'sources':source.proofs,'sceneModels':len(manifest['scenery']),'sceneInstances':before+31,'otherSceneInstances':before,'zeroAlphaInstances':31,'omittedInstances':len(selection['preview']['omitted']),'lightmapBindingPresentButNotConsumed':sum(bool(r['bindings'])for r in rows),'lightsChanged':False,'fullQueueOrderRecovered':False,'scope':'Successful source texture and source alpha-test branch; all fragments discard. No source RGB lighting/queue order guessed.'}
    manifest['sourceZeroPlanes']={'format':FORMAT,'url':write('audit.json',audit)};write('manifest.json',manifest);return audit


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k]for k in('sceneModels','sceneInstances','zeroAlphaInstances','omittedInstances','lightsChanged')}))
