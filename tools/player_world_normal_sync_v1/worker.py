"""One derived loader, unchanged native input/clock/physics/composition/carrier.

Original synchronous shuffle requests remain admitted only by exact own ranges.
The sole absent-duration branch is metadata, never a loaded/playable clip.
"""
from pathlib import Path
from types import FunctionType
import hashlib, importlib.util, json, sys, re
from collections import deque
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/creation_playback')]
from player_world_eight_motion.worker import RuntimeAirRPC
from player_world_air_existing import ExistingLoader,ExistingOwnAir,load_existing
HELPER=ROOT/'analysis/raw/common-eight-gather-run-prefix-20261117/native_duration.py'
HELPER_SHA='ac9a076a26008f4ac187802a7e8bcbab139825a48df04742a2c251161466aa36'

def duration_type():
    if hashlib.sha256(HELPER.read_bytes()).hexdigest()!=HELPER_SHA:raise ValueError('Exact shared original null-duration metadata helper required')
    spec=importlib.util.spec_from_file_location('_own_normal_duration_metadata',HELPER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.OwnDurationNullMetadata

class NormalOwnAir(ExistingOwnAir):
    def __init__(self,image,profile,animation,context,key):
        super().__init__(image,profile,animation,context,key)
        self.normal_source_animation=animation;self.normal_null_receipts=[];self.normal_null_proofs={}
        self.normal_format_metadata=deque(maxlen=64)
        self.normal_sfx_format_literals=frozenset(value for resource in(image.data,animation.b)for value in re.findall(rb'sfx_[A-Za-z0-9_]{1,96}_%s(?=\0)',resource))
        requests=profile.get('normalDurationMetadata',{}).get('actualOriginalRequestNames',[])
        if not isinstance(requests,list)or len(requests)!=len(set(requests))or any(not isinstance(name,str)or not re.fullmatch(r'[A-Za-z0-9_]{1,63}',name)for name in requests):raise ValueError('Exact source duration request metadata required')
        absent=[name for name in requests if not self.own_duration_rows.get(name)]
        if absent:
            metadata=duration_type()(image,animation)
            self.normal_null_proofs={name:metadata.prove_null(name)for name in absent}
            # Metadata only, before any actor/input. Do not construct this VM on
            # an ordinary movement frame or retain it as actor state.
            del metadata
    def hook(self,uc,pc,size,data):
        if self.get('PC')!=pc:return
        if getattr(self,'human_active',False)and self.imports.get(pc)=='sprintf':
            address=self.get('X1');fmt=self.cstr(address)
            if re.fullmatch(rb'sfx_[A-Za-z0-9_]{1,96}_%s',fmt):
                # Original image/own-bank format bytes and actual current C string.
                # Original COW strings may live in heap; pointer location alone
                # is not original-byte provenance.
                # This is libc byte formatting, never an audio handle/success.
                if fmt not in self.normal_sfx_format_literals:raise ValueError('Exact original image/own-bank SFX format bytes required')
                value=self.cstr(self.get('X2'))
                if not value.isascii()or len(value)>64:raise ValueError('Bounded original SFX argument required')
                raw=fmt.replace(b'%s',value)
                self.normal_format_metadata.append({'originalCaller':hex(self.get('X30')-4),'format':fmt.decode(),'argument':value.decode(),'result':raw.decode(),'audioHandleOrPlaySuccessSupplied':False})
                uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        if pc==0x331cbc and getattr(self,'human_active',False):
            name=self.cstr(self.get('X2')).decode()
            if not self.own_duration_rows.get(name) and name in self.normal_null_proofs:
                receipt=self.normal_null_proofs[name]
                if receipt is None:raise ValueError('Original null metadata must be prepared before actor input')
                if receipt['sourceAnimationSHA256']!=self.ANIMATION_SHA or receipt['durationRaw32']!=0xffffffff or receipt['durationOnlyNotPlaybackAdmission'] is not True:raise ValueError('Exact own-bank null metadata required')
                self.normal_null_receipts.append(dict(receipt));self.metadata_queries.append(dict(receipt))
                self.set('W0',receipt['durationRaw32']);self.set('PC',self.get('X30'));return
        return super().hook(uc,pc,size,data)

normal_load=FunctionType(load_existing.__code__,{**load_existing.__globals__,'OwnAir':NormalOwnAir},argdefs=load_existing.__defaults__)
class NormalLoader(ExistingLoader):pass
NormalLoader.prepare=FunctionType(ExistingLoader.prepare.__code__,{**ExistingLoader.prepare.__globals__,'load_own':normal_load})
class NormalSyncRPC(RuntimeAirRPC,NormalLoader):pass

def start(config):
    rpc=NormalSyncRPC(config)
    for line in sys.stdin:
        try:
            q=json.loads(line)
            if not isinstance(q,dict)or set(q)!={'operation','data'}:raise ValueError('Exact original shared RPC envelope required')
            print(json.dumps({'result':rpc.request(q['operation'],q['data'])},separators=(',',':'),allow_nan=False),flush=True)
        except Exception as error:print(json.dumps({'error':str(error)},ensure_ascii=False),flush=True)
def readable_runtime_type(original_readable):
    """Inject only the loader into the frozen GA9 readonly worker MRO."""
    import inspect
    expected='e234a87e5be59752f6ccaa130ce37cb46f6e8652c50c890318d21e917250fed6'
    if not issubclass(original_readable,RuntimeAirRPC)or hashlib.sha256(Path(inspect.getsourcefile(original_readable)).read_bytes()).hexdigest()!=expected:
        raise ValueError('Exact existing readable GA9 worker required')
    return type('NormalSyncReadableRPC',(original_readable,NormalLoader),{})


if __name__=='__main__':start(sys.argv[1])
