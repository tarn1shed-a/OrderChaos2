import copy,json,struct,tempfile,unittest
from pathlib import Path
from navmesh import decode_nav,build_graph
from native_ai import recover_ai,verify_ai_native
from resource_packs import ResourceArchive,DEFAULT_SOURCE,index
from skill_attachments import decode_ftable
from skill_attachments_tests import table
ROOT=Path(__file__).resolve().parents[1]

def tile_bytes(x=0,height=0):
    header=struct.pack('<IIii10I10f',0x444e4156,4,x,0,0,1,4,12,1,0,2,2,0,1,1.8,.1,.9,x*10,height,0,x*10+10,height+2,10,4)
    vertices=struct.pack('<12f',x*10,height,10,x*10+10,height,10,x*10+10,height,0,x*10,height,0)
    poly=struct.pack('<I12HHBB',0,0,1,2,3,0,0,0x8002,0x8000,0x8006,0x8004,0,0,1,4,0)
    return bytearray(header+vertices+poly+bytes(144)+struct.pack('<4H',0,0,0,2)+bytes([2,3,1,17,3,0,1,5])+bytes(32))
class NavmeshTests(unittest.TestCase):
    def test_v4_layout_consumes_entire_payload_and_pairs_only_explicit_source_portals(self):
        a=decode_nav(tile_bytes());b=decode_nav(tile_bytes(1));graph=build_graph([a,b])
        self.assertEqual(a['verification']['bytesConsumed'],368);self.assertEqual(graph[0]['edges'][0]['to'],1)
        self.assertEqual(graph[1]['edges'][0]['to'],0)
        c=decode_nav(tile_bytes(1,10));self.assertEqual(build_graph([a,c])[0]['edges'],[])
        b['polygons'][0]['neighbours']=[0]*4;self.assertEqual(build_graph([a,b])[0]['edges'],[])
        with self.assertRaises(ValueError):build_graph([a,a])
    def test_corrupt_counts_indices_flags_details_version_and_nonfinite_vertices_reject(self):
        source=tile_bytes()
        for b in [source[:-1],source+bytes(4)]:
            with self.assertRaises(ValueError):decode_nav(b)
        for offset,fmt,value in [(4,'I',7),(20,'I',1000000),(96,'f',float('nan')),(148,'H',65535),(172,'H',2),(174,'B',7),(326,'H',90),(328,'B',10)]:
            b=bytearray(source);struct.pack_into('<'+fmt,b,offset,value)
            with self.assertRaises(ValueError):decode_nav(b)
    def test_npc_key_byte_and_ushort_physical_widths_do_not_shift_following_fields(self):
        row={'id':19,'key':0xffffffff,'short':65535,'byte':255,'last':1.25}
        data=table(list(row),'ukhcf',[row]);self.assertEqual(decode_ftable(data)['rows'],[row])
        with self.assertRaises(ValueError):decode_ftable(data[:-1])
    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').exists(),'Original navigation remains local')
    def test_real_nine_tiles_full_source_proof_and_npc_table_boundary(self):
        rows=index(DEFAULT_SOURCE);archives={}
        def extract(path):
            matches=[r for r in rows if r['path']==path and r['pack'] in {'tutorial.bin','tables.bin'}]
            self.assertEqual(len(matches),1);pack=matches[0]['pack']
            if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
            return archives[pack].read(path)
        with tempfile.TemporaryDirectory() as temp:
            result=recover_ai(extract,temp);p=json.loads((Path(temp)/'maps/navigation.json').read_text())
            self.assertEqual(len(p['nodes']),381);self.assertEqual(sum(len(n['edges']) for n in p['nodes']),706)
            self.assertEqual(len(result['wolfCandidates']),57);self.assertEqual(result['previewOriginalWolfSpawns'],[])
            self.assertEqual((result['nonzeroAIPlans'],result['scriptedProtos']),(0,2030))
            self.assertTrue(all(t['verification']['bytesConsumed']==t['verification']['fileSize'] for t in p['tiles']))
    @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').exists(),'Original native code remains local')
    def test_native_movement_enum_and_server_combat_descriptors_are_pinned(self):
        from analyze_native_resources import NativeImage
        p=verify_ai_native(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
        self.assertEqual(p['MoveActionTypes']['values']['chase'],2);self.assertEqual(p['MoveActionTypes']['values']['goBack'],3)
        self.assertEqual([f['name'] for f in p['GS2C_CombatInfo']['fields']],['guid','combat'])
if __name__=='__main__':unittest.main()
