"""Execute bounded original selection camera and character transform consumers.

The actual configuration lookup is an explicit source-file input provider.
Allocation/libc are host services. Model completion is never supplied: transform
tests use an original factory-created empty node with the same base TRS slots.
No role, server, GPU resource or original full Android frame is created.
"""
import configparser
import ctypes
import hashlib
import math
from creation_scene_camera_probe import CreationSceneCameraProbe

FORMAT = 'oc2-source-creation-stage-v1'
CONFIG_SHA256 = {
    'conf/game.conf': 'df5b69a98d0422a59bf691c09f89447cae72f4c5776517d5578e93569dcf3565',
    'conf/game_a.conf': '523f61d1659df8513fbb808186b35c1f55207d4bd99651a6deb4567831995742',
    'conf/game_w.conf': 'a07fdee8b2474afce4dfa1b4a60be5bd59869fe4d993f1b981e16dfc09493b77',
}
PINS = {
    0xa5a008: (44, '38e1c09649d89986c073d217baa8d5543c4368cee59adfc9de70586c0cf02a5f'),
    0x32969c: (44, 'df291d0030d0687c0dac8dbcd20df49968232720d8e813d515769666ce343fde'),
    0x541424: (32, 'd8d7637f4738bf7f7e5983fe6333ad63fb12c0dc00081200a15bcdf56f9e7185'),
    0x540618: (964, '5fba9c9211829efd2014b957b0d19277789f9eaafd838972dfa31693bd5e9bb3'),
    0x329ce0: (116, 'f26e8a1120dcc4a57c67667a4507cd2cfe445ec13e4d7624f58091ceccc7e70c'),
    0x329db8: (48, '1f2b503b28f798190420f38fc025ec1698dee0c3c6b3b625951b0dc625a0bf2d'),
    0x329d74: (68, '54dd387af35105b21d34035e8ec52b66e26cc3b9ce84c969cd15aec87b8d9003'),
    0x329de8: (28, '28fe8cb6a4fa91b613c0a5e6195a0c067591ad15824f45d846525bb0b0031e5d'),
    0x329700: (720, '956a4e1d1166e380a5e6ae95c6f2ab62f7e2876e36f075ee667aabbdb00f94ab'),
    0x53ca0c: (2248, '01493e438fa22bedbdaa97e6d35b3394411f02630ba18171227a52b4c985b649'),
    0x541444: (4680, '6076f9498f46eef35474a43c7f77c6288d2fea6e10302348173319aae8b868bf'),
    0xa792c4: (316, '9054e5a35aa7790c22c2af4aab4dcff66b704a02faefb0793ce5041e20f867a2'),
    0x31f178: (1156, 'a4451ad9235004e34935a1d1e8e8b27849ffb09378574d9663cdd977fa064da5'),
    0x3378c8: (144, 'd66ecbf122720f95739fc5d9e8bab8117a4893f1d8a3fb6708932b94f2e83ca1'),
    0x337a54: (160, 'bd67f8706208a02af3c5693c3d76a30acf672e721085ceffaad402e69c7990a1'),
    0x337b68: (44, '17f507aef006f69f89dcbd2275dabc7e5ff72b9cef4802da3019629c3f5fb182'),
    0x337b94: (144, '63b6989590e6ad3a58fbceb68a96539c93145f040b24fbb4c1c5ad5d0f1a6d8b'),
    0x11dd298: (328, 'c3734cbb0a515a4326dc59e85f1ab1ab014f542dee649096975823d5d1f235bc'),
}
TRS_SLOTS = {0x150: 0x1363f10, 0x158: 0x1363f18, 0x160: 0x1363f84,
             0x168: 0x1363f8c, 0x170: 0x136400c, 0x178: 0x1364014}


def source_splash(sources, name='conf/game.conf'):
    raw = sources.read(name)
    if name not in CONFIG_SHA256 or hashlib.sha256(raw).hexdigest() != CONFIG_SHA256[name]:
        raise ValueError('Original splash configuration differs')
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read_string(raw.decode('utf-8-sig'))
    return dict(parser['splash'])


