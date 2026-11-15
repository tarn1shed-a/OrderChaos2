"""Freeze only the872 default review candidate; no deployment mutation."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from ordinary_npc872_candidate import ROOT,AREA,NAMESPACE
from ordinary_quest_227_package import PRIOR

sha=lambda raw:hashlib.sha256(raw).hexdigest()
OWN=['tools/ordinary_npc872_candidate.py','tools/ordinary_npc872_tests.py','tools/ordinary_npc872_tests.mjs',
 'tools/ordinary_npc872_package.py','tools/preview/source-ordinary-npc872.mjs','docs/ORDINARY_NPC872_ASSET.md']


def freeze():
    if(AREA/'handoff-v1.json').exists():raise ValueError('Preserve872 handoff')
    def put(name,value):
        p=AREA/name
        if p.exists():raise ValueError('Preserve872 receipt')
        p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');return p
    checks=json.loads((AREA/'source-checks-v1.json').read_text())
    if len(checks['commands'])!=2 or any(x['returncode']for x in checks['commands']):raise ValueError('Original/public checks required')
    for name,digest in checks['inputs'].items():
        if sha((ROOT/name).read_bytes())!=digest:raise ValueError('Checked872 file changed '+name)
    node=json.loads((AREA/'node-checks-v1.json').read_text())
    if node['assertions']!=426 or node['GPU']or not node['allDisposedExactlyOnce']:raise ValueError('Actual Three CPU checks required')
    previous=[ROOT/f'analysis/raw/{name}-20261116/frozen-manifest-v1.json'for name in PRIOR]
    previous.extend(ROOT/p for p in['analysis/raw/ordinary-quest-neighbors-20261116/frozen-manifest-v1.json',
      'analysis/raw/ordinary-quest227-interaction-20261116/frozen-manifest-v1.json'])
    seen={};manifests=[]
    for p in previous:
        rows=json.loads(p.read_text())['files']
        for r in rows:
            if sha((ROOT/r['path']).read_bytes())!=r['sha256']:raise ValueError('Previous frozen file changed '+r['path'])
            if r['path']in seen and seen[r['path']]!=r['sha256']:raise ValueError('Previous freeze conflict')
            seen[r['path']]=r['sha256']
        manifests.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'files':len(rows)})
    drafts={'tools/native_character_entry.py':'77a2f2b69bd846b1b96cbc68aee732c68f6959370c3dfe8826ddb08aae8cdd8a',
      'tools/standard_abc.py':'a93057561936010e5adf0249cc569b80e8c5924e58882e349ef368c599ba7152'}
    if any(sha((ROOT/n).read_bytes())!=h for n,h in drafts.items()):raise ValueError('Protected user draft changed')
    previous_receipt=put('previous-freeze-v1.json',{'format':'oc2-npc872-previous-freeze-v1','manifests':manifests,'allUnchanged':True,'uniqueFiles':len(seen),'protectedDrafts':drafts})
    candidate=AREA/'candidate-v2';profile=candidate/'assets'/NAMESPACE/'profile.json';model=candidate/'assets'/NAMESPACE/'npc872.json'
    member_list=json.loads((candidate/'package-files.json').read_text())['files']
    for name,r in member_list.items():
        p=candidate/name
        if not p.resolve().is_relative_to(candidate.resolve())or p.is_symlink()or r!={'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}:raise ValueError('Candidate member changed')
    api=put('integration-contract-v1.json',{'format':'oc2-npc872-host-integration-v1','candidate':str(candidate.relative_to(ROOT)),
      'namespace':NAMESPACE,'profileURL':'/assets/'+NAMESPACE+'/profile.json','profileSHA256':sha(profile.read_bytes()),'modelSHA256':sha(model.read_bytes()),
      'module':'source-ordinary-npc872.mjs','export':'loadNPC872Assets(THREE,{profileURL,json,texture})',
      'factory':'assets.createNPC872({materialFactory})','materialFactory':'({THREE,record,textures,colors}) => existing NPC Material',
      'instance':['root','bones','meshes','materials','geometries','sampleIdle(seconds)','inspect()','dispose()'],
      'idleRangeSeconds':[0,4.266666666666667],'sourceName':'卢西安哪','nameSubstitutionCompleted':False,
      'entry':872,'display':852,'model':32,'extra':720,'meshes':16,'visibleMeshes':11,'visibleTriangles':1878,'nodes':116,'materials':5,'textures':23,
      'originalVisibilityCPUExecuted':True,'base12CPUProofReused':True,'noPlayerOutfitCopied':True,
      'sourceResourceAssemblyComplete':True,'browserGPUVerified':False,'worldPlacement':None,'actorGUID':None,'questState':None,
      'nextCheck':'Parent existing NPC viewer/camera GPU review of geometry/material/idle/disposal; no activity or task admission is inferred.'})
    files=sorted({*(ROOT/name for name in OWN),*(p for p in AREA.rglob('*')if p.is_file())})
    manifest=put('frozen-manifest-v1.json',{'format':'oc2-npc872-frozen-v1','files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes()),'private':p.is_relative_to(AREA)}for p in files],
      'candidateV1IsPreservedIntermediate':True,'productionOrActivityEnabled':False})
    members=sorted({*(ROOT/name for name in OWN),*(p for p in candidate.rglob('*')if p.is_file()),AREA/'source-checks-v1.json',AREA/'node-checks-v1.json',previous_receipt,api,manifest})
    archive=AREA/'npc872-private-candidate-v1.tar.gz'
    if archive.exists():raise ValueError('Preserve872 archive')
    with archive.open('wb')as target,gzip.GzipFile(fileobj=target,mode='wb',filename='',mtime=0)as gz,tarfile.open(fileobj=gz,mode='w')as tar:
        for p in members:
            raw=p.read_bytes();m=tarfile.TarInfo(str(p.relative_to(ROOT)));m.mode=0o644;m.size=len(raw);m.mtime=0;m.uid=m.gid=0;tar.addfile(m,io.BytesIO(raw))
    with tarfile.open(archive,'r:gz')as tar:
        expected={str(p.relative_to(ROOT)):sha(p.read_bytes())for p in members}
        if set(tar.getnames())!=set(expected):raise ValueError('872 package set differs')
        for m in tar.getmembers():
            if not m.isfile()or sha(tar.extractfile(m).read())!=expected[m.name]:raise ValueError('872 package bytes differ')
    handoff=put('handoff-v1.json',{'format':'oc2-npc872-default-assets-handoff-v1','contract':{'path':str(api.relative_to(ROOT)),'sha256':sha(api.read_bytes())},
      'candidate':str(candidate.relative_to(ROOT)),'profile':{'path':str(profile.relative_to(ROOT)),'sha256':sha(profile.read_bytes())},
      'model':{'path':str(model.relative_to(ROOT)),'sha256':sha(model.read_bytes())},
      'manifest':{'path':str(manifest.relative_to(ROOT)),'sha256':sha(manifest.read_bytes()),'files':len(files)},
      'archive':{'path':str(archive.relative_to(ROOT)),'sha256':sha(archive.read_bytes()),'bytes':archive.stat().st_size,'members':len(members),'everyMemberVerified':True,'reviewOnlyNotDeployment':True},
      'checks':{'sourceLocal':12,'sourcePublicPassed':1,'sourcePublicSkipped':11,'realThreeHostAssertions':426,'GPU':False},
      'previousUniqueFilesUnchanged':len(seen),'protectedDraftsUnchanged':2,'activityOrTaskCreated':False,'browserServerSavesGitDeploymentTouched':False,
      'nextGate':'Parent actual GPU review; original activity, dynamic name publication and task227 qualification remain separate.'})
    return{'handoff':str(handoff),'sha256':sha(handoff.read_bytes()),'manifestSHA256':sha(manifest.read_bytes()),'archiveSHA256':sha(archive.read_bytes()),'newFiles':len(files),'oldUnchanged':len(seen)}


if __name__=='__main__':print(json.dumps(freeze(),ensure_ascii=False,indent=2))
