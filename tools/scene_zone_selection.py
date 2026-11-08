"""Audit original rectangular zone selection and frame refresh routing.

Fixed source catalog only: no polygon solver, override map, audio/weather
behavior, active-device state or browser rendering is implied by this oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_environment_state import U32, verify_native as verify_environment
from scene_lighting import ZONE_SHA256, check_zone_layout, f32
from skill_attachments import decode_ftable

FORMAT = 'oc2-zone-selection-evidence-v1'
ROUTINES = {
    0x4c1ac4: (1572, '58bd782a97cf72962ce0566a27f98cb4d91b72b6bfa2d4a2520ab33a831da655'),
    0x4c88e0: (736, '13564b045c44b15957bfaa603d1dd2bc028df5473c9cf7c6a37b337da884dcb6'),
    0x4c4de4: (1548, '80f9e64b023aefbc34dde4ed9b3801f83cb84e62afac04e65e7f3a912043fc26'),
    0x4c2bcc: (296, '0af28d3d5f98cd9a1336728259be0e9ef0e5ecfa3c36cfd09bf04005fa4b4177'),
    0xa3ef00: (64, '5944cce02d6c89b8de027738065028785ba5152d18ad75a7306281b6270a9685'),
    0x4c4cd0: (276, '3c19456773082ed7e456d75c6520230d63e7f350fc99b05c1726bbb4fa458e4e'),
    0x4c0a18: (264, 'bf70ae01be2def983a099c036c58eea2ed866f65d5f7f598653717e804a9267d'),
    0x4c2238: (452, '768acfe8e26845f2d1852264c5fa5e96955a3f23d2cc80ab9c4000d0376a07a0'),
}


def verify_native(image):
    verify_environment(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Source zone selection/routing changed; retrace required')
    return {'selectionRoutines': len(ROUTINES), 'selectionInterval': 'strictly >500ms or force bit0',
            'initialRefreshAccumulator': 1000,
            'activeChangeTargetConsumer': '0x4c5b90', 'appliedToRendering': False}


def _u32(value):
    if type(value) is not int or not 0 <= value <= U32:
        raise ValueError('Expected explicit source uint32')
    return value


def _i32(value):
    value = _u32(value)
    return value-(1 << 32) if value & (1 << 31) else value


def phase_allows(phase, actor_flags=None):
    _u32(phase)
    if actor_flags is not None: _u32(actor_flags)
    if phase == 0: return True
    return 1 <= phase <= 31 and actor_flags is not None and bool(actor_flags & (1 << phase))


def rectangle_contains(row, x, z):
    if row['definition'] != 0:
        raise ValueError('Source polygon zone containment needs separate recovery')
    x, z = f32(x), f32(z)
    # 4c2bcc directly compares these source ends; no normalization or Y test.
    return f32(row['x']) <= x <= f32(row['x1']) and f32(row['z']) <= z <= f32(row['z1'])


class ZoneCatalog:
    def __init__(self, rows, map_id):
        _u32(map_id)
        self.rows = sorted(rows, key=lambda row: _u32(row['ID']))
        if len({row['ID'] for row in self.rows}) != len(self.rows):
            raise ValueError('Duplicate source zone ID')
        # Source table map traversal is ascending ID. Initial bucket uses level0,
        # not parent==-1. fly>0 is routed to another native member, not this list.
        self.base = [row for row in self.rows if row['map_id'] == map_id and row['level'] == 0
                     and _i32(row['fly']) <= 0]

    @staticmethod
    def choose(ordered_rows, x, z, actor_flags=None):
        best = None
        for row in ordered_rows:
            if not phase_allows(row['phasing_id'], actor_flags) or not rectangle_contains(row, x, z):
                continue
            priority = _u32(row['priority'])
            if best is None or priority > _u32(best['priority']): best = row
        return best

    def select(self, x, z, actor_flags=None):
        x, z = f32(x), f32(z)
        base = self.choose(self.base, x, z, actor_flags)
        # 4c88e0 checks direct parent ID without another map_id/level filter.
        children = [row for row in self.rows if base is not None and row['parent_ID'] == base['ID']]
        overlay = self.choose(children, x, z, actor_flags)
        return {'base': base, 'overlay': overlay}


class ZoneRefresh:
    """4c4cd0 routing for a stable catalog; outputs requests, not side effects."""
    def __init__(self):
        # 4c06ec writes1000 at adjusted x19+0x84 = original manager+0xb4.
        self.elapsed = 1000
        self.pair = (None, None)

    def tick(self, catalog, delta_ms, position=None, *, actor_position=None, actor_flags=None,
             force_flags=0, suspended=False, upload_enabled=False):
        _u32(delta_ms); _u32(force_flags)
        if type(suspended) is not bool or type(upload_enabled) is not bool:
            raise ValueError('Native routing gates must be supplied explicitly')
        point = position if position is not None else actor_position
        point = [0, 0, 0] if point is None else point
        if len(point) != 3: raise ValueError('Expected source XYZ position')
        point = [f32(v) for v in point]
        if actor_flags is not None: _u32(actor_flags)
        result = {'queried': False, 'pair': list(self.pair), 'targetRefreshRequested': False,
                  'queueAdvanceRequested': False, 'queueDeltaAccepted': False,
                  'uniformUploadRequested': False, 'position': point}
        if suspended: return result
        elapsed = (self.elapsed+delta_ms) & U32
        queried = _i32(elapsed) > 500 or bool(force_flags & 1)
        if queried:
            selected = catalog.select(point[0], point[2], actor_flags)
            pair = tuple(selected[name]['ID'] if selected[name] is not None else None
                         for name in ('base', 'overlay'))
            result['targetRefreshRequested'] = pair != self.pair
            result['pair'] = list(pair)
            self.pair = pair
            elapsed = 0
        self.elapsed = elapsed
        result.update(queried=queried, queueAdvanceRequested=True,
                      queueDeltaAccepted=1 <= delta_ms <= 100000,
                      uniformUploadRequested=upload_enabled)
        return result


def analyze_selection(source=DEFAULT_SOURCE):
    raw = ResourceArchive(Path(source)/'tables.bin').read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest() != ZONE_SHA256: raise ValueError('Source zone table changed')
    table = decode_ftable(raw, id_column='ID')
    check_zone_layout(table)
    catalog = ZoneCatalog(table['rows'], 5)
    queries = []
    for point in [(-2608, 187.3), (-2700, 187.3), (-2624, 251), (-2608, 251.00002),
                  (-2700, 0), (-2650, 0), (-1000, 0)]:
        pair = catalog.select(*point)
        queries.append({'point': list(point), 'pair': {k: v['ID'] if v else None for k, v in pair.items()}})
    refresh = ZoneRefresh()
    frames = [refresh.tick(catalog, dt, [-2608, 0, 187.3], upload_enabled=True) for dt in (0, 500, 1, 500, 1)]
    return {'format': FORMAT, 'sourceTableSHA256': ZONE_SHA256,
            'tutorialBaseIds': [r['ID'] for r in catalog.base],
            'tutorialDirectChildIds': [r['ID'] for r in catalog.rows if r['parent_ID'] == 194],
            'queries': queries, 'explicitFrameDeltas': [0, 500, 1, 500, 1], 'explicitFrameTrace': frames,
            'appliedToRendering': False, 'nativeActiveStateObserved': False,
            'limits': [
                'Fixed original catalog only. Native override-map replacements, dynamic table reloads and pointer identity changes are not applied.',
                'Only definition0 raw inclusive XZ rectangles are evaluated. Unsupported active polygons fail; no guessed rotation/circle/bounds normalization.',
                'Base list: matching map_id, level0 and signed fly<=0. Overlay list: direct parent matches baseID, not recursive descendants or all matching rectangles.',
                'Candidate priority compares uint32; ties keep first traversal entry. Table map traversal supplies ascending IDs, not a new tie-breaking rule.',
                'Phase0 always eligible; phases1..31 require explicit actor flag bit. Actor suspend gate9f5ea4 and upload byte250a85c are inputs, not guessed dead/quality states.',
                'Constructor refresh accumulator is1000, permitting an initial query. Later counter wraps uint32 then compares signed >500, or force bit0. Queues advance on all non-suspended frames; upload is separately gated.',
                '4c4de4 sends actual selection-change targets through4c5b90. B1.3a4c3614 is an alternate override/update entry. Their full active target branches still need comparison before rendering.',
                'Audio4c53f0/weather4c5550/notifications and side effects are not replayed. An absent selected zone does not invent defaultZone194.',
                'Explicit positions/flags/frame trace are research inputs, not device observations. Browser single-zone lookup remains unchanged.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-zone-selection/selection.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_selection(args.source)
    report['native'] = verify_native(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'queries': len(report['queries']), 'appliedToRendering': False}))


if __name__ == '__main__': main()
