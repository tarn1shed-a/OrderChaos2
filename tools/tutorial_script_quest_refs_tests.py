"""Source-exact finite audit; original runtime state chains are not re-run."""
import ast,hashlib,json,os,unittest
from tutorial_script_quest_refs_probe import ROOT,SO,AREA,ROWS
PRIVATE=SO.is_file() and (AREA/'0x3e7638-decompile.json').is_file() and os.environ.get('OC2_SCRIPT_QUEST_REFS_PUBLIC_ONLY')!='1'
class PublicChecks(unittest.TestCase):
    def test_01_previous212_remain_exact(self):
        path=AREA/'before-frozen.json'
        if not path.is_file():self.skipTest('Private before-freeze manifest absent')
        rows=json.loads(path.read_text());self.assertEqual(len(rows),212)
        for name,r in rows.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),r['sha256'],name)
        for name,digest in {'native_character_entry.py':'77a2f2b69bd846b1b96cbc68aee732c68f6959370c3dfe8826ddb08aae8cdd8a',
            'standard_abc.py':'a93057561936010e5adf0249cc569b80e8c5924e58882e349ef368c599ba7152'}.items():
            p=ROOT/'tools'/name
            if p.exists():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),digest)
        p=ROOT/'tools/tutorial_npc_bitmap_domain_probe.py'
        if p.exists():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'3d76d7b7bfbc2a105d22979212beb1d007ba1a65dd7e04cbfd73f5911d090772')
    def test_02_static_only_no_runtime_or_network(self):
        code=(ROOT/'tools/tutorial_script_quest_refs_probe.py').read_text();tree=ast.parse(code)
        names={n.names[0].name.split('.')[0]for n in ast.walk(tree)if isinstance(n,ast.Import)}
        self.assertTrue(names.isdisjoint({'socket','requests','urllib','http','subprocess'}))
        self.assertNotIn('SourcePhysics',code);self.assertNotIn('emu_start',code)
        self.assertEqual(len(ROWS),14)

@unittest.skipUnless(PRIVATE,'Private original/Ghidra source absent or public-only mode')
class SourceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_script_quest_refs_probe import run
        cls.r=run();cls.rows=cls.r['callers']
    def test_03_fourteen_real_direct_calls_only(self):
        self.assertEqual(len(self.rows),14)
        self.assertEqual(len(self.r['excludedMetadata']),2)
        self.assertEqual({r['section']for r in self.r['excludedMetadata']},{'.eh_frame','.eh_frame_hdr'})
    def test_04_exact_source_call_instructions_and_cleanup(self):
        from analyze_native_resources import NativeImage
        n=NativeImage(SO.read_bytes())
        for row in self.rows:
            p=row['native'];raw=n.read(int(p['functionStart'],16),p['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),p['sha256'])
            i=next(n.disassembler.disasm(n.read(int(p['getterCall'],16),4),int(p['getterCall'],16)))
            self.assertEqual((i.mnemonic,i.op_str),('bl','#0xc99370'))
            self.assertLess(int(p['tableVirtualLookup'],16),int(p['lastCleanupCall'],16))
    def test_05_script_local_is_only_declared_and_initialized(self):
        for row in self.rows:
            self.assertEqual(row['scriptFieldOffset'],0x70)
            refs=row['decompilerScriptLocalReferences'];self.assertEqual(len(refs),2)
            self.assertTrue(refs[0]['text'].startswith('undefined *'))
            self.assertTrue(refs[1]['text'].startswith(row['scriptLocal']+' = '))
    def test_06_row_forwarding_within_lifetime_is_only_cleanup(self):
        for row in self.rows:
            self.assertTrue(row['rowLifetimeForwarding'])
            self.assertTrue(all(r['text']=='FUN_003e78a4('+row['rowLocal']+');'for r in row['rowLifetimeForwarding']))
        row=next(r for r in self.rows if r['address']=='0x4a24bc')
        self.assertEqual(len(row['rowLifetimeForwarding']),2)
    def test_07_native_script_slot_only_has_prelookup_empty_store(self):
        for row in self.rows:
            n=row['native'];self.assertEqual(n['scriptDirectReadsInLookupLifetime'],[])
            self.assertEqual(len(n['directStackTouches']),1)
            t=n['directStackTouches'][0];self.assertFalse(t['read']);self.assertFalse(t['withinRowLookupLifetime'])
            self.assertLess(int(t['pc'],16),int(n['tableVirtualLookup'],16))
    def test_08_reused_original_decompilation_receipts(self):
        rows=json.loads((AREA/'reused-decompilations.json').read_text());self.assertEqual(len(rows),4)
        for r in rows:self.assertEqual(hashlib.sha256((ROOT/r['from']).read_bytes()).hexdigest(),r['sourceSHA256'])
        self.assertEqual({r['address']for r in rows},{'0x49e558','0xa43d40','0xa4572c','0xa46b8c'})
    def test_09_no_global_absence_or_authority_is_claimed(self):
        for key in ('scriptLoaderIdentified','scriptBodyRecovered','wholeProgramAbsenceProved','originalCPUChainRerun',
                    'packetsSent','savesOrProductionAccessed'):self.assertFalse(self.r[key])
        self.assertTrue(all(not r['scriptToLoaderOrCallIdentified']for r in self.rows))

if __name__=='__main__':unittest.main()