def source_race_panel(sources):
    from standard_abc import parse_standard_abc, extract_standard_abc
    from optimized_abc import named_method
    raw = sources.read('ui/Flash/CharacterChooseRace.swf')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != '14af412f5c44f4a91d1a14bed9273cfc04128674f4788472f100288eca676940':
        raise ValueError('Original race panel differs')
    abc = parse_standard_abc(extract_standard_abc(raw))
    cls, = [c for c in abc['classes'] if c['name'] == 'CharacterChooseRace']
    trait, = [t for t in cls['staticTraits'] if t['name'] == 'ENTER_RACE']
    value = abc['ints'][trait['value']] if trait.get('valueKind') == 3 else None
    method = named_method(abc, 'CharacterChooseRace', 'onShow')
    ops = [(i['op'], i['args']) for i in method['instructions']]
    if value != 0 or ('getlex', ['ENTER_RACE']) not in ops or ('pushstring', ['Character_EnterPanel']) not in ops:
        raise ValueError('Original race panel callback differs')
    from optimized_abc import disassemble
    component, = [c for c in abc['classes'] if c['name'] == 'gluic.components.ui::UIComponent']
    body = abc['bodies'][component['iinit']]
    if hashlib.sha256(body['code']).hexdigest() != '24e6fc6ed3035cf69be0c9e62bb4cd945ce775f6934439b6a47d606b23279df6':
        raise ValueError('Original UIComponent constructor differs')
    instructions = disassemble(body['code'], abc, body['exceptions'])
    constructor_ops = [(i['op'], i['args']) for i in instructions]
    if ('pushstring', ['mc_bounds']) not in constructor_ops or ('setproperty', ['visible']) not in constructor_ops:
        raise ValueError('Original authoring bounds visibility missing')
    parents = {c['name']: c['super'] for c in abc['classes']}
    chain = ['txt_select_class']
    while chain[-1] != 'gluic.components.ui::UIComponent':
        if len(chain) > 5 or chain[-1] not in parents: raise ValueError('Original description component base missing')
        chain.append(parents[chain[-1]])
    return {'sourceSHA256': digest, 'onShowSHA256': method['codeSHA256'],
            'boundsConstructorSHA256': hashlib.sha256(body['code']).hexdigest(),
            'descriptionInheritance': chain,
            'screen': 'CharacterChooseRace', 'callback': 'Character_EnterPanel', 'panel': value}


