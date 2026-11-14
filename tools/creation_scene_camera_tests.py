"""Execute original factory/viewport paths; no game assets or saves are written."""
import math
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'

@unittest.skipUnless(LIB.is_file(),'Private original ARM64 library absent')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(LIB.read_bytes())

    def probe(self):
        from creation_scene_camera_probe import CreationSceneCameraProbe
        return CreationSceneCameraProbe(self.image)

    def test_real_registry_dispatch_and_constructor_return_same_attached_camera(self):
        p=self.probe();camera=[r for r in p.registry() if r['name']=='camera']
        self.assertEqual(camera,[{'name':'camera','kind':0x5f6d6163}])
        result=p.create();self.assertEqual(p.r(p.scene+0x238,'Q')[0],p.camera)
        self.assertEqual(result['near'],1);self.assertEqual(result['far'],3000)
        self.assertAlmostEqual(result['fovRadians'],math.pi*.4,places=6)

    def test_auxiliary_setup_changes_its_own_camera_not_main_near_plane(self):
        p=self.probe();main=p.create();aux=p.auxiliary_setup()
        self.assertAlmostEqual(aux['near'],.1,places=6)
        self.assertAlmostEqual(aux['fovRadians'],math.pi/4,places=6)
        self.assertEqual(p.parameters(),main);self.assertNotEqual(p.camera,p.auxiliary_camera)

    def test_full_viewport_updates_original_main_aspect_and_fov(self):
        p=self.probe();result=p.viewport([0,0,1136,640],640)
        self.assertAlmostEqual(result['aspect'],1136/640,places=6)
        self.assertAlmostEqual(result['fovRadians'],math.pi/4,places=6)
        # This writer does not change the constructor near or far fields.
        self.assertEqual((result['near'],result['far']),(1,3000))
        matrix=p.projection();self.assertEqual(matrix[11],-1)
        self.assertAlmostEqual(matrix[0]*1136/640,matrix[5],places=5)
        def depth(z):return (matrix[10]*z+matrix[14])/-z
        self.assertAlmostEqual(depth(-result['near']),-1,places=5)
        self.assertAlmostEqual(depth(-result['far']),1,places=5)

    def test_original_partial_viewport_and_scale_branch_are_not_constant_fov(self):
        for unscaled,scale,degrees in [(True,1,40),(False,1,40),(False,2,20)]:
            with self.subTest(unscaled=unscaled,scale=scale):
                result=self.probe().viewport([10,20,1146,660],960,scale,unscaled)
                self.assertAlmostEqual(result['fovRadians']*180/math.pi,degrees,delta=1e-5)

if __name__=='__main__':unittest.main()
