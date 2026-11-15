"""Original982/1017 defaults, static pose fields and per-garment mask evidence."""
import argparse,hashlib,json,tempfile,math
from pathlib import Path
from tutorial_npc_robe_probe import RobeProbe
from tutorial_npc_catalog_probe import CatalogVisibilityProbe,BASE
from tutorial_npc_inventory import audit
from tutorial_npc_remaining_probe import coverage as previous_coverage
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output
from skill_attachments import decode_ftable
from bdae_convert import BDAE
from bdae_attributes import primitive_bindings

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-npc-final-pair-native-v1'
FOCUS=(982,1017)
BOOT='model/item/armor/6_feet/oc2_human_m_light_19_dark_moon_feet.bdae'


def scalar_default_execution(image,defaults,overrides):
    """Real constructor and numeric loader, with an explicit reflected layout.

    The source-property view contains only the original numeric properties.
    Texture requests/technique selection/FX compilation/GPU are not simulated.
    """
    from source_physics import SourcePhysics
    from character_materials import SCALARS
    from unicorn import UC_HOOK_CODE
    if set(defaults)!=set(SCALARS)or not set(overrides)<=set(defaults):raise ValueError('Uncovered scalar default set')
    if hashlib.sha256(image.data).hexdigest()!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4':raise ValueError('Original numeric consumer image differs')
    class Probe(SourcePhysics):
        def hook(self,uc,at,size,data):
            if at==0x3c0fbc:
                if self.get('X0')!=0x40+4*len(SCALARS)or self.get('W1')!=0x1000:raise ValueError('Original scalar material allocation differs')
                self.material=self.alloc(self.get('X0'));uc.mem_write(self.material,bytes([0xa5])*(0x40+4*len(SCALARS)));self.set('X0',self.material)
            elif at==0x11ddd2c:
                name=self.cstr(self.get('X1')).decode()
                if name not in self.objects or self.get('W2')not in[0,1]:raise ValueError('Unexpected numeric source-name interner input')
                self.set('X0',self.objects[name])
            elif at==0x13daa40:
                self.copied=list(self.r(self.get('X0')+0x40,str(len(SCALARS))+'f'));return
            elif at==0x13e0b30:
                self.writes.append({'index':self.get('W1'),'sourceType':self.get('W2'),'count':self.get('W5'),'stride':self.get('W6')});return
            else:return super().hook(uc,at,size,data)
            self.set('PC',self.get('X30'))
    p=Probe(image);p.copied=[];p.writes=[]
    for at in[0x3c0fbc,0x11ddd2c,0x13daa40,0x13e0b30]:p.uc.hook_add(UC_HOOK_CODE,p.hook,begin=at,end=at)
    effect=p.alloc(0x100);reference=p.alloc(8);declarations=p.alloc(24*len(SCALARS));block=p.alloc(4*len(SCALARS));source=p.alloc(80);properties=p.alloc(32*max(1,len(overrides)));out=p.alloc(8)
    p.w(reference,'Q',effect);p.w(effect,'I',100);p.w(effect+0x1a,'H',len(SCALARS));p.w(effect+0x20,'I',4*len(SCALARS));p.w(effect+0x40,'Q',declarations);p.w(effect+0x50,'Q',block)
    for i,name in enumerate(SCALARS):
        obj=p.alloc(128);p.w(obj+0x10,'I',1000);p.uc.mem_write(obj+24,name.encode()+b'\0');p.objects[name]=obj
        p.w(declarations+24*i,'2Q',obj,4*i);p.w(declarations+24*i+0x11,'B',8);p.w(declarations+24*i+0x14,'H',1);p.w(block+4*i,'f',defaults[name])
    p.w(source+0x20,'Ii',len(overrides),properties-(source+0x24))
    for i,(name,number)in enumerate(overrides.items()):
        prop=properties+32*i;text=p.alloc(len(name)+1);p.uc.mem_write(text,name.encode()+b'\0');value=p.alloc(12)
        p.w(prop,'Q',text);p.w(prop+16,'2I',8,1);p.w(prop+24,'2i',value-(prop+24),value+8-(prop+28));p.w(value,'2I',1,0);p.w(value+8,'f',number)
    p.call(0x1129190,{'X8':out,'X1':p.alloc(16),'X3':reference,'X4':source,'X5':p.alloc(16)},limit=100000)
    if p.r(out,'Q')[0]!=p.material:raise ValueError('Original numeric material output differs')
    result=dict(zip(SCALARS,p.r(p.material+0x40,str(len(SCALARS))+'f')))
    if p.copied!=[defaults[k]for k in SCALARS]or result!={**defaults,**overrides}or len(p.writes)!=len(overrides):raise ValueError('Original effect defaults/material override differs')
    return {'nativeCPU':True,'entry':'0x1129190','loader':'0x112920c','constructor':'0x13baac8','retain':'0x13daa40','numericSetter':'0x13e0b30',
      'sourceFXDefaults':defaults,'copiedBeforeOverrides':dict(zip(SCALARS,p.copied)),'sourceMaterialOverrides':overrides,'result':result,'originalNumericWrites':p.writes,
      'compiledNumericLayoutIsExplicitFixture':True,'sourceViewContainsOnlyOriginalNumericProperties':True,'FXCompilationObserved':False,'actualGPUObserved':False}


