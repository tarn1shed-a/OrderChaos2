// Derived host-module pins and Docker allowlist; no original resource rewrite.
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve,dirname,posix} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

export function synchronizeSourceContent(root,{write=false,docker=true}={}){
  const manifest=resolve(root,'tools/source_world_python.json'),source=readFileSync(manifest,'utf8'),data=JSON.parse(source);
  if(data.format!=='oc2-source-world-python-closure-v1'||!Array.isArray(data.content?.browserModules))throw Error('Canonical source content declaration required');
  for(const row of data.content.browserModules){
    if(!/^deploy\/[a-z0-9_]+\.mjs$/.test(row.path)||row.url!=='/__delivery/'+posix.basename(row.path))throw Error('Explicit browser module identity required');
    const bytes=readFileSync(resolve(root,row.path));row.bytes=bytes.length;row.sha256=createHash('sha256').update(bytes).digest('hex');
  }
  const expected=JSON.stringify(data,null,2)+'\n',changed=[];
  if(source!==expected){changed.push('tools/source_world_python.json');if(write)writeFileSync(manifest,expected);}
  if(docker){
    const path=resolve(root,'.dockerignore'),text=readFileSync(path,'utf8'),start='# BEGIN REVIEWED SOURCE WORLD',end='# END REVIEWED SOURCE WORLD';
    if(text.split(start).length!==2||text.split(end).length!==2)throw Error('Reviewed Docker closure anchor differs');
    const block=text.split(start)[1].split(end)[0];
    const retained=block.split('\n').filter(line=>line&&!line.startsWith('!tools/'));
    const paths=['tools/source_world_python.json',...Object.keys(data.files)].sort(),parents=new Set(['tools/']);
    for(const path of paths){if(!/^tools\/[a-zA-Z0-9_./-]+$/.test(path)||path.split('/').includes('..'))throw Error('Unsafe native code member');let parent=posix.dirname(path);while(parent!=='.'){parents.add(parent+'/');parent=posix.dirname(parent);}}
    const generated='\n'+[...retained,...[...parents].sort().map(p=>'!'+p),...paths.map(p=>'!'+p)].join('\n')+'\n';
    const next=text.replace(start+block+end,start+generated+end);
    if(text!==next){changed.push('.dockerignore');if(write)writeFileSync(path,next);}
  }
  if(changed.length&&!write)throw Error('Derived source content is stale: '+changed.join(', ')+'; run node deploy/source_content_build.mjs --write');
  return {modules:data.content.browserModules.length,nativeFiles:Object.keys(data.files).length,changed};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const args=process.argv.slice(2);if(args.some(a=>!['--write','--check','--modules-only'].includes(a)))throw Error('Unknown content build option');
  console.log(JSON.stringify(synchronizeSourceContent(resolve(dirname(fileURLToPath(import.meta.url)),'..'),{write:args.includes('--write'),docker:!args.includes('--modules-only')})));
}
