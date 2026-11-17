"""Actual Python RPC handlers with explicit host-only ports; never native math.

No source resource, NativeImage, Uc, actor constructor, clock or service runs.
The fixture tests routing, atomic preparation and the production carrier's
push/pull lifecycle. It is not native body readiness or numeric equivalence.
"""
import copy
from collections import deque
import struct
import types
import unittest

from player_world_air_control.worker import SharedOwnAirRPC
from player_world_eight_motion.worker import RuntimeAirRPC

KEYS=('first-host-fixture','selected-host-fixture')


class MemoryPort:
    def __init__(self,key,index):
        self.key=key;self.controller=0x1000+index*0x100;self.uc=self
        self.memory={0x2528410:bytes([index+1])*32,0x2528140:b'O'*8}
        self.calls=[];self.humans={};self.next_rng=None;self.query_error=None
        self.preparation_milliseconds=0
    def mem_read(self,address,length):
        value=self.memory[address];assert len(value)==length;return value
    def mem_write(self,address,value):self.memory[address]=bytes(value)
    def r(self,address,fmt):
        if address==0x2528e18:return(self.controller,)
        if address==self.controller+0x34:return(0xc47a0000,)
        if address==0x2544581:return(0,)
        return struct.unpack('<'+fmt,self.mem_read(address,struct.calcsize('<'+fmt)))
    def set_timeval(self,value):self.timeval=list(value)
    def query(self,operation,*args):
        self.calls.append((operation,args))
        if self.next_rng is not None:self.memory[0x2528410]=self.next_rng
        if self.query_error is not None:raise self.query_error
        return{'operation':operation,'bodyKey':self.key,'arguments':args}
    def ground(self,*args):return self.query('ground',*args)
    def sample(self,*args):return self.query('sample',*args)
    def ray(self,*args):return self.query('ray',*args)
    def fresh_actor(self,identity,position,profession,equipment):
        self.humans[identity]=True;return{'key':self.key,'identity':identity}
    def tick_own(self,data):return{'key':self.key,'identity':data['identity']}
    def disconnect(self,identity):self.humans.pop(identity);return{'forgotten':True}


def fixture(cls=SharedOwnAirRPC,carrier=False):
    value=cls.__new__(cls)
    value.configs=dict.fromkeys(KEYS);value.static_body_key=None
    value.declarations={};value.owners={};value.prepared=[];value.failure=None
    value.engines={key:MemoryPort(key,index) for index,key in enumerate(KEYS)}
    value.infos={key:{'sourceSpeciesKeys':[key],'fixturePreparedKey':key} for key in KEYS}
    value.source_runtime=None;value.operation_timeval=None;value.last_engine=None
    value.runtime_bindings={};value.transfer_count=0;value.global_transfers=deque(maxlen=64)
    if carrier:
        value.source_runtime={'rng':b'R'*32,'origin':b'O'*8,'lastTimeval':[123,456]}
        for key,engine in value.engines.items():
            value.runtime_bindings[key]={'controller':engine.controller,
                'lastRNG':engine.memory[0x2528410],'lastOrigin':engine.memory[0x2528140]}
    def prepare(self,key):
        self.prepared.append(key)
        if self.failure is not None:raise self.failure
        engine=self.engines[key]
        if self.source_runtime is not None:self._push(key,engine)
        return engine,self.infos[key]
    value.prepare=types.MethodType(prepare,value)
    return value


