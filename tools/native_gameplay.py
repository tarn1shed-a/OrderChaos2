"""Checked source-table links and manually traced normal jump/combo algorithms.

No original code executes. Full decoded rows/icons stay in converted/, ignored
by Git. The exported bank is not evidence that every native caller is traced.
"""
import hashlib
import io
import json
import struct
from pathlib import Path
from PIL import Image
from skill_attachments import decode_ftable
from bdae_animation import BDAEAnimation
from native_cast import recover_cast

LIB_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
ROUTINES = {
    0x9f7f68:(3260,'f383607610d7acc48a161ee045cc847f623dfbebcd7856ec8bd35743c5788d39'),
    0x5c05f8:(108,'d4c81b5ec5becd35b0ca974f8f28c06f91f764204be2258bc3dfe7ceaec259ec'),
    0xa8674c:(648,'cc9fee8aa8918b53956559049f1b6f19b943787f4380fe4af29bc187458d06a7'),
    0xa85534:(488,'70c25f223b07abfc14f0257acb6d9f5574a5788e19b98cb60b21c16bacc10ba8'),
    0xa86b3c:(940,'b740efe4266c48de04f0b37c0e236e5d8496a8fb22122d5fdbc79d0c8d799b5a'),
    0xa86ee8:(1072,'799398437e987e3e658082652d3f52504d9d0d25aad1303cc558179bd9f163f5'),
    0xa8a9c0:(996,'3db3b7164373296ce80f2575163081f4bb50983f1454e03449ac53c2a10bdd81'),
    0xa878c0:(1196,'610f4eff46e27d22fc2b8a0e39ed92ac1fca33d5ab2060092bc61d82088e4b7d'),
    0xa883a4:(704,'1160e48b349e201f2da1ba370fb1c46c2418707b8275feaa8ba520d1687f4a61'),
    0xa0ea08:(360,'70653f5440707095676af4916e8c18a553f5c25db8b6b0cea0da8c27aadc9626'),
    0x5c11bc:(488,'663ce213b04789abdd5124724b113fbaba377d4d69c7fdca1aa5f678341df606'),
    0x5c0d38:(368,'309dcd5297d14904265f50fc8420b40d92be98eff80cbc646ec9d367eea55bbd'),
    0x5bf9b4:(432,'d2949286cb807e0fd86f6d6f0b4a850d7ab263f7419e4b4b7f4840a82d94750d'),
    0x659f18:(1076,'2ace20b24438a8a4519efd2f1aaae58177a60fd5f1a3a6e0d2a9b7150dbb908d'),
    0x5c04bc:(316,'0c82849a3a613f508846ed5563f8e176ee6bd4d1256131838e1436f3b85370d3'),
    0x5d2530:(2748,'e568463fec11b66bb334f36842d2444f1cf4fdad5e86e612604989d37ba5a38e'),
    0x5c068c:(44,'30a0290babea45cacc98dd5c364ecc14bb716e9619568a995840f12342fc4020'),
    0x5b9510:(768,'cb648ccd230fb9f8d8fe0ca6be762909598c7cc0e51eac958fd173c7e58bdeae'),
    0x90e63c: (672, '27e3667da4b90d04d6c05697a443b7ca6d9f532c582a09256627f557509b88bc'),
    0x9ec1e4: (72, '5d0c1624c747868be6ee4136b9e443a18f87ab3b3010d83eb3527684ad49bfe7'),
    0x9e171c: (596, 'b3a903695c8af76423778a1221b8477d888502e22b8c30219549c25f28f1c2ee'),
    0x9e3fbc: (652, '08a42f008a60553b0055f1decb2b25fc06bf3c3670a36444ce2f4d8d5fe3e4e2'),
    0x5bec6c: (284, '8b1d607c652451b7eb5e6e5e51da66bf94eff7721f784bacc1515795c3f2d9fc'),
    0x5bef40: (532, 'e71a5f1b68969591e0e01cfa996606e9e32b38a0f09bebede2fa906de11b074e'),
    0x5bf5d0: (404, 'ab5494092fda443785cac132ee46e5d6425e411c2053a7833f822b33998c4e66'),
    0xa6a1ac: (684, 'ead25770556979ec674765653485abe423188e8533fa4efa0dac2aba0d69765a'),
    0x363d30: (740, 'acd29a98443b90dd10177978f4ffa4d1ab9df5ff85d76d9c0d099914db60dfcb'),
    0xa88674: (1524, 'e945994cf9aefdd699c76d8f9f98f08930844848b3d82ee3b943b2bd3f72190b'),
    0xa2d3dc: (400, '11cdeb9af0ec6e91e8f7893b4ab966078fb9dc208e2a6cd970a64e02ad3ca657'),
    0xa2d56c: (60, 'c987c9866bd2cae358d846472466fda1cee779281c85f5bcab4bcc6ecfa52ea3'),
    0xa5880c: (236, '9ac17fee3dcfa3ca2fd95f33e118e01084123dea8d5e9dde4f9a8830fd4678fc'),
    0xa8b790: (328, 'b93d766f788a52ca72bb1ec85cf3d7b610ac0653b8ea22675f3d9c882d1dd672'),
    0xa8b8d8: (620, 'b647c5fa8b0a288eec63bcd4811b47ff0868f81362aca94ce1af6bf81cec72e6'),
    0xa51f20: (1936, '42b55cc1cbc6d0e659bf4d29c049bb97bcbb831874d2c070735d200ebe15bd04'),
    0xa528bc: (464, '43fa7aee72cfa97cef30e662bcfc36b0812bd14475183e88944c62aa6dc6fecc'),
    0xa3cf28: (432, '74cd2d813c6235eb355d3d79411b41930fc2b530ced7dfedf0f7883992aa8eb1'),
    0x5b8a9c: (1668, 'c20efe26eca7f8360871e10e2be57a2eb00240992a0f3a40c26384431f081298'),
    0x5b9ed0: (1156, 'eff45efcabe0457af7004b90ddd2611e6324c7bb095e1d37b588c90e09db44e4'),
    0x5d13a4: (100, '125db88a0924081f3abff3ac92f6451671be87a02b5092037449bd32fc3a74aa'),
    0x5d1454: (340, '13efd1b6c815ddd9f4786ad62b78f52694fbb5ee519a8327f9c6ca4ff646296b'),
    0x5d15a8: (420, 'bfd39a9633873d571a1094af603df86cc491acb756b0ae947450583cad120761'),
    0x5d21ac: (588, 'e730525323f21b7995a37e990c6dabb54e69b6efe771fce2fe07135d34fde2bf'),
    0x5d2148: (40, 'd57dd0f6e08fc5a6503d835908703c2f88aad9133590d18f11bd6c516175a42d'),
    0x5d23f8: (156, '18b19f6b89fb1c49508521df5abf355b7b85bd74bdf0fb6cc8d58ee7263852c4'),
    0x5d3144: (1196, '6c0936bb8e3f7c49a44167513d2716d25d52efa5775a4c39a735610f9004a3b2'),
    0x5d2fec: (24, 'd2959daac66127a1c80ea0f4ad6e8ed1b50bd3f49be3722d0a37a001bb5067b3'),
    0x5d35f0: (112, '6815fd0883b1dc402e0b93455a3952624ec4b55bffe1f7067667f0bd50564d2f'),
    0x5d36fc: (412, '40400028061fcc3e9f9a0780bd5b9c85b2fb6e4872897e0aa9b437efc2ca4c44'),
    0x5d3898: (24, 'd2959daac66127a1c80ea0f4ad6e8ed1b50bd3f49be3722d0a37a001bb5067b3'),
    0x5d3924: (388, 'a9aeb322e540e383854860439ab2d2d378c4e6ccf0e226ca418dd7b955bdf0b1'),
    0x5d3aa8: (52, '1626bbcd3d7485a5d6b8538a95602cf18909b8ac0b7b6aca0c89e7896f7a5a48'),
    0x5d3c6c: (384, '6bf25b27af264914e36f9650aa0bcc7531d651722935f0c2877500b7dca8ec5d'),
    0x5d3dec: (296, '6929f4525d7c6583d63ed54e5cff66076d69c765b03482a4fd8636b08944c74d'),
}
CONSTANTS = {0x250b8cc:-41.6,0x250b8d0:-20,0x250b8d4:-75,0x250b8d8:-6.7,
             0x250b8dc:10,0x250b8e0:3.5,0x250b8e4:13.1,0x250b8ec:5,0x250b8f0:8,
             0x1df7a48:100,0x1df79f4:.001,0x1e39a7c:.31}

