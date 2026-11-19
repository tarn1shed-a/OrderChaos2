"""Public negative controls for immutable ELF inputs; no game or Uc runs.

Synthetic metadata exercises fallback/ownership and ELF64 signed fields. The
private original-byte and full native replay checks are separate acceptance.
"""
import struct
import unittest
from types import SimpleNamespace

from analyze_native_resources import NativeImage
from source_code_pages import RX_MEMORY_BYTES, try_map_original_rx


class ImageViewsControls(unittest.TestCase):
    def image(self, mapper=None, raw=None):
        return SimpleNamespace(native_image_views=True,
                               data=bytes(RX_MEMORY_BYTES) if raw is None else raw,
                               code_pages=mapper,
                               iter_relative_relocations=lambda: iter(()))

    def segment(self, **updates):
        return dict(p_type='PT_LOAD', p_flags=5, p_vaddr=0, p_offset=0,
                    p_memsz=RX_MEMORY_BYTES, p_filesz=RX_MEMORY_BYTES, **updates)

    def test_default_off_never_reads_or_maps(self):
        def forbidden(*args):
            raise AssertionError('Disabled path must not inspect or map')
        for flag in (None, False, 0, 1, '1'):
            image=SimpleNamespace(native_image_views=flag,
                                  code_pages=SimpleNamespace(map_segment=forbidden),
                                  iter_relative_relocations=forbidden)
            self.assertIs(try_map_original_rx(object(), image, {}), False)

    def test_unavailable_mapper_or_other_layout_uses_old_path(self):
        self.assertIs(try_map_original_rx(object(), self.image(), {}), False)
        mapper=SimpleNamespace(map_segment=lambda *args: self.fail('Unexpected map'))
        segment=self.segment()
        for update in ({'p_offset':4096}, {'p_flags':6}, {'p_vaddr':4096},
                       {'p_filesz':RX_MEMORY_BYTES-1}, {'p_memsz':RX_MEMORY_BYTES+1}):
            self.assertIs(try_map_original_rx(object(), self.image(mapper),
                                            {**segment, **update}), False)

    def test_short_bytes_source_uses_old_path_without_mapping(self):
        mapper=SimpleNamespace(map_segment=lambda *args: self.fail('Unexpected map'))
        self.assertIs(try_map_original_rx(object(), self.image(mapper, b'bad'),
                                        self.segment()), False)

    def test_unbranded_buffers_are_refused_before_mapping(self):
        mapper=SimpleNamespace(map_segment=lambda *args: self.fail('Unexpected map'))
        for raw in (bytearray(1), memoryview(b'bad')):
            with self.subTest(kind=type(raw).__name__):
                with self.assertRaisesRegex(ValueError, 'Authenticated whole native-program mmap required'):
                    try_map_original_rx(object(), self.image(mapper, raw), self.segment())

    def test_relative_writes_overlapping_code_do_not_use_view(self):
        mapper=SimpleNamespace(map_segment=lambda *args: self.fail('Unexpected map'))
        for offset in (-4, 0, RX_MEMORY_BYTES-4):
            image=self.image(mapper)
            image.iter_relative_relocations=lambda: iter(((offset, 1),))
            self.assertIs(try_map_original_rx(object(), image, self.segment()), False)

    def test_borrowed_readonly_view_and_real_boolean_result(self):
        raw=bytes(RX_MEMORY_BYTES);calls=[];token=object()
        def mapping(uc, address, size, view):
            self.assertIs(uc, token);self.assertIs(view.obj, raw)
            self.assertTrue(view.readonly);self.assertEqual((address,size),(0,len(raw)))
            with self.assertRaises(TypeError):view[0]=1
            calls.append(view)
            return False
        self.assertIs(try_map_original_rx(token, self.image(SimpleNamespace(map_segment=mapping),raw),self.segment()),False)
        self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):len(calls[0])  # Borrow ends on return.
        with self.assertRaises(ValueError):
            try_map_original_rx(token,self.image(SimpleNamespace(map_segment=lambda *args:None),raw),self.segment())

    def test_mapping_exception_is_never_a_copy_retry(self):
        error=RuntimeError('partial original mapping failed');calls=[]
        def mapping(*args):
            calls.append(True);raise error
        with self.assertRaises(RuntimeError)as caught:
            try_map_original_rx(object(),self.image(SimpleNamespace(map_segment=mapping)),self.segment())
        self.assertIs(caught.exception,error);self.assertEqual(calls,[True])

    def test_relative_table_preserves_type_bits_order_and_signed_addend(self):
        raw=struct.pack('<QQq',100,(31<<32)|1027,-22)+struct.pack('<QQq',90,1025,123)+struct.pack('<QQq',50,1027,7)
        class ELF(dict):
            elfclass=64;little_endian=True
            row={'sh_type':'SHT_RELA','sh_entsize':24,'sh_offset':0,'sh_size':len(raw)}
            def get_section_by_name(self,name):
                self_test.assertEqual(name,'.rela.dyn');return self.row
        self_test=self
        image=SimpleNamespace(data=raw,elf=ELF(e_machine='EM_AARCH64'))
        self.assertEqual(list(NativeImage.iter_relative_relocations(image)),[(100,-22),(50,7)])
        for update in ({'sh_type':'SHT_REL'},{'sh_entsize':16},{'sh_offset':-1},{'sh_size':len(raw)-1},{'sh_offset':1}):
            image.elf.row={**ELF.row,**update}
            with self.assertRaises(ValueError):list(NativeImage.iter_relative_relocations(image))


if __name__=='__main__':unittest.main()