class StaticBodyProtocolTests(unittest.TestCase):
    def test_explicit_init_only_prepares_selected_body_and_keeps_full_declarations(self):
        rpc=fixture();rpc.declarations={'sourceFixturePose':{'fixture':True}}
        result=rpc.request('init',{'bodyKey':KEYS[1]})
        self.assertEqual(rpc.prepared,[KEYS[1]])
        self.assertEqual(rpc.static_body_key,KEYS[1])
        self.assertEqual(result['fixturePreparedKey'],KEYS[1])
        self.assertEqual(result['sourceSpeciesKeys'],list(KEYS))
        self.assertEqual(result['sourceFixturePose'],{'fixture':True})
        self.assertIs(result['bindingDeclarationsArePreparationPromises'],False)

    def test_empty_initial_init_keeps_old_first_config_behavior(self):
        rpc=fixture();result=rpc.request('init',{})
        self.assertEqual(result['fixturePreparedKey'],KEYS[0])
        self.assertEqual(rpc.prepared,[KEYS[0]])

    def test_repeated_empty_or_same_init_keeps_selected_primary(self):
        rpc=fixture();rpc.request('init',{'bodyKey':KEYS[1]})
        for data in ({},{'bodyKey':KEYS[1]}):
            self.assertEqual(rpc.request('init',data)['fixturePreparedKey'],KEYS[1])
        self.assertEqual(rpc.static_body_key,KEYS[1])
        self.assertNotIn(KEYS[0],rpc.prepared)

    def test_unknown_malformed_or_retarget_init_never_prepares(self):
        rpc=fixture();rpc.request('init',{'bodyKey':KEYS[1]});rpc.prepared.clear()
        for data in ({'bodyKey':KEYS[0]},{'bodyKey':'unknown'},{'bodyKey':None},
                     {'bodyKey':True},{'bodyKey':[]},{'bodyKey':KEYS[1],'extra':0},[],None):
            with self.subTest(data=data),self.assertRaises(ValueError):rpc.request('init',data)
        self.assertEqual(rpc.prepared,[])
        self.assertEqual(rpc.static_body_key,KEYS[1])

    def test_failed_preparation_does_not_publish_binding_or_swallow_error(self):
        rpc=fixture();error=RuntimeError('explicit fixture preparation failure');rpc.failure=error
        with self.assertRaises(RuntimeError) as caught:rpc.request('init',{'bodyKey':KEYS[1]})
        self.assertIs(caught.exception,error);self.assertIsNone(rpc.static_body_key)
        rpc.failure=None;rpc.request('init',{'bodyKey':KEYS[0]})
        self.assertEqual(rpc.static_body_key,KEYS[0])

    def test_all_static_queries_use_bound_body_and_original_arguments(self):
        rpc=fixture();rpc.request('init',{'bodyKey':KEYS[1]})
        cases=[('ground',{'point':[1,2,3]},(1,2,3)),('sample',{'point':[1,2]},(1,2)),
               ('ray',{'from':[0,0,0],'to':[1,2,3]},([0,0,0],[1,2,3],False)),
               ('ray',{'from':[0,0,0],'to':[1,2,3],'capsule':True},([0,0,0],[1,2,3],True))]
        for operation,data,args in cases:
            result=rpc.request(operation,data)
            self.assertEqual(result,{'operation':operation,'bodyKey':KEYS[1],'arguments':args})
        self.assertEqual(rpc.engines[KEYS[0]].calls,[])

    def test_legacy_query_before_init_pins_actual_default_world(self):
        rpc=fixture();rpc.request('ground',{'point':[1,2,3]})
        self.assertEqual(rpc.static_body_key,KEYS[0])
        self.assertEqual(rpc.request('init',{})['fixturePreparedKey'],KEYS[0])
        with self.assertRaises(ValueError):rpc.request('init',{'bodyKey':KEYS[1]})

    def test_malformed_query_does_not_prepare_or_bind(self):
        rpc=fixture()
        for operation,data in [('ground',{}),('sample',{'point':[1,2],'bodyKey':KEYS[1]}),
                               ('ray',{'from':[0,0,0]}),('ground',None)]:
            with self.subTest(operation=operation),self.assertRaises(ValueError):rpc.request(operation,data)
        self.assertEqual(rpc.prepared,[]);self.assertIsNone(rpc.static_body_key)

    def test_actor_body_and_owner_lifetime_do_not_retarget_static_world(self):
        rpc=fixture();rpc.request('init',{'bodyKey':KEYS[1]})
        result=rpc.request('reset',{'bodyKey':KEYS[0],'identity':'actor-a','position':[1,2,3],
                                  'species':KEYS[0],'profession':5,'equipment':{}})
        self.assertEqual(result['key'],KEYS[0])
        self.assertEqual(rpc.request('tick',{'bodyKey':KEYS[0],'identity':'actor-a'})['key'],KEYS[0])
        with self.assertRaises(ValueError):rpc.request('tick',{'bodyKey':KEYS[1],'identity':'actor-a'})
        rpc.request('forget',{'bodyKey':KEYS[0],'identity':'actor-a'})
        self.assertEqual(rpc.owners,{})
        self.assertEqual(rpc.request('sample',{'point':[1,2]})['bodyKey'],KEYS[1])


class RuntimeCarrierTests(unittest.TestCase):
    def test_static_query_push_and_finally_pull_use_same_selected_body(self):
        rpc=fixture(RuntimeAirRPC,carrier=True);rpc.request('init',{'bodyKey':KEYS[1]})
        other=copy.deepcopy(rpc.engines[KEYS[0]].memory)
        clock=copy.deepcopy(rpc.source_runtime['lastTimeval'])
        rpc.engines[KEYS[1]].next_rng=b'Q'*32
        result=rpc.request('ground',{'point':[1,2,3]})
        self.assertEqual(result['bodyKey'],KEYS[1])
        self.assertEqual(rpc.source_runtime['rng'],b'Q'*32)
        self.assertEqual(rpc.global_transfers[-1]['key'],KEYS[1])
        self.assertEqual(rpc.engines[KEYS[0]].memory,other)
        self.assertEqual(rpc.source_runtime['lastTimeval'],clock)
        self.assertIsNone(rpc.operation_timeval)

    def test_refused_retarget_cannot_pull_idle_other_body_rng(self):
        rpc=fixture(RuntimeAirRPC,carrier=True);rpc.request('init',{'bodyKey':KEYS[1]})
        before=(copy.deepcopy(rpc.source_runtime),copy.deepcopy(rpc.runtime_bindings),rpc.transfer_count,list(rpc.prepared))
        with self.assertRaises(ValueError):rpc.request('init',{'bodyKey':KEYS[0]})
        self.assertEqual((rpc.source_runtime,rpc.runtime_bindings,rpc.transfer_count,rpc.prepared),before)

    def test_malformed_static_query_cannot_override_pull_body(self):
        rpc=fixture(RuntimeAirRPC,carrier=True);rpc.request('init',{'bodyKey':KEYS[1]})
        before=(copy.deepcopy(rpc.source_runtime),rpc.transfer_count,list(rpc.prepared))
        with self.assertRaises(ValueError):rpc.request('ground',{'point':[1,2,3],'bodyKey':KEYS[0]})
        self.assertEqual((rpc.source_runtime,rpc.transfer_count,rpc.prepared),before)

    def test_query_exception_preserves_original_error_and_selected_finally_pull(self):
        rpc=fixture(RuntimeAirRPC,carrier=True);rpc.request('init',{'bodyKey':KEYS[1]})
        error=RuntimeError('explicit fixture query failure');engine=rpc.engines[KEYS[1]]
        engine.next_rng=b'Z'*32;engine.query_error=error
        with self.assertRaises(RuntimeError) as caught:rpc.request('sample',{'point':[1,2]})
        self.assertIs(caught.exception,error)
        self.assertEqual(rpc.source_runtime['rng'],b'Z'*32)
        self.assertEqual(rpc.global_transfers[-1]['key'],KEYS[1])


if __name__=='__main__':unittest.main(verbosity=2)
