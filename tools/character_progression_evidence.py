"""Read-only character progression evidence from the pinned 3.1.3a client.

Full original tables/ABC/protocol descriptors are written only below analysis/raw.
Nothing here reads character saves, awards XP, learns skills or runs a server.
"""
import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path

from native_combat import descriptor_fields
from optimized_abc import disassemble, extract_abc, extract_named_abc, named_method, parse_abc
from character_portraits import _ABC, decode_abc_metadata
from ui_assets import Bits, tags
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names

ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    'player_xp': ('level', 'ca0bdfe917708248d25df97e8de84890465ad1031a56fde747b2e93b2ce05a67'),
    'playerinfo': ('level', '266f64b4dc13bd44f060fc551779f93481ecc865d3f3893e721a02f54121e524'),
    'skill_unlock': ('id', 'ed5215c9e6c65fa1f78c88841d34687ee0308baec15feb8a49a0bcd3b39bb7a1'),
    'skill_proto': ('skillId', 'fa674aec24fe3d6b9779376efa212936ad3b400774db31c9bd16dfa661db7c19'),
    'skill_runes': ('id', '36fde9142ccf35c8761e5e123eb93d38a519aca30687b4c0ec5ed12d956d28b5'),
    'skill_tree_filter': ('Id', '32389771d8ecf8edd2169b8548e707c6250f72bb505dcbeec27d7b0bb61bc5b3'),
    'skill_combo': ('id', 'f8dada75a9802ae312edeaf0ca3273c74cb7ef8bd9a0ab9dbe5fd297c88d71ae'),
    'skill_basic_attack': ('id', '6342e9f7fd4029b0e4d411835012110aada4fd650557a8f5dd852caeaa80271c'),
}
METHODS = {
    'ExpBar.refresh': '3867cc08e154885af0dc01dc299bb5618ec28d0abd228aa3025ff655286af8fc',
    'AttributePage.SetAttributeValueExp': 'a1871ececb03835c5e621a9ae2f96dd9edb1056e3a5d7dc747fbc9c8f936ef4f',
    'AttributePage.setAttributePlayerClass': '1cc6e865ebf88c453741e4816e245d522ac68ee981ad643183c664e9b01b1663',
    'SkillSetting.MessageBoxLearnSkill': '599b3e778f4c55be811b832a908ca23e5995ac3f0b37379110bc40c2cfbb6706',
    'SkillSetting.MessageBoxLearnRune': 'cdda3ad95ecf7ab94d4f685fc015b19d5a34dce406f9f63549f3a7344bb8c03c',
    'SkillSetting.ShowSkillDetail': '710c28925a01c6717954be21a2a7d1ae73b41882dcda77ffcf1acdb68988d77e',
    'SkillSetting.onShow': 'e530aaf7ac6f7b5e44c2bfb73473f2b7775d4ed59fd9fa263e92863482f81256',
}
ROUTINES = {
    0x668014: (7640, 'b9d212b80a0a401faaddc9443a9241cb91b7542ca7e004df6eda62d1e5aa6fec'),
    0x6a60e4: (388, '4ffcc204522f8d3e9079e72a3a19e634d2a10e331c23cb0930dfb33bed111e5c'),
    0x1d50204: (64, 'b8f116cb9ae465ef63cfbfa2a355d2619671ce5a19bef1e35c7f9ca502be32ef'),
    0x1d50370: (52, '7a8c8177fba86159ceaadc11e52a299d69e1dbb1aecf0c3f463514306924e884'),
    0x1d50798: (208, '78defa7956a014c6d6a40989f203c15d8174efa05749748049610711ebafa43f'),
    0xa0f510: (304, 'd9f7faf6ef006e8ae88b1dc6f8a09ff64ed79992dc7826a0c5d311c63badaafe'),
    0xa0f968: (1700, '64f308357acfd8933b3975b4e962907172ceb62f5dab78d172712690bc4aa6ed'),
    0xa0f0f8: (244, 'ba9f4c91fdb74974affa04c909273cb2d41642ce105e47fdaff04c059b3e4284'),
    0x1dcb628: (96, 'df52b867b51bdc3a4327efc8646c41d5830be6e0cf6bd65a4ed412dd55d0ffde'),
    0x6fd340: (284, '78391553add4386ad513468f856c18999aca319d64cdc58ca7d0edcb343235e1'),
}
SKILL_DESCRIPTOR = (0x2040bf3, 0x163d, 'db6c1fd1ca8dfee6ce6838022db5d8f4a2b78e4591b9f1556ef460da2298189f')
PROFESSIONS = (1, 2, 3, 4, 5)