def final_material_record(reader,name,fx_reader,image):
    """Strict old reader except this source boot's verified sparse scalar set."""
    from character_materials import read_material_record,SCALARS,SAMPLERS
    try:return read_material_record(reader,name)
    except ValueError:
        if reader.path.name!=Path(BOOT).name or name!='_7_-_Default':raise
    n,t=reader.section(172);rows=[t+i*80 for i in range(n)if reader.string(reader.q(t+i*80))==name]
    if len(rows)!=1:raise ValueError('Ambiguous sparse boot material')
    row=rows[0];effect=reader.string(reader.q(row+8));effect_name=reader.string(reader.q(row+16))
    if effect!='lt_cull_pal_normal_solid.bdae'or effect_name!='#lt_cull_pal_normal_solid-fx':raise ValueError('Sparse boot FX differs')
    n,t=reader.u(row+32),reader.rel(row+36);values={};samplers={};technique=None;seen=set();nt,tt=reader.section(148)
    for i in range(n):
        at=t+32*i;field=reader.string(reader.q(at));kind=reader.u(at+16);v=reader.rel(at+28)
        if field in seen or reader.u(at+20)!=1:raise ValueError('Sparse boot property identity/count differs')
        seen.add(field)
        if field in SCALARS:
            number=reader.unpack('f',v)[0]
            if kind!=8 or not math.isfinite(number)or not 0<=number<=16:raise ValueError('Sparse boot scalar differs')
            values[field]=number
        elif field in SAMPLERS:
            ptr=reader.rel(v)
            if kind!=17 or not tt<=ptr<tt+nt*32 or(ptr-tt)%32:raise ValueError('Sparse boot sampler differs')
            samplers[field]=reader.string(reader.q(ptr+16))
        elif field.endswith('/CurrentTechnique'):
            if kind!=28:raise ValueError('Sparse boot technique differs')
            technique=reader.named_technique(v)
        else:raise ValueError('Uncovered sparse boot property')
    if set(values)!=set(SCALARS[:3])or set(samplers)!=set(SAMPLERS)or technique is None:raise ValueError('Uncovered sparse boot parameters')
    fx=fx_reader(effect);nf,tf=fx.section(164)
    if nf!=1 or fx.string(fx.q(tf))!=effect_name[1:]:raise ValueError('Sparse boot source FX identity differs')
    profiles=[]
    for field in[32,36]:
        profile=fx.rel(tf+field);np,tp=fx.u(profile+8),fx.rel(profile+12);defaults={}
        for i in range(np):
            at=tp+32*i;key=fx.string(fx.q(at))
            if key not in SCALARS:continue
            if key in defaults or fx.u(at+8)!=8 or fx.u(at+16)!=1 or fx.unpack('2I',fx.rel(at+20))!=(1,0):raise ValueError('Sparse boot FX scalar declaration differs')
            value=fx.unpack('f',fx.rel(at+24))[0]
            if not math.isfinite(value)or not 0<=value<=16:raise ValueError('Sparse boot FX scalar value differs')
            defaults[key]=value
        if set(defaults)!=set(SCALARS):raise ValueError('Sparse boot FX numeric defaults missing')
        profiles.append({key:defaults[key]for key in SCALARS})
    if profiles[0]!=profiles[1]:raise ValueError('Sparse boot source profiles disagree')
    proof=scalar_default_execution(image,profiles[0],values)
    return {'effectPath':effect,'effectName':effect_name,'scalars':proof['result'],'samplers':samplers,
      'sourceMaterialRecordOffset':row,'sourceTechniqueName':technique['name'],'sourceTechniqueValueWord0':technique['valueWord0'],
      'scalarDefaultInheritance':proof,'missingMaterialScalars':list(SCALARS[3:])}


