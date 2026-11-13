"""Original dynamic-shape query checks for tutorial lift 739.

This is an isolated CPU inspection, not an autonomous elevator or recovered
server state. The host supplies one explicit loaded-shape container and pose;
the original tree iterators, PHY transform and collision queries execute.
"""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from map_loading_evidence import Sources
from native_phy_stream import NativePHYStreamPhysics
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output


LIFT_PHY = 'model/scene_generator_temple_000/god_temple01_inside02.phy'
LIFT_PHY_SHA256 = '86e461a8d5cf567cc31724edbe04c934def699cee060c5f097964762c6a5d080'
ROUTINES = {
    0xa53d6c: (4944, 'ddd6a85efdd83740eefc72c3c16384b723db847941806f11c694745addb2244e'),
    0x903080: (1612, '3453e0a991c6a38ab7130c907b9af73ea28b6d5e0c05a55c111c822a48cdeeb2'),
    0x90c348: (476, '0c86a7a7e904efc973c26fd7d9515a7d3188b10082866fddf412b10e2f85494f'),
    0xa091d4: (864, '6dc548e933b1d99ccc8111a009f30a19872b5cfd9b7e4348fc58822863b3ca41'),
    0xa3f2cc: (36, 'fc89e47351dc9303f2a8c560a8c773e564eac0688f332b773f9697aee230e73e'),
    0xa3f2f0: (80, '8eb8429bdbfa9748514dd124ec5c6fc7f345fe7015528626ae26caf6f1aa7fd7'),
    0x1dcb688: (96, 'df52b867b51bdc3a4327efc8646c41d5830be6e0cf6bd65a4ed412dd55d0ffde'),
    0x363d30: (740, 'acd29a98443b90dd10177978f4ffa4d1ab9df5ff85d76d9c0d099914db60dfcb'),
    0xa2d56c: (60, 'c987c9866bd2cae358d846472466fda1cee779281c85f5bcab4bcc6ecfa52ea3'),
    0xa3f1bc: (272, '0032365acd07b4119d1ef6bb79d116d44ad11d64bef81daa2ceeeb964288af6c'),
    0xa749a4: (544, '307f5c83fc9f10e71579d094a8eb20adddd52983474bfa10e030215f960d3a4c'),
}