def creation_abc(raw):
    """Bounded standard DoABC reader for the pinned creation SWFs only.

    Most runtime SWFs use the existing reordered-ABC reader. These original
    creation files instead contain standard tag 82 and standard method order.
    This independent reader neither imports nor alters user-owned draft tools.
    """
    if raw[:3] == b'CWS':
        raw = b'FWS'+raw[3:8]+zlib.decompress(raw[8:])
    if raw[:3] != b'FWS' or len(raw)<12 or struct.unpack_from('<I',raw,4)[0] != len(raw):
        raise ValueError('Invalid creation SWF extent')
    bits=Bits(raw,8); bits.rect(); blocks=[]
    for kind,at,size in tags(raw,bits.pos()+4,len(raw)):
        if kind == 82:
            block=raw[at:at+size]; end=block.find(b'\0',4)
            if end<4:raise ValueError('Invalid creation ABC wrapper')
            blocks.append(block[end+1:])
    if len(blocks)!=1:raise ValueError('Expected one standard creation ABC')
    data=blocks[0]; metadata=decode_abc_metadata(data); r=_ABC(data)
    r.at=metadata['constantPoolBytes']; names=['*',*metadata['multinames']]; strings=metadata['strings']
    def ref(pool):
        value=r.variable()
        if value>=len(pool):raise ValueError('Creation ABC pool reference outside bounds')
        return value
    count=r.count(); signatures=[]
    def method():
        mid=r.variable()
        if mid>=count:raise ValueError('Creation method outside bounds')
        return mid
    def traits():
        out=[]
        for _ in range(r.count()):
            name=names[ref(names)]; flags=r.byte(); kind=flags&15; item={'name':name,'kind':kind}
            if flags&0x80:raise ValueError('Unsupported creation ABC trait flags')
            if kind in (0,6):
                item.update(slot=r.variable(),type=names[ref(names)],value=r.variable())
                if item['value']:item['valueKind']=r.byte()
            elif kind in (1,2,3):item.update(disp=r.variable(),method=method())
            elif kind==4:item.update(slot=r.variable(),classIndex=r.variable())
            elif kind==5:item.update(slot=r.variable(),method=method())
            else:raise ValueError('Unsupported creation ABC trait')
            if flags&0x40:item['metadata']=[r.variable() for _ in range(r.count())]
            out.append(item)
        return out
    for _ in range(count):
        n=r.count(); returns=names[ref(names)]; params=[names[ref(names)] for _ in range(n)]
        name=strings[ref(strings)]; flags=r.byte()
        optional=[(r.variable(),r.byte())for _ in range(r.count())]if flags&8 else []
        if len(optional)>n:raise ValueError('Invalid creation optional parameter count')
        param_names=[strings[ref(strings)]for _ in range(n)]if flags&128 else []
        signatures.append({'params':params,'return':returns,'name':name,'flags':flags,
                           'optional':optional,'paramNames':param_names})
    annotations=[]
    for _ in range(r.count()):
        name=ref(strings); n=r.count(); keys=[ref(strings)for _ in range(n)]
        annotations.append({'name':name,'keys':keys,'values':[ref(strings)for _ in range(n)]})
    classes=[]
    for _ in range(r.count()):
        name,parent,flags=names[ref(names)],names[ref(names)],r.byte()
        if flags&~15:raise ValueError('Unsupported creation instance flags')
        namespace=r.variable()if flags&8 else None
        interfaces=[names[ref(names)]for _ in range(r.count())]
        classes.append({'name':name,'super':parent,'flags':flags,'namespace':namespace,
                        'interfaces':interfaces,'iinit':method(),'traits':traits()})
    for cls in classes:cls.update(cinit=method(),staticTraits=traits())
    scripts=[{'init':method(),'traits':traits()}for _ in range(r.count())]; bodies={}
    for _ in range(r.count()):
        mid=method()
        if mid in bodies:raise ValueError('Duplicate creation ABC body')
        stack,locals_,scope,max_scope=[r.variable()for _ in range(4)]
        length=r.count(); offset=r.at; code=r.take(length); exceptions=[]
        for _ in range(r.count()):
            begin,end,target=[r.variable()for _ in range(3)];type_,name=ref(names),ref(names)
            if not 0<=begin<end<=length or not 0<=target<length:raise ValueError('Invalid creation exception span')
            exceptions.append([begin,end,target,type_,name])
        activation=traits()
        if scope>max_scope or locals_<len(signatures[mid]['params'])+1:raise ValueError('Invalid creation frame')
        bodies[mid]={'offset':offset,'code':code,'maxStack':stack,'locals':locals_,'scope':scope,
                     'maxScope':max_scope,'exceptions':exceptions,'traits':activation}
    if r.at != len(data):raise ValueError('Trailing creation ABC bytes')
    pool=_ABC(data);pool.take(4)
    ints=[0]+[pool.variable(0xffffffff)for _ in range(max(0,pool.count()-1))]
    ints=[v-(1<<32)if v&(1<<31)else v for v in ints]
    uints=[0]+[pool.variable(0xffffffff)for _ in range(max(0,pool.count()-1))]
    doubles=[float('nan')]+[struct.unpack('<d',pool.take(8))[0]for _ in range(max(0,pool.count()-1))]
    return {'classes':classes,'scripts':scripts,'signatures':signatures,'bodies':bodies,
            'names':names,'strings':strings,'ints':ints,'uints':uints,'doubles':doubles,
            'sourceSHA256':digest(data),'bytesConsumed':r.at}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def local_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Original progression evidence must stay in ignored analysis/raw/')
    path.mkdir(parents=True, exist_ok=True)
    return path


