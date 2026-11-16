import {test}from'node:test';
import assert from'node:assert/strict';
import {mkdtempSync,writeFileSync,unlinkSync,rmSync}from'node:fs';
import {tmpdir}from'node:os';
import {join}from'node:path';
import {planDocument}from'../deploy/plan_documents.mjs';

test('planning Maps copy and alias file references without reading missing inputs',()=>{
 const dir=mkdtempSync(join(tmpdir(),'oc2-plan-doc-')),path=join(dir,'data.json');
 try{
  const doc=planDocument(path),base=new Map([['original',doc]]),copy=new Map(base);
  copy.set('alias',base.get('original'));
  assert.equal(copy.get('alias'),doc);assert.throws(()=>JSON.parse(doc),/ENOENT/);
  const data={label:'原文件',materials:[{diffuse:'/assets/source-a/image.png'}],values:[1,2,3]};
  writeFileSync(path,JSON.stringify(data));assert.deepEqual(JSON.parse(copy.get('alias')),data);
  copy.set('original',JSON.stringify({curated:true}));assert.deepEqual(JSON.parse(copy.get('original')),{curated:true});
  assert.deepEqual(JSON.parse(base.get('original')),data);assert.deepEqual(JSON.parse(copy.get('alias')),data);
  unlinkSync(path);assert.doesNotThrow(()=>new Map(copy));assert.throws(()=>String(doc),/ENOENT/);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
test('dependency scans and configured-world matching preserve exact UTF-8 string semantics',()=>{
 const dir=mkdtempSync(join(tmpdir(),'oc2-plan-scan-')),path=join(dir,'module.mjs');
 const text='// 原场景\nimport {a} from "./same.mjs";\nconst image="/assets/source-a/image.png";\nconst x=12;';
 try{
  writeFileSync(path,text);const doc=planDocument(path);
  assert.equal(String(doc),text);
  for(const regex of [/x=(\d+)/,/["'](\/assets\/[^"'`\s]+)["']/g,/(?:from\s*|import\s*(?:\(\s*)?)["']([^"']+)["']/g]){
   assert.deepEqual(doc.match(new RegExp(regex)),text.match(new RegExp(regex)));
   if(regex.global)assert.deepEqual([...doc.matchAll(new RegExp(regex))],[...text.matchAll(new RegExp(regex))]);
  }
 }finally{rmSync(dir,{recursive:true,force:true});}
});
