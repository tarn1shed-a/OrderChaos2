"""Bounded original quest227 crocodile animation and range consumers.

This executes the pinned client's property construction, sampler and clock.
It does not extend the frozen float-only decoder, invent a byte codec, attach
a game actor, approve combat/loot, or change any save. Camera properties are
sampled separately; their original camera attachment is not a skin bone.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from bdae_animation import BDAEAnimation
from bdae_convert import BDAE

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SHA = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
MODEL = 'model/npc/creature/beast/crocodile/crocodile.bdae'
ANIMATION = 'model/npc/creature/beast/crocodile/anim/animations.bdae'
SOURCE_SHAS = {
    MODEL: '7fbf80b869a1b75a11cc29e8151a3cf4318567813d27bd84271c3cf5099593fd',
    ANIMATION: '613cbe7a7fe3aaa5ece10e00f8b18280ac20da77f6cdd67ae9a450bc44d21f9b',
}


def probe_type():
    from bdae_character import aliases
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
    from tutorial_npc_binding_probe import BindingProbe

    class CrocodileProbe(BindingProbe):
        def __init__(self, image, skin):
            from unicorn import UC_HOOK_CODE
            NativeBresWorldBoundsProbe.__init__(self, image)
            self.image = image
            self.skin = skin
            self.sample_calls = []
            self.sampling_channel = None
            self.sampler_entries = 0
            self.source_nodes = aliases(skin['nodes'])
            bone_nodes = {b['node'] for b in skin['bones']}
            self.source_bone_targets = {name for name, index in self.source_nodes.items()
                                        if index in bone_nodes}
            for at in set([0x29f300, 0x2a2430, 0x3c0fe8, *image.imports]):
                if at not in (0x29e010, 0x29e3c0, 0x2a2120, 0x29eaf0, 0x29f0f0,
                              0x29fbb0, 0x29f220, 0x2a0180, 0x2a1030, 0x2a1e50, 0x29f5b0):
                    self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)
            for at in (0x1109aec, 0x1109b7c, 0x1109ba0):
                self.uc.hook_add(UC_HOOK_CODE, self.observe_sample, begin=at, end=at)

        def observe_sample(self, uc, at, size, data):
            ch = self.sampling_channel
            if at == 0x1109aec:
                self.sampler_entries += 1
                return
            if ch is not None and ch['node'] == 'Camera01-node':
                self.sample_calls.append({'node': ch['node'], 'propertyType': ch['type'],
                                          'callsite': hex(at), 'callee': hex(self.get('X8'))})

        def prepare_animation(self, reader):
            self.regs()
            self.uc.emu_start(0x119bf2c, self.EXIT, count=500000)
            if self.get('PC') != self.EXIT:
                raise ValueError('Original compatibility bootstrap exceeded bound')
            self.regs()
            self.set('X20', 0x25da730)
            self.run(0x2ce3d0, 0x2ce3ec)
            loaded = self.load(reader.b)
            info = loaded['info']
            pair = self.resource_pair(loaded)
            manager = self.alloc(0x100)
            self.invoke(0x1103d9c, X0=manager)
            self.invoke(0x1106f94, X0=manager, X1=pair)
            self.invoke(0x110749c, X0=manager)
            count = self.r(manager + 0x40, 'I')[0]
            source_count, _ = reader.section(64)
            if count != source_count or count != 44:
                raise ValueError('Original crocodile property selection differs')
            start = self.r(manager + 0x98, 'Q')[0]
            objects = self.r(manager + 0x28, 'Q')[0]
            targets = self.r(manager + 0x10, 'Q')[0]
            self.channels = []
            for i in range(count):
                kind, record = self.r(start + i * 16, '2Q')
                target = self.r(targets + i * 8, 'Q')[0]
                name = self.c(self.r(target, 'Q')[0]).decode()
                typ = self.r(target + 8, 'I')[0]
                if kind != 2 or typ not in (1, 5):
                    raise ValueError('Uncovered original crocodile property')
                if name not in self.source_nodes:
                    raise ValueError('Unexpected unmapped original target')
                self.channels.append({'record': record, 'node': name, 'type': typ,
                                      'object': self.r(objects + i * 8, 'Q')[0],
                                      'sourceSkinBone': name in self.source_bone_targets})
            self.segment_table = info + 0x4c + self.r(info + 0x4c, 'i')[0]
            # The frozen reader rejects the whole bundle because its first segment
            # starts with 0xfffffff9. This bounded idle experiment uses only the
            # positive segments covering idle; it does not redefine that field.
            table = reader.rel(reader.info + 76)
            segment_count, width = reader.unpack('2I', table)
            if (segment_count, width) != (7, 4):
                raise ValueError('Original crocodile segment table differs')
            self.segments, self.segment_cache = [], {}
            for i in range(segment_count):
                rec = table + 8 + i * 40
                start, end, reserved, flags = reader.unpack('4I', rec)
                data, size = reader.unpack('2Q', rec + 16)
                reader.at(data, size)
                if reserved or flags != 0x01000000:
                    raise ValueError('Original segment descriptor differs')
                self.segments.append({'startBits': start, 'endBits': end,
                                      'positiveBounds': 0 <= start < end < 0x80000000})

        def sample_case(self, absolute_ms):
            indexes = [i for i, s in enumerate(self.segments)
                       if s['positiveBounds'] and s['startBits'] <= absolute_ms <= s['endBits']]
            if not indexes:
                raise ValueError('Original segment does not cover sample')
            index = indexes[-1]
            if index not in self.segment_cache:
                obj, vt = self.alloc(16), self.alloc(32)
                self.w(obj, 'Q', vt)
                self.w(vt + 0x10, 'Q', 0x30000108)
                self.segment_cache[index] = self.invoke(
                    0x117c40c, X0=self.segment_table + 16 + index * 40, X1=obj, W2=0)
            samples = []
            for ch in self.channels:
                context, state = self.alloc(24), self.alloc(16)
                output, sample_index = self.alloc(16), self.alloc(4)
                self.w(context, '3Q', ch['record'], self.segment_cache[index], state)
                self.sampling_channel = ch
                self.invoke(0x1109aec, time=absolute_ms, X0=ch['object'], X1=context,
                            X2=output, X3=sample_index, W4=1)
                self.sampling_channel = None
                values = list(self.r(output, '4f' if ch['type'] == 5 else '3f'))
                if not all(math.isfinite(v) for v in values):
                    raise ValueError('Non-finite native sample')
                samples.append({k: ch[k] for k in ('node', 'type', 'sourceSkinBone')} |
                               {'value': values})
            return {'absoluteMs': absolute_ms, 'samples': samples,
                    'settersOrPaletteExecuted': False}

        def clock_case(self, reader, record):
            clock, table = self.alloc(0x70), self.alloc(32)
            self.invoke(0x1195f3c, X0=clock)
            self.w(table, 'Ii', 1, 4)
            # Exact original range, including original signed bit patterns.
            self.uc.mem_write(table + 8, reader.b[record:record + 24])
            self.invoke(0x1196824, X0=clock, X1=table)
            return {'currentMs': self.r(clock + 8, 'f')[0],
                    'startEndMs': list(self.r(clock + 0x20, '2f')),
                    'loop': self.r(clock + 0x29, 'B')[0],
                    'speed': self.r(clock + 0x34, 'f')[0]}
    return CrocodileProbe


def inspect(resources, native, output):
    from analyze_native_resources import NativeImage
    from tutorial_npc_binding_probe import controller
    output.resolve().relative_to((ROOT / 'analysis/raw').resolve())
    if (output / 'evidence.json').exists():
        raise ValueError('Preserve the existing original-source receipt')
    image = NativeImage(native.read_bytes())
    if hashlib.sha256(image.data).hexdigest() != NATIVE_SHA:
        raise ValueError('Original client identity differs')
    for name, digest in SOURCE_SHAS.items():
        if hashlib.sha256((resources / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Original crocodile asset identity differs')
    model = BDAE(resources / MODEL)
    animation = BDAEAnimation(resources / ANIMATION)
    frozen_diagnostics = {}
    for name in ('channels', 'ranges', 'segments'):
        try:
            getattr(animation, name)()
        except ValueError as error:
            frozen_diagnostics[name] = str(error)
        else:
            raise ValueError('Frozen reader contract changed; retrace this bounded probe')
    data = model.parse()
    skin = controller(model, data)
    probe = probe_type()(image, skin)
    probe.prepare_animation(animation)
    count, table = animation.section(84)
    ranges = []
    for i in range(count):
        at = table + i * 24
        name = animation.string(animation.q(at))
        if name.split('-', 1)[0] not in ('idle', 'walk_forward'):
            continue
        ranges.append({'sourceName': name,
                       'literalUnsignedWords': list(animation.unpack('4I', at + 8)),
                       'literalSignedWords': list(animation.unpack('4i', at + 8)),
                       'nativeClock': probe.clock_case(animation, at)})
    if len(ranges) != 2:
        raise ValueError('Expected exactly original idle and forward-walk ranges')
    idle = next(r for r in ranges if r['sourceName'].startswith('idle-'))
    start, end = idle['nativeClock']['startEndMs']
    cases = [probe.sample_case(t) for t in (start, 35000, 35123, (start + end) / 2, end)]
    output.mkdir(parents=True, exist_ok=True)
    result = {'format': 'oc2-original-crocodile-animation-probe-v1',
              'nativeSHA256': NATIVE_SHA, 'sourceSHA256': SOURCE_SHAS,
              'propertyCount': len(probe.channels),
              'skinBonePropertyCount': sum(c['sourceSkinBone'] for c in probe.channels),
              'boneCount': len(skin['bones']), 'ranges': ranges, 'cases': cases,
              'sourceSegments': probe.segments,
              'cameraOriginalSamplerCalls': probe.sample_calls,
              'originalSamplerEntries': probe.sampler_entries,
              'frozenReaderDiagnostics': frozen_diagnostics,
              'adapters': ['bounded source bytes, allocation, strings, locks and libm',
                           'original samplers execute; camera attachment is not constructed',
                           'range wrapper supplies one exact source record; name pointer is not consumed',
                           'property outputs only; no setters, palette, GPU creation or game actor'],
              'codecRewritten': False, 'runtimeChanged': False,
              'lootOrCombatApproved': False}
    path = output / 'evidence.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--resources', type=Path, required=True)
    cli.add_argument('--native', type=Path, default=ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    r = inspect(args.resources, args.native, args.output)
    print(json.dumps({k: r[k] for k in ('propertyCount', 'skinBonePropertyCount', 'boneCount', 'ranges', 'runtimeChanged')}))


if __name__ == '__main__':
    main()
