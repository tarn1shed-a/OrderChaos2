"""Recover source portrait-slot and model binding evidence without running SWF.

The original gauge uses a Model3D component around a dynamic image slot. Web
portraits use the recovered local models; camera, lighting and framing remain
explicit web adaptations, not recovered native portrait camera parameters.
"""
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bdae_skin import read_nodes
from skill_attachments import decode_ftable
from ui_assets import Bits, tags, read_swf

GAUGE_SWF = 'ui/Flash/PlayerGauges.swf'
MODEL_TABLE = 'tables/creaturemodeldata.tbl'
DISPLAY_TABLE = 'tables/creaturedisplayinfo.tbl'
PLAYER_MODEL = 'model/npc/creature/humanoid/forest_elf/forest_elf.bdae'
MODULAR_PLAYER_MODEL = 'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'
WOLF_MODEL = 'model/npc/creature/beast/wolf/wolf.bdae'


class _ABC:
    """Bounded ABC 46.16 constant-pool reader; bytecode is never run."""
    def __init__(self,data):self.data,self.at=data,0
    def take(self,size):
        if size<0 or self.at+size>len(self.data):raise ValueError('Truncated ABC')
        result=self.data[self.at:self.at+size];self.at+=size;return result
    def byte(self):return self.take(1)[0]
    def variable(self,limit=0x3fffffff):
        value=0
        for shift in range(0,35,7):
            byte=self.byte();value|=(byte&127)<<shift
            if not byte&128:
                if value>limit:raise ValueError('ABC variable integer overflow')
                return value
        raise ValueError('ABC variable integer too long')
    def count(self):
        value=self.variable()
        if value>100000:raise ValueError('ABC count exceeds bounded reader')
        return value


def decode_abc_metadata(data):
    reader=_ABC(data)
    if reader.take(4)!=struct.pack('<HH',16,46):raise ValueError('Unsupported ABC version')
    for _ in range(2):
        for _ in range(max(0,reader.count()-1)):reader.variable(0xffffffff)
    reader.take(max(0,reader.count()-1)*8)
    strings=['']
    for _ in range(max(0,reader.count()-1)):
        try:strings.append(reader.take(reader.count()).decode('utf-8'))
        except UnicodeDecodeError as error:raise ValueError('Invalid ABC UTF-8') from error
    namespaces=[None]
    for _ in range(max(0,reader.count()-1)):namespaces.append((reader.byte(),reader.variable()))
    nssets=[[]]
    for _ in range(max(0,reader.count()-1)):nssets.append([reader.variable() for _ in range(reader.count())])
    names=[None]
    for _ in range(max(0,reader.count()-1)):
        kind=reader.byte()
        if kind in (7,13):item=(kind,reader.variable(),reader.variable())
        elif kind in (15,16):item=(kind,reader.variable())
        elif kind in (17,18):item=(kind,)
        elif kind in (9,14):item=(kind,reader.variable(),reader.variable())
        elif kind in (27,28):item=(kind,reader.variable())
        elif kind==29:item=(kind,reader.variable(),[reader.variable() for _ in range(reader.count())])
        else:raise ValueError('Unsupported ABC multiname kind')
        names.append(item)
    def string(index):
        if index>=len(strings):raise ValueError('ABC string index outside pool')
        return strings[index]
    def qname(index):
        if index==0:return '*'
        if index>=len(names):raise ValueError('ABC multiname index outside pool')
        item=names[index]
        if item[0] in (7,13):
            if not 0<item[1]<len(namespaces):raise ValueError('ABC namespace index outside pool')
            namespace=string(namespaces[item[1]][1]);name=string(item[2])
            return namespace+'::'+name if namespace else name
        if item[0] in (9,14,15,16):return string(item[1])
        return '<runtime-name>'
    # Metadata-only API. The observed reordered/length-prefixed method layout
    # is handled separately by optimized_abc; neither reader executes bytecode.
    return {'version':[16,46],'strings':strings,'multinames':[qname(i) for i in range(1,len(names))],
            'constantPoolBytes':reader.at,'unparsedMethodBytes':len(data)-reader.at,
            'proofScope':'constant-pool-only; method/trait proof requires optimized_abc',
            'sourceSHA256':hashlib.sha256(data).hexdigest()}


