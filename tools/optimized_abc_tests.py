import struct
import unittest

from character_portraits_tests import u30, swf, abc, tag
from optimized_abc import parse_abc, disassemble, extract_abc, named_method
from resource_packs import ResourceArchive, DEFAULT_SOURCE


def fixture(code=b'\x47',signature_size=4,body_id=1):
    strings=['','C','Object','go']
    pool=b'\x01\x01\x01'+u30(len(strings))+b''.join(u30(len(s))+s.encode() for s in strings[1:])
    pool+=b'\x02\x16\0\x01\x04'+b''.join(b'\x07\x01'+u30(i) for i in [1,2,3])
    # Two methods; class C has go(), and constructor/cinit share method zero.
    definitions=b'\x02\0\x01\x01\x02\0\0\0\x01\x03\x01\0\x01\0\0\0'
    signatures=b'\x02'+u30(signature_size)+b'\0\0\0\0'+b'\x04\0\0\0\0'
    def body(mid,bytecode):
        payload=b'\x01\x01\0\x01'+u30(len(bytecode))+bytecode+b'\0\0'
        return u30(mid)+u30(len(payload))+payload
    return struct.pack('<HH',16,46)+pool+definitions+signatures+b'\x02'+body(0,b'\x47')+body(body_id,code)


class OptimizedABCTests(unittest.TestCase):
    def test_reordered_signatures_bodies_and_method_lookup(self):
        raw=fixture();p=parse_abc(raw)
        self.assertEqual(p['bytesConsumed'],len(raw))
        self.assertEqual(p['classes'][0]['name'],'C')
        self.assertEqual(len(p['signatures']),2)
        m=named_method(p,'C','go')
        self.assertEqual(m['methodId'],1)
        self.assertEqual(m['instructions'][0]['op'],'returnvoid')
        with self.assertRaisesRegex(ValueError,'missing'):named_method(p,'C','absent')

    def test_malformed_extents_duplicate_bodies_and_trailing_data(self):
        for data in [fixture()[:-1],fixture()+b'\0',fixture(signature_size=3),fixture(body_id=0),fixture(body_id=2)]:
            with self.subTest(data=data[-15:]),self.assertRaises(ValueError):parse_abc(data)
        # Bad version and an overflowing count fail before allocating tables.
        for data in [b'\0'*20,b'\x10\0\x2e\0'+b'\xff'*6]:
            with self.assertRaises(ValueError):parse_abc(data)

    def test_signed_sentinel_and_branch_boundaries(self):
        p=parse_abc(fixture())
        instructions=disassemble(b'\x25\x98\xf8\xff\xff\x0f\x47',p)
        self.assertEqual(instructions[0]['args'],[-1000])
        self.assertEqual(disassemble(b'\x10\0\0\0\x47',p)[0]['targets'],[4])
        # Target into an operand, past code, bad pool ref, unknown/truncated op.
        for code in [b'\x10\xfe\xff\xff\x47',b'\x10\x01\0\0\x47',b'\x2c\x7f\x47',b'\xff',b'\x10\0']:
            with self.subTest(code=code),self.assertRaises(ValueError):disassemble(code,p)
        # lookupswitch targets are relative to the start, not the instruction end.
        code=b'\x1b\x08\0\0\0\x08\0\0\x47'
        self.assertEqual(disassemble(code,p)[0]['targets'],[8,8])

    def test_swf_wrapper_rejects_non_swf_or_missing_block(self):
        raw=swf(['foo']);self.assertEqual(extract_abc(raw),abc(['foo']))
        duplicate=raw[:-2]+tag(300,b'\x01\0\0\0\0'+abc(['foo']))+raw[-2:]
        duplicate=duplicate[:4]+struct.pack('<I',len(duplicate))+duplicate[8:]
        with self.assertRaisesRegex(ValueError,'one optimized'):extract_abc(duplicate)
        for raw in [b'',b'FWS'+bytes(20),b'CWS'+bytes(20)]:
            with self.assertRaises(ValueError):extract_abc(raw)

    @unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file(),'Original game scripts are local-only')
    def test_original_containers_consume_eof_and_named_controls_disassemble(self):
        archive=ResourceArchive(DEFAULT_SOURCE/'ui.bin')
        for stem,counts in [('Joystick',(1888,1864)),('OperationPanel2',(169,169))]:
            data=extract_abc(archive.read(f'ui/Flash/{stem}.swf'));p=parse_abc(data)
            self.assertEqual((len(p['signatures']),len(p['bodies'])),counts)
            self.assertEqual(p['bytesConsumed'],len(data))
            if stem=='Joystick':
                rows=named_method(p,stem,'endMove')['instructions']
                self.assertIn(-1000,[a for i in rows for a in i['args']])
                rows=named_method(p,stem,'StartMove')['instructions']
                self.assertIn('stageWidth',[a for i in rows for a in i['args']])
            else:
                rows=named_method(p,stem,'onJumpPress')['instructions']
                self.assertIn('Hero_SetJumpState',[a for i in rows for a in i['args']])


if __name__=='__main__':unittest.main()
