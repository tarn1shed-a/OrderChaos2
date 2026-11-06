"""Recover selected source skill slots and compatible model dummy transforms.

Original table slot names are cross-checked with the ARM64 attachment string table
at 0x241a350. Missing forest-elf dummies are explicitly adapted from the same elf
female model used for its action clips; they are not claimed native to that NPC.
"""
import hashlib
import math
import re
import struct

EFFECT_TABLE = 'tables/skill_visual_effect.tbl'
STATE_TABLE = 'tables/skill_visual_state.tbl'
REFERENCE_MODEL = 'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'
SOCKET_NAMES = ('Dummy_R_Hand','Dummy_L_Hand','Dummy_Chest')
SLOTS = {
    'casterRHand': {'slotIndex':8,'dummy':'Dummy_R_Hand','owner':'caster','pointOnly':False,'inheritRotation':True,'rotationMode':'dummy'},
    'casterLHand': {'slotIndex':9,'dummy':'Dummy_L_Hand','owner':'caster','pointOnly':False,'inheritRotation':True,'rotationMode':'dummy'},
    'targetChest': {'slotIndex':2,'dummy':'Dummy_Chest','owner':'target','pointOnly':True,'inheritRotation':False,'rotationMode':'owner-facing','sourceForward':[1,0,0]},
    'targetGround': {'slotIndex':4,'dummy':None,'owner':'target','groundOffset':.1,'pointOnly':True,'inheritRotation':False,'rotationMode':'owner-facing','sourceForward':[1,0,0]},
}
SELECTED = {
    'fireCast': (464,728,['casterRHand','casterLHand']),
    'fireMissile': (234,729,['targetChest']),
    'fireHit': (994,1584,['targetChest']),
    'frostHit': (65,137,['targetGround']),
}


def decode_ftable(data,id_column='id'):
    """Read the observed FTABLE fixed records and absolute string spans safely."""
    if len(data)<44 or data[:8]!=b'FTABLE\0\0': raise ValueError('Invalid FTABLE header')
    version,count,columns,ids_at,types_at,rows_at,stride,strings_at,reserved=struct.unpack_from('<9I',data,8)
    if version!=0x100000 or reserved or not 1<=count<=100000 or not 1<=columns<=256:
        raise ValueError('Unsupported FTABLE metadata')
    if not (44<ids_at and types_at==ids_at+count*4 and rows_at==types_at+columns+1
            and strings_at==rows_at+count*stride and strings_at<=len(data)):
        raise ValueError('Invalid FTABLE section extents')
    sql=data[44:ids_at].split(b'\0')[0]
    try: names=re.findall(r'^\s*`([^`]+)`\s+',sql.decode('utf-8'),re.MULTILINE)
    except UnicodeDecodeError as error: raise ValueError('Invalid FTABLE schema encoding') from error
    if len(names)!=columns or len(set(names))!=columns: raise ValueError('FTABLE schema column mismatch')
    types=data[types_at:rows_at]
    if types[-1]!=0 or any(kind not in b'uisf' for kind in types[:-1]): raise ValueError('Unsupported FTABLE physical type')
    widths={ord('u'):4,ord('i'):4,ord('f'):4,ord('s'):6}
    if sum(widths[k] for k in types[:-1])!=stride: raise ValueError('FTABLE row stride mismatch')
    ids=struct.unpack_from('<'+'I'*count,data,ids_at)
    if len(set(ids))!=count: raise ValueError('Duplicate FTABLE row ID')
    rows=[]
    for index,identifier in enumerate(ids):
        at=rows_at+index*stride;row={}
        for name,kind in zip(names,types[:-1]):
            if kind==ord('s'):
                pointer,size=struct.unpack_from('<IH',data,at);at+=6
                if not size: value=''
                else:
                    if pointer<strings_at or pointer+size>=len(data) or data[pointer+size]!=0:
                        raise ValueError('FTABLE string span outside pool or missing terminator')
                    raw=data[pointer:pointer+size]
                    if b'\0' in raw: raise ValueError('Embedded NUL in FTABLE string span')
                    try: value=raw.decode('utf-8')
                    except UnicodeDecodeError as error: raise ValueError('Invalid FTABLE string encoding') from error
            else:
                value,=struct.unpack_from('<'+chr(kind).replace('u','I'),data,at);at+=4
                if kind==ord('f') and not math.isfinite(value): raise ValueError('Non-finite FTABLE value')
            row[name]=value
        if row.get(id_column)!=identifier: raise ValueError('FTABLE ID index differs from row')
        rows.append(row)
    return {'rows':rows,'columns':names,'physicalTypes':types[:-1].decode(),
            'verification':{'rows':count,'rowStride':stride,'stringPoolOffset':strings_at,
                            'sourceSHA256':hashlib.sha256(data).hexdigest()}}


def _named(nodes,name):
    matches=[i for i,node in enumerate(nodes) if name==node['name'] or name in node.get('aliases',[])]
    if len(matches)>1: raise ValueError(f'Ambiguous socket node: {name}')
    return matches[0] if matches else None


