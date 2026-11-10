"""Private source checks; no fabricated renderer or successful GL results."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


@unittest.skipUnless(NATIVE.is_file() and (SOURCE/'tutorial.bin').is_file(),
                     'Original library and texture inputs stay private')
class TextureLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from texture_loading_evidence import source_links
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.sources = source_links(cls.image, SOURCE)

    def test_original_tasks_upload_and_material_edges(self):
        from texture_loading_evidence import verify_native
        proof = verify_native(self.image)
        self.assertFalse(proof['uploadRoutineReturnOneGuaranteesNoGLError'])
        self.assertFalse(proof['loadingWorkerChecksPayloadLoaderReturn'])

    def test_changed_error_bit_cleanup_or_callback_is_rejected(self):
        from texture_loading_evidence import verify_native
        image = self.image
        for changed in (0x14917e0, 0x1560cac, 0x142e6d8, 0x1444788,
                        0x143b8dc, 0x143b92c, 0x1432a58, 0x1432be0):
            class Changed:
                elf = image.elf
                disassembler = image.disassembler
                routine = image.routine

                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_explicit_source_sample_not_reported_as_runtime_residency(self):
        s = self.sources
        self.assertEqual(len(s['objectLightmapRequests']), 12)
        self.assertEqual(len(s['terrainSamples']), 9)
        self.assertEqual(sum(len(m['materials']) for m in s['modelDeclarations']['models']), 7)
        for tile in s['terrainSamples']:
            for request in tile['layers']+tile['lightmapRequestCandidatesAtExplicitPhaseZero']:
                self.assertFalse(request['runtimeSelectionObserved'])

    def test_actual_container_inventory_keeps_compressed_input(self):
        import collections
        textures = self.sources['textureFiles'].values()
        self.assertEqual(collections.Counter(r['metadata']['container'] for r in textures),
                         {'PVR2': 32, 'TGA': 2})
        self.assertEqual(collections.Counter(r['metadata'].get('encoding') for r in textures),
                         {'ETC1': 28, 'PVRTC1-2bpp-RGBA': 4, None: 2})
        self.assertTrue(all(r['sha256'] and r['crc32'] for r in textures))

    def test_duplicate_default_lightmap_is_not_silently_selected(self):
        files = [r for r in self.sources['textureFiles'].values()
                 if r['path'].lower() == 'texture/lightmap.tga']
        self.assertEqual(len(files), 2)
        self.assertEqual(len({r['sha256'] for r in files}), 2)
        for m in self.sources['modelDeclarations']['models']:
            for mat in m['materials']:
                for sampler in mat['samplers'].values():
                    if sampler['texture'] == 'texture/lightmap.tga':
                        self.assertEqual(len(sampler['fileInspection']['candidates']), 2)
                        self.assertFalse(sampler['fileInspection']['runtimeSelectionObserved'])

    def test_truncated_pvr_payload_is_rejected(self):
        from resource_packs import read_entry
        from map_loading_evidence import Sources
        from texture_loading_evidence import texture_container
        sources = Sources(SOURCE)
        for name in ('texture/hum_box001_01.tga', 'texture/god_wall002_01.tga'):
            entry, = sources.candidates(name)
            raw = read_entry(entry, SOURCE)
            with self.subTest(name=name), self.assertRaises(ValueError):
                texture_container(raw[:-1])


if __name__ == '__main__':
    unittest.main()