class DynamicShapeProbe(NativePHYStreamPhysics):
    def __init__(self, image):
        from unicorn import UC_HOOK_CODE
        for address, (size, digest) in ROUTINES.items():
            if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
                raise ValueError('Original lift/query/passenger routine differs')
        super().__init__(image)
        self.slice_stop = None
        for address in (0xa54cd4, 0x9034bc):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=address, end=address)
        self.dynamic_managers = set()
        self.initialized_managers = set()
        self.dynamic_head = 0
        self.manager = self.alloc(0x200)
        self.dynamic_managers.add(self.manager)
        self.install_dynamic(0)
        self.w(0x2528df8, 'Q', self.manager)

    def hook(self, uc, address, size, data):
        if address == self.slice_stop:
            self.set('PC', self.EXIT)
            return
        if address in (0xa3f2cc, 0xa3f2f0):
            return  # Execute the actual iterator, not SourcePhysics's empty hook.
        return super().hook(uc, address, size, data)

    def install_dynamic(self, head):
        """Use original registration, with an explicit inspection key and PHY.

        Empty header layout is a host container input. a2d56c/a3f1bc and the
        original tree helpers create/update nodes. Key 739 is a fixture key,
        not a recovered server GUID. No spawn/admission/removal is inferred.
        """
        if not head and self.dynamic_head:
            raise ValueError('Dynamic removal has not been restored')
        self.dynamic_head = head
        for manager in self.dynamic_managers:
            self.initialize_registry(manager)
            if head:
                self.register_dynamic(739, head, manager)

    def initialize_registry(self, manager):
        if manager not in self.initialized_managers:
            sentinel = manager + 0x78
            self.w(sentinel, 'Q', 0)
            self.w(sentinel + 8, '3Q', 0, sentinel, sentinel)
            self.w(manager + 0x98, 'Q', 0)
            self.w(manager + 0xa0, 'Q', sentinel)
            self.initialized_managers.add(manager)

    def register_dynamic(self, fixture_key, head, manager=None):
        manager = self.manager if manager is None else manager
        self.initialize_registry(manager)
        self.call(0xa2d56c, {'X0': manager, 'X1': fixture_key, 'X2': head})

    def actor(self, identity, position):
        actor = super().actor(identity, position)
        self.dynamic_managers.add(actor['manager'])
        self.install_dynamic(self.dynamic_head)
        return actor

    def enumerate_shapes(self, manager=None):
        manager = self.manager if manager is None else manager
        result = []
        value = self.call(0xa3f2cc, {'X0': manager})
        while value:
            if value in result or len(result) >= 4096:
                raise ValueError('Original dynamic iterator did not terminate')
            result.append(value)
            value = self.call(0xa3f2f0, {'X0': manager})
        if self.r(manager + 0xa0, 'Q')[0] != manager + 0x78:
            raise ValueError('Original iterator did not end at its sentinel')
        return result

    def lift_pose(self, raw, position, owner=0):
        if hashlib.sha256(raw).hexdigest() != LIFT_PHY_SHA256:
            raise ValueError('Original lift PHY differs')
        head = self.read_phy(raw, LIFT_PHY)
        self.transform(head, {'id': 739, 'position': list(position),
                             'quaternion': [0, 0, 0, 1], 'scale': [1, 1, 1]})
        self.w(head + 0x18, 'Q', owner)
        self.install_dynamic(head)
        return head

    def ground_excluding(self, x, z, top, owner=0):
        normal = self.scratch + 0x2400
        state = normal + 0x100
        result = normal + 0x200
        self.uc.mem_write(normal, bytes(12))
        self.uc.mem_write(state, bytes(12))
        self.uc.mem_write(result, bytes(32))
        self.call(0xa8752c, {'X0': 0, 'W1': 0, 'X2': normal, 'X3': owner,
                            'W4': 0, 'W5': 0, 'X6': state, 'X7': result},
                  {'S0': x, 'S1': z, 'S2': top})
        shape = self.r(result, 'Q')[0]
        return {'height': self.gf('S0'), 'normal': list(self.r(normal, '3f')),
                'sourceObjectInspectionId': self.objects.get(shape)}

    def original_slice(self, begin, end, registers):
        """Execute a pinned straight-line source fragment, not its whole frame."""
        if (begin, end) not in ((0xa54c34, 0xa54cd4), (0x903450, 0x9034bc)):
            raise ValueError('Unverified source fragment')
        self.slice_stop = end
        try:
            self.call(begin, registers)
        finally:
            self.slice_stop = None

    def mark_passenger(self, actor, head):
        """Original bounds check and +ca0 write, for an explicit type14 fixture."""
        fixture = self.alloc(0xd00)
        self.w(fixture + 0x50, 'Q', head)
        self.w(fixture + 0xc88, 'I', 14)
        self.w(self.r(actor['address'], 'Q')[0] + 0x70, 'Q', 0x904f7c)
        self.w(actor['manager'] + 0x68, 'Q', actor['address'])
        self.w(0x2528df8, 'Q', actor['manager'])
        self.original_slice(0xa54c34, 0xa54cd4,
                            {'X19': fixture, 'X22': 0x2528000})
        return self.r(actor['address'] + 0xca0, 'B')[0]

    def passenger_support_fragment(self, actor, *, numeric_gate):
        """Original post-movement +ca0 branch and virtual128 ground resample.

        The two numeric settings comparisons in 90c348 are explicit fixture
        inputs. They are not inferred active map/session values.
        """
        root = self.r(0x2528db0, 'Q')[0]
        settings = self.alloc(0x100); state = self.alloc(0x100)
        self.w(root + 0x178, 'Q', settings)
        self.w(settings + 0x58, 'Q', state)
        self.w(state + 0x58, 'I', 1 if numeric_gate else 0)
        self.w(state + 0x40, 'I', 4)
        address = actor['address']; vtable = self.r(address, 'Q')[0]
        self.w(vtable + 0x70, 'Q', 0x904f7c)
        self.w(vtable + 0x128, 'Q', 0x90c348)
        self.w(0x2528df8, 'Q', actor['manager'])
        self.original_slice(0x903450, 0x9034bc, {'X19': address})
        return {'position': list(self.r(address + 0x118, '3f')),
                'pendingPosition': list(self.r(address + 0x1ac, '3f')),
                'passengerFlagAfter': self.r(address + 0xca0, 'B')[0],
                'supportCacheValid': self.r(address + 0xc00, 'B')[0]}


