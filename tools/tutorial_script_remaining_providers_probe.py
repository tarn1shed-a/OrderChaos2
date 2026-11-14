"""Pinned original FS remaining providers and bounded startup-order contract.

Static original instructions/xrefs only. No provider, open result, actual path,
startup state, stream or script is manufactured or executed.
"""
import argparse,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/tutorial-script-remaining-providers-20261115'
SO=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
PINS={'0x12705a4': [400, 'c08706aa49aa7a392897831cf794403c9417e9539fbc6b8931954a8b3cc0482c'], '0x12709dc': [564, '1c807e2f4623db361cf619a0c8559d8f1c941a2d8d55bd3dc16ea548d4a92ad4'], '0x127699c': [728, '51833013a134bcd850d17971e2f28a306202c1750771f1c616d6fd1b1e790693'], '0x127b86c': [260, '1a83397b295ff98a47be7f651359baac3ca1820eb10a21977b3c10148fb04749'], '0x127b9f4': [556, '14c0bb8694663fc5a88560957f8a309802f0dcbc865ebdd4be45ddedc5a7091a'], '0x1276f34': [252, '64f47120279815180fa5659d51d6b0ea38d10c85c097704cec9b03c9e1e592b9'], '0x12717f0': [424, '92e56dc3f7283466d2b90acb5c7af36ac50647c548fac4faac93b12581deab63'], '0x1270734': [680, '6a42ac98fd3b2914242e843147d377169e6de8cb26a78a4b20e3a35eef7f6f36'], '0x3ba314': [2016, 'd5082ffc5cb0ac7e701141482a852f7ad9abc2083a1a3d7bb8767e7410fa5527'], '0x8e335c': [232, 'b7608e74f499a6d8984a8f99351f60cb20cd23db9fe20348bfa56a638665068d'], '0x8e3864': [1616, 'b44826797ef328b930dd210c86638235973c10dfd8d9a7acc497d77933b04e1a'], '0x8ec1b4': [16, '12e8497545b5160c34bf55523c8656a391103d9458be92e8c714ffc97a61a058'], '0x2f8728': [16, 'beb9de58f04db1953496361d56dd2c09b82a9c88d313e493c3f6a5085bc34be1'], '0x8f7a14': [1720, 'a4ca88ce5969d98aff954d14b79ad6e1daa9a24ade6e435599e623f0d2bc73a1']}
PARENT_CORRECTIONS={'tools/tutorial_script_quest_refs_probe.py': {'oldSHA256': '6210635fc8ab5d681ad9733b6e6f809ed98d3a6762e40c6248afc5edde287ca3', 'currentSHA256': 'd5140d6d1175ec65401538cca8f2e2b14525e9615af0aa5c0da30c3d0164266e', 'parentCommit': 'd30e1d3', 'reason': 'Move private NativeImage import into run for public CI without capstone'}, 'docs/TUTORIAL_SCRIPT_QUEST_REFS.md': {'oldSHA256': '663649993910a494dee518983a61328ba7c9ab2a7631d5e91f52101d9e6fbe01', 'currentSHA256': '7eea6629fe4b06f5043f460eaeb953319f06154c8340d0aaf4652a141addd1b1', 'parentCommit': 'd30e1d3', 'reason': 'Distinguish public checkout1pass8skip from local public-only2pass7skip'}}
CALLS={0x1270a9c:0x127699c,0x1270b5c:0x129e70c,0x1270654:0x127b86c,
       0x12706c8:0x129e5ac,0x127badc:0x1274120,0x127ba50:0x15441d0,
       0x1276ff8:0x1274f00,0x3ba70c:0x8f7a14,0x3ba5fc:0x2f8728,0x3ba674:0x2f8728}
SLOTS={0x24160f0:{0x38:0x1270734,0x40:0x12705a4,0x48:0x12709dc,0x78:0x12717f0},
       0x246e948:{0x20:0x1276f34},0x246ebb8:{0x20:0x127b9f4},
       0x24211e8:{0x20:0x8ec1b4,0x28:0x8e3864},0x2421238:{0x38:0x8e335c}}
