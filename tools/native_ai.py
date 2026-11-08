"""Recover client navigation and NPC data; server AI scripts remain unavailable."""
import hashlib
import json
from pathlib import Path
from navmesh import decode_nav
from skill_attachments import decode_ftable
from native_combat import descriptor_fields

MOVE_ACTIONS={'stand':0,'patrol':1,'chase':2,'goBack':3,'wayPoint':4,'pause':5,'freeze':6,
              'follow':7,'followLeader':8,'rapidMove':9,'move':10}
NATIVE_ROUTINES={
    0x357618:(468,'724e71ebe5a7721e6cc320de72025c471433aedfa41774585517937d89ef8a6c'),
    0x474c9c:(16,'cc08591c8376426a2ccd1229ca1e538b193dc0e71b3a7aa4ffe0580b39067382'),
    0x15ed978:(844,'b21c241a425cdf37accf23ac9a90c79085a41011173af7562db4eb2d783ffdb9'),
    0x15ee7b4:(256,'d9b2a07a80c79b6b5702067ed65cc893d355e36957463bfc603201e91646f4c2'),
    0x15ee18c:(560,'91898e9917a4372e268e5715a73790c8c52ed1171b03e2fda29acbf86a1d628f'),
}
PROTOCOL={
    'GS2C_ObjectUnit':(0x2029469,129,'40e799d2aeae39d863833c732da4cc6c9993bb5d88c927da75f8c1eaa3e6f907'),
    'GS2C_CombatInfo':(0x202a7ed,47,'e0cb8b8afc1c2007cf587f134e433886c75e9c53402370c093f8d6ecbed4e266'),
    'MoveActionTypes':(0x2036dc6,320,'1556dd6d9efe1df3c9c95082539031244f4a148b4977c88c3ad38736683d53e5'),
}
def verify_ai_native(image):
    proofs={}
    for name,(address,size,digest) in PROTOCOL.items():
        raw=image.read(address,size)
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('NPC protocol changed; retrace required')
        if name=='MoveActionTypes':
            for key,value in MOVE_ACTIONS.items():
                title={'goBack':'GoBack','wayPoint':'WayPoint','followLeader':'FollowLeader','rapidMove':'RapidMove'}.get(key,key.title())
                needle=('MoveActionType_'+title).encode();at=raw.find(needle)
                if at<0 or raw[at+len(needle):at+len(needle)+2]!=bytes([16,value]):raise ValueError('NPC movement enum mismatch')
            parsed={'values':MOVE_ACTIONS}
        else:parsed=descriptor_fields(raw)
        proofs[name]={'address':hex(address),'bytes':size,'sha256':digest,**parsed}
    return proofs

def recover_ai(extract,output):
    def raw(path):
        value=extract(path);return bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
    tables={};proofs={}
    for name,key in [('creature_proto','entry'),('creature_appearance','entry'),('creaturedisplayinfo','ID'),
                     ('creaturemodeldata','ID'),('creature_spawns','id'),('creature_skill','Id'),('way_points','id')]:
        parsed=decode_ftable(raw('tables/'+name+'.tbl'),key);tables[name]=parsed['rows'];proofs[name]=parsed['verification']
    model=next(r for r in tables['creaturemodeldata'] if r['ID']==12)
    if model['ModelPath']!='model/npc/creature/beast/wolf/wolf_skin.bdae':raise ValueError('Wolf source model changed')
    displays={r['ID'] for r in tables['creaturedisplayinfo'] if r['Model']==12}
    entries={r['entry'] for r in tables['creature_appearance'] if r['creaturedisplayinfo_id'] in displays}
    wolves=[r for r in tables['creature_proto'] if r['entry'] in entries]
    spawns=[r for r in tables['creature_spawns'] if r['map']==4 and -2752<=r['position_x']<=-2560 and 128<=r['position_z']<=320]
    tiles=[]
    for z in range(2,5):
        for x in range(-43,-40):
            path=f'world/tutorial/navmesh/{x:04d}_{z:04d}.nav';tile=decode_nav(raw(path))
            if tile['tile']!=[x,z]:raise ValueError('Navigation filename and header coordinates differ')
            tile['sourcePath']=path;tiles.append(tile)
    navigation={'format':'oc2-navigation-record-evidence-v1','tiles':tiles,
        'limitations':['Raw decoded DNAV source records only. The local portal graph and web routing have been removed. This does not execute the original Detour query.']}
    out=Path(output);out.mkdir(parents=True,exist_ok=True);(out/'navigation-evidence.json').write_text(json.dumps(navigation,separators=(',',':')))
    return {'format':'oc2-npc-evidence-v1','moveActions':MOVE_ACTIONS,
        'navigation':{'evidenceFile':'navigation-evidence.json','format':navigation['format'],'tileCount':len(tiles),'polygonCount':sum(len(t['polygons']) for t in tiles)},
        'wolfModel':model,'wolfCandidates':wolves,'wolfSkills':[r for r in tables['creature_skill'] if r['creatureID'] in entries],
        'previewOriginalSpawns':spawns,'previewOriginalWolfSpawns':[r for r in spawns if r['entry'] in entries],
        'tableProofs':proofs,'nonzeroAIPlans':sum(r['aiplan']!=0 for r in tables['creature_proto']),
        'scriptedProtos':sum(bool(r['script']) for r in tables['creature_proto']),
        'limitations':['The camp wolf is a local encounter using model12, not an identified original tutorial NPC entry/spawn. No wolf occurs in the selected source tutorial spawn area.',
            'All source aiplan fields are zero; 2030 proto script names exist but their server implementations are not available. A filename/model cannot establish original aggro, threat, patrol or evade rules.',
            'Current combat uses explicitly local passive aggro, damage-based threat, home leash, unreachable timeout, invulnerable return and healing on arrival. Native speed200/400 units, sight/EnemyMaxDis and script hooks remain evidence, not guessed live tuning.']}
