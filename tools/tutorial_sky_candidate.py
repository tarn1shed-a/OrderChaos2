"""Build an isolated, append-only tutorial sky candidate from original inputs.

This exports the zone-selected sky, not new world geometry. The web renderer
bridge remains a documented adaptation; no original GPU frame is claimed.
"""
import argparse
import hashlib
import io
import json
import struct
import tarfile
import tempfile
import zipfile
from pathlib import Path

from bdae_convert import BDAE
from map_loading_evidence import Sources, read_world_container
from map_selection_evidence import DEFAULT_APK, apk_config
from resource_packs import DEFAULT_SOURCE
from scene_active_lighting import NativeTargetProbe
from scene_collision import apply_scene_transforms
from scene_lighting import ZONE_SHA256, color_vector, f32
from scene_render_state import _shader, read_pass_state
from scene_sky import SOURCE_HASHES, sky_distance_uniform, verify_native as verify_sky
from scene_sky_frame import verify_native as verify_frame
from scene_zone_selection import ZoneCatalog
from skill_attachments import decode_ftable

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-source-tutorial-sky-candidate-v1'
PREFIX = 'source-tutorial-sky'
MODELS = {'main': 'model/scene/other_sky/tutorial_sky001.bdae',
          'hill': 'model/scene/other_sky/tutorial_skyhill001.bdae'}
HASHES = {**SOURCE_HASHES,
          MODELS['hill']: '7e6069dfd4ab6407d109434780a4e1ca1bcdb1135927cf3a163091d46d44f1a8'}
ROUTINES = {0xa66de4: (1212, '8c6a4ec60b64b87fd5c39ac84e437e62a3ca4fb46074e7409a9d161dbe763714'),
            0xa672a0: (272, '42d351c70bf008437db1f1f916b9c69a8c8893b53d6e55ac7138fe958a03d1f5')}
FIELDS = {'sky_near': (0x68, 'f'), 'sky_half': (0x6c, 'f'),
          'sky_color_near': (0x70, 'I'), 'sky_color_far': (0x74, 'I'),
          'skybox_fog_intensity': (0x128, 'f'), 'skyhill_fog_intensity': (0x12c, 'f'),
          'skybox_saturation': (0x13c, 'f')}
CHANNELS = {'distance': (0x110, 2), 'near': (0x128, 3), 'far': (0x148, 3),
            'saturation': (0x168, 1), 'mainFog': (0x240, 1), 'hillFog': (0x258, 1)}


def sha(raw): return hashlib.sha256(raw).hexdigest()


def source_sky_request(row, base, *, hill=False):
    """4c6438..4c6510: nonempty selected path, base fallback; hill '0' hides."""
    key = 'skybox_hill' if hill else 'skybox'
    selected = row[key]
    if hill and selected == '0': return None
    path = selected or (base[key] if base is not None else '')
    if hill and path == '0': return None
    return path.replace('\\', '/').lower() or None


def target_writes(row, base):
    """Only settled writes in 4c6e04..4c730c; skipped distance retains state."""
    owner = row if base is None or row['sky_half'] > 0 else base
    near_owner = row if base is None or row['sky_color_near'] else base
    far_owner = row if base is None or row['sky_color_far'] else base
    fog_owner = base if base is not None else row
    return {'distance': [f32(owner['sky_near']), f32(owner['sky_half'])] if owner['sky_half'] > 0 else None,
            'near': color_vector(near_owner['sky_color_near']) if near_owner['sky_color_near'] else None,
            'far': color_vector(far_owner['sky_color_far']) if far_owner['sky_color_far'] else None,
            'saturation': [f32(far_owner['skybox_saturation'])],
            'mainFog': [f32(fog_owner['skybox_fog_intensity']) if fog_owner['skybox_fog_intensity'] > 0 else 8.],
            'hillFog': [f32(fog_owner['skyhill_fog_intensity']) if fog_owner['skyhill_fog_intensity'] > 0 else 4.]}