OPS={0x3ba5f8:('ldr','x22, [x8, #0x40]'),0x3ba610:('blr','x22'),
     0x3ba620:('ldr','x8, [x8, #0x38]'),0x3ba638:('blr','x8'),
     0x3ba648:('ldr','x8, [x8, #0x38]'),0x3ba660:('blr','x8'),
     0x3ba670:('ldr','x22, [x8, #0x78]'),0x3ba680:('blr','x22'),
     0x1270798:('cbz','x23, #0x1270970'),0x1270a38:('cbz','x24, #0x1270ba8'),
     0x8e33cc:('ldr','w21, [x20, #0x50]'),0x8e33ec:('cmp','w21, #2'),
     0x8e340c:('add','x8, x8, #0x1d8'),0x8e3410:('add','x8, x8, #0x10'),
     0x8e3418:('str','x8, [x19]'),0x3ba6e0:('cbnz','w8, #0x3ba728')}
NAMES={0x1dfa6b9:'main.31320.com.gameloft.android.ANMP.GloftO2HM.obb',
       0x1dfd556:'patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb'}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def section_at(image,address):
    return next((s.name for s in image.elf.iter_sections()if s['sh_addr']<=address<s['sh_addr']+s['sh_size']),None)
def frozen_check():
    before=AREA/'before-frozen.json'
    if not before.is_file():return {'available':False,'sourceChecksSkipped':True}
    rows=json.loads(before.read_text())
    if len(rows)!=215:raise ValueError('Expected215 prior frozen files')
    parent_changes=[]
    for name,row in rows.items():
        current=digest(ROOT/name)
        if current==row['sha256']:continue
        correction=PARENT_CORRECTIONS.get(name)
        if not correction or correction['oldSHA256']!=row['sha256'] or correction['currentSHA256']!=current:
            raise ValueError('Unapproved old source change '+name)
        parent_changes.append({'path':name,**correction})
    drafts={'native_character_entry.py':'77a2f2b69bd846b1b96cbc68aee732c68f6959370c3dfe8826ddb08aae8cdd8a',
        'standard_abc.py':'a93057561936010e5adf0249cc569b80e8c5924e58882e349ef368c599ba7152',
        'tutorial_npc_bitmap_domain_probe.py':'3d76d7b7bfbc2a105d22979212beb1d007ba1a65dd7e04cbfd73f5911d090772'}
    for name,expected in drafts.items():
        p=ROOT/'tools'/name
        if p.exists()and digest(p)!=expected:raise ValueError('Protected draft/checkpoint changed '+name)
    return {'available':True,'oldFiles':len(rows),'unchangedOldFiles':len(rows)-len(parent_changes),
        'oldManifestPreserved':True,'parentCorrections':parent_changes,'protectedDraftsAndCheckpoint':'unchanged'}
def refs(image,name):
    path=AREA/name;source=json.loads(path.read_text())
    if source['program']['sha256']!=hashlib.sha256(image.data).hexdigest():raise ValueError('Different Ghidra source image')
    result=[]
    for q in source['queries']:
        response=q['result']
        if response['has_more']or response['total']!=len(response['items']):raise ValueError('Truncated references')
        result.append({'target':q['request']['args']['address'],'references':[
            {**r,'section':section_at(image,int(r['from'],16)),
             'unwindMetadataOnly':section_at(image,int(r['from'],16))in('.eh_frame','.eh_frame_hdr')}
            for r in response['items']]})
    return result