def adapt_socket_nodes(reference_nodes,target_nodes):
    """Append three reference dummies under exact matching existing parent names.

    Append these BEFORE action track rebasing: both hand dummies have original
    animation channels and must not be treated as static effect offsets.
    """
    result=[]
    for name in SOCKET_NAMES:
        if _named(target_nodes,name) is not None: continue
        source_index=_named(reference_nodes,name)
        if source_index is None: raise ValueError(f'Reference socket missing: {name}')
        source=reference_nodes[source_index]
        parent=source['parent']
        if parent<0 or parent>=len(reference_nodes): raise ValueError('Reference socket has no valid parent')
        parent_name=reference_nodes[parent]['name']
        target_parent=_named(target_nodes,parent_name)
        if target_parent is None: raise ValueError(f'No compatible source socket parent: {parent_name}')
        for key in ['position','quaternion','scale']:
            if not all(math.isfinite(v) for v in source[key]): raise ValueError('Non-finite socket transform')
        result.append({'name':source['name'],'aliases':list(source.get('aliases',[])),
            'parent':target_parent,'position':list(source['position']),
            'quaternion':list(source['quaternion']),'scale':list(source['scale']),
            'attachmentOrigin':{'mode':'source-adapted','referenceModel':REFERENCE_MODEL,
                'referenceNode':source_index,'referenceParent':parent_name,
                'animated':name in ('Dummy_R_Hand','Dummy_L_Hand')}})
    return result


def _native_sockets(nodes):
    return {name:{'node':index,'mode':'native'} for name in SOCKET_NAMES
            if (index:=_named(nodes,name)) is not None}


def _scale(row):
    result=[];decoded=[]
    for name in ['scaleX','scaleY','scaleZ']:
        value,=struct.unpack('<f',struct.pack('<I',row[name]))
        if not math.isfinite(value): raise ValueError('Invalid packed effect scale')
        decoded.append(value)
        result.append(1.0 if abs(value)<1e-6 else value*.01)
    return result,decoded


def recover_skill_attachments(read_bytes,reference_nodes,player_nodes,wolf_nodes):
    effect_data,state_data=read_bytes(EFFECT_TABLE),read_bytes(STATE_TABLE)
    effect_table,state_table=decode_ftable(effect_data),decode_ftable(state_data)
    effects={row['id']:row for row in effect_table['rows']};states={row['id']:row for row in state_table['rows']}
    bindings={}
    for key,(effect_id,state_id,slots) in SELECTED.items():
        effect,state=effects.get(effect_id),states.get(state_id)
        if effect is None or state is None: raise ValueError('Missing selected source skill record')
        if any(state[slot+'Eff']!=effect_id for slot in slots): raise ValueError('Source slot/effect reference mismatch')
        scale,raw_float=_scale(effect)
        bindings[key]={'effectId':effect_id,'sourceStateIds':[state_id],
            'sourceStateName':state['editName'],'path':effect['pathName'],
            'slots':slots,'slot':slots[0] if len(slots)==1 else None,
            'scale':scale,'rawScaleWords':[effect[n] for n in ['scaleX','scaleY','scaleZ']],
            'particleScale':sum(scale)/3,
            'decodedScalePercent':raw_float,'missileType':effect['missileType'],
            'missileCount':effect['missileNum'],'missileSpeed':effect['missileSpeed'],
            'sourceAnimationIds':{n:state[n] for n in ['casterPreAnim','casterLoopAnim'] if state[n]}}
        if key=='frostHit': bindings[key]['groundOffset']=.1
    return {'format':'oc2-skill-attachments-v1','slots':SLOTS,'effects':bindings,
        'models':{'player':{'appendNodes':adapt_socket_nodes(reference_nodes,player_nodes),'nativeSockets':_native_sockets(player_nodes)},
                  'wolf':{'appendNodes':[],'nativeSockets':_native_sockets(wolf_nodes)}},
        'provenance':{'effectTable':{'path':EFFECT_TABLE,**effect_table['verification']},
            'stateTable':{'path':STATE_TABLE,**state_table['verification']},
            'nativeEvidence':{'slotTableVA':'0x241a350','slotLookup':'0x5b4b34-0x5b4b48',
                'effectScale':'0x5c79a0-0x5c7a14','groundHeight':'0x5c59ac-0x5c5a08',
                'chestLookup':'0x5c5a44-0x5c5b3c','pointEffectSlots':'0x5b4a04-0x5b4a44',
                'pointEffectFacing':'0x5c5d38-0x5c5d78','facingQuaternion':'0x11dd004',
                'particleScaleAverage':'0xeb08a8-0xeb08e0',
                'particleParameterScale':'0xe9cbb4-0xe9ce34'},
            'referenceModel':REFERENCE_MODEL,
            'limitations':['Fire and frost state rows are source attachment examples, not proof of complete original player skill-ID linkage.',
                'Forest-elf dummy transforms are adapted from the same elf-female action reference; native wolf chest is used directly.',
                'Both hand dummy animation tracks must be included during character conversion.']}}
