"""Re-run original equipped-slot consumers without real roles or game state.

Full source schemas, config bytes, original instructions and fixture reports stay
only below ignored analysis/raw/character-equipped-20261114/.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from analyze_native_resources import NativeImage
from character_equipped_probe import CharacterEquippedProbe
from character_progression_evidence import TABLES,profession_catalog,skill_schema
from optimized_abc import extract_abc,parse_abc,named_method
from resource_packs import ResourceArchive,DEFAULT_SOURCE
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-equipped-20261114'
LIBRARY=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
ROUTINES=(0x5f6ce0,0x6270ec,0x626fac,0x63fd84,0x7b80e8,0x5b2998,0x5ae560,
          0x573b74,0x578798,0x57887c,0x5bfb64,0x5c01bc,0xa100f0,0xa115ec,
          0xa0f6b0,0xa10034,0xa10054,0x91a53c,0xa1042c,0x4cd210,0xa78964)
def sha(raw):return hashlib.sha256(raw).hexdigest()


def load_tables(source=DEFAULT_SOURCE):
    archive=ResourceArchive(Path(source)/'tables.bin');tables={}
    for name,(key,expected)in TABLES.items():
        raw=archive.read('tables/'+name+'.tbl')
        if sha(raw)!=expected:raise ValueError('Original equipped input table changed')
        tables[name]=decode_ftable(raw,key)
    raw=archive.read('tables/String_Skill_zh.tbl')
    if sha(raw)!='3f27ebc3d3c192fc99c886249a94c91465a12cefd90611809c2a973053e8811b':raise ValueError('Original skill names changed')
    return tables,decode_localized_names(raw,'SC')['values']


def recover(output,source=DEFAULT_SOURCE,library=LIBRARY):
    output=Path(output).resolve()
    if not output.is_relative_to(RAW.resolve())or output.exists():raise ValueError('Choose a new ignored equipped evidence directory')
    output.mkdir(parents=True);image=NativeImage(Path(library).read_bytes());tables,names=load_tables(source);probe=CharacterEquippedProbe(image)
    routines={}
    for address in ROUTINES:
        meta,lines=image.routine(address);name=hex(address)+'.asm';(output/name).write_text('\n'.join(lines)+'\n')
        routines[hex(address)]={**meta,'sha256':sha(image.read(int(meta['start'],16),meta['size'])),'file':name}
    ui=ResourceArchive(Path(source)/'ui.bin');methods={};constants={}
    for stem in ['SkillSetting','SkillPassive']:
        raw=ui.read('ui/Flash/'+stem+'.swf');abc=parse_abc(extract_abc(raw));cls=next(c for c in abc['classes']if c['name']==stem)
        constants[stem]={}
        for trait in cls['traits']:
            if trait['name'].startswith('OPIT_')and trait.get('valueKind')==3:constants[stem][trait['name']]=abc['ints'][trait['value']]
        available={t['name']for t in cls['traits']if'method'in t}
        for name in ['onShow','onBtnSkillSlot','FindSlotCurrSkillItemEquipedOn']:
            if name in available:methods[stem+'.'+name]=named_method(abc,stem,name)
    conf=ResourceArchive(Path(source)/'conf.bin');configs={}
    for name in ['game.conf','game_a.conf','game_w.conf']:
        raw=conf.read('conf/'+name);(output/name).write_bytes(raw)
        configs[name]={'sha256':sha(raw),'bytes':len(raw),'NumOfSkillToShowLines':[line.decode(errors='replace')for line in raw.splitlines()if b'NumOfSkillToShow'in line]}
    catalogs={str(p):profession_catalog(tables,names,p)for p in range(1,6)}
    empty={}
    for p in range(1,6):empty[str(p)]=probe.receive_init_equipped(tables,profession=p,num_skills=6)
    init=probe.receive_init_equipped(tables,[(90,0),(90,2)],[(90,2,2),(94,0,6),(404,0,11)],page=2,operation_bank=3,num_skills=6)
    getters=[probe.get_slot(4,0,entries=[(4,0,2),(5,0,90)],active_slots=[-1,94,17,0,0]),
             probe.get_slot(5,0,entries=[(4,0,2),(5,0,90)],active_slots=[-1,94,17,0,0]),
             probe.get_slot(4,9,entries=[(4,0,2)],active_slots=[-1,94,17,0,0]),
             probe.get_slot(5,0,entries=[(5,0,90)],argument_type=1)]
    receipts=[probe.receive_equip(tables,90,2,2,success=s,operation_bank=2)for s in [None,False,True]]
    requests={'page':probe.page_request(tables,2),'active':probe.active_equip_request(tables,90,2),
              'invalidActiveSlot':probe.active_equip_request(tables,90,6)}
    mapping_snapshot={'format':'oc2-original-equipped-cache-v1','roleId':'native-projection-fixture-mage','profession':2,
        'operationBank':0,'skillPage':init['state']['skillPage'],'operationBanks':init['state']['operationBanks'],
        'actorSlots11To20':init['state']['actorSlots11To20'],'learningRecords':init['fixture']['learned'],
        'selectedRunes':[[row['skillId'],row['selectedRune']]for row in init['state']['activeRows']],
        'fixture':True,'source':'Original SkillInit consumer, stopped before shortcut restoration. operationBank=0 is explicit GetSkillIdByOpSlot(type4) context, not derived from skill_page.'}
    report={'format':'oc2-original-equipped-evidence-v1','nativeSHA256':sha(Path(library).read_bytes()),'routines':routines,
        'schema':{name:skill_schema(image)[name]for name in ['SMSG_SkillInit','CMSG_EquipSkill','CMSG_EquipShortcut','CMSG_EquipPage']},
        'methods':methods,'constants':constants,'configs':configs,'catalogs':catalogs,'mappingSnapshot':mapping_snapshot,
        'configSelection':{'boot':'4cd210; 4cd488 selects literal conf/game_a.conf; a78964 loads into 02528e28+8',
            'getter':'a0f6b0 calls a792c4([test],NumOfSkillToShow,default=6)',
            'boundary':'game_w.conf=4 is not the proven Android selection; all later overrides are not audited; samples use explicit config-return fixtures 6 or 4.'},
        'samples':{'emptyEquip':empty,'explicitEquip':init,'getters':getters,'equipReceipts':receipts,'requests':requests,
                   'configFour':probe.receive_init_equipped(tables,num_skills=4)},
        'boundaries':['No original server snapshot or saved role is accessed. All actor, op-object, config-return and message inputs are explicit fixtures.',
                      'Init runs through equipment then stops at573f34 before shortcut reconstruction. Equip receipt578798 and getters/request cores run to return.',
                      'AS numeric conversion/return, op virtual identity, presentation objects/delivery and downstream a1314c recalculation are host boundaries. Original parser/slot writes/selected-rune map/serializers execute.',
                      'Operation-manager bank selector and actor skill_page are separate fields. No source proof currently makes them equivalent.',
                      'An original SkillInit with an empty equip group triggers a client fallback. A missing snapshot or web hotbar:null is never this input.',
                      'Incoming EquipSkill applies raw fields without checking optional is_success; it does not grant learning or prove service permission.',
                      'CMSG_EquipPage outgoing0xac is executed; its dedicated incoming consumer has not been established.']}
    (output/'evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    checks={str(p.relative_to(output)):sha(p.read_bytes())for p in output.iterdir()if p.is_file()}
    (output/'SHA256.json').write_text(json.dumps(checks,indent=2)+'\n')
    return report


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--library',type=Path,default=LIBRARY)
    args=cli.parse_args();result=recover(args.output,args.source,args.library)
    print(json.dumps({'output':str(args.output/'evidence.json'),'routines':len(result['routines']),'sourceServerOrSavesUsed':False}))