def load_fixture(config):
    config = local_output(config)
    cfg = json.loads(config.read_text())
    if cfg['nativeSHA256'] != NATIVE_SHA256:
        raise ValueError('Original native build differs')
    engine = DynamicShapeProbe(NativeImage(Path(cfg['library']).read_bytes()))
    terrain = json.loads(Path(cfg['terrain']).read_text())
    profile = json.loads(Path(cfg['collision']).read_text())
    flags = {tuple(t['tile']): t['runtimeFlags'] for t in
             json.loads(Path(cfg['terrainLighting']).read_text())['tiles']}

    def read(name):
        row = cfg['sourceFiles'][name]; raw = Path(row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Original PHY input differs')
        return raw

    loaded = engine.load_world(terrain, profile, read, flags)
    return engine, loaded


def probe(config, source=DEFAULT_SOURCE):
    from tutorial_quest_chain import audit
    chain = audit(source)
    spawn, = [r for r in chain['elevatorSpawns'] if r['id'] == 739]
    proto, = [r for r in chain['objectPrototypes'] if r['entry'] == spawn['Entry']]
    display, = [r for r in chain['objectDisplays'] if r['entry'] == proto['DisplayID']]
    if proto['Type'] != 14 or display['strPath'] != LIFT_PHY.replace('.phy','.bdae'):
        raise ValueError('Different source elevator type/model: retrace before inspection')
    engine, loaded = load_fixture(config)
    sources = Sources(source); raw = sources.read(LIFT_PHY)
    x, y, z = [spawn[k] for k in ('position_x','position_y','position_z')]
    baseline = engine.ground_excluding(x, z, 150)
    owner = engine.alloc(0x100)
    head = engine.lift_pose(raw, [x, y, z], owner)
    upper = engine.ground_excluding(x, z, 150)
    excluded = engine.ground_excluding(x, z, 150, owner)
    engine.w(head + 0x118, 'B', 1)
    hidden = engine.ground_excluding(x, z, 150)
    engine.w(head + 0x118, 'B', 0)
    initial = [x, upper['height'], z]
    standing = [engine.actor_tick('lift-standing-inspection', initial, [0, 0], 50)
                for _ in range(20)]
    actor = engine.actors['lift-standing-inspection']
    raised_head = engine.lift_pose(raw, [x, y + .25, z], owner)
    marked = engine.mark_passenger(actor, raised_head)
    passenger = engine.passenger_support_fragment(actor, numeric_gate=True)
    engine.lift_pose(raw, [x, spawn['elevator_over_y'], z], owner)
    engine.w(0x2528df8, 'Q', engine.manager)
    lower = engine.ground_excluding(x, z, 150)
    return {'format': 'oc2-tutorial-lift-dynamic-query-v1',
            'loaded': {k:v for k,v in loaded.items() if k!='instanceIds'},
            'sourceSpawn': spawn, 'sourcePrototype': proto, 'sourceDisplay': display,
            'sourceTableProofs': {n:r for n,r in chain['sourceProofs'].items()
                                  if 'staticobject_' in n},
            'configSHA256': hashlib.sha256(Path(config).read_bytes()).hexdigest(),
            'source': sources.proofs[LIFT_PHY], 'baseline': baseline,
            'upperPose': upper, 'lowerPose': lower,
            'ownerExcluded': excluded, 'hiddenShape': hidden,
            'nativeEnumerationCount': len(engine.enumerate_shapes()),
            'standingFrames': standing,
            'passengerFragment': {'flagBefore': marked, **passenger},
            'scope': ['Original tree enumeration, collision query and PHY transform execute.',
                      'Original registration builds the tree from an explicit fixture key/PHY.',
                      'Host supplies diagnostic poses; fixture key739 is not an original server GUID.',
                      'Identity rotation/unit scale are query fixtures, not recovered object transforms.',
                      'Passenger marking and resampling fragments execute with explicit numeric state gates.',
                      'Source packet timing, has_physics/admission, motion task and complete frame update remain absent.',
                      'This does not start an elevator or change the game/server/save.'],
            'routeVerified': False, 'productionChanged': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--config', type=Path, required=True)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args(); output = local_output(args.output)
    if output.exists():
        cli.error('Preserve existing research output; choose a fresh path')
    report = probe(args.config, args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'upper': report['upperPose']['height'],
                      'lower': report['lowerPose']['height'], 'routeVerified': False}))
