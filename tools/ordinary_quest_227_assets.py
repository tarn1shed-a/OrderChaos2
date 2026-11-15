"""Private quest227 geometry/material review, never a world actor admission.

Uses the existing strict 946 readers. A rejected clip/skin is preserved as a
named boundary. No fallback body, animation, texture or successful GPU is made.
"""
import hashlib
import json
from pathlib import Path
from ordinary_quest_227_probe import ROOT, AREA, SO

sha=lambda raw:hashlib.sha256(raw).hexdigest()


def review(source_file,output):
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from native_missing_records import MissingRecordProbe
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from bdae_character import aliases
    from scene_flags_evidence import literal_nodes
    from tutorial_npc_soldier_probe import strict_original_skin
    from tutorial_npc_final_pair_probe import source_or_native_default_basis
    from texture_decode import decode
    source_file=Path(source_file);output=Path(output)
    if not output.resolve().is_relative_to(AREA.resolve())or output.exists():raise ValueError('Use a new owned ignored review directory')
    source=json.loads(source_file.read_text())
    if source['format']!='oc2-original-quest227-inventory-v2':raise ValueError('Requires corrected descriptor-stem evidence')
    image=NativeImage(SO.read_bytes())
    if sha(image.data)!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4':raise ValueError('Original library pin differs')
    s=Sources(DEFAULT_SOURCE);output.mkdir(parents=True);choices={};raw_files={};parsed={};models=[];textures={};gaps=[]
    def get(name):
        rows=s.candidates(name)
        if len(rows)>1:
            if name!='texture/lightmap.tga'or{r['pack']for r in rows}!={'res_t.bin','res_t_upd10.bin'}:raise ValueError('Unreviewed archive choice '+name)
            if name not in choices:
                class Probe(MissingRecordProbe):
                    def call(self,address,registers,**options):
                        if address==0x54bc84:
                            at=self.alloc(len(name)+1);self.uc.mem_write(at,name.encode()+b'\0');registers={**registers,'X1':at}
                        return super().call(address,registers,**options)
                trace=Probe(image).fresh_archives({p.name for p in s.root.glob('*.bin')},{r['pack']for r in rows})
                if trace['order']!=['res_t_upd%d.bin'%n for n in range(10,16)]+['res_t.bin']or trace['selected']!='res_t_upd10.bin':raise ValueError('Original fresh res_t selection differs')
                choices[name]={'trace':trace,'freshMount':True,'emptyNameCache':True,'otherProvidersEmpty':True,'actualAndroidVFSObserved':False}
            selected=[r for r in rows if r['pack']==choices[name]['trace']['selected']]
            from resource_packs import read_entry
            raw=read_entry(selected[0],s.root)
        elif len(rows)==1:raw=s.read(name)
        else:raise ValueError('Missing original resource '+name)
        target=output/'original-resources'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        raw_files[name]={'path':str(target.relative_to(output)),'sha256':sha(raw),'bytes':len(raw),'pack':rows[0]['pack']if len(rows)==1 else choices[name]['trace']['selected']}
        return target
    base=source['npcAndMonster']['872']['model']['ModelPath']
    croc=source['npcAndMonster']['638']['model']['ModelPath']
    grave=source['finishObject']['display']['strPath']
    model_paths=[base]+[r['path']for r in source['nativeDefaultRequests']['npc872']['requests']if r.get('path')]+[croc,grave]
    base_nodes=None;native_base_reuse=None
    for name in dict.fromkeys(model_paths):
        row={'source':name,'renderAdmitted':False,'meshBindingOrVisibilityRecovered':False}
        try:
            r=BDAE(get(name));data=source_or_native_default_basis(r,r.parse(),image)
            nodes=literal_nodes(r)
            row.update(meshes=len(data['meshes']),materials=len(data['materials']),nodes=len(nodes),vertices=sum(m['vertexCount']for m in data['meshes']))
            if name==base:base_nodes=nodes
            skins=r.section(188)[0]
            if skins:
                try:
                    rig=strict_original_skin(r,data,external_nodes=base_nodes if name not in(base,croc,grave)else nodes)
                    data['rig']=rig
                    row['strictSkin']={'accepted':True,'skins':len(rig['skins']),'nodes':len(rig['nodes']),
                      'sourceFloatWeightsRetained':all(x['verification'].get('sourceFloatWeightsRetainedAfterStrictValidation')for x in rig['skins'])}
                except ValueError as error:
                    row['strictSkin']={'accepted':False,'reason':str(error)}
                    if name==base and str(error)=='Rest skeleton and inverse binds do not reproduce bind shape':
                        # This exact Model32 was already compared against all
                        # original controller/palette/vertex paths. Reuse only
                        # its matching base meshes, never the player's outfit.
                        old=ROOT/'analysis/raw/character-world-motion-20261115/female-v4-final'
                        files={key:old/path for key,path in {'model':'assets/character.json','native':'binding-private.json','sources':'sources-private.json'}.items()}
                        previous=json.loads(files['model'].read_text());proofs=json.loads(files['sources'].read_text())
                        native=next(x['proof']for x in json.loads(files['native'].read_text())if x['source']==name)
                        if proofs[name]['sha256']!=sha(r.path.read_bytes())or not native['originalCPUExecuted']or not native['sourcePoseInversesWeightsUnchanged']:raise ValueError('Original Model32 CPU reuse input differs')
                        fields=['name','aliases','parent','position','quaternion','scale']
                        if len(nodes)!=len(previous['rig']['nodes'])or any(any(x[k]!=y[k]for k in fields)for x,y in zip(nodes,previous['rig']['nodes'])):raise ValueError('Model32 original node semantics differ')
                        rig={'nodes':nodes,'skins':[],'quaternionConvention':'XYZW','matrixConvention':'column-major','coordinateSystem':'Y_UP'}
                        for index,mesh in enumerate(data['meshes']):
                            matches=[(i,m)for i,m in enumerate(previous['meshes'])if m['name']==mesh['name']]
                            if len(matches)!=1:raise ValueError('Model32 CPU source mesh not unique')
                            old_index,prior=matches[0]
                            if any(mesh[k]!=prior[k]for k in ['positions','normals','uvs','indices']if k in mesh):raise ValueError('Model32 CPU source geometry differs')
                            skin=next(x for x in previous['rig']['skins']if x['mesh']==old_index)
                            if not skin['verification']['sourceFloatWeightsRetainedAfterStrictValidation']:raise ValueError('Original Model32 float weights not retained')
                            rig['skins'].append({**skin,'mesh':index})
                        if {x['name']for x in rig['skins']}!={x['skin']for x in native['controllers']}:raise ValueError('Model32 exact original CPU controller coverage differs')
                        data['rig']=rig
                        native_base_reuse={'files':{key:{'path':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes())}for key,path in files.items()},
                          'modelSHA256':proofs[name]['sha256'],'animationSHA256':proofs[base.rsplit('/',1)[0]+'/anim/animations.bdae']['sha256'],
                          'meshCount':len(rig['skins']),'nodeCount':len(nodes),'allSourceGeometryAndTRSEqual':True,'noPlayerOutfitCopied':True,
                          'originalCPUProofReusedNotRerun':True,'maximumSourceRestDiagnostic':max(x['sourceRestEqualsBindDiagnosticError']for x in native['controllers'])}
                        row['nativeBaseReuse']=native_base_reuse
                    else:gaps.append({'source':name,'kind':'strict-skin','reason':str(error)})
            else:row['strictSkin']={'accepted':False,'reason':'No original skin controllers; static geometry is separate'}
            path=output/'parsed'/('model%d.json'%len(models));path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
            row['parsed']={'path':str(path.relative_to(output)),'sha256':sha(path.read_bytes())};parsed[name]=(r,data,nodes)
        except ValueError as error:row['readerRejected']=str(error);gaps.append({'source':name,'kind':'strict-model','reason':str(error)})
        models.append(row)
    for name in source['resources']:
        if name.endswith('.tga'):
            try:
                raw_path=get(name);picture=decode(raw_path.read_bytes());png=output/'png'/(sha(raw_path.read_bytes())+'.png');png.parent.mkdir(parents=True,exist_ok=True);picture.save(png)
                textures[name]={'sourceSHA256':sha(raw_path.read_bytes()),'size':list(picture.size),'png':str(png.relative_to(output)),'pngSHA256':sha(png.read_bytes())}
            except ValueError as error:gaps.append({'source':name,'kind':'strict-texture','reason':str(error)})
    animations=[]
    for entry,model in[(872,base),(638,croc)]:
        name=model.rsplit('/',1)[0]+'/anim/animations.bdae';path=get(name);a=BDAEAnimation(path)
        record={'entry':entry,'source':name,'actualNativePathResolved':False,'renderAdmitted':False}
        try:record['ranges']=a.ranges()
        except ValueError as error:
            count,table=a.section(84)
            record['rangeReaderRejected']=str(error)
            record['rawRangeRows']=[{'sourceName':a.string(a.q(table+i*24)),'sourceWords':list(a.unpack('4I',table+i*24+8))}for i in range(count)]
        try:
            clip=a.parse(['idle'])['clips'][0]
            if model not in parsed:raise ValueError('Model rejected; no implicit animation binding')
            node_map=aliases(parsed[model][2]);unbound=sorted({t['node']for t in clip['tracks']if t['node']not in node_map})
            record.update(clipName=clip['name'],tracks=len(clip['tracks']),duration=clip['duration'],unboundNodes=unbound)
            if unbound:gaps.append({'source':name,'kind':'idle-binding','unboundNodes':unbound})
        except ValueError as error:
            count,table=a.section(64);uncovered=[]
            for i in range(count):
                row=table+i*40;prop=a.rel(row+12);target=a.rel(row+20);values=list(a.unpack('8I',prop))
                if values[0]!=1 or values[1:3]!=[3,1]or values[4]!=6 or values[7]!=values[5]<<18:uncovered.append({'ordinal':i,'node':a.string(a.q(target)),'sourceSamplerWords':values,'targetType':a.u(target+8)})
            record.update(readerRejected=str(error),uncoveredSourceChannels=uncovered);gaps.append({'source':name,'kind':'strict-animation','reason':str(error)})
        animations.append(record)
    result={'format':'oc2-quest227-private-resource-review-v1','sourceInventory':{'path':str(source_file.relative_to(ROOT)),'sha256':sha(source_file.read_bytes())},
      'models':models,'textures':textures,'animations':animations,'sourceFiles':raw_files,'coldArchiveChoices':choices,'gaps':gaps,
      'materialApplication':'Original declaration and PNG decode only; no composed visibility, compiled reflection, shader or GPU success is supplied.',
      'runtimeEnabled':False,'renderAdmitted':False,'actualActivityOrQuestState':None,'savesServicesDeploymentTouched':False}
    target=output/'profile.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return{'path':str(target),'sha256':sha(target.read_bytes()),'models':len(models),'textures':len(textures),'gaps':gaps}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=AREA/'candidate-v2/source-v1.json');p.add_argument('--output',type=Path,default=AREA/'resource-review-v1');a=p.parse_args()
    print(json.dumps(review(a.source,a.output),ensure_ascii=False,indent=2))
