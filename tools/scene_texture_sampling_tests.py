import io,json,struct,tempfile,unittest,zipfile
from pathlib import Path
from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE,ResourceArchive
from scene_texture_sampling import texture_dimensions,recover_scene_sampling,verify_native
ROOT=Path(__file__).resolve().parents[1]

def pvr(width=8,height=4,mips=True):
    count=max(width,height).bit_length()-1 if mips else 0
    size=sum(((max(1,width>>i)+3)//4)*((max(1,height>>i)+3)//4)*8 for i in range(count+1))
    return struct.pack('<13I',52,height,width,count,0x136 if mips else 0x36,size,4,0,0,0,0,0x21525650,1)+bytes(size)

def split(rgb,alpha,mode=bytes(4)):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for key,value in [('SPLIT',mode),('rgb.pvr',rgb),('alpha.pvr',alpha)]:z.writestr(key,value)
    return out.getvalue()

class SceneTextureSamplingTests(unittest.TestCase):
    def test_original_mips_are_counted_as_file_levels_without_choosing_runtime_quality(self):
        result=texture_dimensions(pvr())
        self.assertEqual((result['width'],result['height'],result['typeId'],result['fileMipLevels']),(8,4,1,4))
        self.assertEqual(texture_dimensions(pvr(mips=False))['fileMipLevels'],1)
        self.assertEqual(texture_dimensions(split(pvr(),pvr()))['container'],'ZIP-PVR2-split')
    def test_incomplete_payload_bad_mip_count_unknown_formats_and_npot_are_rejected(self):
        for offset,value in [(0,44),(8,0),(8,7),(12,1),(16,0x1136),(16,0x4036),(24,2),(28,255),(44,0),(48,6)]:
            raw=bytearray(pvr());struct.pack_into('<I',raw,offset,value)
            with self.assertRaises(ValueError):texture_dimensions(raw)
        for raw in (pvr()[:-1],pvr()+b'\0',bytes(51),pvr(7,4)):
            with self.assertRaises(ValueError):texture_dimensions(raw)
    def test_split_must_have_matching_mip_chains_and_the_observed_mode(self):
        for raw in (split(pvr(),pvr(4,4)),split(pvr(),pvr(mips=False)),split(pvr(),pvr(),b'\1\0\0\0')):
            with self.assertRaises(ValueError):texture_dimensions(raw)
    def test_changed_native_loader_is_rejected(self):
        class Changed:
            def read(self,address,size):return bytes(size)
        with self.assertRaises(ValueError):verify_native(Changed())
    @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original native library stays local')
    def test_native_pvr_factory_initialization_cache_and_setter_fingerprints(self):
        from analyze_native_resources import NativeImage
        result=verify_native(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
        self.assertEqual(result['sourceAddressName'],'Repeat');self.assertEqual(result['routineCount'],14)
    @unittest.skipUnless((DEFAULT_SOURCE/'res_scene_generator_temple_000.bin').is_file(),'Original scene resources stay local')
    def test_real_wall_uses_source_pot_repeat_and_rejects_a_changed_material_link(self):
        archives={key:ResourceArchive(DEFAULT_SOURCE/(key+'.bin')) for key in ['res','res_t','res_scene_generator_temple_000']}
        with tempfile.TemporaryDirectory() as temp:
            def extract(path):
                pack='res_t' if path.startswith('texture/') else 'res_scene_generator_temple_000' if path.startswith('model/') else 'res'
                return archives[pack].read(path)
            path=Path(temp)/'wall.bdae';path.write_bytes(extract('model/scene_generator_temple_000/god_wall_03.bdae'));reader=BDAE(path);data=reader.parse()
            profile=recover_scene_sampling(extract,reader,data)
            self.assertEqual(len(profile['materials']),3)
            for mat in profile['materials']:
                self.assertEqual((mat['addressU'],mat['addressV']),(0,0));self.assertEqual(mat['sourceTexture']['fileMipLevels'],10)
            data['materials'][0]['diffuse']='texture/wrong.tga'
            with self.assertRaises(ValueError):recover_scene_sampling(extract,reader,data)
            self.assertEqual(texture_dimensions(extract('texture/hum_city_big_tree01.tga'))['fileMipLevels'],9)

if __name__=='__main__':unittest.main()
