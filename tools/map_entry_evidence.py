"""Reproduce tutorial entry evidence without inventing an original spawn.

Full source tables, descriptor bytes, native dumps and probe outputs stay local.
This tool neither writes character saves nor changes the live preview.
"""
import hashlib
import json
from pathlib import Path

def descriptor_wire(raw):
    """Read only the varint/length spans used by the embedded descriptors."""
    def varint(at):
        value=0
        for shift in range(0,70,7):
            if at>=len(raw):raise ValueError('Truncated descriptor varint')
            b=raw[at];at+=1;value|=(b&127)<<shift
            if b<128:return value,at
        raise ValueError('Unbounded descriptor varint')
    result=[];at=0
    while at<len(raw):
        tag,at=varint(at);number,wire=tag>>3,tag&7
        if not number:raise ValueError('Zero descriptor field')
        if wire==0:value,at=varint(at)
        elif wire==2:
            length,at=varint(at)
            if at+length>len(raw):raise ValueError('Truncated descriptor span')
            value=raw[at:at+length];at+=length
        else:raise ValueError('Unsupported descriptor wire')
        result.append((number,value))
    return result

def protocol_evidence(image):
    from native_combat import descriptor_fields
    raw=image.read(0x2028b48,64615)
    if hashlib.sha256(raw).hexdigest()!='40998743ad3be39eb76cb01d49030e2f73b0ccfc89b8a1654d8b45e82a01cbc1':
        raise ValueError('Original embedded descriptor file differs')
    fields=descriptor_wire(raw);messages=[v for n,v in fields if n==4]
    if len(messages)!=475:raise ValueError('Original message index differs')
    selected=[]
    for index,name in [(13,'GS2C_ObjectLocation'),(14,'GS2C_EnterMap')]:
        parsed=descriptor_fields(messages[index])
        if parsed['name']!=name:raise ValueError('Original message identity differs')
        type_names={dict(descriptor_wire(v))[1].decode():dict(descriptor_wire(v)).get(6,b'').decode()
                    for n,v in descriptor_wire(messages[index])if n==2}
        selected.append({'index':index,**parsed,'messageTypes':{k:v for k,v in type_names.items()if v}})
    # Original constructor's vtable -> metadata getter -> descriptor index 14.
    for at,size,expected in [
        (0x1b85d1c,20,'a073d14c003a243dfc70bbcfaa5b2a4bdbed8adfaeabf3ec97e404b6bb8fd563'),
        (0x1bb1948,52,'3928d637518bd6ec19771210fa685e8d279d2f5a97ffe3edf236017d35210362'),
        (0xa35654,144,'b7907311e46fcdcff1cf799245da28adaae620b809f203cf959a0e74cdbe59b9'),
        (0xa358c0,64,'77e7fb83ec647b93e4360fa372bae0c18dca2c9d3d0e9fec9719e45f3502e573')]:
        if hashlib.sha256(image.read(at,size)).hexdigest()!=expected:raise ValueError('Entry evidence bytes differ')
    return {'file':next(v.decode()for n,v in fields if n==1),'messages':selected,
            'handler':'0xa34f28','constructor':'0x1bb0b60','metadataGetter':'0x1bb1948',
            'descriptorIndex':14,'actualServerPayloadAvailable':False}

def source_entry_evidence():
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    from temple_assembly_evidence import entry_evidence
    source=Sources(DEFAULT_SOURCE);tables={}
    for name,key,map_key in [('map_transfer_point_info','id','location_map'),
                             ('teleport_spot','id','MapId'),('area_trigger','id','map_id'),
                             ('quest_map_exit','zone_id','map_id'),('bot_map_factory','id','map_id')]:
        rows=decode_ftable(source.read('tables/'+name+'.tbl'),key)['rows']
        selected=[r for r in rows if r[map_key]==5]
        tables[name]={'rows':len(rows),'map5Rows':len(selected)}
        if name=='area_trigger':
            tables[name]['triggerIDs']=[r[key]for r in selected]
            tables[name]['scripts']=[r['script']for r in selected]
    return {**entry_evidence(),'additionalTables':tables,'additionalSourceProofs':source.proofs,
            'triggerIsAnEntryPosition':False}

def probe_runtime(runtime):
    from analyze_native_resources import NativeImage
    from native_map_entry_probe import NativeMapEntryProbe
    runtime=Path(runtime);cfg=json.loads((runtime/'prototype/native-physics.json').read_text())
    image=NativeImage(Path(cfg['library']).read_bytes());engine=NativeMapEntryProbe(image)
    def source(name):
        r=cfg['sourceFiles'][name];raw=Path(r['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('Original collision input differs')
        return raw
    terrain=json.loads(Path(cfg['terrain']).read_text());profile=json.loads(Path(cfg['collision']).read_text())
    lighting=json.loads(Path(cfg['terrainLighting']).read_text())
    loaded=engine.load_world(terrain,profile,source,{tuple(t['tile']):t['runtimeFlags']for t in lighting['tiles']})
    cases=[]
    for y,stage,preserve in [(132.34999084472656,(1,4),False),(150,(1,4),False),
                            (172.3668975830078,(1,4),False),(196,(1,4),False),
                            (172.3668975830078,(0,4),False),(172.3668975830078,(1,3),False),
                            (196,(1,4),True)]:
        actor,entry=engine.entry_position([-2611.41015625,y,185.84120178222656])
        cases.append({'entry':entry,'support':engine.initial_support(actor,stage,preserve)})
    return {'protocol':protocol_evidence(image),'sourceEntries':source_entry_evidence(),
            'loaded':loaded,'cases':cases,'actualOriginalEntryKnown':False,
            'gameplayChanged':False,
            'scope':'explicit host stage/position/actor/static scene; original setter, center capture and complete initial-support CPU; no original server reply or Android frame'}

if __name__=='__main__':
    import argparse
    from tutorial_map_geometry import local_output
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    output=local_output(args.output);report=probe_runtime(args.runtime);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'cases':len(report['cases']),'actualOriginalEntryKnown':False,'gameplayChanged':False}))
