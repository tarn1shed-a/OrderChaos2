"""Checked client combat evidence, distinct from missing server scripts/formulas.

The selected durations/bonus are stated by the shipped Chinese descriptions.
Damage display coefficients are exported as evidence, never used as a server
formula. Aura assignment for FrostBlast is a candidate, not a traced script.
"""
import hashlib
from pathlib import Path
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names
from native_cast import BINDINGS

DESCRIPTORS = {
    'SMSG_Skill_DmgLog':(0x2041093,222,'6b39ba4742bf7f934b20fe9023abd5fcf1f8b9a02d8fee4300456177d2c56957'),
    'SMSG_Skill_AddBuff':(0x204126a,213,'3e69098f3cf955f25a0a971cb50e2f45e1741081121fadc00a44cc9c4c5c5681'),
    'SMSG_Skill_BuffUpdate':(0x2041396,173,'dc1699883b7f9531e34d7c0951097d8b42caf7e1f5d0cce638b9e2f0d31a30ea'),
    'SMSG_Skill_RemoveBuff':(0x2041446,148,'b1cedc2bb6e71eaffcd156dc8587f98025c18d8beacfcb9eeaad796462857298'),
}

def descriptor_fields(data):
    """Bounded protobuf DescriptorProto reader, not a network protocol client."""
    def varint(raw,at):
        value=0
        for shift in range(0,70,7):
            if at>=len(raw):raise ValueError('Truncated descriptor varint')
            word=raw[at];at+=1;value|=(word&127)<<shift
            if word<128:return value,at
        raise ValueError('Oversized descriptor varint')
    def fields(raw):
        at=0;result=[]
        while at<len(raw):
            tag,at=varint(raw,at);number,wire=tag>>3,tag&7
            if number==0:raise ValueError('Invalid descriptor field')
            if wire==0:value,at=varint(raw,at)
            elif wire==2:
                size,at=varint(raw,at)
                if at+size>len(raw):raise ValueError('Truncated descriptor span')
                value=raw[at:at+size];at+=size
            else:raise ValueError('Unsupported descriptor wire type')
            result.append((number,value))
        return result
    top=fields(data);name=[v for n,v in top if n==1]
    if len(name)!=1:raise ValueError('Descriptor name missing')
    result=[]
    for n,raw in top:
        if n!=2:continue
        row=dict(fields(raw))
        if not {1,3,4,5}<=row.keys():raise ValueError('Incomplete field descriptor')
        result.append({'name':row[1].decode(),'number':row[3],'label':row[4],'type':row[5]})
    if len({r['number'] for r in result})!=len(result):raise ValueError('Duplicate descriptor field')
    return {'name':name[0].decode(),'fields':result}

def recover_protocol(image):
    result={}
    for name,(address,size,digest) in DESCRIPTORS.items():
        raw=image.read(address,size)
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Combat descriptor changed; retrace required')
        parsed=descriptor_fields(raw)
        if parsed['name']!=name:raise ValueError('Combat descriptor name mismatch')
        result[name]={**parsed,'address':hex(address),'bytes':size,'sha256':digest}
    return result

