import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from resource_packs import entries, read_entry, safe_output
from texture_decode import decode

class ResourceTests(unittest.TestCase):
    def test_pack_crc_and_all_observed_compressions(self):
        for method in [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_LZMA]:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/'test.bin'; payload = b'known resource data\0'*100
                with zipfile.ZipFile(p,'w',compression=method) as z:z.writestr('model/sample.bin',payload)
                data=p.read_bytes();p.write_bytes(b'GBMP'+data[4:])
                e=list(entries(p));self.assertEqual(len(e),1);self.assertEqual(read_entry(e[0],Path(tmp)),payload)
                broken=dict(e[0]);broken['crc']^=1
                with self.assertRaises(ValueError):read_entry(broken,Path(tmp))

    def test_no_archive_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['../outside','/absolute','folder/../../bad','x\\..\\bad','C:/bad']:
                with self.assertRaises(ValueError):safe_output(root,name)
            self.assertEqual(safe_output(root,'model/npc/elf.bdae'),root/'model/npc/elf.bdae')

    def test_etc1_header_and_split_alpha(self):
        # ETC1 all-zero block yields an opaque near-black constant 4x4 image.
        h=struct.pack('<13I',52,4,4,0,0x36,8,4,0,0,0,0,int.from_bytes(b'PVR!','little'),1)
        pvr=h+bytes(8); img=decode(pvr);self.assertEqual(img.size,(4,4));self.assertEqual(img.getpixel((0,0))[3],255)
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as z:z.writestr('rgb.pvr',pvr);z.writestr('alpha.pvr',pvr)
        result=decode(blob.getvalue());self.assertEqual(result.getpixel((0,0))[3],img.getpixel((0,0))[0])
        with self.assertRaises(ValueError):decode(h)

if __name__=='__main__':unittest.main()
