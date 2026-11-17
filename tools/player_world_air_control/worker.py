"""Single own-body RPC protocol; only explicit pinned data selects the body."""
import copy,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools')]
from player_world_air_control.core import load_own,pinned,SPECS
DELEGATES={'human-male':('character_human_idle02_worker','sourceHumanPose',1992),
 'elf-female':('player_choice_elf_female_water_integration_worker','sourceElfFemalePose',1536)}

class SharedOwnAirRPC:
    def __init__(self,config):
        from source_runtime_resources import SourceRuntimeResources
        self.resources=SourceRuntimeResources()
        self.config=json.loads(Path(config).read_text());self.engines={};self.infos={};self.owners={}
        if self.config.get('format')!='oc2-shared-own-air-rpc-v1'or not self.config.get('bodies')or set(self.config['bodies'])-(set(SPECS)|set(DELEGATES)):raise ValueError('Explicit supported own body RPC subset required')
        self.configs={key:pinned(row)[0]for key,row in self.config['bodies'].items()}
        records={key:json.loads(p.read_text())for key,p in self.configs.items()}
        self.declarations={}
        for key,cfg in records.items():
            if key in SPECS:
                _,raw=pinned(cfg['inputs']['binding']);binding=json.loads(raw);_,_,_,field,properties,size=SPECS[key]
                if binding.get('sourceMotion',{}).get('key')!=key or binding.get('valueBytes')!=size:raise ValueError('Own body binding declaration differs')
                self.declarations[field]={'key':key,'bindingId':binding['bindingId'],'valueBytes':size,'sourceProperties':properties,'originalCompositionCPU':True,'originalGPUExecuted':False}
        def world_record(cfg):
            return({k:cfg['inputs'][k]['sha256']for k in('library','terrain','collision','terrainLighting','water','diving')},
              {k:v['sha256']for k,v in cfg['sourceFiles'].items()})
        first=world_record(next(iter(records.values())))
        if any(world_record(cfg)!=first for cfg in records.values()):raise ValueError('Same original world byte closure required across own bodies')

    def prepare(self,key):
        if key not in self.configs:raise ValueError('Body is outside this actual host closure')
        if key not in self.engines:
            if key in DELEGATES:
                import importlib
                module=importlib.import_module(DELEGATES[key][0]);e,info=module.load(self.configs[key])
            else:e,info=load_own(self.configs[key],resources=self.resources)
            if info.get('sourceSpeciesKeys')!=[key]:raise ValueError('Actual own loader identity differs')
            if self.infos:
                old=next(iter(self.infos.values()))
                if any(info.get(k)!=old.get(k)for k in('bounds','frame','instanceIds','nativeSHA256')):raise ValueError('Actual native world coordinate frame differs')
            self.engines[key]=e;self.infos[key]=info
        return self.engines[key],self.infos[key]

    def request(self,operation,data):
        if not isinstance(data,dict):raise ValueError('Structured actual RPC input required')
        if operation=='init':
            if data:raise ValueError('No invented init data')
            # Real loaded static geometry is shared only after identical source
            # world pins are independently checked by each own config loader.
            _,info=self.prepare(next(iter(self.configs)))
            return{**copy.deepcopy(info),**copy.deepcopy(self.declarations),'sourceSpeciesKeys':list(self.configs),'otherBodiesPrepared':False,'bindingDeclarationsArePreparationPromises':False}
        if operation=='prepareOwnBody':
            if set(data)!={'species'}:raise ValueError('Explicit own body preparation required')
            key=data['species'];e,info=self.prepare(key)
            if key in DELEGATES:_,field,size=DELEGATES[key]
            else:_,_,_,field,_,size=SPECS[key]
            from player_choice_all_worker import resident_bytes
            return{'key':key,'ready':True,'pose':{'field':field,'bindingId':info[field]['bindingId'],'valueBytes':size},'milliseconds':e.preparation_milliseconds,'rssBytes':resident_bytes()}
        if operation in('ground','sample','ray'):
            e,_=self.prepare(next(iter(self.configs)))
            if operation=='ground'and set(data)=={'point'}:return e.ground(*data['point'])
            if operation=='sample'and set(data)=={'point'}:return e.sample(*data['point'])
            if operation=='ray'and set(data)in({'from','to'},{'from','to','capsule'}):return e.ray(data['from'],data['to'],data.get('capsule',False))
            raise ValueError('Exact original static query required')
        key=data.get('bodyKey');identity=data.get('identity')
        if key not in self.configs or not isinstance(identity,str)or not 0<len(identity)<=128:raise ValueError('Current body and owned actor identity required')
        e,_=self.prepare(key);d={k:v for k,v in data.items()if k!='bodyKey'}
        if operation=='reset':
            if set(d)!={'identity','position','species','profession','equipment'}or d['species']!=key or identity in self.owners:raise ValueError('New scoped identity and matching own species required')
            result=e.fresh_actor(identity,d['position'],d['profession'],d['equipment']);self.owners[identity]=key;return result
        if self.owners.get(identity)!=key:raise ValueError('This actor is not owned by that body')
        if operation in('press','release'):
            if set(d)!={'identity'}:raise ValueError('Exact owned press/release edge required')
            return e.press_event(identity,operation=='press')
        if operation=='tick':return e.tick_own(d)
        if operation in('input-state','water','forget')and set(d)!={'identity'}:raise ValueError('Exact current owner lifetime/query required')
        if operation=='input-state':return e.inputs.inspect(identity)
        if operation=='water':return e.water_state(identity)
        if operation=='forget':
            result=e.disconnect(identity);del self.owners[identity];return result
        raise ValueError('Unsupported own air RPC operation')

def start(config):
    engine=SharedOwnAirRPC(config)
    for line in sys.stdin:
        try:
            q=json.loads(line)
            if not isinstance(q,dict)or set(q)!={'operation','data'}:raise ValueError('Exact original RPC envelope required')
            print(json.dumps({'result':engine.request(q['operation'],q['data'])},separators=(',',':'),allow_nan=False),flush=True)
        except Exception as error:print(json.dumps({'error':str(error)},ensure_ascii=False),flush=True)

if __name__=='__main__':start(sys.argv[1])
