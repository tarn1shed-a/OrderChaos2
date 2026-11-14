"""Finite static field-flow audit of the 14 direct quests getter callers.

No original CPU state chain, packet, file loader or script is executed. Original
Ghidra records and instruction bytes are private inputs, not game providers.
"""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SO=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
AREA=ROOT/'analysis/raw/tutorial-script-quest-refs-20261115'
XREFS=ROOT/'analysis/raw/tutorial-script-entry-20261115/manager-xrefs-response-v1.json'
ROWS={0x3e7638:(0x1d8,'Type copied into related-record summary'),
 0x8b8df8:(0x148,'TrackingId returned'),0x418388:(0x150,'Title localized'),
 0x49e558:(0x190,'Quest selection, TrackingId and presentation/analytics scalars'),
 0x4a24bc:(0x138,'Current record TrackingId returned'),0x9ebec4:(0x180,'NPC interaction relation -> quest Type summary'),
 0xa4572c:(0x480,'Received quest handling, TrackingId and presentation/analytics scalars'),
 0xa43d40:(0x3c8,'Received query handling, TrackingId and presentation/analytics scalars'),
 0xa48200:(0x1b0,'Received quest handling and analytics scalar fields'),
 0xa46b8c:(0x2d0,'Received quest completion handling and presentation/analytics scalar fields'),
 0xa4a3c4:(0x218,'Quest-event presentation and analytics scalar fields'),
 0x8b13a4:(0x350,'Type/Title/Objectives display'),0x8b2e08:(0x150,'Title localized'),0x83fe44:(0x148,'Title localized')}

def num(value):return int(value,0)
def width(mnemonic,operands):
    first=operands.split(',')[0].strip()
    w=16 if first.startswith('q') else 8 if first.startswith(('x','d')) else 4 if first.startswith(('w','s')) else 1
    if mnemonic.endswith('b'):w=1
    if mnemonic.endswith('h'):w=2
    return w*(2 if mnemonic.startswith(('ldp','stp')) else 1)

def native_slot_audit(image,start,callsite,row_offset):
    meta,asm=image.routine(start);raw=image.read(int(meta['start'],16),meta['size'])
    ins=list(image.disassembler.disasm(raw,int(meta['start'],16)))
    if not any(i.address==callsite and i.mnemonic=='bl' and i.op_str=='#0xc99370'for i in ins):raise ValueError('Original direct call differs')
    after=[i for i in ins if i.address>callsite]
    lookup=next(i.address for i in after if i.mnemonic=='blr')
    cleanup=max(i.address for i in ins if i.address>lookup and i.mnemonic=='bl' and i.op_str=='#0x3e78a4')
    saved=None;subtract=0;fp=None
    for i in ins[:24]:
        m=re.search(r'\[sp, #(-?0x[0-9a-f]+)\]!',i.op_str)
        if i.mnemonic=='stp' and m and saved is None:saved=-num(m[1])
        m=re.fullmatch(r'x29, sp, #(0x[0-9a-f]+)',i.op_str)
        if i.mnemonic=='add' and m:fp=-saved+num(m[1])
        m=re.fullmatch(r'sp, sp, #(0x[0-9a-f]+)',i.op_str)
        if i.mnemonic=='sub' and m:subtract+=num(m[1])
    if saved is None or fp is None:raise ValueError('Unsupported original frame prologue')
    frame=saved+subtract;slot=-row_offset+0x70;touches=[]
    for i in ins:
        if not i.mnemonic.startswith(('ld','st')):continue
        m=re.search(r'\[(sp|x29)(?:, #(-?0x[0-9a-f]+))?\]',i.op_str)
        if not m:continue
        address=(-frame if m[1]=='sp' else fp)+(num(m[2])if m[2] else 0)
        w=width(i.mnemonic,i.op_str)
        if address<slot+8 and slot<address+w:
            touches.append({'pc':hex(i.address),'instruction':i.mnemonic+' '+i.op_str,
                'read':i.mnemonic.startswith('ld'),'withinRowLookupLifetime':lookup<i.address<cleanup})
    return {'functionStart':meta['start'],'bytes':meta['size'],'sha256':hashlib.sha256(raw).hexdigest(),
        'getterCall':hex(callsite),'tableVirtualLookup':hex(lookup),'lastCleanupCall':hex(cleanup),
        'scriptStackOffsetFromEntry':slot,'directStackTouches':touches,
        'scriptDirectReadsInLookupLifetime':[t for t in touches if t['read'] and t['withinRowLookupLifetime']],
        'unwindInstructions':asm}