def boot_palette_address_execution(image):
    from native_temple_sampling import TempleSamplingProbe
    p=TempleSamplingProbe(image);texture=p.alloc(0x80);state=p.alloc(0x100);driver=p.alloc(0x4000);config=p.alloc(0x200)
    p.w(texture+0x28,'Q',state);p.w(texture+0x30,'3I',16,16,1);p.w(state+0x48,'Q',driver);p.w(driver+0x2e8,'Q',config);p.w(state+0x70,'f',1)
    p.call(0x146f58c,{'X0':texture,'W1':0,'W2':1});p.gl=[];p.call(0x14320d4,{'X0':texture})
    if p.gl!=[{'name':'glTexParameteri','target':3552,'parameter':10242,'value':33071}]:raise ValueError('Original enum1 palette sampler differs')
    return {'nativeCPU':True,'setter':'0x146f58c','consumer':'0x14320d4','sourceEnumU':1,'originalGLWrapS':33071,'calls':p.gl,
      'textureAndDriverAreExplicitFixtures':True,'actualGPUObserved':False,'webMapping':'ClampToEdgeWrapping'}


def source_or_native_default_basis(reader,data,image):
    """Keep real streams, or the original14118f8 missing-attribute constants.

    A differing per-primitive stream selection still rejects. No UV-derived
    tangent generation and no change to the frozen strict source-only reader.
    """
    count,table=reader.section(180)
    if count!=len(data['meshes']):raise ValueError('Original final-pair mesh order differs')
    native_defaults=None
    for ordinal,mesh in enumerate(data['meshes']):
        wrapper=reader.rel(table+ordinal*24+20);body=reader.q(wrapper+8)+((reader.u(wrapper+4)&0xffffff)-1)*8
        attributes=reader.u(body+16);count=reader.u(body+96);primitives=reader.rel(body+100)
        bindings=[primitive_bindings(reader,primitives+i*88,attributes)for i in range(count)]
        if not bindings:raise ValueError('Original primitive binding is empty')
        for semantic,name,runtime,default_index in[(22,'sourceTangents',18,0),(18,'sourceBinormals',22,1)]:
            indices={r.get(semantic)for r in bindings}
            if len(indices)!=1:raise ValueError('Per-primitive tangent selection differs')
            index=indices.pop()
            if index is None:
                if native_defaults is None:
                    from native_scene_palette import PaletteProbe
                    native_defaults=PaletteProbe(image).missing_attributes()
                value=native_defaults['calls'][default_index]['value']
                mesh[name]=value[:3]*mesh['vertexCount']
                mesh.setdefault('sourceTangentBindings',{})[name]={'sourceSemantic':semantic,'runtimeSemantic':runtime,
                  'sourceStreamAbsent':True,'nativeDefaultValue':value,'nativeDefaultConsumer':'0x14118f8',
                  'generatedFromUV':False,'nativeProgramReflectionIsExplicitFixture':True}
                mesh['nativeMissingAttributeEvidence']=native_defaults
                continue
            stride=reader.u(reader.rel(body+20)+index*4);offset=reader.u(reader.rel(body+28)+index*4)
            kind=reader.u(reader.rel(body+36)+index*4);width=reader.u(reader.rel(body+44)+index*4);vertex=reader.q(body+64);size=reader.q(body+72)
            if kind!=6 or width!=3 or offset+12>stride or(mesh['vertexCount']-1)*stride+offset+12>size:raise ValueError('Uncovered original tangent stream layout')
            values=[round(v,7)for i in range(mesh['vertexCount'])for v in reader.unpack('3f',vertex+i*stride+offset)]
            if name in mesh and mesh[name]!=values:raise ValueError('Existing source tangent differs')
            mesh[name]=values;mesh.setdefault('sourceTangentBindings',{})[name]={'sourceSemantic':semantic,'attributeIndex':index,'stride':stride,'offset':offset,'components':3,'generated':False}
    return data


def coverage_after(inventory):
    result=previous_coverage(inventory,(973,1013))
    previous=ROOT/'analysis/raw/tutorial-npc-remaining-20261114/handoff.json'
    for row in result['templates']:
        row['currentBatchReviewed']=False
        if row['entry']in[973,1013]:row['priorAssetEvidence']={'handoff':str(previous.relative_to(ROOT)),'sha256':hashlib.sha256(previous.read_bytes()).hexdigest()}
        if row['entry']==972:row['knownGaps']=['Original chest100037 Flags hide the beard with missing skinColorMask. Prior attribution to hood is superseded by this per-item execution.']
        if row['entry']not in FOCUS:continue
        row['currentBatchReviewed']=True;row['skinStatus']='strict-source-binding-reviewed';row['animationStatus']='independent-original-idle-request;actual-pose-unknown'
        row['knownGaps']=['Original chest Flags hide beard002_002 with absent source skinColorMask; no substitute.']
        if row['entry']==982:
            row['stage']='body-reviewed-weapon-UT-gap';row['defaultMaterialStatus']='visible-body-source-profile-reviewed;weapon-UT-gap'
            row['knownGaps'].append('Original200029 UT actual globals/reflection/cache remain unknown; weapon not rendered.')
        else:row['stage']='visible-default-reviewed-hidden-source-gap';row['defaultMaterialStatus']='visible-default-materials-reviewed'
    result['summary']['stages']={key:sum(r['stage']==key for r in result['templates'])for key in sorted({r['stage']for r in result['templates']})}
    result['summary']['currentBatchReviewed']=list(FOCUS);return result


