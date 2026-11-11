"""Inventory actual omitted source instances, grouping shared formats and gaps.

Full rows, pointers, original values and files stay in ignored local output.
This is inspection, not a model/lighting fallback or a rendering admission rule.
"""
import collections,hashlib,json,tempfile
from pathlib import Path
from bdae_convert import BDAE
from scene_sampling import material_samplers
from scene_render_state import effect_render_state
from scene_collision import geometry_transforms
from scene_lightmaps import read_records,object_records,source_names
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output

FORMAT='oc2-source-scene-omission-inventory-v1'


def nodes(reader):
    count,table=reader.section(220)
    if count!=1:raise ValueError('Expected one original node tree')
    result=[];seen=set()
    def visit(at):
        if at in seen or len(seen)>4096:raise ValueError('Cyclic or excessive original node tree')
        seen.add(at);reader.at(at,96);items=[];n,p=reader.u(at+80),reader.rel(at+84)
        for i in range(n):
            item=p+8*i;kind=reader.u(item);ref=reader.rel(item+4);reader.at(ref,16)
            items.append({'type':kind,'reference':reader.string(reader.q(ref+8)),'sourceOffset':ref})
        result.append({'name':reader.string(reader.q(at)),'attachments':items})
        n,p=reader.u(at+72),reader.rel(at+76)
        if n>1024:raise ValueError('Excessive source children')
        for i in range(n):visit(p+96*i)
    n,p=reader.u(table+16),reader.rel(table+20)
    for i in range(n):visit(p+96*i)
    return result


def analyze(runtime,output,manifest='source-map-trees/manifest.json'):
    runtime,output=map(local_output,(runtime,output));assets=runtime/'game-data/converted';m=json.loads((assets/manifest).read_text());selection=json.loads((assets/m['sourceSelection']['url'].removeprefix('/assets/')).read_text());source=Sources(DEFAULT_SOURCE);output.mkdir(parents=True,exist_ok=True)
    ledger=[];models={};effects={};record_gaps=[]
    with tempfile.TemporaryDirectory()as tmp:
        for omission in selection['preview']['omitted']:
            matches=[r for r in selection['instances']if r['id']==omission['id']and(r.get('requestedModel')==omission['path']or r.get('recordPath')==omission['path'])and r['admission']=='admittedBeforeTypeFactory']
            if len(matches)!=1:raise ValueError('Omitted instance is ambiguous; require tile-qualified source evidence')
            row=matches[0];name=row['requestedModel'];ledger.append({'id':row['id'],'tile':row['tile'],'model':name,'position':row['position'],'reason':omission['reason']})
            if name not in models:
                raw=source.read(name);p=Path(tmp)/'model.bdae';p.write_bytes(raw);reader=BDAE(p);parsed=reader.parse();materials=material_samplers(reader)
                try:geometry_transforms(reader,parsed);node_gap=None
                except ValueError as e:node_gap=str(e)
                models[name]={'sourceSHA256':hashlib.sha256(raw).hexdigest(),'bufferSHA256':hashlib.sha256(reader.b).hexdigest(),'materials':materials,'nodes':nodes(reader),'nodeGap':node_gap,'meshCount':len(parsed['meshes']),'instances':0,'properties':[]}
                for material in materials:
                    fx=material['effectPath']
                    if fx not in effects:
                        p=Path(tmp)/'fx.bdae';p.write_bytes(source.read(fx));f=BDAE(p);effects[fx]={'bufferSHA256':hashlib.sha256(f.b).hexdigest(),**effect_render_state(f)}
                n,p=reader.section(172)
                for i in range(n):
                    at=p+80*i;cnt,prop=reader.u(at+32),reader.rel(at+36);fields=[]
                    for j in range(cnt):
                        a=prop+j*32;kind=reader.u(a+16);value=reader.rel(a+28)
                        fields.append({'name':reader.string(reader.q(a)),'sourceType':kind,'count':reader.u(a+20),'sourceOffset':value,**({'floatValues':list(reader.unpack('f'if kind==8 else'3f',value))}if kind in(8,10)else{})})
                    models[name]['properties'].append({'name':reader.string(reader.q(at)),'fields':fields})
            models[name]['instances']+=1
            if omission['reason']=='selected slot lightmap record or atlas missing':
                slot=selection['settings']['ForceModelLodLevel'];table=read_records(source.read(row['recordPath']));records=object_records(table,row['id']);alternates=[]
                for other in(0,1):
                    req=source_names('tutorial',*row['tile'],slot=other)
                    exists=bool(source.candidates(req['record']));rows=object_records(read_records(source.read(req['record'])),row['id'])if exists else[]
                    alternates.append({'slot':other,'record':req['record'],'filePresent':exists,'objectRecords':len(rows)})
                record_gaps.append({'id':row['id'],'tile':row['tile'],'model':name,'selectedSlot':slot,'recordPath':row['recordPath'],'selectedObjectRecords':len(records),'bindings':row['bindings'],'slotChecks':alternates,'appliedAlternative':False})
    material_groups=collections.defaultdict(lambda:{'models':[],'instances':0})
    for name,data in models.items():
        key=' | '.join(sorted({v['effectPath']for v in data['materials']}));material_groups[key]['models'].append(name);material_groups[key]['instances']+=data['instances']
    result={'format':FORMAT,'manifest':manifest,'omittedInstances':len(ledger),'uniqueModels':len(models),'effects':effects,'models':models,'ledger':ledger,'recordGaps':record_gaps,'sharedMaterialGroups':dict(material_groups),'reasonCounts':dict(collections.Counter(r['reason']for r in ledger)),'sources':source.proofs,'renderingChanged':False,'limits':['A node reference type2 is recorded without inventing type3 geometry binding.','Alternate slot records are inspected, never substituted for selected slot0.','Effect names and macros do not by themselves prove active inputs or rendered behavior.']}
    (output/'omissions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=analyze(a.runtime,a.output);print(json.dumps({k:r[k]for k in('omittedInstances','uniqueModels','reasonCounts')}))