def wire_fields(raw):
    """Inspect a bounded descriptor (not a game packet or protobuf group decoder)."""
    def varint(at):
        result = 0
        for shift in range(0, 70, 7):
            if at >= len(raw):
                raise ValueError('Truncated descriptor integer')
            byte = raw[at]; at += 1
            if shift == 63 and byte > 1:
                raise ValueError('Oversized descriptor integer')
            result |= (byte & 127) << shift
            if byte < 128:
                return result, at
        raise ValueError('Oversized descriptor integer')
    at = 0
    while at < len(raw):
        tag, at = varint(at); field, wire = tag >> 3, tag & 7
        if not 1 <= field <= 0x1fffffff:
            raise ValueError('Invalid descriptor field')
        if wire == 0:
            value, at = varint(at)
        elif wire == 2:
            size, at = varint(at)
            if size > len(raw)-at:
                raise ValueError('Truncated descriptor span')
            value = raw[at:at+size]; at += size
        else:
            raise ValueError('Unsupported descriptor wire')
        yield field, wire, value


def skill_schema(image):
    address, size, expected = SKILL_DESCRIPTOR
    raw = image.read(address, size)
    if digest(raw) != expected:
        raise ValueError('Original Skill.proto differs; retrace required')
    result = {}
    def message(data):
        parsed = descriptor_fields(data)
        parsed['nested'] = [message(v) for n,w,v in wire_fields(data) if n == 3]
        return parsed
    fields = list(wire_fields(raw))
    if [v for n,w,v in fields if n == 1] != [b'Skill.proto']:
        raise ValueError('Different original descriptor file')
    for n,w,v in fields:
        if n == 4:
            parsed = message(v)
            if parsed['name'] in result:
                raise ValueError('Duplicate original message')
            result[parsed['name']] = parsed
    return result


def verify_native(image):
    for address, (size, expected) in ROUTINES.items():
        if digest(image.read(address, size)) != expected:
            raise ValueError('Original progression routine differs; retrace required')
    return skill_schema(image)