def decode_gauge_abc(raw):
    swf=read_swf(raw)
    if raw[:3]!=b'FWS':raise ValueError('Portrait proof requires observed uncompressed SWF')
    bits=Bits(raw,8);bits.rect();blocks=[]
    for kind,at,size in tags(raw,bits.pos()+4,len(raw)):
        if kind==300:
            payload=raw[at:at+size]
            if len(payload)<9:raise ValueError('Truncated DoABC wrapper')
            end=payload.find(b'\0',4)
            if end<0:raise ValueError('ABC script name has no terminator')
            blocks.append(decode_abc_metadata(payload[end+1:]))
    if len(blocks)!=1:raise ValueError('Expected one source gauge ABC block')
    return swf,blocks[0]


def _placements(swf,sprite):
    kind,data=swf['records'].get(sprite,(None,None))
    if kind!=39:raise ValueError('Portrait slot parent is not a sprite')
    result=[]
    for tag,at,size in tags(data,4,len(data)):
        if tag!=26:continue
        payload=data[at:at+size]
        if len(payload)<3:raise ValueError('Truncated portrait placement')
        flags=payload[0];q=3;character=None;matrix=None;name=None
        if flags&2:
            if q+2>len(payload):raise ValueError('Truncated portrait character')
            character=struct.unpack_from('<H',payload,q)[0];q+=2
        if flags&4:
            bits=Bits(payload,q);matrix=bits.matrix();q=bits.pos()
        if flags&8:
            bits=Bits(payload,q);add,multiply,count=bits.u(1),bits.u(1),bits.u(4)
            for _ in range(4*(add+multiply)):bits.s(count)
            bits.align();q=bits.pos()
        if flags&16:q+=2
        if flags&32:
            end=payload.find(b'\0',q)
            if end<q:raise ValueError('Unterminated portrait slot name')
            name=payload[q:end].decode('utf-8')
        result.append({'name':name,'character':character,'matrixTwips':matrix})
    return result


def source_portrait_slot(swf):
    root=swf['symbols'].get('Window_PlayerGauges')
    if root is None:raise ValueError('Source player-target gauge symbol missing')
    def child(sprite,name):
        found=[value for value in _placements(swf,sprite) if value['name']==name]
        if len(found)!=1 or found[0]['character'] is None:raise ValueError('Source portrait named slot missing or ambiguous')
        return found[0]
    slot=child(root,'playerIcon');image=child(slot['character'],'objImage')
    children=[value for value in _placements(swf,image['character']) if value['character'] is not None]
    if len(children)!=1:raise ValueError('Expected one source portrait placeholder shape')
    shape_id=children[0]['character'];kind,payload=swf['records'].get(shape_id,(None,None))
    if kind!=2:raise ValueError('Source portrait placeholder is not a shape')
    bits=Bits(payload,2);bounds=bits.rect();fill=bits.pos()
    if bounds!=[0,960,0,960]:raise ValueError('Source portrait placeholder bounds differ')
    if len(payload)<fill+6 or payload[fill:fill+2]!=b'\x01\0' or payload[fill+5]!=0:
        raise ValueError('Source portrait placeholder is not the verified solid-fill shape')
    return {'rootSpriteId':root,'slotPath':'playerIcon.objImage','spriteIds':[slot['character'],image['character']],
            'placeholderShapeId':shape_id,'placeholderBoundsTwips':bounds,'placementMatrixTwips':slot['matrixTwips'],
            'placeholderPixels':[48,48],'staticBitmapPortrait':False}


def _bytes(value):
    return bytes(value) if isinstance(value,(bytes,bytearray,memoryview)) else Path(value).read_bytes()