class NativeSkyTargets(NativeTargetProbe):
    """Execute original constructor and the sky-only selected-zone target block.

    Zone storage, allocation and mode=0 are explicit fixtures. Existing fog,
    ambient light, weather and postprocessing channels are never advanced here.
    """
    def __init__(self, image):
        super().__init__(image)
        self.uc.mem_map(0x4be000, 4096)
        self.uc.mem_write(0x4be000, image.read(0x4be000, 4096))

    def run_sky(self, row, base, previous=None):
        self.heap = 0x10010000
        self.uc.mem_write(0x10000000, bytes(0x40000))
        self.uc.mem_write(0x20000000, bytes(0x10000))
        for index in range(31): self.uc.reg_write(getattr(self.reg, f'UC_ARM64_REG_X{index}'), 0)
        for index in range(32): self.uc.reg_write(getattr(self.reg, f'UC_ARM64_REG_Q{index}'), 0)
        manager, env, base_at, row_at, stack = 0x10000000, 0x10001000, 0x10002000, 0x10003000, 0x20008000
        self.uc.reg_write(self.reg.UC_ARM64_REG_SP, stack)
        self.uc.reg_write(self.reg.UC_ARM64_REG_X0, env)
        self.uc.emu_start(0x4be824, 0x4be9b8, count=200)
        initial = {key: list(self._read(env+off, 'f'*dim)) for key, (off, dim) in CHANNELS.items()}
        if previous is not None:
            if set(previous) != set(CHANNELS): raise ValueError('Missing explicit previous sky state')
            for key, (off, dim) in CHANNELS.items():
                if len(previous[key]) != dim: raise ValueError('Previous sky channel shape differs')
                self._write(env+off, 'f'*dim, *previous[key])
        for source, at in ((base, base_at), (row, row_at)):
            if source is not None:
                for key, (off, fmt) in FIELDS.items(): self._write(at+off, fmt, source[key])
        self._write(manager+0x88, 'Q', base_at if base is not None else 0)
        self._write(manager+0xc0, 'Q', env)
        for key, value in [('X19', manager), ('X27', row_at), ('X25', stack+0x108), ('W20', 0), ('W22', 0)]:
            self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+key), value)
        self.uc.reg_write(self.reg.UC_ARM64_REG_S8, struct.unpack('<I', struct.pack('<f', 1/255))[0])
        self.uc.emu_start(0x4c6e04, 0x4c730c, count=5000)
        if self.uc.reg_read(self.reg.UC_ARM64_REG_PC) != 0x4c730c:
            raise ValueError('Original sky target block did not reach bounded end')
        result = {key: list(self._read(env+off, 'f'*dim)) for key, (off, dim) in CHANNELS.items()}
        expected = dict(initial if previous is None else previous)
        expected.update({k: v for k, v in target_writes(row, base).items() if v is not None})
        if result != expected: raise ValueError('Original sky target writes differ from independent reader')
        return {'initial': initial, 'result': result}


def effect(reader, state_probe=None):
    n, at = reader.section(164)
    if n != 1: raise ValueError('Expected one original sky effect')
    result = []
    for fld in (32, 36):
        profile = reader.rel(at+fld); count, start = reader.u(profile), reader.rel(profile+4)
        rows = []
        for i in range(count):
            item = start+24*i
            if reader.u(item+8) != 1: raise ValueError('Sky multi-pass effect is outside candidate scope')
            source_pass = reader.rel(item+12)
            state = read_pass_state(reader, source_pass+72)
            if state_probe is not None:
                src, out, device = state_probe.alloc(88), state_probe.alloc(28), state_probe.alloc(0x3000)
                state_probe.uc.mem_write(src, reader.b[source_pass+72:source_pass+160])
                state_probe.call(0x114dd1c, {'X0': out, 'X1': src})
                translated = bytes(state_probe.uc.mem_read(out, 28))
                state_probe.uc.mem_write(device+0x38+0x48c, translated)
                state_probe.gl = []
                state_probe.call(0x1433a54, {'X0': device+0x38, 'X1': out})
                calls = {e['name']: e['args'] for e in state_probe.gl}
                if state['blendEnabled'] and (calls.get('glBlendFunc', [])[:2] != [770, 771] or
                                              calls.get('glBlendEquation', [])[:1] != [32774]):
                    raise ValueError('Original sky blend factors need a different web bridge')
                state['originalNumericStateConversionExecuted'] = True
                state['originalGLCallsRecordedWithoutGPU'] = state_probe.gl
            rows.append({'name': reader.string(reader.q(item)), 'vertex': _shader(reader, source_pass),
                         'fragment': _shader(reader, source_pass+24), 'state': state})
        result.append({'sourcePointerField': fld, 'techniques': rows})
    return result