def profession_catalog(tables, names, profession):
    """Select static source requirements, never a learned/unlocked/equipped list.

    needprofession is essential: several player/passive protos have reqProfession
    zero. rune_id is a slot index, not skill_runes.id. category is preserved,
    because this build has category=0 even for its passive requirements.
    """
    if type(profession) is not int or profession not in PROFESSIONS:
        raise ValueError('Only the verified five-profession entry is supported')
    protos = {r['skillId']:r for r in tables['skill_proto']['rows']}
    runes = {r['id']:r for r in tables['skill_runes']['rows']}
    filters = {r['Id']:r for r in tables['skill_tree_filter']['rows']}
    requirements = {}
    for row in tables['skill_unlock']['rows']:
        if row['needprofession'] != profession:
            continue
        key = row['skill_id'], row['rune_id']
        if key in requirements or type(key[1]) is not int or key[1] not in range(4):
            raise ValueError('Duplicate/unsupported original skill requirement')
        requirements[key] = row
    result = []
    for skill_id in sorted({skill for skill,index in requirements}):
        proto = protos.get(skill_id)
        if not proto or proto['reqProfession'] not in (0, profession):
            raise ValueError('Original profession requirement mismatch')
        if (skill_id,0) not in requirements:
            raise ValueError('Missing base-skill requirement')
        entries = []
        for index in range(4):
            requirement = requirements.get((skill_id,index))
            if requirement is None:
                continue
            rune = runes.get(proto['rune'+str(index)])
            if not rune or not names.get(rune['nameStrId']):
                raise ValueError('Missing original rune/name; no fallback skill')
            entries.append({'index':index, 'sourceRuneId':rune['id'],
                'name':names[rune['nameStrId']], 'icon':rune['icon'],
                'requirement':dict(requirement), 'sourceRuneReqLevel':rune['reqLevel']})
        source_filter = filters.get(proto['filter'])
        if source_filter is None:
            raise ValueError('Missing original skill classification')
        # a0f968 classifies from the proto attributes byte at +9, bit zero.
        passive = bool(proto['attributes'] & 0x100)
        if len(entries) != (1 if passive else 4):
            raise ValueError('Original inscription count differs')
        result.append({'skillId':skill_id, 'profession':profession,
            'protoProfession':proto['reqProfession'], 'sourceFilter':dict(source_filter),
            'sourceAttributes':proto['attributes'],
            'kind':'passive' if passive else 'active', 'runes':entries})
    # Original tree iteration is ordered by unlock-row ID, and insertion sort
    # preserves that order when two skills have the same required level.
    return sorted(result, key=lambda r:(r['kind'],r['runes'][0]['requirement']['needlevel'],r['runes'][0]['requirement']['id']))


def profession_mapping(ui_archive,table_archive):
    main=ui_archive.read('ui/Flash/mainUI.swf')
    if digest(main)!='e18152cbddf51f335ad764fd57c928a990cb0846de05b2628968050e1dcbc0ac':
        raise ValueError('Original profession definitions differ')
    definitions=parse_abc(extract_named_abc(main,'Common/ASDefines'))
    cls=next(c for c in definitions['classes']if c['name']=='Common::ASDefines')
    constants={t['name']:definitions['ints'][t['value']] for t in cls['staticTraits']
               if t['name'].startswith('PLAYER_CLASS_')and t.get('valueKind')==3}
    raw=ui_archive.read('ui/Flash/CharacterChooseClass.swf')
    if digest(raw)!='83f552329ad0ab1b1967f17371d7ff4e58fba8d7c5bcac5d5f7f04aae7839bb1':
        raise ValueError('Original creation class SWF differs')
    abc=creation_abc(raw); cls=next(c for c in abc['classes']if c['name']=='Window_ChooseClass')
    constructor=abc['bodies'][cls['iinit']]
    if digest(constructor['code'])!='b291f82d14d9332962c5ba51c63cd24598a30e35db31ac78c25d9321b8aa2301':
        raise ValueError('Original creation class constructor differs')
    instructions=disassemble(constructor['code'],abc)
    icons=[i['args'][0] for i in instructions if i['op']=='pushstring'and i['args'][0].startswith('ui/icons/userinterface/class_')]
    title_keys=[i['args'][0]for i in instructions if i['op']=='pushstring'and i['args'][0].startswith('GENERAL_CH_SELEC_')][:5]
    english=decode_localized_names(table_archive.read('tables/String_General_.tbl'),'EN')['values']
    chinese=decode_localized_names(table_archive.read('tables/String_General_zh.tbl'),'SC')['values']
    ids={v:k for k,v in english.items()}
    callback=named_method(abc,'Window_ChooseClass','seleteCharacter')
    if callback['codeSHA256']!='42d6fdedad2f2f6471422463bb270f02185f44f4fee5316b2320e5ba75dc0b23':
        raise ValueError('Original creation selection callback differs')
    return {'asConstants':constants,
        'creation':{'sourceSWFSHA256':digest(raw),'constructorCodeSHA256':digest(constructor['code']),
            'iconsByIndex':icons,'titleKeysByIndex':title_keys,
            'titlesByIndex':[chinese[ids[k]] for k in title_keys],
            'selectionCallback':callback,
            'nativeCallback':'Character_Class registered 64edc0 -> 6fd340; execute probe to verify index mapping'},
        'playerClassProperty':'Hero_GetHeroInfo 6684a8..6684b4 reads property +0x3f8; a0f968 uses the same property for skill_unlock.needprofession',
        'webProfessionMap':{'1':'战士','2':'法师','3':'游侠','4':'武僧','5':'血骑士'},
        'boundary':'PLAYER_CLASS_HUNTER/PRIEST use ranger/monk source icons; do not equate NPC class fields or sixth static class with a playable web profession.'}


