"""Export four original type15 primary models as an isolated inspection candidate.

No existing preview, saves or production assets are written. Original factory
requests, source TRS, node/index/UV streams, FX states and DAT part ordinals are
checked. Missing companion resources and live inside visibility stay explicit.
"""
import argparse
import copy
import hashlib
import json
import math
import struct
import tempfile
from pathlib import Path

from bdae_attributes import primitive_bindings, verify_native as verify_attributes
from bdae_convert import BDAE
from map_loading_evidence import Sources, NATIVE_SHA256
from resource_packs import DEFAULT_SOURCE
from scene_alpha import material_techniques, texture_alpha, verify_native as verify_alpha
from scene_baked_lighting import recover_model_lighting
from scene_collision import apply_scene_transforms
from scene_culling import recover_scene_culling
from scene_render_state import SHADERS, effect_render_state
from scene_sampling import material_samplers, read_sampler_2d
from scene_texture_sampling import EFFECTS, texture_dimensions, repeat_override
from terrain_convert import read_instances
from tutorial_map_geometry import ROOT, local_output
from source_physics import SourcePhysics

FORMAT = 'oc2-source-tutorial-inside-models-v1'
UV = 'ut_lightmap_trans_uv.bdae'
LUMIN = 'u2t_lightmap_trans_uv_lumin.bdae'
EFFECT_HASHES = {**EFFECTS,
 UV: 'cb1026eae591abb8246e275dab8503081503cd4bbf1f067823270142927c23e4',
 LUMIN: '6b84eafacc11c596553a2a0071d14ea65243d37727a3db9a2640a997da6650a8'}
VALUES = {UV: {'uvSpeed': 9},
 LUMIN: {'uvSpeed2': 9, 'tex2_color': 10, 'tex2_intensity': 8}}
EXTRAS = {UV: VALUES[UV], LUMIN: {**VALUES[LUMIN], 'texture2': 17, 'texture2Mask': 17}}
DEFINES = {UV: {'UV_ANIM'}, LUMIN: {'TWO_TEXTURE', 'UV_ANIM_2', 'TEX2_COLOR', 'TEX_LUMIN_WITH_MASK'}}
MODELS = tuple('model/scene_generator_temple_000/'+name+'.bdae' for name in (
 'god_temple01_inside01', 'god_underground_palace01',
 'god_underground_palace02', 'god_underground_palace02_02'))