def verify_native(data):
    if hashlib.sha256(data).hexdigest() != LIB_SHA256:
        raise ValueError('Native gameplay build changed; retrace required')
    from analyze_native_resources import NativeImage
    image = NativeImage(data)
    for address, (size, expected) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != expected:
            raise ValueError('Native gameplay routine changed')
    for address, expected in CONSTANTS.items():
        if image.read(address,4) != struct.pack('<f',expected):
            raise ValueError('Native motion constant changed')
    return {'librarySHA256':LIB_SHA256,'routines':{hex(a):{'bytes':n,'sha256':h} for a,(n,h) in ROUTINES.items()},
            'constants':{hex(a):struct.unpack('<f',struct.pack('<f',v))[0] for a,v in CONSTANTS.items()}}

def recover_gameplay(extract, output, selected_items):
    loaded, tables, proofs = {}, {}, {}
    def load(path):
        if path not in loaded:
            value=extract(path)
            loaded[path]=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
        return loaded[path]
    for name, key in [('skill_combo','id'),('skill_proto','skillId'),('skill_runes','id'),
                      ('skill_visual_state','id'),('c_animationdata','anim_id'),('items','entry'),('cls_weapon','id')]:
        parsed=decode_ftable(load('tables/'+name+'.tbl'),key)
        tables[name]={r[key]:r for r in parsed['rows']};proofs[name]=parsed['verification']
    anim_path='model/npc/character/elf/female/anim/animations.bdae'
    # Parser needs a file; extract returns a checked local file in this builder.
    animation=BDAEAnimation(Path(extract(anim_path)))
    source_ranges=animation.ranges()
    ranges={r['name'] for r in source_ranges}
    survey=[]
    for race,sex in [('daisauros','male'),('elf','female'),('elf','male'),('human','female'),('human','male'),('mendel','female'),('mendel','male'),('orc','female'),('orc','male')]:
        path=f'model/npc/character/{race}/{sex}/anim/animations.bdae'
        source=Path(extract(path));raw=source.read_bytes();rr=BDAEAnimation(source).ranges()
        survey.append({'source':path,'sha256':hashlib.sha256(raw).hexdigest(),'rangeCount':len(rr),
            'stationaryJumpRanges':[r['name'] for r in rr if r['name']=='jump_in_place' or r['sourceName']=='jump_in_place'],
            'rawNamePresent':b'jump_in_place' in raw})
    normal=[r for r in tables['skill_combo'].values() if r['isNormalAttack']==1]
    # The live normal bank uses weighted selection for group 0 as well as later
    # groups. Keep every eligible on-foot starter; exclude summoned NPC banks.
    seeds=set()
    for main in {r['reqMainWeaponType'] for r in normal}:
        for profession in range(1,7):
            matches=[r for r in normal if r['skillId']==0 and r['summonNormalSkill']!=1 and r['reqMainWeaponType']==main and
                r['reqOffWeaponType']==0xffff and tables['skill_proto'][r['nextSkillId']]['reqProfession'] in (0,7,profession)]
            seeds.update(r['id'] for r in matches)
    reachable={r['nextSkillId'] for r in normal if r['id'] in seeds}
    while True:
        expanded=reachable|{r[k] for r in normal if r['skillId'] in reachable for k in ('nextSkillId','timeOutSkill') if r[k]}
        if expanded==reachable:break
        reachable=expanded
    rows=[r for r in normal if r['id'] in seeds or r['skillId'] in reachable]
    ids={r[k] for r in rows for k in ['skillId','nextSkillId','timeOutSkill'] if r[k]}
    skills, actions, icons = {}, {}, {}
    output=Path(output);(output/'ui').mkdir(parents=True,exist_ok=True)
    for identifier in sorted(ids):
        proto=tables['skill_proto'].get(identifier)
        if proto is None:raise ValueError('Combo references missing proto')
        rune=tables['skill_runes'].get(proto['rune0'])
        state=tables['skill_visual_state'].get(rune['releaseState']) if rune else None
        anim=tables['c_animationdata'].get(state['casterPreAnim']) if state else None
        name=anim['anim_name'] if anim else None
        entry={'id':identifier,'reqProfession':proto['reqProfession'],'editName':proto['editName'],
               'runeId':proto['rune0'],'releaseState':rune['releaseState'] if rune else None,
               'animationId':state['casterPreAnim'] if state else None,'sourceAnimation':name,
               'clip':None,'commonCD':proto['commonCD'],'coolDownTime':proto['coolDownTime']}
        if name in ranges and sum(r['name']==name or r['sourceName']==name for r in source_ranges)==1:
            entry['clip']=next((k for k,v in actions.items() if v==name),'attack_'+str(identifier))
            actions[entry['clip']]=name
            interval=next(r for r in source_ranges if r['name']==name)
            entry['durationMs']=(round(interval['endMs']*.03)-round(interval['startMs']*.03))/.03
        if rune and rune['icon']:
            path='ui/icons/'+rune['icon'];raw=load(path)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!='PNG' or image.size!=(96,96):raise ValueError('Invalid basic attack PNG')
                image.verify()
            target='basic-attack-'+str(identifier)+'.png';(output/'ui'/target).write_bytes(raw)
            icons[str(identifier)]={'url':'/assets/ui/'+target,'width':96,'height':96,'sourcePath':path,
                                    'sourceSHA256':hashlib.sha256(raw).hexdigest()}
        skills[str(identifier)]=entry
    weapons={}
    for key, selection in selected_items.items():
        if selection['slot']!='mainHand':continue
        item=tables['items'][selection['entry']]
        if item['class']!=1:raise ValueError('Selected main hand is not a source weapon')
        second,third=item['subclass'],item['third_cat']
        match=[r for r in tables['cls_weapon'].values() if r['second_category']==second and r['third_category']==third]
        if len(match)!=1:raise ValueError('Ambiguous source weapon category')
        r=match[0];fields=['cls_warrior','cls_mage','cls_hunter','cls_priest','cls_demon_slayer','cls_sword_man']
        weapons[key]={'sourceItemId':item['entry'],'secondCategory':second,'thirdCategory':third,
                      'word':second+(third<<16),'allowedProfessions':[i+1 for i,k in enumerate(fields) if r[k]],
                      'legacy':not any(r[k] for k in fields),'sourceTypeName':r['weapon_type']}
    casting,cast_actions=recover_cast(extract,animation);actions.update(cast_actions)
    result={'format':'oc2-native-gameplay-v3','comboRows':rows,'skills':skills,'weapons':weapons,'icons':icons,'casting':casting,
        'jump':{'mode':'normal-on-foot','initialVelocity':10,'initialGravity':struct.unpack('<f',struct.pack('<f',-41.6))[0],
                'gravityByNextVelocity':[[-13.1,-6.7],[-3.5,-75],[3.5,-20]],'predictPositionBeforeVelocity':True,
                'velocityStepCapMs':100,'stationaryAnimationAvailable':'jump_in_place' in ranges,
                'webStepMs':50,'webLandingClip':'jumplandrun','stationarySurvey':survey,
                'missingStationaryPolicy':'retain-locomotion; native enter has no animation override when clip check fails'},
        'evidence':{'librarySHA256':LIB_SHA256,'routines':{hex(a):{'bytes':n,'sha256':h} for a,(n,h) in ROUTINES.items()},
                    'tables':proofs,'animationSHA256':hashlib.sha256(load(anim_path)).hexdigest()},
        'limitations':['Native normal-air impulse/gravity branches and table filters are traced; original frame timing, speed/direction renormalization, complete engine collision flags, water, mounts and flying remain outside this web solver.',
            'Horizontal speed/air steering remains existing web movement; static and registered runtime PHY geometry now own world-space floor, wall and ceiling contact in its bounded web solver.',
            'On-foot normal-bank caller chain is traced: items.class/subclass/third_cat → a0ea08 → 5c11bc → 5bef40; Hero_CastSpell → 5c04bc → 9f7f68; execution 5d2530 → 5c0d38; timer 5bf9b4. Full proprietary protocol and original server are not reproduced.',
            'Normal bank 1 only; no bank-0 legacy fallback, summoned/mounted normal attack, temporary bank-2/3 replacement or complete charge/channel targeting is implemented.',
            'All nine supplied player animation files lack jump_in_place. The stationary branch retains locomotion instead of relabeling a different clip.',
            'Normal attack execution retains source clip duration. The two selected spells use recovered prepare/chant/release/channel/end stages and movement bits; original actor arbitration, all targeting branches and packet handlers remain outside this implementation.',
            'Damage, range, 700 ms attack cooldown, character class creation and item grants remain local prototype rules.']}
    (output/'gameplay').mkdir(exist_ok=True)
    (output/'gameplay/native.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result,actions

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=verify_native(args.library.read_bytes())
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2))
    print(json.dumps({'verifiedRoutines':len(report['routines']),'verifiedConstants':len(report['constants'])}))
