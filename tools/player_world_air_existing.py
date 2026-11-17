"""Add existing HumanM/ElfF own banks to the single frozen OwnAir core.

Only identity data and the existing Human-specific composition adapter differ.
No source track, time, mask, renderer, input or queue algorithm is copied here.
"""
import hashlib
import json
import sys
from pathlib import Path
from types import FunctionType

from female_air_null.source import source_method
from player_world_air_control import core
from player_world_air_control.worker import SharedOwnAirRPC
from player_world_first_history import FirstHistoryRPC

SPECS = {**core.SPECS,
    'human-male': (1, 0, 0, 'sourceHumanPose', 135, 1992),
    'elf-female': (2, 1, 1, 'sourceElfFemalePose', 110, 1536)}


class ExistingOwnAir(core.OwnAir):
    pass


# The same source guard, now checked against these two own descriptor rows.
ExistingOwnAir.__init__ = FunctionType(core.OwnAir.__init__.__code__,
    {**core.OwnAir.__init__.__globals__, 'SPECS': SPECS})


def declare_binding(key, binding):
    if key != 'human-male':
        return binding
    # Human's historical binding schema derives these two transport fields in
    # its existing verified constructor; do not rewrite/relabel that asset.
    from character_human_idle02_probe import transport_type
    transport = transport_type(binding['sourceMotion']['sha256'])(binding)
    return {**binding, 'bindingId': transport.binding_id, 'valueBytes': 1992}


def prepare_existing_human(image, body, animation, data, mask, files, binding, profile):
    from character_human_queue_fast_probe import FastHumanCompositionProbe
    from character_human_queue_composition_probe import HumanCompositionProbe
    from character_human_idle02_probe import transport_type
    from character_elf_male_binding import source_controller
    skin = source_controller(body, {'meshes': [data['meshes'][0]]}, data['rig']['nodes'], 0)
    vm = FastHumanCompositionProbe(image, body, body, skin, 0)
    vm.animation(animation)
    prepare = FunctionType(HumanCompositionProbe.prepare_composition.__code__,
        {**HumanCompositionProbe.prepare_composition.__globals__, 'MASK': files['mask'][0]})
    prepare(vm, data)
    if vm.mask_report != mask:
        raise ValueError('Own Human mask bytes differ')
    transport = transport_type(profile['species']['sha256'])(binding)
    return vm, lambda _: vm.bind_profile(profile), transport


load_existing, LOAD_SOURCE_SHA256 = source_method(core.load_own, [
    ("binding=json.loads(files['binding'][1])",
     "binding=declare_binding(key,json.loads(files['binding'][1]))", 1),
    ("if key=='elf-male':",
     "if key=='human-male':\n        vm,bind,transport=prepare_existing_human(image,body,animation,data,mask,files,binding,profile)\n    elif key=='elf-male':", 1),
], {'SPECS': SPECS, 'OwnAir': ExistingOwnAir,
    'prepare_existing_human': prepare_existing_human, 'declare_binding': declare_binding})


class ExistingLoader(SharedOwnAirRPC):
    pass


ExistingLoader.prepare = FunctionType(SharedOwnAirRPC.prepare.__code__,
    {**SharedOwnAirRPC.prepare.__globals__, 'SPECS': SPECS,
     'DELEGATES': {}, 'load_own': load_existing})


class ExistingAirRPC(FirstHistoryRPC, ExistingLoader):
    """One RPC/OwnAir implementation; six old and two existing own data rows."""
    pass


# Retain FirstHistoryRPC's original super anchor so its actual loader resolves
# to ExistingLoader in this explicit MRO. All six old inputs remain untouched.
ExistingAirRPC.__init__, DECLARATION_SOURCE_SHA256 = source_method(SharedOwnAirRPC.__init__, [
    ('binding=json.loads(raw);', 'binding=declare_binding(key,json.loads(raw));', 1),
], {'SPECS': SPECS, 'DELEGATES': {}, 'declare_binding': declare_binding})
ExistingAirRPC.prepare = FunctionType(FirstHistoryRPC.prepare.__code__,
    {**FirstHistoryRPC.prepare.__globals__, 'SPECS': SPECS},
    closure=FirstHistoryRPC.prepare.__closure__)


def start(config):
    rpc = ExistingAirRPC(config)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or set(request) != {'operation', 'data'}:
                raise ValueError('Exact existing own-body RPC envelope required')
            print(json.dumps({'result': rpc.request(request['operation'], request['data'])},
                separators=(',', ':'), allow_nan=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': str(error)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    start(sys.argv[1])
