"""Compare temple geometry/placement with source and original ITM/quaternion code.

This audit deliberately does not repair or fill surfaces. Matching source inputs
does not establish the original active scene or explain screenshot holes.
"""
import hashlib
import json
import struct
import tempfile
from pathlib import Path

def audit(runtime):
    from tutorial_map_geometry import local_output
    from map_loading_evidence import Sources,read_world_container
    from resource_packs import DEFAULT_SOURCE
    from bdae_convert import BDAE
    from terrain_convert import read_instances
    from bdae_skin import compose
    from scene_collision import geometry_transforms
    from bres_world_bounds_evidence import verify_native
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
    from analyze_native_resources import NativeImage
    from source_physics import SourcePhysics
    runtime=local_output(runtime);assets=runtime/'game-data/converted'
    manifest=json.loads((assets/'source-temple-sampling/manifest.json').read_text())
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());image=NativeImage(Path(cfg['library']).read_bytes());verify_native(image)
    sources=Sources(DEFAULT_SOURCE);world=read_world_container(sources.read('world/tutorial.wld'))
    words=struct.pack('<3I',*world['configurationWords']);models=[];instances=[]
    probe=NativeBresWorldBoundsProbe(image);rotation=SourcePhysics(image)
    with tempfile.TemporaryDirectory()as tmp:
        for item in manifest['scenery']:
            if item['model']not in {f'model/scene_generator_temple_000/god_temple{i:02d}.bdae'for i in range(1,6)}:continue
            raw=sources.read(item['model']);path=Path(tmp)/'model.bdae';path.write_bytes(raw)
            reader=BDAE(path);original=reader.parse();current=json.loads((assets/item['url'][8:]).read_text())
            if current['sourceSHA256']!=hashlib.sha256(raw).hexdigest()or len(current['meshes'])!=len(original['meshes']):raise ValueError('Temple source/mesh count differs')
            for a,b in zip(current['meshes'],original['meshes']):
                for key in ('positions','normals','uvs','indices','groups'):
                    if a[key]!=b[key]:raise ValueError('Temple geometry/UV/group differs: '+key)
            transforms=geometry_transforms(reader,original)
            if any(m.get('sourceNodeTransform')!=transforms[i]for i,m in enumerate(current['meshes'])):raise ValueError('Temple node transform differs')
            models.append({'model':item['model'],'sourceSHA256':hashlib.sha256(raw).hexdigest(),
                           'meshes':len(original['meshes']),'triangles':sum(m['triangleCount']for m in original['meshes']),
                           'skins':reader.section(188)[0],'animations':reader.section(196)[0],
                           'geometryUVAndGroupsEqual':True,'nodeTransformsEqual':True})
            for inst in item['instances']:
                tx,tz=inst['tile'];name=f'world/tutorial/items/{tx:04d}_{tz:04d}.itm';itm=sources.read(name)
                path=Path(tmp)/Path(name).name;path.write_bytes(itm);rows=read_instances(path)
                matches=[(i,r)for i,r in enumerate(rows)if r['id']==inst['id']]
                if len(matches)!=1:raise ValueError('Temple ITM match ambiguous')
                index,row=matches[0]
                if any(row[k]!=inst[k]for k in row):raise ValueError('Temple placement differs')
                trs=probe.itm_transform(itm[24+index*76:24+(index+1)*76],inst['tile'],words)
                expected=[*inst['position'],*inst['quaternion'],*inst['scale']]
                if max(abs(a-b)for a,b in zip(trs,expected))>0.00025:raise ValueError('Native ITM transform differs')
                q=rotation.scratch;rotation.w(q,'4f',*inst['quaternion'])
                rotation.call(0x11dd3e0,{'X0':q,'X1':q+128});matrix=list(rotation.r(q+128,'16f'))
                for c in range(3):
                    for r in range(3):matrix[c*4+r]*=inst['scale'][c]
                matrix[12:15]=trs[:3]
                web=compose(inst['position'],inst['quaternion'],inst['scale'])
                delta=max(abs(a-b)for a,b in zip(web,matrix))
                if delta>0.00025:raise ValueError('Browser/native root matrix differs')
                instances.append({'model':item['model'],'tile':inst['tile'],'id':inst['id'],
                                  'nativeITMEqualsExport':True,'matrixMaxDelta':delta})
    if len(models)!=5 or len(instances)!=8:raise ValueError('Temple inventory changed')
    return {'models':models,'instances':instances,'sources':sources.proofs,
            'nativeScope':'original a61bdc-a61c70 ITM transform and 11dd3e0 quaternion CPU only; source node tree read independently',
            'originalAndroidFrameObserved':False,'templeHolesFixed':False,
            'limits':['Geometry/placement equality is not proof of complete source world assembly or final drawing.',
                      'This audit supplies no surfaces, lights, collision restrictions, spawn positions or original server state.']}

if __name__=='__main__':
    import argparse
    from tutorial_map_geometry import local_output
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit(a.runtime);out=local_output(a.output)
    if out.exists():raise ValueError('Preserve existing audit')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'models':len(result['models']),'nativeInstances':len(result['instances']),'templeHolesFixed':False}))
