"""Real extraction and preservation checks without original resources."""
import hashlib
import io
import json
import tarfile
import tempfile
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


if __name__=='__main__':unittest.main()