def inspect():
    from analyze_native_resources import NativeImage
    image=NativeImage(SO.read_bytes())
    for address,(size,expected)in PINS.items():
        if hashlib.sha256(image.read(int(address,16),size)).hexdigest()!=expected:raise ValueError('Original routine changed '+address)
    for a,target in CALLS.items():
        word,=struct.unpack('<I',image.read(a,4));delta=word&0x3ffffff
        if delta&(1<<25):delta-=1<<26
        if word&0xfc000000!=0x94000000 or a+delta*4!=target:raise ValueError('Original BL changed '+hex(a))
    rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()if r['r_info_type']==1027}
    for table,slots in SLOTS.items():
        for offset,value in slots.items():
            if rel.get(table+offset)!=value:raise ValueError('Real vtable slot differs')
    for a,expected in OPS.items():
        instruction=next(image.disassembler.disasm(image.read(a,4),a))
        if(instruction.mnemonic,instruction.op_str)!=expected:raise ValueError('Original branch/virtual operation changed '+hex(a))
    for a,text in NAMES.items():
        if image.read(a,len(text)+1)!=text.encode()+b'\0':raise ValueError('Original OBB constant differs')
    return {'format':'oc2-original-remaining-fs-providers-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'verification':{'routinePins':len(PINS),'directBLs':len(CALLS),'relocatedSlots':sum(map(len,SLOTS.values())),
            'originalOperations':len(OPS),'OBBConstants':len(NAMES),'execution':'static native/Ghidra evidence only'},
        'frozen':frozen_check(),
        'remainingGroups':[
            {'field':'FS+40','writer':'12709dc','defaultFSVirtualSlot':'48','providerVptr':'246e948','openSlot20':'1276f34',
             'kind':'PAK-style archive:12B header,64B directory entries (56B names + offset/length)',
             'sourceHeaderCheck':'1276a14..1276a2c checks byte0=P OR byte1=A; do not strengthen into full PACK signature validation',
             'inputGate':'FS v18 returned non-null stream;127699c parse result is not checked before insertion',
             'actualClientV48CallInBoundedFrame':None},
            {'field':'FS+58','writer':'12705a4','defaultFSVirtualSlot':'40','providerVptr':'246ebb8','openSlot20':'127b9f4',
             'kind':'physical-directory prefix provider, not an archive alias map',
             'pathNormalizer':'127b86c copies prefix and ensures final slash',
             'actualOpen':'prefix+requestedName ->15441d0 exists ->1274120 physical reader; null remains possible',
             'sourceClientMountCall':'3ba610 currentFS v40','sourceClientRemoveCall':'3ba680 currentFS v78 ->12717f0',
             'prefixProducer':'2f8728 returns C++string at global2526fb0+8; actual string value unknown'}],
        'OBBMount':{'appFrame':'3ba314','condition':'App+3c0==3',
            'actualVirtualCalls':[{'pc':'3ba638','slot':'currentFS+38','constantVA':'1dfa6b9','filename':NAMES[0x1dfa6b9]},
                {'pc':'3ba660','slot':'currentFS+38','constantVA':'1dfd556','filename':NAMES[0x1dfd556]}],
            'argumentW2W3W4':[1,1,1],'defaultTarget':'1270734','providerVptr':'246eb58','vector':'FS+28',
            'openGate':'127078c invokesFSv18;1270798 rejects null before construction/append',
            'existsGuardSeparate':False,'indexReader':'127a484','indexReaderReturnGatesAppend':False,
            'actualOpenOrMountSuccessObserved':False,'contentsOrScriptsKnown':False,
            'externalCollectionCandidate':'Android/obb/com.gameloft.android.ANMP.GloftO2HM/ + the exact two filenames; candidate location, not observed runtime prefix'},
        'boundedOrder':{'withinState3':['temporary folder v40','main OBB v38','patch OBB v38','remove same folder v78',
            'if2528209==0:8f4e3c then8f7a14','guard2528209=1 regardless8f7a14 result;Appstate4'],
            'resourceCall':'3ba70c ->8f7a14','initialFeedTaskProducer':'8e335c selects and enqueues child on owner+8',
            'initialFeedChoice':'controller+50!=2 selects vptr24211e8;==2 selects2421288',
            'initialFeedMethod':'24211e8+28=8e3864, task.v20=8ec1b4 requires task+14==-1',
            'actualSchedulerCallOrderAgainst8f7a14':None,'earlierOrLaterInitialFeedProved':False},
        'references':{n:refs(image,n)for n in ('writer-xrefs-v1.json','order-xrefs-v1.json','feed-task-xrefs-v1.json','feed-queue-xrefs-v1.json')},
        'noProviderCreated':True,'noOpenSuccessSupplied':True,'actualInitialFeedStreamRecovered':False,
        'scriptBodyRecovered':False,'gameSaveServiceOrDeploymentChanged':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--public-only',action='store_true');a=p.parse_args()
    if a.public_only:r={'format':'oc2-remaining-providers-public-boundary-v1','frozen':frozen_check(),'originalSourceChecks':'skipped; original ELF/Ghidra records stay private','noProviderCreated':True}
    else:r=inspect()
    if a.output:
        out=a.output.resolve()
        if not out.is_relative_to(AREA.resolve())or out.exists():p.error('New private output required')
        out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verification':r.get('verification'),'frozen':r['frozen'],'noProviderCreated':True,'actualInitialFeedStreamRecovered':False}))
