import struct
import unittest
from pathlib import Path

from bdae_convert import BDAE
from bdae_attributes import FORMAT, primitive_bindings, select_attributes, verify_native

ROOT = Path(__file__).resolve().parents[1]
WALL = ROOT/'game-data/extracted/model/scene_generator_temple_000/god_wall_03.bdae'
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def fixture():
    raw = bytearray(512)
    entries = [(5, 0), (0, 1), (4, 3), (1, 4), (6, 2)]
    for primitive in range(2):
        at, table = primitive*88, 256+primitive*40
        struct.pack_into('<Ii', raw, at+20, len(entries), table-(at+24))
        for index, (semantic, attribute) in enumerate(entries):
            struct.pack_into('<Ib', raw, table+index*8, semantic, attribute)
    reader = BDAE.__new__(BDAE)
    reader.b = raw
    # UV1 precedes UV0; a third unused float2 is also before UV0. Position
    # and normal are deliberately out of the old first-two-stream order.
    attributes = [(48, 32, 6, 2), (48, 0, 6, 3), (48, 40, 6, 2),
                  (48, 24, 6, 2), (48, 12, 6, 3)]
    return reader, attributes


class AttributeBindingTests(unittest.TestCase):
    def test_source_bindings_choose_roles_even_with_reordered_streams_and_extra_uv(self):
        reader, attributes = fixture()
        streams, metadata = select_attributes(reader, 0, 2, attributes, 3, 144)
        self.assertEqual(streams, {'positions': attributes[1], 'normals': attributes[4],
                                  'uvs': attributes[3], 'sourceUV1': attributes[0]})
        self.assertEqual(metadata['format'], FORMAT)
        self.assertEqual(metadata['checkedPrimitives'], 2)
        self.assertEqual(metadata['streams']['uvs']['sourceSemantic'], 4)
        self.assertEqual(metadata['streams']['uvs']['runtimeSemantic'], 1)
        self.assertEqual(metadata['streams']['sourceUV1']['runtimeName'], 'texcoord1')

    def test_uv1_is_optional_and_negative_signed_indices_are_absent(self):
        for signed in (-1, -128):
            reader, attributes = fixture()
            for at in (260, 300):
                struct.pack_into('<b', reader.b, at, signed)
            streams, _ = select_attributes(reader, 0, 2, attributes, 3, 144)
            self.assertNotIn('sourceUV1', streams)
            for at in (276, 316):
                struct.pack_into('<b', reader.b, at, -1)
            with self.assertRaisesRegex(ValueError, 'Missing required'):
                select_attributes(reader, 0, 2, attributes, 3, 144)

    def test_different_primitive_roles_require_splitting_instead_of_using_first_uv(self):
        reader, attributes = fixture()
        struct.pack_into('<b', reader.b, 316, 2)
        with self.assertRaisesRegex(ValueError, 'mesh splitting'):
            select_attributes(reader, 0, 2, attributes, 3, 144)

    def test_duplicate_semantic_counts_indices_and_invalid_pointers_are_rejected(self):
        for at, fmt, value in ((20, 'I', 0), (20, 'I', 65), (24, 'i', 512),
                               (264, 'I', 5), (276, 'b', 5), (276, 'b', 127)):
            reader, attributes = fixture()
            struct.pack_into('<'+fmt, reader.b, at, value)
            with self.assertRaises(ValueError):
                select_attributes(reader, 0, 2, attributes, 3, 144)
        reader, _ = fixture()
        reader.b = reader.b[:295]
        with self.assertRaises(ValueError):
            primitive_bindings(reader, 88, 5)

    def test_selected_types_components_stride_and_each_stream_extent_are_checked(self):
        for replacement in ((48, 24, 1, 2), (48, 24, 6, 3), (0, 24, 6, 2),
                             (65536, 24, 6, 2), (48, -1, 6, 2), (48, 44, 6, 2)):
            reader, attributes = fixture()
            attributes[3] = replacement
            with self.assertRaises(ValueError):
                select_attributes(reader, 0, 2, attributes, 3, 144)
        reader, attributes = fixture()
        with self.assertRaisesRegex(ValueError, 'texcoord1'):
            select_attributes(reader, 0, 2, attributes, 3, 130)

    def test_changed_native_attribute_code_is_rejected(self):
        class Changed:
            def read(self, address, size):
                return bytes(size)
        with self.assertRaisesRegex(ValueError, 'retrace'):
            verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native library stays local')
    def test_native_source_runtime_id_mapping_and_relocated_name_table(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual((result['routineCount'], result['checkedRuntimeNames'], result['checkedShaderAliases']), (10, 4, 4))
        self.assertTrue(result['sourceToGLSemanticChainVerified'])
        self.assertFalse(result['originalSceneShaderExecutionRestored'])
        class Relocations:
            def iter_relocations(self):
                for row in image.elf.get_section_by_name('.rela.dyn').iter_relocations():
                    yield {'r_offset': row['r_offset'], 'r_addend':
                           0x1f4c134 if row['r_offset'] == 0x250e760 else row['r_addend']}
        class ELF:
            def get_section_by_name(self, name):
                return Relocations()
        class Changed:
            elf = ELF()
            read = image.read
        with self.assertRaisesRegex(ValueError, 'semantic name table'):
            verify_native(Changed())
        class ChangedAlias:
            elf = image.elf
            def read(self, address, size):
                return bytes(size) if address == 0x2499a00+8 else image.read(address, size)
        with self.assertRaisesRegex(ValueError, 'semantic alias changed'):
            verify_native(ChangedAlias())

    @unittest.skipUnless(WALL.is_file(), 'Original scene model stays local')
    def test_original_uv_sets_keep_their_identity_when_stream_table_order_changes(self):
        original = BDAE(WALL)
        expected = original.parse()
        changed = BDAE(WALL)
        changed.b = bytearray(changed.b)
        count, table = changed.section(180)
        for index in range(count):
            wrapper = changed.rel(table+index*24+20)
            data = changed.q(wrapper+8)+((changed.u(wrapper+4) & 0xffffff)-1)*8
            for field in (20, 28, 36, 44):
                pointers = changed.rel(data+field)
                a, b = bytes(changed.b[pointers+8:pointers+12]), bytes(changed.b[pointers+12:pointers+16])
                changed.b[pointers+8:pointers+12], changed.b[pointers+12:pointers+16] = b, a
            primitives, primitive_table = changed.u(data+96), changed.rel(data+100)
            for primitive in range(primitives):
                at = primitive_table+primitive*88
                size, bindings = changed.u(at+20), changed.rel(at+24)
                for entry in range(size):
                    value = changed.unpack('b', bindings+entry*8+4)[0]
                    if value in (2, 3):
                        struct.pack_into('<b', changed.b, bindings+entry*8+4, 5-value)
        actual = changed.parse()
        self.assertEqual(actual['sourceAttributes']['format'], FORMAT)
        for a, b in zip(actual['meshes'], expected['meshes']):
            for field in ('positions', 'normals', 'uvs', 'sourceUV1', 'indices', 'groups'):
                self.assertEqual(a[field], b[field])
            self.assertEqual(a['sourceAttributes']['streams']['uvs']['attributeIndex'], 3)
            self.assertNotEqual(a['uvs'], a['sourceUV1'])


if __name__ == '__main__':
    unittest.main()
