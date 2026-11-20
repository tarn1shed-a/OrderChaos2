"""New path namespace over the frozen shared projection core, no new parser."""
from pathlib import Path
from types import FunctionType
import hashlib
from world_air_delivery_v2 import portable as _base

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'analysis/raw/portable/running-preview'
PREFIX='native-inputs/world-latest-v1/'
PLAN=PREFIX+'projection.json'
BASE_SHA='72ba769f01c32a3117f206f50e65c73595ed7f36382ab9866f3a55d9ab4dce6e'
if hashlib.sha256(Path(_base.__file__).read_bytes()).hexdigest()!=BASE_SHA:
    raise ValueError('Exact frozen V2 path projection core required')
# A private function namespace preserves old V2 defaults and installed files.
# Only transport paths/plan are rebound; original recursive projection and all
# resource/code/envelope/provenance validation execute the original code object.
_scope={**vars(_base),'ROOT':ROOT,'RUNTIME':RUNTIME,'PREFIX':PREFIX,'PLAN':PLAN}
for _name,_value in vars(_base).items():
    if isinstance(_value,FunctionType) and _value.__module__==_base.__name__:
        _scope[_name]=FunctionType(_value.__code__,_scope,_value.__name__,_value.__defaults__,_value.__closure__)
for _name in ('encoded','sha','inside','read_plan','project','validate_sources','materialize','validate_config','run'):
    globals()[_name]=_scope[_name]
