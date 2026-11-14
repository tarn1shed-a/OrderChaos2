"""Original lower-area references and inside-selection consumer, read only.

The initial owner/state, LocalHero position provider, resource-list wrapper and
presentation sinks are named inspection inputs. Actual source PHY chains and
the a6337c point-containment/state branches execute unchanged. No active inside
state, companion resource, surface, or scene visibility is manufactured.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from tutorial_temple_scene_probe import DEFAULT_NATIVE, NATIVE_SHA256, ROOT, private_path

FORMAT = 'oc2-tutorial-lower-references-inside-review-v1'
OLD_MODEL = 'model/scene_generator_temple_000/god_temple02.bdae'
POINTS = [
    {'name': 'old-lower-isolated-QA', 'position': [-2611.41015625, 132.34999084472656, 185.84120178222656]},
    {'name': 'authorized-cinematic7-QA', 'position': [-2594, 135.72999572753906, -64]},
    {'name': 'previous-inside-route-QA', 'position': [-2725.3064, 108.0266, -62.3292]},
]


def inventory(sources):
    from terrain_convert import read_instances
    rows, counts = [], {}
    with tempfile.TemporaryDirectory(prefix='oc2-lower-references-') as temporary:
        for name in sorted(sources.lookup):
            if not (name.startswith('world/tutorial/items/') and name.endswith('.itm')):
                continue
            raw = sources.read(name)
            path = Path(temporary)/'source.itm'
            path.write_bytes(raw)
            for row in read_instances(path):
                kind = str(row['sourceType'])
                counts[kind] = counts.get(kind, 0)+1
                if row['sourceType'] == 15 or row['model'] == OLD_MODEL or 'god_temple06' in row['model']:
                    rows.append({**row, 'sourceITM': name, 'sourceITMSHA256': hashlib.sha256(raw).hexdigest()})
    inside = [r for r in rows if r['sourceType'] == 15]
    for row in inside:
        stem = row['model'][:-5]
        row['originalCompanion'] = stem+'_inside.bdae'
        row['companionCandidates'] = len(sources.candidates(row['originalCompanion']))
        row['insidePHYCandidates'] = len(sources.candidates(stem+'_inside.phy'))
    xml = []
    for name in ('world/tutorial/entityconfig.xml', 'world/tutorial/bdaeinstanceconfig.xml'):
        raw = sources.read(name)
        xml.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                    'bytes': len(raw), 'containsOldModelStem': b'god_temple02' in raw,
                    'containsInsideWord': b'inside' in raw.lower()})
    variants = [name for name in sorted(sources.lookup)
                if name.startswith('model/scene_generator_temple_000/god_temple02')]
    return {'allTutorialITMTypeCounts': counts, 'selectedOriginalRows': rows,
            'insideRows': inside, 'oldModelFileVariants': variants, 'tutorialXML': xml,
            'originalOldModelInsideCompanionPresent': bool(sources.candidates(OLD_MODEL[:-5]+'_inside.bdae')),
            'scope': 'Existing tutorial ITM/XML references and exact archive presence; not observed server residency'}


def native_probe_type():
    from native_inside_collision_probe import InsidePhysicsProbe
    from unicorn import UC_HOOK_CODE

    class OriginalInsideConsumer(InsidePhysicsProbe):
        VISIBILITY_SINK = 0x30000900

        def __init__(self, image):
            super().__init__(image)
            self.effects = []
            self.uc.hook_add(UC_HOOK_CODE, self.inside_sink, begin=0x34e454, end=0x34e454)
            self.uc.hook_add(UC_HOOK_CODE, self.inside_sink, begin=self.VISIBILITY_SINK, end=self.VISIBILITY_SINK)
            manager, hero, vt = self.alloc(0x100), self.alloc(0x200), self.alloc(0x100)
            self.w(vt+0x70, 'Q', self.POSITION)
            self.w(hero, 'Q', vt)
            self.w(manager+0x68, 'Q', hero)
            self.w(0x2528df8, 'Q', manager)
            self.hero_position = hero+0x118
            root, self.scene_boundary = self.alloc(0x300), self.alloc(0x100)
            self.w(root+0x1c0, 'Q', self.scene_boundary)
            self.w(0x2528db0, 'Q', root)
            self.w(0x25443e0, 'Q', 0)
            # The list wrapper is an explicit input boundary. Its head comes
            # only from the original PHY loader/selection, never fake shapes.
            self.owner, self.wrapper = self.alloc(0x28), self.alloc(0x20)
            self.w(self.owner, 'Q', 0x2423fe8)
            self.w(self.owner+0x10, 'Q', self.wrapper)
            self.model_sink, vt = self.alloc(0x180), self.alloc(0x100)
            self.w(vt+0x80, 'Q', self.VISIBILITY_SINK)
            self.w(self.model_sink, 'Q', vt)
            self.w(self.owner+0x18, 'Q', self.model_sink)

        def inside_sink(self, uc, address, size, data):
            if address == 0x34e454:
                self.effects.append({'kind': 'global-inside-request', 'value': self.get('W1')})
            else:
                self.effects.append({'kind': 'companion-visibility-request', 'visible': bool(self.get('W1')),
                                     'propagate': self.get('W2')})
            # Original callers consume no success result at these interfaces.
            self.set('PC', self.get('X30'))

        def prepare(self, sources, row):
            result = self.select(row['model'], sources, inside=True)
            head = result.pop('head')
            self.transform(head, row)
            self.w(self.wrapper+0x10, 'Q', head)
            self.w(0x25443e0, 'Q', 0)
            self.w(self.owner+0x20, 'I', 1)
            shapes = []
            for i, shape in enumerate(self.links(head)):
                flags = self.r(shape+0x104, 'I')[0]
                shapes.append({'ordinal': i, 'flags': flags,
                               'pointContainsEntry': hex(self.r(self.r(shape, 'Q')[0]+0x28, 'Q')[0])})
            return {**result, 'runtimeShapeFlags': shapes}

        def evaluate(self, point):
            self.effects = []
            self.w(self.hero_position, '3f', *point)
            # Reproduce an explicit empty active-owner boundary for each point;
            # it is not a claim about the lost Android session's state.
            self.w(0x25443e0, 'Q', 0)
            self.w(self.owner+0x20, 'I', 1)
            self.call(0xa6337c, {'X0': self.owner})
            return {'positionInput': point,
                    'selectedThisInsideOwner': self.r(0x25443e0, 'Q')[0] == self.owner,
                    'ownerStateAfter': self.r(self.owner+0x20, 'I')[0],
                    'presentationRequests': list(self.effects),
                    'initialActiveOwner': 'explicit-empty-inspection-input',
                    'initialOwnerState': 'explicit-1-inspection-input'}
    return OriginalInsideConsumer


def investigate(source, native):
    from map_loading_evidence import Sources
    from analyze_native_resources import NativeImage
    from scene_collision import decode_phy
    from bdae_skin import compose
    from tutorial_temple_scene_probe import transform
    raw_native = Path(native).read_bytes()
    if hashlib.sha256(raw_native).hexdigest() != NATIVE_SHA256:
        raise ValueError('Original library identity differs')
    image, sources = NativeImage(raw_native), Sources(source)
    records = inventory(sources)
    cases = []
    for row in records['insideRows']:
        probe = native_probe_type()(image)
        prepared = probe.prepare(sources, row)
        name = prepared['selected']
        stream = prepared['nativeStream']
        decoded = decode_phy(sources.read(name), retained_at_eof=(stream['retainedShapeCount'] if stream['descriptorError'] else None))
        # A literal original source shape center is an additional containment
        # experiment, not a player position or newly selected walkable surface.
        center = transform(compose(row['position'], row['quaternion'], row['scale']), decoded['shapes'][0]['center'])
        points = POINTS+[{'name': 'first-source-shape-center-inspection', 'position': center}]
        cases.append({'model': row['model'], 'sourceInstanceID': row['id'], 'preparedOriginalPHY': prepared,
                      'consumer': [{**probe.evaluate(p['position']), 'name': p['name']} for p in points]})
    return {'format': FORMAT, 'nativeSHA256': NATIVE_SHA256, 'inventory': records,
            'originalInsideConsumer': cases, 'sourceProofs': sources.proofs,
            'scope': {'originalPointContainmentAndStateConsumerExecuted': True,
                      'resourceWrapperAndHeroPositionAreInputs': True,
                      'presentationSinksAreNotLoadedCompanionModels': True,
                      'originalLiveInsideStateRecovered': False, 'productionChanged': False,
                      'savesChanged': False, 'sourceShapeFlagsChanged': False,
                      'originalSpawnRecovered': False}}


def main():
    from resource_packs import DEFAULT_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--native', type=Path, default=DEFAULT_NATIVE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = private_path(args.output)
    if output.exists():
        parser.error('Preserve previous source evidence')
    result = investigate(args.source, args.native)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(output), 'insideModels': len(result['originalInsideConsumer']),
                      'productionChanged': False}))


if __name__ == '__main__':
    main()