class NativeInsideFactoryProbe(SourcePhysics):
    """Original a62fe4 orchestration; async model creation is an explicit sink."""
    def __init__(self,image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        rel={r['r_offset']:r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
        self.visibility=rel[0x240ddd8+0x80]
        self.trace=[]
        for at in (0x33ebf8,0x341c2c,0x34e2ac,0xa6337c,self.visibility):
            self.uc.hook_add(UC_HOOK_CODE,self.boundary,begin=at,end=at)

    def string(self,text):
        raw=text.encode()+b'\0';p=self.alloc(len(raw));self.uc.mem_write(p,raw);return p

    def hook(self,uc,at,size,data):
        if self.imports.get(at)=='sprintf':
            fmt=self.cstr(self.get('X1'))
            if fmt!=b'%s_inside.bdae':raise ValueError('Unexpected original inside request format')
            raw=self.cstr(self.get('X2'))+b'_inside.bdae';uc.mem_write(self.get('X0'),raw+b'\0')
            self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        super().hook(uc,at,size,data)

    def boundary(self,uc,at,size,data):
        if at==0x33ebf8:
            owner,p=self.get('X0'),self.get('X1');name=self.cstr(self.r(p,'Q')[0]).decode()
            self.trace.append({'kind':'model-owner-initialize-boundary','source':name,
                'position':list(self.r(p+8,'3f')),'quaternion':list(self.r(p+0x14,'4f')),
                'scale':list(self.r(p+0x24,'3f')),'incomingSlot':self.get('W2'),
                'originalModelTaskExecuted':False})
            if not name.endswith('.bdae'):raise ValueError('Unexpected source model extension')
            self.w(owner+0x60,'Q',self.string(name[:-5]))
        elif at==0x341c2c:
            self.trace.append({'kind':'slot-request-boundary','slot':self.get('W1'),'force':self.get('W2')})
        elif at==self.visibility:
            self.trace.append({'kind':'model-visibility-boundary','visible':bool(self.get('W1')),'argument2':self.get('W2')})
        elif at==0x34e2ac:self.trace.append({'kind':'scene-container-attach-boundary'})
        elif at==0xa6337c:self.trace.append({'kind':'inside-camera-PHY-update-boundary','executed':False})
        else:raise ValueError('Unexpected inside factory boundary')
        self.set('PC',self.get('X30'))

    def requests(self,instance):
        self.trace=[];obj=self.alloc(0x28);params=self.alloc(0xa0);root=self.alloc(0x300)
        self.w(obj,'Q',0x2423fe8);self.w(obj+0x20,'I',1);self.w(0x2528db0,'Q',root)
        self.w(root+0x1c0,'Q',self.alloc(0x100));self.w(params,'Q',self.string(instance['model']))
        self.w(params+8,'3f',*instance['position']);self.w(params+0x14,'4f',*instance['quaternion'])
        self.w(params+0x24,'3f',*instance['scale'])
        self.call(0xa62fe4,{'X0':obj,'X1':params,'W2':0})
        initial=[r for r in self.trace if r['kind']=='model-owner-initialize-boundary']
        if (len(initial)!=2 or initial[0]['source']!=instance['model'] or
            initial[1]['source']!=instance['model'][:-5]+'_inside.bdae' or
            any(r[k]!=instance[k] for r in initial for k in ('position','quaternion','scale'))):
            raise ValueError('Original type15 requests/TRS differ')
        return {'nativeFactoryExecuted':True,'originalConstructorsExecuted':True,
            'asyncModelAndGPUExecuted':False,'trace':copy.deepcopy(self.trace)}


def verify(image):
    from scene_dynamic_wind import verify_native as verify_clock
    from scene_wind_identity import verify_uv2
    verify_attributes(image); verify_alpha(image); verify_uv2(image); verify_clock(image)
    rel = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if (rel.get(0x2423fe8+0xb0) != 0xa62fe4 or
        image.read(0x1e65dd8, 15) != b'%s_inside.bdae\0'):
        raise ValueError('Original type15 factory/name format changed')
    # The same original source i+4 / runtime 2<<i loop handles UV3 (i=3).
    from source_physics import SourcePhysics
    v = SourcePhysics(image); v.set('W13', 3); v.uc.emu_start(0x12db438, 0x12db43c, count=2)
    if v.get('W18') != 7: raise ValueError('Original UV3 source semantic changed')
    v.set('W14', 2); v.uc.emu_start(0x12db478, 0x12db47c, count=2)
    if v.get('W3') != 16: raise ValueError('Original UV3 runtime semantic changed')
    if rel.get(0x250e758+4*8) != 0x1f4c148 or image.read(0x1f4c148, 10) != b'texcoord3\0':
        raise ValueError('Original UV3 name differs')
    return {'originalSHA256': NATIVE_SHA256, 'type15Factory': '0xa62fe4',
            'insideVisibilityUpdate': '0xa6337c', 'UV3SourceSemantic': 7,
            'UV3RuntimeSemantic': 4, 'nativeCPU': True, 'liveStateObserved': False}


def additional_uvs(reader, data):
    count, table = reader.section(180)
    if count != len(data['meshes']): raise ValueError('Source mesh count differs')
    for j, mesh in enumerate(data['meshes']):
        wrapper = reader.rel(table+j*24+20)
        at = reader.q(wrapper+8)+((reader.u(wrapper+4)&0xffffff)-1)*8
        nc, nv = reader.u(at+16), reader.u(at+12)
        np, pt = reader.u(at+96), reader.rel(at+100)
        vp, size = reader.q(at+64), reader.q(at+72)
        descriptors = {}
        for semantic, runtime in ((6, 3), (7, 4)):
            indices = [primitive_bindings(reader, pt+i*88, nc).get(semantic) for i in range(np)]
            if not indices or indices[0] is None or len(set(indices)) != 1:
                raise ValueError('Per-part secondary UV bindings need separate recovery')
            index = indices[0]
            stride, offset, kind, components = [reader.u(reader.rel(at+o)+index*4) for o in (20,28,36,44)]
            if (kind != 6 or components != 2 or not 0 < stride <= 65535 or
                offset+8 > stride or (nv-1)*stride+offset+8 > size):
                raise ValueError('Unsupported original secondary UV stream')
            values = [v for i in range(nv) for v in reader.unpack('2f', vp+i*stride+offset)]
            if not all(math.isfinite(v) for v in values): raise ValueError('Nonfinite source UV')
            mesh['sourceUV'+str(semantic-4)] = values
            descriptors['UV'+str(semantic-4)] = {'sourceSemantic': semantic, 'runtimeSemantic': runtime,
                'attributeIndex': index, 'stride': stride, 'offset': offset, 'type': kind, 'components': 2}
        mesh['sourceInsideAttributes'] = descriptors


def properties(reader):
    count, table = reader.section(172); rows, techniques_extras = [], {}
    for i in range(count):
        at = table+i*80; name = reader.string(reader.q(at)); effect = reader.string(reader.q(at+8)); fields = {}
        expected = VALUES.get(effect, {})
        for j in range(reader.u(at+32)):
            p = reader.rel(at+36)+j*32; field = reader.string(reader.q(p))
            if field not in expected: continue
            kind = expected[field]; length = {8: 1, 9: 2, 10: 3}[kind]
            if (field in fields or reader.u(p+16) != kind or reader.u(p+20) != 1 or
                reader.unpack('2I', reader.rel(p+24)) != (1,0)):
                raise ValueError('Original inside typed property shape differs')
            value = list(reader.unpack(str(length)+'f', reader.rel(p+28)))
            if not all(math.isfinite(v) for v in value): raise ValueError('Nonfinite source material field')
            fields[field] = value
        if set(fields) != set(expected): raise ValueError('Missing source inside material field')
        techniques_extras[effect] = EXTRAS.get(effect, {})
        rows.append({'index': i, 'name': name, 'effect': effect, 'values': fields})
    return rows, techniques_extras


def native_property_values(image, rows):
    """Execute the original generic typed writer; loaded material is a fixture."""
    from source_physics import SourcePhysics
    if hashlib.sha256(image.read(0x13e0b30,2960)).hexdigest() != 'a8bf6500e4b7ced06f9357377a44cb51e1d0b818abfb5dd14210f26ce29cfecb':
        raise ValueError('Original material typed copy changed')
    v = SourcePhysics(image)
    for row in rows:
        proof = {}
        for name, values in row['values'].items():
            kind = VALUES[row['effect']][name]
            m, fx, decl, src = v.alloc(128), v.alloc(80), v.alloc(24), v.alloc(16)
            v.w(m+8,'Q',fx); v.w(fx+0x1a,'H',1); v.w(fx+0x40,'Q',decl)
            v.w(decl+0x11,'B',kind); v.w(decl+0x14,'H',1); v.w(src,str(len(values))+'f',*values)
            if v.call(0x13e0b30, {'X0':m,'W1':0,'W2':kind,'X3':src,'W4':0,'W5':1,'W6':len(values)*4}) != 1:
                raise ValueError('Original typed inside property copy failed')
            actual = list(v.r(m+0x40,str(len(values))+'f'))
            if actual != values: raise ValueError('Original typed copy changed values')
            proof[name] = {'kind':kind,'value':actual,'nativeCPU':True,'GPUCreated':False}
        row['nativePropertyCopy'] = proof


def effect_parameters(reader, effect):
    """Both original FX profiles, including float2 parameters absent in old tools."""
    count, table = reader.section(164)
    if count != 1: raise ValueError('Expected one source FX')
    for field in (32,36):
        profile = reader.rel(table+field); names = set()
        for i in range(reader.u(profile+8)):
            p = reader.rel(profile+12)+i*32; name = reader.string(reader.q(p)); kind = reader.u(p+8)
            if name in names or reader.u(p+16) != 1 or reader.unpack('2I',reader.rel(p+20)) != (1,0):
                raise ValueError('Unsupported source FX parameter state')
            names.add(name); value = reader.rel(p+24)
            if kind == 17:
                request=read_sampler_2d(reader,value)
                if (reader.i(value) != 0 or request['addressU'] not in (None,0) or
                    request['addressV'] not in (None,0) or request['minFilter'] is not None or request['magFilter'] is not None):
                    raise ValueError('Non-null FX texture default or sampler override')
            elif kind == VALUES.get(effect,{}).get(name):
                count = {8:1,9:2,10:3}[kind]
                if not all(math.isfinite(x) for x in reader.unpack(str(count)+'f',value)):
                    raise ValueError('Nonfinite source FX default')
            else: raise ValueError('Unrecognized original inside FX parameter')
        expected = {'texture','lightMap'} | set(EXTRAS.get(effect,{}))
        if names != expected: raise ValueError('Source FX parameter set differs')


def recover_materials(sources, reader, data, image):
    rows, extras = properties(reader); techniques = material_techniques(reader,extra_properties=extras)
    records = material_samplers(reader); sampling, alpha = [], []; effect_defs = {}
    for name, digest in SHADERS.items():
        if hashlib.sha256(sources.read(name)).hexdigest() != digest: raise ValueError('Source shader changed')
    with tempfile.TemporaryDirectory(prefix='oc2-inside-fx-') as tmp:
        for index, (r,t,p,m) in enumerate(zip(records,techniques,rows,data['materials'])):
            effect = r['effectPath']
            if effect not in EFFECT_HASHES or r['material'] != m['name'] or p['name'] != m['name']:
                raise ValueError('Unrecognized inside material/effect')
            expected_samplers = {'texture','lightMap'} | ({'texture2','texture2Mask'} if effect == LUMIN else set())
            if set(r['samplers']) != expected_samplers: raise ValueError('Inside material sampler set differs')
            if effect not in effect_defs:
                raw = sources.read(effect); path = Path(tmp)/effect; path.write_bytes(raw); fx = BDAE(path)
                if hashlib.sha256(fx.b).hexdigest() != EFFECT_HASHES[effect]: raise ValueError('Original inside FX changed')
                effect_parameters(fx,effect); effect_defs[effect] = effect_render_state(fx)
            definition = effect_defs[effect]
            if r['effectName'] != '#'+definition['effectName']: raise ValueError('FX name differs')
            expected_defines = {'LIGHTMAP'} | ({'ALPHA_TEST'} if effect != 'ut_cull_lightmap_solid.bdae' and effect != 'ut_lightmap_solid.bdae' else set()) | DEFINES.get(effect,set())
            for profile in definition['profiles']:
                if (t['name'] != profile['technique'] or t['name'] != 'tech0' or
                    profile['vertexShader']['file'] != 'ut_common_vs.glsl' or profile['fragmentShader']['file'] != 'ut_common_fs.glsl' or
                    profile['vertexShader']['defines'] != {n:'' for n in expected_defines} or
                    profile['fragmentShader']['defines'] != {n:'' for n in expected_defines} or profile['state']['blendEnabled']):
                    raise ValueError('Unrecovered inside shader/pass variant')
            diffuse = r['samplers']['texture']
            if diffuse['texture'] != m['diffuse']: raise ValueError('Diffuse source differs')
            p['missingSamplers']=[]
            for name, s in r['samplers'].items():
                if any(v is not None for v in s['request'].values()) and not repeat_override(s['request']):
                    raise ValueError('Unrecovered inside sampler override')
                if name != 'lightMap':
                    if len(sources.candidates(s['texture'])) != 1:
                        if name=='texture':raise ValueError('Primary source texture missing')
                        p['missingSamplers'].append({'sampler':name,'path':s['texture'],'candidateCount':len(sources.candidates(s['texture']))})
                    else:texture_dimensions(sources.read(s['texture']))
            sampling.append({'index':index,'name':m['name'],'texture':m['diffuse'],
                'textureSHA256':hashlib.sha256(sources.read(m['diffuse'])).hexdigest(),
                'sourceTexture':texture_dimensions(sources.read(m['diffuse'])),
                'sourceRequest':diffuse['request'],'addressU':0,'addressV':0})
            cut = 'ALPHA_TEST' in expected_defines
            alpha.append({'index':index,'name':m['name'],'texture':m['diffuse'],'effectPath':effect,
                'sourceTechnique':t,'resolvedTechniqueIndex':0,'rule':'discard-less-equal' if cut else 'none',
                'reference':.5 if cut else None,'sourceAlpha':texture_alpha(sources.read(m['diffuse']))})
            p['samplers'] = r['samplers']
    native_property_values(image,rows); additional_uvs(reader,data)
    data['sceneSampling'] = {'format':'oc2-scene-sampling-v2','materials':sampling,'applied':['diffuse-address-U','diffuse-address-V'],
        'limits':['Original address/defaults checked; existing web mip/filter adapter retained.']}
    data['sceneAlpha'] = {'format':'oc2-scene-alpha-v1','materials':alpha,'applied':['fragment-alpha-cutout'],
        'limits':['Source ALPHA_TEST; luminance contribution is added after the base light calculation.']}
    data['sceneCulling'] = recover_scene_culling(sources.read,reader,data,effect_hashes=EFFECT_HASHES,extra_properties=extras)
    data['sceneBakedLighting'] = recover_model_lighting(reader,data,allow_repeat_override=True)
    data['sourceInsideMaterials'] = {'format':FORMAT,'materials':rows,'shaderSHA256':SHADERS,
        'clock':'same verified unpaused source clock adapter as dynamic wind; host origin, not Android epoch',
        'fullOriginalFrameRestored':False,'lightsChanged':False}


def export(runtime, output):
    runtime, output = map(local_output,(runtime,output))
    if output.exists(): raise ValueError('Choose a new candidate; existing work is preserved')
    from analyze_native_resources import NativeImage
    from bres_world_bounds_evidence import inner_bres
    from native_part_lightmaps import PartLightmapProbe
    from scene_lightmaps import source_names, read_records, object_records
    from scene_lightmap_binding import material_request_slots
    from terrain_missing_textures import texture_image
    assets = runtime/'game-data/converted'; source_manifest = assets/'source-temple-sampling/manifest.json'
    original_bytes = source_manifest.read_bytes(); manifest = json.loads(original_bytes)
    selection = json.loads((assets/manifest['sourceSelection']['url'][8:]).read_text())
    baked = json.loads((assets/manifest['sceneBakedLighting']['url'][8:]).read_text())
    part_policy = json.loads((assets/manifest['sourcePartLightmaps']['url'][8:]).read_text())
    if selection['profile'] != 'APK_Default' or selection['settings']['ForceModelLodLevel'] != 0 or selection['phase'] != 0:
        raise ValueError('Only explicitly checked original default/phase0/slot0 candidate')
    cfg = json.loads((runtime/'prototype/native-physics.json').read_text()); image = NativeImage(Path(cfg['library']).read_bytes())
    native = verify(image); probe = PartLightmapProbe(image); factory=NativeInsideFactoryProbe(image);sources = Sources(DEFAULT_SOURCE)
    output.mkdir(parents=True); prefix = '/assets/source-tutorial-inside/'
    atlases = {a['sourcePath']:a for a in baked['atlases']}; added = []; model_audits = []
    def write(name,data):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n');return prefix+name
    def texture(name):
        if name in manifest['textures']: return manifest['textures'][name]
        raw=sources.read(name);decoded,proof=texture_image(sources,name,None)
        if proof: raise ValueError('No texture fallback supplied for inside candidate')
        filename=hashlib.sha256(raw).hexdigest()+'.png';decoded.save(output/filename)
        manifest['textures'][name]=prefix+filename;return prefix+filename
    before=copy.deepcopy(manifest['scenery']); old_instance_keys={(tuple(i['tile']),i['id']) for e in before for i in e['instances']}
    with tempfile.TemporaryDirectory(prefix='oc2-inside-candidate-') as tmp:
        for model in MODELS:
            rows=[r for r in selection['instances'] if r['model']==model and r['sourceType']==15]
            if len(rows)!=1 or rows[0]['admission']!='admittedBeforeTypeFactory':raise ValueError('Source inside admission differs')
            row=rows[0];x,z=row['tile'];itmpath=f'world/tutorial/items/{x:04d}_{z:04d}.itm'
            p=Path(tmp)/'tile.itm';p.write_bytes(sources.read(itmpath));original=[r for r in read_instances(p) if r['id']==row['id']]
            if len(original)!=1 or any(original[0][k]!=row[k] for k in ('position','quaternion','scale','model','sourceType','tile')):
                raise ValueError('Type15 source TRS differs')
            instance=original[0]
            if (tuple(instance['tile']),instance['id']) in old_instance_keys:raise ValueError('Existing visible instance would be replaced')
            raw=sources.read(model);p=Path(tmp)/'model.bdae';p.write_bytes(raw);reader=BDAE(p)
            data=apply_scene_transforms(reader,reader.parse());recover_materials(sources,reader,data,image);data['source']=model
            order=[g['material'] for g in data['meshes'][0]['groups']]
            refs=probe.references(inner_bres(raw))
            if (len(data['meshes'])!=1 or sorted(order)!=list(range(len(data['materials']))) or
                [r['localIndex']for r in refs]!=order or any(data['materials'][r['localIndex']]['name']!=r['material']for r in refs)):
                raise ValueError('Source inside mesh part/material identity differs')
            record=source_names('tutorial',x,z,slot=0)['record'];requests=material_request_slots(object_records(read_records(sources.read(record)),instance['id']))
            bindings=[{'ordinal':r['sortKey'],'atlas':source_names('tutorial',x,z,slot=0,atlas=r['atlasIndex'])['texture'],
                       'uvTransform':r['uvParameter']['whenUniformPresent']} for r in requests]
            if not bindings or [b['ordinal']for b in bindings]!=list(range(len(bindings))):raise ValueError('Incomplete source DAT ordinal bindings')
            for b in bindings:
                name=b['atlas'];encoded=sources.read(name)
                if name not in atlases:atlases[name]={'sourcePath':name,'url':texture(name),'sha256':hashlib.sha256(encoded).hexdigest(),**texture_dimensions(encoded)}
            for r in data['sourceInsideMaterials']['materials']:
                for name,s in r['samplers'].items():
                    if name!='lightMap' and sources.candidates(s['texture']):texture(s['texture'])
            companion=model[:-5]+'_inside.bdae'
            data['sourceInsideModel']={'format':FORMAT,'sourceType':15,'originalPrimary':model,
                'originalCompanion':companion,'companionPresent':bool(sources.candidates(companion)),
                'liveInsideVisibilityRestored':False,'primaryOnlyCandidate':True}
            instance={**instance,'flags':15}
            manifest['scenery'].append({'url':write(hashlib.sha256(raw).hexdigest()+'.json',data),'model':model,
                'vertices':sum(m['vertexCount']for m in data['meshes']),
                'triangles':sum(m['triangleCount']for m in data['meshes']),'instances':[instance]})
            baked['instances'].append({'objectId':instance['id'],'model':model,'tile':instance['tile'],'recordPath':record,'bindings':bindings})
            if order!=list(range(len(order))):part_policy['models'].append({'model':model,'sourceSHA256':data['sourceSHA256'],'partToMaterial':order})
            item={'model':model,'id':instance['id'],'tile':instance['tile'],'position':instance['position'],
                'quaternion':instance['quaternion'],'scale':instance['scale'],'sourceITM':itmpath,
                'sourceSHA256':data['sourceSHA256'],'nodeMatrices':[m['sourceNodeTransform']for m in data['meshes']],
                'materials':len(data['materials']),'vertices':sum(m['vertexCount']for m in data['meshes']),
                'pendingMaterialParts':[{'material':r['index'],'name':r['name'],'missingSamplers':r['missingSamplers']}for r in data['sourceInsideMaterials']['materials']if r['missingSamplers']],
                'partToMaterial':order,'bindings':bindings,'originalPartBindingCPU':probe.bindings(order,bindings),
                'originalFactoryCPU':factory.requests(instance),
                'companion':companion,'companionCandidates':len(sources.candidates(companion)),
                'preFactoryAdmission':row['admission'],'liveInsideVisibilityRestored':False}
            model_audits.append(item);added.append((instance['id'],model))
    if manifest['scenery'][:len(before)]!=before:raise ValueError('Existing 1258 visible placements changed')
    baked['atlases']=list(atlases.values());manifest['sceneBakedLighting']['url']=write('baked-lighting.json',baked)
    manifest['sourcePartLightmaps']['url']=write('part-lightmaps.json',part_policy)
    # Original admission records remain factoryPending. This candidate does not
    # rewrite them as live completed original loads or change old omission flags.
    audit={'format':FORMAT,'native':native,'added':model_audits,'sourceProofs':sources.proofs,
        'previousVisibleModels':len(before),'previousVisiblePlacements':sum(len(m['instances'])for m in before),
        'candidateVisibleModels':len(manifest['scenery']),'candidateVisiblePlacements':sum(len(m['instances'])for m in manifest['scenery']),
        'originalPreviewManifestSHA256':hashlib.sha256(original_bytes).hexdigest(),
        'oldSceneryUnchanged':True,'existingSavesReadOrWritten':False,'lightsChanged':False,
        'wholeMapAccepted':False,'browserAccepted':False,'sourceEffectType8Added':False,
        'limits':['Four original type15 primary model resources only; missing companion *_inside.bdae is not fabricated.',
          'Source inside-state camera/PHY gate and global visibility grouping are not wired by this candidate.',
          'Existing browser mip/filter, host clock origin, scene assembly and lighting adapter retained; not a complete original frame.',
          'No live server lift state or continuous full tutorial task route is asserted.']}
    manifest['sourceInsideRecovery']={'format':FORMAT,'url':write('audit.json',audit)};write('manifest.json',manifest)
    if source_manifest.read_bytes()!=original_bytes:raise ValueError('Reviewed source preview was modified')
    return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();r=export(a.runtime,a.output)
    print(json.dumps({k:r[k]for k in ('candidateVisibleModels','candidateVisiblePlacements','oldSceneryUnchanged','wholeMapAccepted','browserAccepted')}))
