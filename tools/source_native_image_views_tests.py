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



# Explicit synthetic source-layout/lease controls. No original ELF admission,
# Unicorn, actor or game state is provided by this fixture. The real unbranded
# readonly-map rejection is tested with the unpatched production checker.
import io,mmap,tempfile,threading
from pathlib import Path
from unittest.mock import patch
import source_immutable_inputs as authentication
import analyze_native_resources as image_module
Image=NativeImage
TARGETS=(0x900100,0x900140,0x900180,0x9001c0,0x900200)

class ImmutableRoutineProofControls(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'explicit-synthetic-not-original-elf.bin'
  self.base=0x900000;self.count=5;data=bytearray(1024);table=bytearray(12+8*self.count)
  for i,address in enumerate(sorted(TARGETS)):
   fde=self.base+64+i*16;struct.pack_into('<ii',table,12+i*8,address-self.base,fde-self.base);struct.pack_into('<iI',data,64+i*16+8,address-(fde+8),32)
  self.path.write_bytes(data)
  with self.path.open('rb')as backing:self.raw=mmap.mmap(backing.fileno(),0,access=mmap.ACCESS_READ)
  self.stream=io.FileIO(self.path,'rb');self.program=SimpleNamespace(sha256=image_module.NATIVE_SHA256,size=len(data))
  self.image=Image.__new__(Image);self.image.data=self.raw;self.image.native_image_views=True;self.image._unwind_header=bytes(table);self.image._unwind_base=self.base;self.image._unwind_count=self.count
  self.image.elf=SimpleNamespace(stream=self.stream,iter_segments=lambda:iter([{'p_type':'PT_LOAD','p_vaddr':self.base,'p_offset':0,'p_filesz':len(data)}]))
  self.calls=[];self.fail_at=None
  def synthetic_static_routine(image,address):
   self.calls.append(address)
   if address==self.fail_at:raise ValueError('explicit synthetic static failure')
   image._immutable_routine_row(address)
   return {'synthetic':True},[]
  self.routine=patch.object(Image,'routine',synthetic_static_routine);self.routine.start()
  # Explicit schema/lifetime fixture, not fake production authentication. The
  # unpatched production checker is tested separately and must reject this map.
  def fixture_lease(raw,stream=None):
   if raw is not self.raw or self.raw.closed or stream is not self.stream or self.stream.closed:raise ValueError('synthetic fixture lease changed')
   return self.program
  self.auth=patch.object(authentication,'require_native_program',fixture_lease);self.auth.start()
 def tearDown(self):
  self.auth.stop();self.routine.stop();self.stream.close();self.raw.close();self.temp.cleanup()
 def prepare(self):self.assertIs(self.image.prepare_immutable_routines(TARGETS),True)
 def test_one_static_verification_shared_by_repeated_consumers(self):
  self.prepare()
  for _ in range(4):self.assertTrue(self.image.prepare_immutable_routines(TARGETS));self.assertTrue(self.image.require_prepared_immutable_routines(TARGETS))
  self.assertEqual(self.calls,list(TARGETS))
 def test_unprepared_map_never_mints_proof_from_frame(self):
  with self.assertRaisesRegex(ValueError,'prepared before'):self.image.require_prepared_immutable_routines(TARGETS)
  self.assertEqual(self.calls,[])
 def test_wrong_program_sha_and_size_fail(self):
  self.program.sha256='0'*64
  with self.assertRaisesRegex(ValueError,'identity differs'):self.prepare()
  self.program.sha256=image_module.NATIVE_SHA256;self.program.size-=1
  with self.assertRaisesRegex(ValueError,'identity differs'):self.prepare()
 def test_partial_prepare_failure_has_no_published_cache(self):
  self.fail_at=TARGETS[2]
  with self.assertRaisesRegex(ValueError,'static failure'):self.prepare()
  self.assertFalse(getattr(self.image,'_immutable_routine_proofs',None));self.fail_at=None;self.prepare();self.assertEqual(len(self.calls),8)
 def test_in_place_fde_change_same_mmap_is_rejected(self):
  self.prepare();row=self.image._immutable_routine_proofs[TARGETS][1][0];offset=row[4]
  with self.path.open('r+b')as f:f.seek(offset+4);f.write(struct.pack('<I',31));f.flush()
  with self.assertRaisesRegex(ValueError,'row changed'):self.image.require_prepared_immutable_routines(TARGETS)
  self.assertEqual(len(self.calls),5)
 def test_unwind_replacement_or_mutable_index_rejected(self):
  self.image._unwind_header=bytearray(self.image._unwind_header)
  with self.assertRaisesRegex(ValueError,'table bytes'):self.prepare()
  self.image._unwind_header=bytes(self.image._unwind_header);self.prepare();self.image._unwind_header=bytes(bytearray(self.image._unwind_header))
  with self.assertRaisesRegex(ValueError,'index lease changed'):self.image.require_prepared_immutable_routines(TARGETS)
 def test_parser_stream_and_closed_lease_are_not_reused(self):
  self.prepare();self.image.elf.stream=io.BytesIO(b'synthetic')
  with self.assertRaisesRegex(ValueError,'lease changed'):self.image.require_prepared_immutable_routines(TARGETS)
  self.image.elf.stream=self.stream;self.stream.close()
  with self.assertRaisesRegex(ValueError,'lease changed'):self.image.require_prepared_immutable_routines(TARGETS)
 def test_other_thread_cannot_borrow_shared_parser_proof(self):
  self.prepare();errors=[]
  def run():
   try:self.image.require_prepared_immutable_routines(TARGETS)
   except Exception as e:errors.append(e)
  t=threading.Thread(target=run);t.start();t.join();self.assertEqual(len(errors),1);self.assertIn('owner',str(errors[0]))
 def test_bytes_mode_keeps_original_checks_and_map_replacement_fails(self):
  self.image.data=b'explicit old-mode source fixture';self.assertFalse(self.image.prepare_immutable_routines(TARGETS));self.assertFalse(self.image.require_prepared_immutable_routines(TARGETS));self.assertEqual(self.calls,[])
  self.image.data=self.raw;self.prepare();self.image.data=b'replaced'
  with self.assertRaisesRegex(ValueError,'replaced'):self.image.require_prepared_immutable_routines(TARGETS)
 def test_real_authentication_rejects_unbranded_readonly_map(self):
  self.auth.stop()
  with self.assertRaisesRegex(ValueError,'authenticated whole native'):self.prepare()
  self.auth.start()

if __name__=='__main__':unittest.main()