def material(reader):
    from scene_sampling import material_samplers
    rows = material_samplers(reader)
    n, at = reader.section(172)
    if n != 1 or len(rows) != 1: raise ValueError('Only single-material sky source is scoped')
    count, props = reader.u(at+32), reader.rel(at+36)
    technique = None
    for i in range(count):
        p = props+32*i
        if reader.u(p+16) == 28:
            if technique is not None: raise ValueError('Ambiguous source sky technique')
            technique = reader.string(reader.q(reader.rel(p+28)+8))
    if technique is None: raise ValueError('Sky source has no explicit named technique')
    return {**rows[0], 'technique': technique}


def build(source, apk, image, output):
    from texture_decode import decode
    if output.exists() or not output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Use a fresh ignored analysis/raw candidate directory')
    verify_sky(image); verify_frame(image)
    for at, (n, digest) in ROUTINES.items():
        if sha(image.read(at, n)) != digest: raise ValueError('Original hill routine changed')
    if image.read(0x1df79f0, 4) != struct.pack('<f', 400): raise ValueError('Original hill size constant changed')
    proof = apk_config(apk)
    with zipfile.ZipFile(apk) as archive: options = json.loads(archive.read('assets/GameOptions.json'))
    from native_device_selection_probe import NativeDeviceSelectionProbe
    defaults = dict(NativeDeviceSelectionProbe(image).updates(options['profiles']['GPU'], ''))
    if defaults.get('ShowHillInSky') is not True: raise ValueError('Original Default hill gate changed')
    source = Sources(source); zone_raw = source.read('tables/zones.tbl')
    if sha(zone_raw) != ZONE_SHA256: raise ValueError('Original zone table changed')
    table = decode_ftable(zone_raw, id_column='ID'); offset = 0; offsets = {}
    for name, kind in zip(table['columns'], table['physicalTypes']):
        offsets[name] = (offset, 'I' if kind == 'u' else kind); offset += 8 if kind == 's' else 4
    if any(offsets[key] != value for key, value in FIELDS.items()): raise ValueError('Original sky zone layout changed')
    catalog = ZoneCatalog(table['rows'], 5); base = next(r for r in catalog.base if r['ID'] == 194)
    selected_rows = [base]+[r for r in table['rows'] if r['parent_ID'] == 194]
    native = NativeSkyTargets(image); zones = []; native_rows = []
    for row in selected_rows:
        fallback = None if row['ID'] == base['ID'] else base
        state = native.run_sky(row, fallback)
        requests = {k: source_sky_request(row, fallback, hill=k == 'hill') for k in MODELS}
        if requests != MODELS: raise ValueError('Unscoped source sky model request')
        zones.append({'id': row['ID'], 'requests': requests, 'writes': target_writes(row, fallback)})
        native_rows.append({'zone': row['ID'], **state})
    prior = native.run_sky(next(r for r in selected_rows if r['ID'] == 195), base)['result']
    retained = native.run_sky(base, None, prior)
    output.mkdir(parents=True)
    asset_root = output/'game-data/converted'/PREFIX; asset_root.mkdir(parents=True)
    def write(name, raw):
        path = asset_root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        return {'url': '/assets/'+PREFIX+'/'+name, 'sha256': sha(raw), 'bytes': len(raw)}
    def document(name, value): return write(name, (json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n').encode())
    def original(name):
        data = source.read(name)
        if name in HASHES and sha(data) != HASHES[name]: raise ValueError('Original source identity changed: '+name)
        return data
    shaders = {name: write(name, original(name)) for name in ('sky_box_vs.glsl', 'sky_box_fs.glsl')}
    models = {}
    from native_mixed_walls import Probe
    state_probe = Probe(image)
    with tempfile.TemporaryDirectory(prefix='oc2-sky-candidate-') as temp:
        for key, name in MODELS.items():
            raw = original(name); p = Path(temp)/(key+'.bdae'); p.write_bytes(raw); reader = BDAE(p)
            data = apply_scene_transforms(reader, reader.parse()); data['source'] = name
            mat = material(reader)
            fx_raw = original(mat['effectPath']); fx_path = Path(temp)/(key+'-effect.bdae'); fx_path.write_bytes(fx_raw)
            profiles = effect(BDAE(fx_path), state_probe); selected = [t for t in profiles[0]['techniques'] if t['name'] == mat['technique']]
            if len(selected) != 1: raise ValueError('Original named technique missing')
            if selected[0]['vertex']['file'] != 'sky_box_vs.glsl' or selected[0]['fragment']['file'] != 'sky_box_fs.glsl':
                raise ValueError('Unscoped sky shader dependency')
            tex_name = mat['samplers']['skyTexture']['texture']; tex_raw = original(tex_name); texture = decode(tex_raw)
            buffer = io.BytesIO(); texture.save(buffer, format='PNG')
            tex_meta = write(key+'.png', buffer.getvalue())
            tex_meta.update(source=tex_name, sourceSHA256=sha(tex_raw), width=texture.width, height=texture.height)
            # Original scale consumes the wrapper's model box. For these two
            # pure-translation trees, every possible raw/transformed AABB has
            # the same largest absolute X/Z bound; no mesh/box repair is used.
            biggest = max(abs(v) for end in data['bounds'] for v in end)
            for mesh in data['meshes']:
                m = mesh['sourceNodeTransform']['matrix']
                if m[:12] != [1., 0., 0., 0, 0., 1., 0., 0, 0., 0., 1., 0]:
                    raise ValueError('Sky scale needs a newly traced non-translation tree')
                if abs(m[13])+max(abs(data['bounds'][i][1]) for i in (0, 1)) >= biggest:
                    raise ValueError('Sky translated Y can change native largest bound')
            scale = f32((450 if key == 'main' else 400)/biggest) if biggest > f32(.1) else 1.
            payload = document(key+'.json', data)
            models[key] = {'model': payload, 'texture': tex_meta, 'source': name, 'sourceSHA256': sha(raw),
                           'sourceEffect': mat['effectPath'], 'effectSHA256': sha(fx_raw),
                           'technique': selected[0], 'scale': scale, 'modelBoxMaxAbs': biggest,
                           'sourceSamplerDeclaration': mat['samplers']['skyTexture']['request']}
    profile = {'format': FORMAT, 'sourceMapId': 5, 'configuration': {'profile': 'APK_Default', 'ShowHillInSky': True},
               'models': models, 'shaders': shaders, 'zones': zones,
               'initialEnvironment': native_rows[0]['initial'],
               'cameraFollow': {'axes': 'XYZ', 'wrapperOffsets': [16, 24], 'originalNodeTransformRetained': True},
               'webAdapter': {'renderBeforeOpaqueGeometry': True, 'sameCurrentHDRTarget': True,
                              'changesFogLightingWeatherOrHDR': False, 'originalGPUObserved': False}}
    manifest = document('manifest.json', profile)
    report = {'format': FORMAT, 'manifest': manifest, 'apk': proof, 'world': read_world_container(source.read('world/tutorial.wld')),
              'sourceProofs': source.proofs, 'nativeSkyTargets': native_rows, 'retainedDistanceAfter195To194': retained,
              'defaultHillGate': defaults['ShowHillInSky'], 'hillConstant': 400, 'routines': ROUTINES,
              'originalGPUExecuted': False, 'limitations': [
                  'Original default profile is a selected baseline, not a capture of an Android runtime override.',
                  'Only settled environment mode=0 is connected, matching the current preview; native transition timing remains separate.',
                  'Three.js shader translation, sampler reuse and background-before-foreground ordering are browser adaptations; original final GPU queue is not claimed recovered.',
                  'Sky fills only genuine background pixels. It does not reconstruct missing building faces, unknown activities or server spawn data.']}
    (output/'evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    archive = output/'tutorial-sky-append.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for path in sorted((output/'game-data').rglob('*')):
            if path.is_file(): tar.add(path, arcname=path.relative_to(output).as_posix())
    print(json.dumps({'candidate': str(output), 'manifest': manifest, 'appendArchive': str(archive),
                      'appendSHA256': sha(archive.read_bytes()), 'models': len(models), 'sourceZones': len(zones)}))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--apk', type=Path, default=DEFAULT_APK)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    build(args.source, args.apk, NativeImage(args.native.read_bytes()), args.output)