def _model_nodes(raw):
    # Reuse the strict observed BDAE reader without adding another binary parser.
    with tempfile.TemporaryDirectory(prefix='oc2-portrait-rig-') as temporary:
        path=Path(temporary)/'model.bdae';path.write_bytes(raw)
        return read_nodes(BDAE(path))


def _head(nodes,alias):
    matches=[(index,node) for index,node in enumerate(nodes)
             if node['name']==alias or alias in node.get('aliases',[])]
    if len(matches)!=1:raise ValueError('Source portrait head node missing or ambiguous: '+alias)
    index,node=matches[0]
    return {'headNode':alias,'headNodeIndex':index,'sourceHeadNodeName':node['name'],
            'sourceHeadParent':nodes[node['parent']]['name'] if node['parent']>=0 else None,
            'sourceHeadRest':{key:node[key] for key in ('position','quaternion','scale')}}


def recover_character_portraits(extract,output, *, player_model=PLAYER_MODEL):
    """Write ui/portraits.json; extract(path) returns checked bytes or a Path.

    No static portrait is invented. The selected-player Model3D component and
    enemy status icon are kept distinct from this web game's model thumbnails.
    """
    if player_model not in (PLAYER_MODEL, MODULAR_PLAYER_MODEL):raise ValueError('Unverified web player portrait model')
    loaded={}
    def load(path):
        if path not in loaded:loaded[path]=_bytes(extract(path))
        return loaded[path]
    proofs={};named_slot=None
    for path,required in (
        (GAUGE_SWF,['playerIcon','Model3D','targetGuid','TARGET_TYPE_PLAYER','Hero_GetTargetInfo','TYPE_MODEL','initWithGuid']),
        ('ui/Flash/Gauges2.swf',['vehicleIcon','Model3D','Hero_GetHeroInfo','TYPE_MODEL','initWithGuid']),
        ('ui/Flash/EnemyGauges.swf',['m_enemyIcon','Icon','Hero_GetTargetInfo',
                                 'ui/icons/userinterface/elite_head.png','ui/icons/userinterface/dungeon_elite_head.png'])):
        swf,abc=decode_gauge_abc(load(path))
        if any(name not in abc['strings'] for name in required):raise ValueError('Source gauge portrait identifiers differ: '+path)
        component='Icon' if path.endswith('EnemyGauges.swf') else 'Model3D'
        if 'Common.gluicEx.components.ui::'+component not in abc['multinames']:
            raise ValueError('Source gauge component namespace differs')
        if path==GAUGE_SWF:named_slot=source_portrait_slot(swf)
        proofs[path]={'pack':'ui.bin','sourceSHA256':swf['sha256'],'abcTag':300,
            'abcVersion':abc['version'],'abcSHA256':abc['sourceSHA256'],
            'requiredIdentifiers':required,'proofScope':abc['proofScope']}
    model_table=decode_ftable(load(MODEL_TABLE),'ID')
    display_table=decode_ftable(load(DISPLAY_TABLE),'ID')
    forest=[row for row in model_table['rows'] if row['ModelPath']==PLAYER_MODEL]
    if len(forest)!=1 or forest[0]['ID']!=335:raise ValueError('Forest-elf source model-table identity differs')
    displays=[row for row in display_table['rows'] if row['Model']==335]
    if not displays or any(row['Icon'] for row in displays):raise ValueError('Forest-elf source static icon mapping differs')
    models={}
    for key,path,url,alias,slot,role in (
        ('player',player_model,'/assets/models/elf-female.json' if player_model==MODULAR_PLAYER_MODEL else '/assets/models/forest-elf.json','Bip01_Head','playerIcon',
         'web self-avatar reuse; original playerIcon belongs to selected-player-target gauge'),
        ('targetWolf',WOLF_MODEL,'/assets/models/wolf.json','Bip001_Head','m_enemyIcon',
         'web target portrait adaptation; original enemy slot is an elite/status icon')):
        raw=load(path);nodes=_model_nodes(raw)
        matches=[row for row in model_table['rows'] if row['ModelPath']==path]
        models[key]={'modelPath':path,'modelURL':url,'mode':'source-model-web-framing',
            'sourcePack':'res_npc.bin','sourceModelSHA256':hashlib.sha256(raw).hexdigest(),
            'slot':slot,'sourceSlotRole':role,'sourceModelTableIds':[row['ID'] for row in matches],
            'originalStaticPortraitMapping':False,**_head(nodes,alias)}
    models['player']['sourceDisplayIds']=[row['ID'] for row in displays] if player_model==PLAYER_MODEL else []
    models['player']['webPlayerSelection']='modular-elf-female-body' if player_model==MODULAR_PLAYER_MODEL else 'forest-elf-npc'
    models['player']['webFraming']={'frameHeight':.52,'direction':[.16,.04,1]}
    models['targetWolf']['webFraming']={'frameHeight':.86,'direction':[.25,.08,1]}
    models['targetWolf']['unprovenTableCandidates']=[{'id':row['ID'],'modelPath':row['ModelPath']}
        for row in model_table['rows'] if row['ModelPath']=='model/npc/creature/beast/wolf/wolf_skin.bdae']
    profile={'format':'oc2-character-portraits-v1','models':models,
        'forestElfReference':{'modelPath':PLAYER_MODEL,'sourceModelTableId':335,
            'sourceDisplayIds':[row['ID'] for row in displays],
            'isCurrentWebPlayer':player_model==PLAYER_MODEL},
        'sourceComponents':{
            'selectedPlayer':{'sourceSWF':GAUGE_SWF,'root':'Window_PlayerGauges',
                'slot':'playerIcon.objImage','component':'Common.gluicEx.components.ui.Model3D',
                'namedSlot':named_slot,
                'role':'selected player target; not proven as the original self-HUD portrait'},
            'selfHUD':{'sourceSWF':'ui/Flash/Gauges2.swf','registeredName':'Gauges',
                'modelComponentName':'vehicleIcon','component':'Common.gluicEx.components.ui.Model3D',
                'role':'self HUD has a Model3D identifier associated with vehicleIcon; original self-avatar binding unresolved'},
            'enemyTarget':{'sourceSWF':'ui/Flash/EnemyGauges.swf','root':'Window_EnemyGaugesInfo',
                'slot':'m_enemyIcon','component':'Common.gluicEx.components.ui.Icon',
                'role':'original elite/status icon; no verified wolf static portrait'}},
        'sources':{**proofs,MODEL_TABLE:{'pack':'tables.bin',**model_table['verification']},
                   DISPLAY_TABLE:{'pack':'tables.bin',**display_table['verification']}},
        'provenance':{'swfExecution':False,'staticPortraitImagesExported':False,
            'cameraAndLighting':'web adaptation; no native portrait framing parameters recovered',
            'webRenderer':'prototype/public/character-portraits.js; independent 192px source-model thumbnail with web lighting',
            'limitations':[
                'Original gauge identifiers and Model3D API names are decoded from bounded ABC constant pools; optimized method/trait bodies are not fully decompiled.',
                'PlayerGauges is the selected-player target component. The original self HUD is Gauges2, whose vehicleIcon name does not establish an original forest-elf self-portrait binding.',
                'EnemyGauges uses an elite/status Icon. The web wolf head thumbnail is a source-model adaptation, not an original monster portrait image.',
                'Forest elf maps exactly to model-table 335; source wolf_skin.bdae candidates are not equated with the web wolf.bdae file.',
                'Head nodes come from the exact recovered model. Browser camera angle, crop, pose and lighting must be documented as web choices.']}}
    destination=Path(output)/'ui';destination.mkdir(parents=True,exist_ok=True)
    (destination/'portraits.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
    return profile