def recover(image,source=DEFAULT_SOURCE):
    inventory=audit(source);sources=Sources(source);p=RobeProbe(image,sources);originals={r['entry']:r for r in inventory['creatures']};entries=[]
    models={r['ID']:r for r in decode_ftable(sources.read('tables/itemmodeldata.tbl'),'ID')['rows']}
    logic=decode_ftable(sources.read('tables/quest_objective_logic.tbl'),'id')['rows']
    if any(r['quest_id']==202 and r['entry']in FOCUS for r in logic):raise ValueError('Selected final-pair202 relationship scope changed')
    with tempfile.TemporaryDirectory(prefix='oc2-final-mask-')as tmp:
        f=Path(tmp)/'base';f.write_bytes(sources.read(BASE));names=[m['name'].removesuffix('-mesh')for m in BDAE(f).parse()['meshes']]
        ablation=[];parts972=p.parts(951)
        for slot in[9,11,14]:
            request=p.part_resource(slot,parts972['slots'][slot],parts972['slots'][0]);key=next(r['id']for r in request['tableLookups']if r['table']=='itemmodeldata'and r['found']);model=models[key]
            v=CatalogVisibilityProbe(image);v.bind_original_parts(names)
            for i in range(7):v.feature_request(i,'feature:'+str(i)if parts972['slots'][i]else None)
            before=v.visibility()['feature:2'];mask=v.apply_item_mask(model['Flags0'],model['Flags1'])
            ablation.append({'entry':972,'singleSourceSlot':slot,'sourceItemKey':parts972['slots'][slot],'sourceModel':model,
              'beforeBeardVisible':before,'afterBeardVisible':v.visibility()['feature:2'],'nativeRemappedMask':str(mask)})
    if [r['afterBeardVisible']for r in ablation]!=[True,False,True]:raise ValueError('Original per-item beard mask evidence differs')
    for entry in FOCUS:
        original=originals[entry];display=original['appearance']['creaturedisplayinfo_id'];selection=p.entry_selection(entry)
        if selection['result']['selectedDisplayAtD60']!=display:raise ValueError('Original final-pair default display differs')
        parts=p.parts(display)
        if any(parts['slots'][i]for i in[7,8]):raise ValueError('Uncovered unnamed source feature')
        requests=[p.part_resource(i,parts['slots'][i],parts['slots'][0])for i in range(7)]
        requests.extend(p.part_resource(i,parts['slots'][i],parts['slots'][0])for i in range(9,15)if parts['slots'][i])
        candidate=next(c for c in original['appearanceCandidates']if c['display']['ID']==display)
        entries.append({'entry':entry,'name':original['name'],'original':original,'defaultCandidate':candidate,'entrySelection':selection,
          'parts':parts,'resourceRequests':requests,'defaultIdle':p.idle(entry,display),'sourceScriptKey':original['prototype']['script'],
          'sourceStaticPoseFields':[{'spawnId':r['id'],**{key:r[key]for key in['standstate','emote_state','movetype','bytes1','bytes2']}}for r in original['spawns']],
          'staticPoseFieldsFedAsActivity':False,'quest202Start':202 in original['questStartReferences'],'quest202ObjectiveReferences':[],
          'actualGUID':None,'actualAppearanceOverrides':None,'actualPose':None,'questAvailability':None})
    return {'format':FORMAT,'entries':entries,'families':[{'model':entries[0]['defaultCandidate']['model'],'entries':list(FOCUS)}],
      '972PerItemMaskAttributionCorrection':{'cases':ablation,'correction':'The default beard-hidden fact is unchanged. Hood-alone does not hide it; chest100037 does. Prior hood-cause wording is superseded.',
        'oldFilesOrPackagesChanged':False,'defaultVisibleRenderingResultChanged':False},
      'sourceProofs':sources.proofs,'inventorySourceProofs':inventory['sourceProofs'],'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
      'actualActivityObserved':False,'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing final-pair evidence stays preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':len(result['entries']),'maskAblationCases':3}))
