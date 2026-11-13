import base64
import hashlib
import io
from pathlib import Path
import struct
import unittest

from native_font_draw import FontDrawCPU, full_font_from_woff
from resource_packs import DEFAULT_SOURCE
from source_physics import SourcePhysics

SO = Path(__file__).resolve().parents[1]/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


class ActorNameProbe(SourcePhysics):
    def __init__(self, image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.lookup_names = []
        for at in (0x901f0c, 0x42002c, 0x420404, 0x331cbc):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if at in (0x901f0c, 0x42002c, 0x420404):
            self.set('PC', self.get('X30')); return  # Explicit timer/state interfaces.
        if at == 0x331cbc:
            self.lookup_names.append(self.cstr(self.get('X2')).decode())
            self.set('W0', 1200); self.set('PC', self.get('X30')); return
        super().hook(uc, at, size, data)

    def self_relation(self, faction, predicate):
        actor, vt, props = self.alloc(0x1900), self.alloc(0x400), self.alloc(0x800)
        self.w(actor, 'Q', vt); self.w(actor+0x18, 'Q', props)
        a, b = self.r(0x2582f40, '2I'); self.w(props, '2I', 0x120a^a, 0x120a^b)
        self.w(actor+0x338, 'I', faction); self.w(vt+0x2e8, 'Q', self.TRUE if predicate else self.FALSE)
        return bool(self.call(0xa09b20, {'X0': actor, 'X1': actor}) & 1)

    def model_complete(self, flags):
        actor = self.alloc(0x1900); self.w(actor+0x38, 'Q', self.alloc(8))
        self.w(actor+0x5a0, 'I', flags); self.lookup_names = []
        self.call(0x9edf20, {'X0': actor})
        return self.r(actor+0x5a0, 'I')[0], self.lookup_names


@unittest.skipUnless(SO.is_file(), 'Original library stays local')
class SourceNameActorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(SO.read_bytes()); cls.vm = ActorNameProbe(cls.image)

    def test_factory_and_actual_localhero_slots_are_source_pinned(self):
        im = self.image
        self.assertEqual(hashlib.sha256(im.read(0xa771e0, 48)).hexdigest(), 'e34659a9101decf7ce2448fea598f5756de8ac61dd89b6a0f81f22d0b476db88')
        rel = {r['r_offset']: r['r_addend'] for r in im.elf.get_section_by_name('.rela.dyn').iter_relocations() if r['r_info_type'] == 1027}
        self.assertEqual(rel[0x24228a8+0x310], 0x9097ec)
        self.assertEqual(rel[0x24228a8+0x318], 0x9097f4)
        self.assertEqual(rel[0x24228a8+0x338], 0x9edf20)
        self.assertEqual(self.vm.call(0x9097ec), 0)
        self.assertEqual(self.vm.call(0x9097f4), 0)

    def test_original_self_comparison_is_false_without_invented_faction_or_guild(self):
        for faction in (0, 1, 2, 5, 99, 0xffffffff):
            for predicate in (False, True):
                self.assertFalse(self.vm.self_relation(faction, predicate))

    def test_original_completion_sets_name_bit_after_named_animation_lookups(self):
        for flags in (0, 1, 0x20, 0x80000000):
            result, names = self.vm.model_complete(flags)
            self.assertEqual(result, flags | 0x40)
            self.assertEqual(names, ['run_normal', 'walk_forward', 'swim_forward'])


@unittest.skipUnless(SO.is_file() and (DEFAULT_SOURCE/'ui/Font/Alegreya-Bold.ttf').is_file(), 'Original font and library stay local')
class SourceFontDrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(SO.read_bytes())
        cls.font = (DEFAULT_SOURCE/'ui/Font/Alegreya-Bold.ttf').read_bytes()

    def test_native_font_face_cache_pixels_layout_outline_and_indices_are_real(self):
        vm = FontDrawCPU(self.image, self.font); packet = vm.text('精灵A')
        self.assertTrue(packet['nativeGlyphCPU']); self.assertFalse(packet['originalGPUObserved'])
        self.assertEqual((packet['vertexCount'], packet['indexCount']), (24, 36))
        vertices = list(struct.iter_unpack('<5fI', base64.b64decode(packet['vertices'])))
        self.assertEqual([v[5] for v in vertices[:8]], [0xff000000]*4+[0xfffed8a2]*4)
        self.assertEqual(struct.unpack('<6H', base64.b64decode(packet['indices'])[:12]), (0, 2, 1, 0, 3, 2))
        from PIL import Image
        image = Image.open(io.BytesIO(base64.b64decode(packet['atlas'].split(',')[1])))
        alpha = image.getchannel('A')
        self.assertIsNotNone(alpha.getbbox()); self.assertGreater(len(set(alpha.tobytes())), 20)

    def test_font_worker_uses_source_bytes_for_spaces_and_chinese_not_system_fonts(self):
        vm = FontDrawCPU(self.image, self.font); packet = vm.text('A 精灵')
        self.assertEqual(packet['vertexCount'], 24)  # Space advances but adds no visible glyph.
        for value in ('', 'x'*25, 'x\ny'):
            with self.assertRaises(ValueError): vm.text(value)

    def test_full_woff_unwrap_preserves_every_original_font_table(self):
        from chinese_fonts import convert_full_font
        from fontTools.ttLib import TTFont
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'full.woff'; convert_full_font(self.font, path)
            decoded = full_font_from_woff(path.read_bytes())
        a, b = TTFont(io.BytesIO(self.font), lazy=True), TTFont(io.BytesIO(decoded), lazy=True)
        for tag in a.reader.keys():
            x, y = a.reader[tag], b.reader[tag]
            if tag == 'head': x, y = x[:8]+b'\0'*4+x[12:], y[:8]+b'\0'*4+y[12:]
            self.assertEqual(x, y, tag)
        direct = FontDrawCPU(self.image, self.font).text('Kevin精灵')
        wrapped = FontDrawCPU(self.image, decoded).text('Kevin精灵')
        self.assertEqual(direct, wrapped)


if __name__ == '__main__': unittest.main()
