"""Recover part-ordered lightmap binding, without changing source light values.

Native local-reference resolution is executed on the original relocated BRES.
The original setter/count/getters and binding loop are checked separately by
native_part_lightmaps. Provider/material/texture objects there are fixtures.
"""
import hashlib
import json
from pathlib import Path
from tutorial_map_geometry import local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_lightmaps import read_records, object_records, source_names
from scene_lightmap_binding import material_request_slots

FORMAT='oc2-source-part-lightmaps-v1'
ROUTINES={
    0x1132210:(28,'287114df7b98cbd6e255fd8008c43047995d2f0b41c3197e4e258abcce070163'),
    0x113222c:(88,'c657353ed5cb1747cd8d174b892c6598b1ffe9c487b6703f152e2ed6834919f1'),
    0x1132284:(64,'ff00bdb4c1aba3d2713e76ac561742dd7d20d8b75867d3ef0293d584d045569c'),
}

def verify(image):
    from material_list_evidence import verify_native as material_verify
    from scene_lightmap_binding import verify_native as binding_verify
    material_verify(image);binding_verify(image)
    for at,(n,sha)in ROUTINES.items():
        if hashlib.sha256(image.read(at,n)).hexdigest()!=sha:raise ValueError('Original mesh part consumer changed')
    rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rel.get(0x244e410+slot)!=at for slot,at in [(0x20,0x1132210),(0x28,0x113222c),(0x30,0x1132284),(0x58,0x113235c)]):
        raise ValueError('Original mesh part dispatch changed')

def signature(row):return row['atlas'],tuple(row['uvTransform'])

def export(runtime,output):
    from analyze_native_resources import NativeImage
    from native_part_lightmaps import PartLightmapProbe
    from bres_world_bounds_evidence import inner_bres
    runtime,output=map(local_output,(runtime,output));assets=runtime/'game-data/converted'
    manifest=json.loads((assets/'source-map-record-gaps/manifest.json').read_text())
    profile=json.loads((assets/manifest['sceneBakedLighting']['url'][8:]).read_text())
    if profile['configuration']['modelSlot']!=0:raise ValueError('Only original slot0 is covered')
    image=NativeImage(Path(json.loads((runtime/'prototype/native-physics.json').read_text())['library']).read_bytes());verify(image)
    source=Sources(DEFAULT_SOURCE);probe=PartLightmapProbe(image)
    by={(r['model'],tuple(r['tile']),r['objectId']):r for r in profile['instances']}
    models=[];changes=[];native=[];counts={'models':len(manifest['scenery']),'instances':sum(len(e['instances'])for e in manifest['scenery'])}
    for entry in manifest['scenery']:
        data=json.loads((assets/entry['url'][8:]).read_text())
        if len(data['meshes'])!=1:raise ValueError('Multiple meshes need a separate source audit')
        order=[r['material']for r in data['meshes'][0].get('groups',[])]
        if order==list(range(len(data['materials']))):continue
        if sorted(order)!=list(range(len(data['materials']))):raise ValueError('Shared or absent part materials need separate recovery')
        raw=source.read(entry['model'])
        if hashlib.sha256(raw).hexdigest()!=data['sourceSHA256']:raise ValueError('Source model changed')
        refs=probe.references(inner_bres(raw))
        if [r['localIndex']for r in refs]!=order or any(data['materials'][r['localIndex']]['name']!=r['material']for r in refs):raise ValueError('Original material resolution differs')
        models.append({'model':entry['model'],'sourceSHA256':data['sourceSHA256'],'partToMaterial':order})
        for inst in entry['instances']:
            row=by.get((entry['model'],tuple(inst['tile']),inst['id']))
            if not row:raise ValueError('Original lightmap instance missing')
            bindings=row['bindings'];records=material_request_slots(object_records(read_records(source.read(row['recordPath'])),inst['id']))
            original=[{'ordinal':r['sortKey'],'atlas':source_names('tutorial',*inst['tile'],atlas=r['atlasIndex'])['texture'],'uvTransform':r['uvParameter']['whenUniformPresent']}for r in records]
            if bindings!=original:raise ValueError('Converted binding differs from original DAT')
            delta=[{'part':part,'material':idx,'oldBinding':idx if idx<len(bindings)else 0,'sourceBinding':part if part<len(bindings)else 0}for part,idx in enumerate(order)if signature(bindings[idx if idx<len(bindings)else 0])!=signature(bindings[part if part<len(bindings)else 0])]
            if delta:
                changes.append({'model':entry['model'],'id':inst['id'],'tile':inst['tile'],'changedParts':delta,'bindings':bindings})
                native.append({'model':entry['model'],'id':inst['id'],'tile':inst['tile'],**probe.bindings(order,bindings)})
    if (len(models),len(changes),len({r['model']for r in changes}))!=(55,17,9):raise ValueError('Covered source part-order population changed')
    policy={'format':FORMAT,'world':'tutorial','profile':'APK_Default','slot':0,'models':models,'originalDeviceObserved':False,'lightingValuesChanged':False}
    manifest['sourcePartLightmaps']={'url':'/assets/source-map-part-lightmaps/policy.json','format':FORMAT}
    audit={'format':FORMAT,**counts,'nonIdentityModels':len(models),'nonIdentityInstances':sum(len(e['instances'])for e in manifest['scenery']if e['model']in {m['model']for m in models}),'changedInstances':len(changes),'changedModels':9,'changes':changes,'nativeLoop':native,'sourceProofs':source.proofs,'lightingValuesChanged':False,'limits':['Original part references and binding-loop CPU execution; loaded provider, material and texture identities are explicit fixtures.','Does not recover actual Android GPU state or a complete original frame.','17 incorrect associations corrected; global darkness remains unproven. Single-part temple04 is unaffected.']}
    output.mkdir(parents=True,exist_ok=True)
    for name,data in [('policy.json',policy),('manifest.json',manifest),('audit.json',audit)]:
        (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return audit

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k]for k in ['models','instances','nonIdentityModels','nonIdentityInstances','changedInstances','changedModels']}))
