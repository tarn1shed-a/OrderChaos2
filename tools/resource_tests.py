import io
import lzma
import zlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from resource_packs import (entries, read_entry, safe_output, ResourceArchive,
                            normalize_resource_name, resource_name_hash)
from texture_decode import decode

class ResourceTests(unittest.TestCase):
    def make_indexed_pack(self, directory, with_index=True):
        path = Path(directory) / 'sample.bin'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('an', b'first collision entry')
            archive.writestr('ba', b'second collision entry')
            records = archive.infolist()
        data = bytearray(path.read_bytes())
        index = bytearray(struct.pack('<4sI', b'\x01IKP', len(records)))
        name_offset = 0
        for record in records:
            data[record.header_offset:record.header_offset+4] = b'GBMP'
            # Both ASCII names independently have hash 1371: 97*13+110, 98*13+97.
            packed = (record.compress_type << 16) | (30 + len(record.filename))
            index.extend(struct.pack('<7I', 1371, record.header_offset, name_offset,
                                     packed, record.file_size, record.compress_size,
                                     record.flag_bits))
            name_offset += 4
        path.write_bytes(data)
        if with_index:
            path.with_name('sample_i.bin').write_bytes(index)
        return path

    def test_native_name_normalization_and_known_hash(self):
        self.assertEqual(normalize_resource_name('./MODEL\\Elf.BDAE'), 'model/elf.bdae')
        self.assertEqual(normalize_resource_name('Ä/FILE'), 'Ä/file')
        self.assertEqual(normalize_resource_name('././FILE'), './file')
        self.assertEqual(resource_name_hash('an'), 1371)
        self.assertEqual(resource_name_hash('ba'), 1371)
        self.assertEqual(resource_name_hash('é'), 4294966416)
        self.assertEqual(resource_name_hash('model/npc/character/elf/female/oc2_elf_f_body_01.bdae'), 985527393)
        with self.assertRaises(ValueError): normalize_resource_name('file\0other')

    def test_native_hash_collision_does_not_alias_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = ResourceArchive(self.make_indexed_pack(tmp))
            self.assertTrue(archive.index_validation['all_fields_match'])
            self.assertEqual(archive.read('./AN'), b'first collision entry')
            self.assertEqual(archive.read('BA'), b'second collision entry')
            with self.assertRaises(KeyError): archive.read('missing')

    def test_original_index_rejects_each_inconsistent_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_indexed_pack(tmp)
            index = path.with_name('sample_i.bin')
            valid = index.read_bytes()
            for field in range(7):
                with self.subTest(field=field):
                    broken = bytearray(valid)
                    broken[8 + field * 4] ^= 1
                    index.write_bytes(broken)
                    with self.assertRaises(ValueError): ResourceArchive(path)
            index.write_bytes(valid[:-1])
            with self.assertRaises(ValueError): ResourceArchive(path)

    def test_archive_without_optional_index_uses_local_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = ResourceArchive(self.make_indexed_pack(tmp, with_index=False))
            self.assertFalse(archive.index_validation['present'])
            self.assertEqual(archive.read('an'), b'first collision entry')

    def test_pack_crc_and_all_observed_compressions(self):
        for method in [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_LZMA]:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/'test.bin'; payload = b'known resource data\0'*100
                with zipfile.ZipFile(p,'w',compression=method) as z:z.writestr('model/sample.bin',payload)
                data=p.read_bytes();p.write_bytes(b'GBMP'+data[4:])
                e=list(entries(p));self.assertEqual(len(e),1);self.assertEqual(read_entry(e[0],Path(tmp)),payload)
                self.assertEqual(ResourceArchive(p).read('./MODEL/SAMPLE.BIN'), payload)
                broken=dict(e[0]);broken['crc']^=1
                with self.assertRaises(ValueError):read_entry(broken,Path(tmp))

    def test_no_archive_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['../outside','/absolute','folder/../../bad','x\\..\\bad','C:/bad']:
                with self.assertRaises(ValueError):safe_output(root,name)
            self.assertEqual(safe_output(root,'model/npc/elf.bdae'),root/'model/npc/elf.bdae')

    def test_no_eos_lzma_uses_declared_output_bound_and_still_requires_crc(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload=b'FTABLE bounded output\0'*40
            filters=[{'id':lzma.FILTER_LZMA1,'dict_size':1<<23,'lc':3,'lp':0,'pb':2}]
            packed=bytes([9,4,5,0,0x5d])+struct.pack('<I',1<<23)+lzma.compress(payload+b'x',format=lzma.FORMAT_RAW,filters=filters)
            Path(tmp,'sample.bin').write_bytes(packed)
            entry={'pack':'sample.bin','path':'table','offset':0,'compressed':len(packed),'size':len(payload),'crc':zlib.crc32(payload),'flags':0,'method':14}
            self.assertEqual(read_entry(entry,Path(tmp)),payload)
            with self.assertRaises(ValueError):read_entry({**entry,'crc':entry['crc']^1},Path(tmp))
            with self.assertRaises(ValueError):read_entry({**entry,'flags':2},Path(tmp))
            Path(tmp,'sample.bin').write_bytes(packed[:15])
            with self.assertRaises((ValueError,lzma.LZMAError)):read_entry(entry,Path(tmp))

    def test_etc1_header_and_split_alpha(self):
        # ETC1 all-zero block yields an opaque near-black constant 4x4 image.
        h=struct.pack('<13I',52,4,4,0,0x36,8,4,0,0,0,0,int.from_bytes(b'PVR!','little'),1)
        pvr=h+bytes(8); img=decode(pvr);self.assertEqual(img.size,(4,4));self.assertEqual(img.getpixel((0,0))[3],255)
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as z:z.writestr('rgb.pvr',pvr);z.writestr('alpha.pvr',pvr)
        result=decode(blob.getvalue());self.assertEqual(result.getpixel((0,0))[3],img.getpixel((0,0))[0])
        with self.assertRaises(ValueError):decode(h)

if __name__=='__main__':unittest.main()
