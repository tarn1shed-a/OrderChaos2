import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {synchronizeSourceContent} from './source_content_build.mjs';
import {sourceWorldActorResource} from './source_world_runtime.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
function fixture(fn){
  const root=mkdtempSync(join(tmpdir(),'oc2-content-build-'));
  try{
    mkdirSync(join(root,'tools/nested'),{recursive:true});mkdirSync(join(root,'deploy'));
    const code='original calculation\n',host='export const host=1;\n';
    writeFileSync(join(root,'tools/nested/core.py'),code);writeFileSync(join(root,'deploy/host.mjs'),host);
    const data={format:'oc2-source-world-python-closure-v1',files:{'tools/nested/core.py':sha(code)},content:{browserModules:[{url:'/__delivery/host.mjs',path:'deploy/host.mjs',bytes:0,sha256:'0'.repeat(64)}]}};
    writeFileSync(join(root,'tools/source_world_python.json'),JSON.stringify(data,null,2)+'\n');
    writeFileSync(join(root,'.dockerignore'),'**\n# BEGIN REVIEWED SOURCE WORLD\n!deploy/world_route/route.mjs\n!tools/stale.py\n# END REVIEWED SOURCE WORLD\n# unrelated policy\n');
    fn({root,data,code,host});
  }finally{rmSync(root,{recursive:true,force:true});}
}
test('one declaration generates exact module pins and the native allowlist without rewriting calculations',()=>fixture(({root,data,code,host})=>{
  assert.throws(()=>synchronizeSourceContent(root),/stale/);
  const changed=synchronizeSourceContent(root,{write:true});assert.equal(changed.nativeFiles,1);
  const next=JSON.parse(readFileSync(join(root,'tools/source_world_python.json')));
  assert.deepEqual(next.files,data.files);assert.equal(next.content.browserModules[0].sha256,sha(host));
  const docker=readFileSync(join(root,'.dockerignore'),'utf8');
  for(const line of ['!tools/','!tools/nested/','!tools/nested/core.py','!tools/source_world_python.json','!deploy/world_route/route.mjs','# unrelated policy'])assert.ok(docker.split('\n').includes(line));
  assert.ok(!docker.includes('!tools/stale.py'));assert.equal(readFileSync(join(root,'tools/nested/core.py'),'utf8'),code);
  assert.deepEqual(synchronizeSourceContent(root).changed,[]);
  writeFileSync(join(root,'deploy/host.mjs'),host+'// changed\n');assert.throws(()=>synchronizeSourceContent(root),/stale/);
}));
test('an escaping host module cannot become a generated resource pin',()=>fixture(({root,data})=>{
  data.content.browserModules[0].path='deploy/../../private.mjs';
  writeFileSync(join(root,'tools/source_world_python.json'),JSON.stringify(data));assert.throws(()=>synchronizeSourceContent(root,{write:true}),/identity/);
}));
test('both original actor closures require their own exact superseded provenance',()=>{
  const row={url:'/__delivery/player_choice_scene.mjs',bytes:1,sha256:'1'.repeat(64)},current={bytes:2,sha256:'2'.repeat(64)};
  const catalog={resources:{['public:'+row.url]:{...current,superseded:[{plan:'actors',planRef:'runtime:actors.json',bytes:row.bytes,sha256:row.sha256},{plan:'ownActors',planRef:'sha256:own',bytes:row.bytes,sha256:row.sha256}]}}};
  assert.deepEqual(sourceWorldActorResource(catalog,row,'runtime:actors.json'),{url:row.url,...current});
  assert.deepEqual(sourceWorldActorResource(catalog,row,'sha256:own','ownActors'),{url:row.url,...current});
  assert.throws(()=>sourceWorldActorResource(catalog,row,'sha256:own'),/not declared/);
  assert.throws(()=>sourceWorldActorResource(catalog,{...row,bytes:3},'runtime:actors.json'),/not declared/);
  assert.throws(()=>sourceWorldActorResource(catalog,{...row,url:'/missing'},'runtime:actors.json'),/missing/);
});