def recover_combat(extract,output):
    def raw(path):
        value=extract(path)
        return bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
    tables={};proofs={}
    for name,key in [('skill_proto','skillId'),('skill_runes','id'),('skill_event','ID'),
                     ('skill_aura','ID'),('aura_runes','id'),('aura_Event','ID'),
                     ('skill_dmg_display','id'),('playerinfo','level'),('config_values','id')]:
        parsed=decode_ftable(raw('tables/'+name+'.tbl'),key)
        tables[name]={r[key]:r for r in parsed['rows']};proofs[name]=parsed['verification']
    data=raw('tables/String_Skill_zh.tbl');localized=decode_localized_names(data,'SC');names=localized['values']
    proofs['String_Skill_zh']=localized['verification']
    spells={}
    for alias,identifier in BINDINGS.items():
        proto=tables['skill_proto'][identifier];rune=tables['skill_runes'][proto['rune0']]
        display=[r for r in tables['skill_dmg_display'].values() if r['skill_id']==identifier]
        if len(display)!=1:raise ValueError('Selected skill damage display row missing/ambiguous')
        spells[alias]={'sourceSkillId':identifier,'runeId':rune['id'],
            'description':names[rune['descStrId']],'damageType':rune['damageType'],
            'damageAttribute':rune['damageAttribute'],'displayCoefficients':display[0],
            'uncontrolCanCast':proto['uncontrolCanCast'],'freezeCanNotCast':proto['freezeCanNotCast'],
            'events':[r for r in tables['skill_event'].values() if r['parentSkillId']==identifier]}
    # Fail closed if a different source localization no longer supports these
    # selected mechanics. Other rune variants must be traced independently.
    if '燃烧7秒' not in spells['fireball']['description'] or '提高5%' not in spells['fireball']['description']:
        raise ValueError('Scorcher description changed')
    if '冻结' not in spells['frost_blast']['description'] or '2秒' not in spells['frost_blast']['description']:
        raise ValueError('FrostBlast description changed')
    if '额外造成50%' not in spells['arcane_missile']['description']:raise ValueError('Arcane bonus changed')
    if spells['fireball']['displayCoefficients']['dot_hitCount']!=5:raise ValueError('Burn display count changed')
    auras={}
    for alias,identifier,expected in [('burn',22,'sorcher_burn'),('freeze',20,'freeze'),('stun',18,'stun'),('silence',334,'Silence')]:
        aura=tables['skill_aura'][identifier];rune=tables['aura_runes'][aura['rune0']]
        if aura['editName']!=expected or aura['maxStack']!=1:raise ValueError('Selected aura changed')
        icon=raw('ui/icons/'+aura['icon']);target='buff-'+alias+'.png'
        destination=Path(output)/'ui';destination.mkdir(parents=True,exist_ok=True);(destination/target).write_bytes(icon)
        auras[alias]={'id':identifier,'runeId':rune['id'],'name':names[aura['nameStrID']],
            'description':names[aura['descStrID']],'maxStack':aura['maxStack'],'attributes':aura['attributes'],
            'visuals':{k:rune[k] for k in ['addState','buffState','removeState','hitState']},
            'icon':{'url':'/assets/ui/'+target,'sourcePath':'ui/icons/'+aura['icon'],'sourceSHA256':hashlib.sha256(icon).hexdigest()},
            'events':[r for r in tables['aura_Event'].values() if r['parentAuraId']==identifier]}
    return {'format':'oc2-native-combat-v1','spells':spells,'auras':auras,
        'mechanics':{'burnDurationMs':7000,'burnTicks':5,'burnDisplayRate':spells['fireball']['displayCoefficients']['dot_dmgRate'],
                     'freezeDurationMs':2000,'arcaneBurnBonus':.5,'scorcherEquippedCritBonus':.05},
        'baseAttributes':list(tables['playerinfo'].values()),'tableProofs':proofs,
        'limitations':[
            'Damage coefficients are client display data, not a recovered server formula. Base damage, armor, HP/XP growth, critical resolution and rewards remain local rules.',
            'Durations and Arcane bonus are supported by rune0 Chinese descriptions. Five burn ticks/10% come from damage display; equal 1400ms spacing, rounding, refresh and cross-caster replacement are local policies.',
            'Scorcher22 aura is linked by its exact burn name and Aura22 scripts. FrostBlast94 to generic freeze20 is a candidate: Skill94_OnSkillHit and Aura20 scripts are absent. Aura bitfields are retained raw, not decoded into guessed controls.',
            'Freeze blocks movement, attacks, jumps and spells locally. Stun/silence are server-only supported policies; their original script/actor-state arbitration is not reconstructed.',
            'Equipped-skill +5% critical is documented but not applied: original equip semantics, critical formula and server roll are unknown.',
            'Original AddBuff/Update/Remove and DmgLog descriptors show server duration/stacks and final HP/damage fields. No original server transport or handlers are implemented.',
            'playerinfo race/class bases are preserved for research, not substituted into existing local saves. Source config explicitly marks default_weapon_strength unused (UnitAttrCalcCenter.cpp).']}