def run():
    from analyze_native_resources import NativeImage
    image=NativeImage(SO.read_bytes());original=json.loads(XREFS.read_text())
    if original['program']['sha256']!=hashlib.sha256(image.data).hexdigest():raise ValueError('Ghidra program differs')
    q=next(q for q in original['queries']if q['request']['args']['address']=='0xc99370')
    direct={};excluded=[]
    for ref in q['result']['items']:
        address=int(ref['from'],16);section=next((s.name for s in image.elf.iter_sections()if s['sh_addr']<=address<s['sh_addr']+s['sh_size']),None)
        if section=='.text' and ref['type']=='UNCONDITIONAL_CALL':direct[int(ref['from_function']['address'],16)]=address
        else:excluded.append({'address':hex(address),'section':section,'type':ref['type']})
    if direct.keys()!=ROWS.keys()or q['result']['has_more']:raise ValueError('Bounded direct-call inventory differs')
    result=[]
    for address,(row_offset,role)in ROWS.items():
        path=AREA/(hex(address)+'-decompile.json');response=json.loads(path.read_text());code=response['result']['code']
        if response['result']['truncated']:raise ValueError('Complete original decompilation required')
        token='auStack_'+format(row_offset,'x');script='local_'+format(row_offset-0x70,'x');lines=code.splitlines()
        refs=[{'line':i+1,'text':line.strip()}for i,line in enumerate(lines)if re.search(r'\b'+script+r'\b',line)]
        lookups=[i for i,line in enumerate(lines)if token in line and '0x18))' in line]
        if len(lookups)!=1:raise ValueError('Explicit original row lookup must be unique')
        at=lookups[0];end=max(i for i in range(at+1,len(lines))if'FUN_003e78a4('+token+')'in lines[i])
        lifetime=[{'line':i+1,'text':lines[i].strip()}for i in range(at+1,end+1)if re.search(r'\b'+token+r'\b',lines[i])]
        native=native_slot_audit(image,address,direct[address],row_offset)
        instructions=native.pop('unwindInstructions')
        (AREA/(hex(address)+'-instructions.json')).write_text(json.dumps({'proof':native,'instructions':instructions},indent=2)+'\n')
        result.append({'address':hex(address),'reviewedNonScriptUse':role,'rowLocal':token,'scriptLocal':script,
            'scriptFieldOffset':0x70,'decompilerScriptLocalReferences':refs,'rowLifetimeForwarding':lifetime,
            'decompilationSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'native':native,
            'scriptToLoaderOrCallIdentified':False})
    return {'format':'oc2-quests-script14-direct-caller-audit-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'xrefInputSHA256':hashlib.sha256(XREFS.read_bytes()).hexdigest(),'callers':result,'excludedMetadata':excluded,
        'scope':'14 named direct c99370 callers only. Direct stack-slot and decompiled row-lifetime checks; not a whole-program/indirect-alias proof.',
        'scriptLoaderIdentified':False,'scriptBodyRecovered':False,'wholeProgramAbsenceProved':False,
        'originalCPUChainRerun':False,'packetsSent':False,'savesOrProductionAccessed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if not out.is_relative_to(AREA.resolve()) or out.exists():p.error('New private audit output required')
    r=run();out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'callers':len(r['callers']),'scriptLoaderIdentified':False,'output':str(out)}))