def recover(source, output, image=None, runtime=None):
    output = local_output(output)
    table_archive, ui_archive = (ResourceArchive(Path(source)/(n+'.bin')) for n in ('tables','ui'))
    tables = {}
    for name,(key,expected) in TABLES.items():
        raw = table_archive.read('tables/'+name+'.tbl')
        # playerinfo is already validated by native_combat's separate source
        # recovery; its pin is still checked here like every other table.
        if digest(raw) != expected:
            raise ValueError('Original progression table differs: '+name)
        tables[name] = decode_ftable(raw,key)
    names = decode_localized_names(table_archive.read('tables/String_Skill_zh.tbl'),'SC')
    methods, abc_cache = {}, {}
    for full,expected in METHODS.items():
        cls,name = full.split('.')
        if cls not in abc_cache:
            abc_cache[cls] = parse_abc(extract_abc(ui_archive.read('ui/Flash/'+cls+'.swf')))
        method = named_method(abc_cache[cls],cls,name)
        if method['codeSHA256'] != expected:
            raise ValueError('Original progression ABC differs: '+full)
        methods[full] = method
    result = {'format':'oc2-character-progression-evidence-v1', 'tables':tables,
        'methods':methods, 'catalogs':{str(prof):profession_catalog(tables,names['values'],prof) for prof in PROFESSIONS},
        'staticExtraProfessionIds':sorted({r['needprofession'] for r in tables['skill_unlock']['rows']}-set(PROFESSIONS)),
        'professionMapping':profession_mapping(ui_archive,table_archive),
        'xpSemantics':{'hud':'xp / upgradeXp; fields supplied by native Hero_GetHeroInfo',
            'nativeProperties':{'xp':'actor+0x18 -> +0x450','upgradeXp':'actor+0x18 -> +0x458','level':'actor+0x18 -> +0x268'},
            'level55Display':'native getter uses upgradeXp as numerator when level==55',
            'slotConsumer':'a0f510 reads player_xp +0x34/+0x38, then unconditionally writes active/passive slot counts 4/2',
            'playerXpTableMeaning':'xp_levelup/xp_levelupold consumer and server rollover not yet traced; no conversion applied'},
        'boundaries':['Static requirements do not establish a learned/unlocked/equipped state.',
            'skill_rune in SMSG_SkillInit has not been normalized from its original consumer; no wire-to-learned-state adapter exists.',
            'No XP award/reset, level change, skill learning, point spend, save migration or transport is implemented.']}
    if image is not None:
        result['skillProtocol'] = verify_native(image)
    if runtime is not None:
        manifest = json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())['files']
        wanted = ['prototype/game/character-store.mjs','prototype/game/combat.mjs','prototype/public/skills.js',
                  'prototype/public/skill-book.js','prototype/public/hud-progress.js','prototype/game/basic-attack.mjs',
                  'prototype/public/professions.js']
        result['reviewedRuntime'] = {}
        for name in wanted:
            raw = (Path(runtime)/name).read_bytes()
            if digest(raw) != manifest[name]:
                raise ValueError('Reviewed runtime identity differs: '+name)
            result['reviewedRuntime'][name] = {'sha256':digest(raw)}
        source=(Path(runtime)/'prototype/public/professions.js').read_text()
        observed=dict(re.findall(r"(\d+):'([^']+)'",source))
        if observed!=result['professionMapping']['webProfessionMap']:
            raise ValueError('Web profession names/IDs differ; explicit bridge review required')
        entry=(ROOT/'deploy/entry_ui.mjs').read_text()
        anchor='profession:[1,3,2,5,4][draft.cls]'
        if entry.count(anchor)!=1:
            raise ValueError('Current creation adapter differs; explicit bridge review required')
        result['professionMapping']['currentWebAudit']={
            'runtimeProfessionMap':observed,'creationAdapter':'deploy/entry_ui.mjs',
            'creationAdapterSHA256':digest(entry.encode()),'observedCreationMapping':[1,3,2,5,4]}
    (output/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    cli.add_argument('--library',type=Path)
    cli.add_argument('--runtime',type=Path)
    cli.add_argument('--output',type=Path,required=True)
    args = cli.parse_args()
    image = None
    if args.library:
        from analyze_native_resources import NativeImage
        image = NativeImage(args.library.read_bytes())
    report = recover(args.source,args.output,image,args.runtime)
    print(json.dumps({'output':str(args.output/'evidence.json'),
        'xpRows':len(report['tables']['player_xp']['rows']),
        'catalogs':{k:len(v) for k,v in report['catalogs'].items()},
        'savesReadOrChanged':False}))


if __name__ == '__main__':
    main()