class CreationStageProbe(CreationSceneCameraProbe):
    def __init__(self, image, splash):
        for at, (size, digest) in PINS.items():
            if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
                raise ValueError('Original creation stage routine differs')
        self.gl_uniforms = []
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.splash = dict(splash); self.queries = []; self.next_token = None
        self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=0xa78ffc, end=0xa78ffc)
        self.game = self.alloc(0x400); self.world_context = self.alloc(0x60)
        self.w(0x2528db0, 'Q', self.game); self.w(self.game+0x1c0, 'Q', self.renderer)
        self.w(self.renderer+0x30, 'Q', self.world_context)
        # Original lazy producer allocates the controller and creates its real
        # camera/light using the registered original factory. No node reply hook.
        self.call(0xa5a008, {'X0': self.world_context}, limit=100000)
        self.controller = self.r(self.world_context+0x38, 'Q')[0]
        self.camera = self.r(self.controller+0x18, 'Q')[0]
        if not self.camera or self.camera != self.r(self.scene+0x238, 'Q')[0]:
            raise ValueError('Original primary camera was not attached')
        self.owner = self.alloc(0x200); self.w(self.owner+0x98, 'i', -1)
        self.w(0x2528e28, 'Q', self.alloc(16))  # Lookup provider context only.
        eye = [float(v) for v in self.splash['cameraposition'].split(',')]
        delta = [float(v) for v in self.splash['cameratarget'].split(',')]
        if len(eye) != 3 or len(delta) != 3 or not all(math.isfinite(v) for v in eye+delta):
            raise ValueError('Original configured camera vector missing')
        # Initial configured values are explicit inputs; original setters and
        # all later group parsing/relative-target addition execute below.
        target = [self._f32(self._f32(a)+self._f32(b)) for a, b in zip(eye, delta)]
        self.w(self.owner+0x9c, '6f', *eye, *target)
        self.set_pose(eye, target)

    @staticmethod
    def _f32(v):
        import struct
        return struct.unpack('<f', struct.pack('<f', v))[0]

    def string(self, raw):
        p = self.alloc(25+len(raw)); self.w(p, '3Q', len(raw), len(raw), 1000)
        self.uc.mem_write(p+24, raw+b'\0'); return p+24

    def hook(self, uc, at, size, data):
        name = self.imports.get(at)
        if at == 0xa78ffc:
            key = self.cstr(self.r(self.get('X2'), 'Q')[0]).decode()
            section = self.cstr(self.r(self.get('X1'), 'Q')[0]).decode()
            if section != 'splash': raise ValueError('Unverified configuration section')
            fallback = self.cstr(self.r(self.get('X3'), 'Q')[0]).decode()
            value = self.splash.get(key.lower(), fallback)
            self.queries.append({'section': section, 'key': key, 'value': value})
            self.w(self.get('X8'), 'Q', self.string(value.encode()))
        elif name == 'strtol':
            raw = self.cstr(self.get('X0')); buf = ctypes.create_string_buffer(raw)
            end = ctypes.c_void_p(); fn = ctypes.CDLL(None).strtol
            fn.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int]
            fn.restype = ctypes.c_long
            result = fn(buf, ctypes.byref(end), self.get('W2'))
            self.w(self.get('X1'), 'Q', self.get('X0')+end.value-ctypes.addressof(buf))
            self.set('X0', result & ((1 << 64)-1))
        elif name == 'atof': self.df('D0', float(self.cstr(self.get('X0'))))
        elif name == 'sprintf':
            text = self.cstr(self.get('X1'))
            if b'%' in text: raise ValueError('Only original numeric-vector copy format is hosted')
            self.uc.mem_write(self.get('X0'), text+b'\0'); self.set('W0', len(text))
        elif name == 'strtok':
            p = self.get('X0') or self.next_token; delimiters = set(self.cstr(self.get('X1')))
            if p:
                while self.r(p, 'B')[0] in delimiters: p += 1
                if not self.r(p, 'B')[0]: p = 0; self.next_token = None
                else:
                    end = p
                    while self.r(end, 'B')[0] and self.r(end, 'B')[0] not in delimiters: end += 1
                    if self.r(end, 'B')[0]: self.w(end, 'B', 0); self.next_token = end+1
                    else: self.next_token = None
            self.set('X0', p or 0)
        elif name == 'glUniform3fv':
            # Record submitted CPU values only. This void sink claims no GL
            # context, success, shader binding, resource readiness or frame.
            self.gl_uniforms.append(list(self.r(self.get('X2'), '3f')))
        else: return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def set_pose(self, eye, target):
        a, b = self.alloc(16), self.alloc(16); self.w(a, '3f', *eye); self.w(b, '3f', *target)
        self.call(0x329db8, {'X0': self.controller, 'X1': b})
        self.call(0x329ce0, {'X0': self.controller, 'X1': a})

    def pose(self):
        a, b = self.alloc(16), self.alloc(16)
        self.call(0x329d74, {'X0': self.controller, 'X1': a})
        self.call(0x329de8, {'X0': self.controller, 'X1': b})
        return {'eye': list(self.r(a, '3f')), 'target': list(self.r(b, '3f'))}

    def view(self):
        self.call(0x12bb180, {'X0': self.camera}, limit=20000)
        return list(self.r(self.camera+0x250, '16f'))

    def light_direction(self):
        node = self.r(self.controller+0x28, 'Q')[0]
        light = self.r(self.controller+0x20, 'Q')[0]
        self.call(0x1364674, {'X0': node}, limit=20000)
        device, world, box = self.alloc(0x3000), self.alloc(64), self.alloc(24)
        self.call(0x148cb40, {'X0': device+0x2070})
        self.w(world, '16f', 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        self.call(0x1413868, {'X0': device, 'W1': 2, 'X2': world, 'X3': box, 'W4': 0})
        declaration = self.alloc(24); self.w(declaration+8, 'I', 7)
        self.w(declaration+16, 'H', 20 | (10 << 8)); self.gl_uniforms = []
        self.call(0x1414888, {'X0': device, 'X1': light, 'X2': declaration}, limit=40000)
        if len(self.gl_uniforms) != 1: raise ValueError('Original direction submission differs')
        return {'direction': self.gl_uniforms[0], 'sourceLightType': self.r(light+0x70, 'H')[0],
                'originalControllerLight': True, 'identityModelInput': True,
                'sourceWorldTransformUpdateExecuted': True, 'originalGPUObserved': False}

    def select_camera(self, mode, race=0, *, panel=False):
        if type(race) is not int or not 0 <= race <= 4 or type(mode) is not int:
            raise ValueError('Explicit original race/group input required')
        self.w(self.owner+0x5c, 'i', race)
        self.call(0x541424 if panel else 0x541444,
                  {'X0': self.owner, 'W1': mode & 0xffffffff}, limit=50000)
        return {'group': self.r(self.owner+0x98, 'i')[0],
                'eye': list(self.r(self.owner+0xcc, '3f')),
                'target': list(self.r(self.owner+0xd8, '3f')),
                'step': list(self.r(self.owner+0xb4, '6f')),
                'moving': bool(self.r(self.owner+0xe4, 'B')[0])}

    def step_camera(self):
        from unicorn import UC_HOOK_CODE
        events = []
        def boundary(uc, at, size, data):
            events.append('debug-output' if at == 0x5407bc else 'camera-block-end')
            self.set('PC', self.EXIT)
        hooks = [self.uc.hook_add(UC_HOOK_CODE, boundary, begin=a, end=a)
                 for a in (0x5407bc, 0x5409c4)]
        # Only the camera update block. The preceding UI refresh, following
        # ostream diagnostic and the rest of the client frame are not executed.
        try: self.call(0x540680, {'X19': self.owner, 'X21': 0x2533000}, limit=20000)
        finally:
            for h in hooks: self.uc.hook_del(h)
        return {**self.pose(), 'moving': bool(self.r(self.owner+0xe4, 'B')[0]), 'boundaries': events}

    def transform(self, with_node=True):
        from unicorn import UC_HOOK_CODE
        actor = self.alloc(0xe20); self.call(0x31f178, {'X0': actor}, limit=30000)
        node = None
        if with_node:
            name, result = self.alloc(8), self.alloc(8); self.uc.mem_write(name, b'empty\0')
            self.call(0x12f9df8, {'X0': self.scene, 'X1': name, 'X8': result}, limit=40000)
            node = self.r(result, 'Q')[0]; vptr = self.r(node, 'Q')[0]
            for slot, expected in TRS_SLOTS.items():
                if self.r(vptr+slot, 'Q')[0] != expected or self.r(0x24604d8+slot, 'Q')[0] != expected:
                    raise ValueError('Original model/empty base transform dispatch differs')
            self.w(actor+8, 'Q', node)  # Explicit transform-only input; NOT model completion.
        pair = self.alloc(16); self.w(pair, 'Q', actor); completed = []
        def stop(uc, at, size, data): completed.append(at); self.set('PC', self.EXIT)
        hook = self.uc.hook_add(UC_HOOK_CODE, stop, begin=0x53ce58, end=0x53ce58)
        try:
            self.call(0x53cb68, {'X19': self.owner, 'X20': pair, 'X29': self.STACK+0x1c0}, limit=50000)
        finally: self.uc.hook_del(hook)
        if completed != [0x53ce58]: raise ValueError('Original transform block not completed')
        return {'originalTransformBlockExecuted': True, 'originalModelCompleted': False,
                'nodeProvided': with_node, 'wrapperNode': self.r(actor+8, 'Q')[0],
                'inputEuler': list(self.r(self.owner+0xe8, '3f')),
                'freshModelEyeColor': list(self.r(actor+0xdd8, '3f')),
                'position': list(self.r(node+0xa8, '3f')) if node else None,
                'quaternion': list(self.r(node+0xb4, '4f')) if node else None,
                'scale': list(self.r(node+0xc4, '3f')) if node else None,
                'matrix': list(self.r(node+0x28, '16f')) if node else None}


def main():
    import argparse
    import json
    from pathlib import Path
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('analysis/raw/creation-stage-transform-20261115/source-stage.json'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    image = NativeImage((root/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes())
    configs = {name: source_splash(Sources(DEFAULT_SOURCE), name) for name in CONFIG_SHA256}
    if any(configs[name] != configs['conf/game.conf'] for name in configs):
        # Comparison is scoped to consumed inputs below, not unrelated splash effects.
        keys = ['characterposition', 'characterrotation', 'characterscale', 'cameraposition', 'cameratarget', 'racecamerapos', 'racecameratar']
        if any(any(configs[name][key] != configs['conf/game.conf'][key] for key in keys) for name in configs):
            raise ValueError('Original platform creation transform inputs differ')
    probe = CreationStageProbe(image, configs['conf/game.conf'])
    initial = probe.pose(); constructor = probe.parameters()
    transform = probe.transform(); camera_groups = []
    for race in range(5):
        for mode in range(5):
            probe.w(probe.owner+0x98, 'i', -1); probe.set_pose(initial['eye'], initial['target'])
            selected = probe.select_camera(mode, race); frames = []
            for _ in range(40):
                frames.append({**probe.step_camera(), 'view': probe.view()})
                if not frames[-1]['moving']: break
            if frames[-1]['moving']: raise ValueError('Original camera did not settle within bounded updates')
            camera_groups.append({'race': race, **selected, 'frames': frames})
    report = {'format': FORMAT, 'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
              'configSHA256': CONFIG_SHA256, 'transform': transform,
              'primaryConstructor': constructor, 'configuredInitialPose': initial,
              'fullViewport': probe.viewport([0, 0, 1136, 640], 640),
              'projection': probe.projection(), 'cameraGroups': camera_groups,
              'sourceControllerLight': probe.light_direction(),
              'panelGroups': list(probe.r(0x1e15bb0, '8i')),
              'racePanel': source_race_panel(Sources(DEFAULT_SOURCE)),
              'cameraStepFraction': probe.r(0x1df7ab8, 'f')[0],
              'cameraDistanceSquaredThreshold': probe.r(0x1df7be8, 'd')[0],
              'scope': {'originalCPU': True, 'modelReadyProved': False, 'originalGPUObserved': False,
                        'originalFullFrameExecuted': False, 'viewportIsExplicitWebInput': True,
                        'completeOriginalCreationRestored': False}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'output': str(args.output), 'cameraCases': len(camera_groups),
                      'sourceTransformExecuted': True, 'modelReadyProved': False}))


if __name__ == '__main__': main()
