import gc
import hashlib
import threading
import unittest
import weakref
from types import SimpleNamespace
from source_runtime_resources import SourceRuntimeResources


class ResourceLifetimeTests(unittest.TestCase):
    def test_one_verified_image_but_not_mutable_execution_state(self):
        calls=[]
        class Image:
            def __init__(self, raw):
                if raw != b'original-image':raise ValueError('Original build differs')
                calls.append(raw);self.data=raw
        pool=SourceRuntimeResources()
        a=pool.native_image(b'original-image',Image)
        b=pool.native_image(bytes(bytearray(b'original-image')),Image)
        self.assertIs(a,b);self.assertEqual(len(calls),1)
        with self.assertRaisesRegex(ValueError,'Original build differs'):
            pool.native_image(b'different-image',Image)

    def test_a_shared_elf_cursor_cannot_cross_rpc_threads(self):
        pool=SourceRuntimeResources();errors=[]
        def other():
            try:pool.native_image(b'original',lambda raw:SimpleNamespace(data=raw))
            except Exception as error:errors.append(error)
        worker=threading.Thread(target=other);worker.start();worker.join()
        self.assertEqual(len(errors),1);self.assertIn('serial RPC owner',str(errors[0]))

    def test_unneeded_geometry_is_collectible_without_touching_native_state(self):
        class Geometry:pass
        geometry=Geometry();ref=weakref.ref(geometry)
        native=object();motion={'key':'own-body'}
        vm=SimpleNamespace(batch_prepared=True,bound_motion=motion,native_buffers=native,
            data={'rig':{'skins':[{'boneNames':['root','hand']}]},'meshes':[geometry],'clips':[geometry]})
        before=tuple(sorted({n for s in vm.data['rig']['skins'] for n in s['boneNames']}))
        del geometry
        SourceRuntimeResources().retain_compositor(vm);gc.collect()
        after=tuple(sorted({n for s in vm.data['rig']['skins'] for n in s['boneNames']}))
        self.assertEqual(before,after);self.assertIsNone(ref());self.assertIs(vm.native_buffers,native);self.assertIs(vm.bound_motion,motion)

    def test_no_retention_before_original_batch_and_binding(self):
        vm=SimpleNamespace(batch_prepared=False,data={'still':'needed'})
        with self.assertRaisesRegex(ValueError,'original preparation'):
            SourceRuntimeResources().retain_compositor(vm)
        self.assertEqual(vm.data,{'still':'needed'})


if __name__=='__main__':unittest.main()
