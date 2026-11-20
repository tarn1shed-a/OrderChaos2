"""Real extraction and preservation checks without original resources."""
import hashlib
import io
import json
import tarfile
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from deployment_tests import bootstrap
from runtime_delta import package, inspect


def digest(raw):return hashlib.sha256(raw).hexdigest()


class RuntimeDeltaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.cache=self.root/'cache';self.cache.mkdir()
        (self.root/'tools').mkdir();(self.root/'deploy/node_modules').mkdir(parents=True)
        self.pinned={'nativeSHA256':digest(b'original-library'),'files':{'prototype/public/game.js':digest(b'reviewed')}}
        (self.root/'tools/local_mvp_runtime.json').write_text(json.dumps(self.pinned))
        (self.root/'tools/worker.py').write_bytes(b'host')
        self.old={'prototype/public/game.js':b'reviewed','native-inputs/library.so':b'original-library'}
        self.new={**self.old,'game-data/converted/original-fire.json':b'{"source":true}'}
        self.base=self.archive(self.cache/'base.tar.gz',self.old)
        target=self.cache/(bootstrap.sha(self.base)+'.tar.gz');self.base.rename(target);self.base=target
        self.complete=self.archive(self.root/'complete.tar.gz',self.new)
        self.patch=patch.object(bootstrap,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def archive(self,path,files,extra=None):
        manifest={'format':'oc2-private-runtime-v1','runtimeIdentity':self.pinned,'pythonFiles':{'tools/worker.py':digest(b'host')},'localSavesImported':False,
                  'files':{name:{'bytes':len(raw),'sha256':digest(raw)}for name,raw in files.items()}}
        payload={**files,'bundle-manifest.json':(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode(),**(extra or {})}
        self.pack(path,payload);return path

    def pack(self,path,payload):
        with tarfile.open(path,'w:gz')as archive:
            for name,raw in payload.items():
                member=tarfile.TarInfo(name);member.size=len(raw);archive.addfile(member,io.BytesIO(raw))

    def delta(self):
        import runtime_delta
        path=self.cache/'delta.tar.gz'
        with patch.object(runtime_delta,'ROOT',self.root):
            out=self.root/'analysis/raw/delta.tar.gz';result=package(self.base,self.complete,out)
        path.write_bytes(out.read_bytes());return path,result

    def mutate(self,path,change):
        with tarfile.open(path)as archive:payload={m.name:archive.extractfile(m).read()for m in archive.getmembers()}
        change(payload);self.pack(path,payload)

    def test_delta_and_full_extract_identically_without_touching_cached_files_or_saves(self):
        path,result=self.delta();self.assertEqual(result['newFiles'],1)
        saved=self.root/'data/saves/characters.json';saved.parent.mkdir(parents=True);saved.write_bytes(b'unchanged-save')
        before={p.name:bootstrap.sha(p)for p in self.cache.iterdir()}
        a,b=self.root/'delta-out',self.root/'full-out'
        bootstrap.extract_verified(path,bootstrap.sha(path),a);bootstrap.extract_verified(self.complete,bootstrap.sha(self.complete),b)
        for name in [*self.new,'bundle-manifest.json']:self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
        self.assertFalse((a/'bundle-base.json').exists());self.assertEqual(saved.read_bytes(),b'unchanged-save')
        self.assertEqual(before,{p.name:bootstrap.sha(p)for p in self.cache.iterdir()})

    def test_missing_or_corrupt_cached_base_keeps_current_runtime(self):
        path,_=self.delta();dest=self.root/'live';dest.mkdir();(dest/'keep').write_bytes(b'old-live')
        self.base.write_bytes(b'bad-base')
        with self.assertRaisesRegex(ValueError,'base is unavailable'):bootstrap.extract_verified(path,bootstrap.sha(path),dest)
        self.assertEqual((dest/'keep').read_bytes(),b'old-live')

    def test_delta_cannot_change_base_metadata(self):
        path,_=self.delta()
        def change(payload):
            m=json.loads(payload['bundle-manifest.json']);m['files']['prototype/public/game.js']['sha256']='0'*64;payload['bundle-manifest.json']=json.dumps(m).encode()
        self.mutate(path,change)
        with self.assertRaisesRegex(ValueError,'cannot replace'):bootstrap.extract_verified(path,bootstrap.sha(path),self.root/'out')

    def test_changed_new_bytes_and_extra_members_are_refused(self):
        path,_=self.delta();self.mutate(path,lambda p:p.update({'game-data/converted/original-fire.json':b'wrong'}))
        with self.assertRaisesRegex(ValueError,'identity differs'):bootstrap.extract_verified(path,bootstrap.sha(path),self.root/'out')
        self.mutate(path,lambda p:p.update({'extra.json':b'{}'}))
        with self.assertRaisesRegex(ValueError,'member set'):bootstrap.extract_verified(path,bootstrap.sha(path),self.root/'out')

    def test_base_reference_cannot_escape_cache_or_chain_to_another_delta(self):
        path,_=self.delta()
        self.mutate(path,lambda p:p.update({'bundle-base.json':json.dumps({'format':'oc2-private-runtime-delta-v1','baseArchiveSHA256':'../../bad'}).encode()}))
        with self.assertRaisesRegex(ValueError,'base reference'):bootstrap.extract_verified(path,bootstrap.sha(path),self.root/'out')
        chained=self.archive(self.cache/'chain.tar.gz',self.old,{'bundle-base.json':b'{}'});sha=bootstrap.sha(chained);chained.rename(self.cache/(sha+'.tar.gz'))
        self.mutate(path,lambda p:p.update({'bundle-base.json':json.dumps({'format':'oc2-private-runtime-delta-v1','baseArchiveSHA256':sha}).encode()}))
        with self.assertRaisesRegex(ValueError,'one complete'):bootstrap.extract_verified(path,bootstrap.sha(path),self.root/'out')

    def test_builder_preserves_existing_outputs_and_rejects_modified_runtime(self):
        import runtime_delta
        with patch.object(runtime_delta,'ROOT',self.root):
            output=self.root/'analysis/raw/delta.tar.gz';package(self.base,self.complete,output)
            with self.assertRaisesRegex(ValueError,'preserved'):package(self.base,self.complete,output)
            changed=self.archive(self.root/'changed.tar.gz',{**self.new,'prototype/public/game.js':b'changed'})
            with self.assertRaisesRegex(ValueError,'cannot replace'):package(self.base,changed,self.root/'analysis/raw/second.tar.gz')


class RuntimeDeltaV2Tests(unittest.TestCase):
    archive = RuntimeDeltaTests.archive
    pack = RuntimeDeltaTests.pack
    mutate = RuntimeDeltaTests.mutate

    def setUp(self):
        RuntimeDeltaTests.setUp(self)
        import runtime_delta
        self.worker = self.root/'tools/worker.py'
        self.worker.write_bytes(b'new-host')
        self.new = dict(self.old)
        self.new.update({'new/a-base-copy':self.old['prototype/public/game.js'],
                         'new/b-payload':b'new-content', 'new/c-alias':b'new-content'})
        self.complete=self.archive(self.root/'complete-v2.tar.gz',self.new)
        with tarfile.open(self.complete)as packed:
            payload={m.name:packed.extractfile(m).read()for m in packed.getmembers()}
        manifest=json.loads(payload['bundle-manifest.json'])
        manifest['pythonFiles']={'tools/worker.py':digest(b'new-host')}
        payload['bundle-manifest.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
        self.pack(self.complete,payload)
        self.canonical_manifest=payload['bundle-manifest.json']
        self.out=self.root/'analysis/raw/v2.tar.gz'
        self.cache_patch=patch.object(bootstrap,'BUNDLE_CACHE',self.cache)
        self.cache_patch.start();self.addCleanup(self.cache_patch.stop)
        # Package and extraction use the same actual protocol source.
        (self.root/'deploy').mkdir(exist_ok=True)
        shutil.copyfile(Path(bootstrap.__file__),self.root/'deploy/bootstrap.py')
        self.delta_root=patch.object(runtime_delta,'ROOT',self.root)
        self.delta_root.start();self.addCleanup(self.delta_root.stop)
        self.saved=self.root/'data/saves/characters.json'
        self.saved.parent.mkdir(parents=True);self.saved.write_bytes(b'keep-test-save')
        self.dest=self.root/'old-runtime';self.dest.mkdir();(self.dest/'keep').write_bytes(b'old-runtime')

    def v2(self):
        import runtime_delta
        return runtime_delta.package(self.base,self.complete,self.out,version=2)

    def reject(self, pattern=None):
        before={p.name:bootstrap.sha(p)for p in self.cache.iterdir()}
        with self.assertRaisesRegex(ValueError,pattern or '.'):
            bootstrap.extract_verified(self.out,bootstrap.sha(self.out),self.dest)
        self.assertEqual((self.dest/'keep').read_bytes(),b'old-runtime')
        self.assertEqual(self.saved.read_bytes(),b'keep-test-save')
        self.assertEqual(before,{p.name:bootstrap.sha(p)for p in self.cache.iterdir()})

    def ref_mutate(self, edit):
        def change(p):
            reference=json.loads(p['bundle-base.json']);edit(reference)
            p['bundle-base.json']=(json.dumps(reference,sort_keys=True,indent=2)+'\n').encode()
        self.mutate(self.out,change)

    def target_mutate(self,edit):
        def change(p):
            manifest=json.loads(p['bundle-manifest.json']);edit(manifest)
            raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
            reference=json.loads(p['bundle-base.json']);reference['targetManifestSHA256']=digest(raw)
            p['bundle-manifest.json']=raw;p['bundle-base.json']=json.dumps(reference).encode()
        self.mutate(self.out,change)

    def test_v2_full_tree_aliases_and_python_rebind_equal_complete(self):
        result=self.v2();self.assertEqual(result['payloadFiles'],1);self.assertEqual(result['aliases'],2)
        before={p.name:bootstrap.sha(p)for p in self.cache.iterdir()}
        a,b=self.root/'v2-out',self.root/'full-out'
        bootstrap.extract_verified(self.out,bootstrap.sha(self.out),a)
        bootstrap.extract_verified(self.complete,bootstrap.sha(self.complete),b)
        for name in [*self.new,'bundle-manifest.json']:
            self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            self.assertFalse((a/name).is_symlink())
        self.assertEqual((a/'bundle-manifest.json').read_bytes(),self.canonical_manifest)
        self.assertFalse((a/'bundle-base.json').exists())
        self.assertEqual(before,{p.name:bootstrap.sha(p)for p in self.cache.iterdir()})
        self.assertEqual(self.saved.read_bytes(),b'keep-test-save')

    def test_cache0_v2_reads_existing_base_without_cache_writes(self):
        self.v2();before={p.name:bootstrap.sha(p)for p in self.cache.iterdir()}
        with patch.dict('os.environ',{'OC2_BUNDLE_CACHE':'0','OC2_BUNDLE_SHA256':bootstrap.sha(self.out),
                                      'OC2_BUNDLE_PATH':str(self.out)},clear=True):
            self.assertEqual(bootstrap.archive_from_env(),(self.out,bootstrap.sha(self.out)))
            bootstrap.extract_verified(self.out,bootstrap.sha(self.out),self.root/'actual-out')
        self.assertEqual(before,{p.name:bootstrap.sha(p)for p in self.cache.iterdir()})

    def test_v2_does_not_relax_v1_python_pin_gate(self):
        import runtime_delta
        with self.assertRaisesRegex(ValueError,'cannot replace'):
            runtime_delta.package(self.base,self.complete,self.out)

    def test_alias_chain_rejected(self):
        self.v2();self.ref_mutate(lambda r:r['aliases']['new/c-alias'].update(path='new/a-base-copy'))
        self.reject('aliases differ')

    def test_alias_source_metadata_mismatch_rejected(self):
        self.v2();self.ref_mutate(lambda r:r['aliases']['new/a-base-copy'].update(path='native-inputs/library.so'))
        self.reject('aliases differ')

    def test_alias_path_escape_rejected(self):
        self.v2();self.ref_mutate(lambda r:r['aliases']['new/c-alias'].update(path='../outside'))
        self.reject('Unsafe')

    def test_missing_actual_payload_rejected(self):
        self.v2();self.mutate(self.out,lambda p:p.pop('new/b-payload'))
        self.reject('member set')

    def test_unlisted_or_redundant_payload_rejected(self):
        self.v2();self.mutate(self.out,lambda p:p.update({'new/c-alias':b'new-content'}))
        self.reject('member set')

    def test_corrupt_payload_rejected(self):
        self.v2();self.mutate(self.out,lambda p:p.update({'new/b-payload':b'wrong'}))
        self.reject('identity differs')

    def test_base_archive_missing_or_changed_rejected(self):
        self.v2();self.ref_mutate(lambda r:r.update(baseArchiveSHA256='0'*64))
        self.reject('base is unavailable')

    def test_base_manifest_pin_rejected(self):
        self.v2();self.ref_mutate(lambda r:r.update(baseManifestSHA256='0'*64))
        self.reject('base manifest differs')

    def test_target_manifest_pin_rejected(self):
        self.v2();self.ref_mutate(lambda r:r.update(targetManifestSHA256='0'*64))
        self.reject('target manifest differs')

    def test_removal_rejected(self):
        self.v2();self.target_mutate(lambda m:m['files'].pop('prototype/public/game.js'))
        self.reject('replace or remove')

    def test_existing_payload_change_rejected(self):
        self.v2();self.target_mutate(lambda m:m['files']['prototype/public/game.js'].update(sha256='0'*64))
        self.reject('replace or remove')

    def test_image_host_mismatch_rejected(self):
        self.v2();self.worker.write_bytes(b'wrong-image-host')
        self.reject('Physics host modules differ')

    def test_reference_extra_or_duplicate_field_rejected(self):
        self.v2();self.ref_mutate(lambda r:r.update(extra=True));self.reject('Invalid private delta v2 reference')

    def test_logical_tree_bytes_limit_rejected_with_aliases(self):
        self.v2();self.target_mutate(lambda m:m['files']['new/c-alias'].update(bytes=2**31,sha256='f'*64))
        self.reject('Logical private runtime')

    def test_logical_tree_member_count_limit_rejected_with_aliases(self):
        self.v2()
        def inflate(m):
            row=m['files']['new/b-payload']
            m['files'].update({f'new/many/{i}':dict(row)for i in range(20000)})
        self.target_mutate(inflate);self.reject('Logical private runtime')


if __name__=='__main__':unittest.main()
