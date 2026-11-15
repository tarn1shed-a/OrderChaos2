"""Freeze a private quest227 review subset; no deployment/runtime package."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from ordinary_quest_227_probe import ROOT,AREA

sha=lambda raw:hashlib.sha256(raw).hexdigest()
PRIOR=['ordinary-quest-journal','ordinary-quest-book-bridge','ordinary-quest-item-action','ordinary-quest-book-state',
 'ordinary-quest-reward-slot','ordinary-quest-journal-web','ordinary-quest-journal-session','ordinary-quest-journal-widgets',
 'ordinary-quest-journal-render-audit','ordinary-quest-journal-net']
OWN=['tools/ordinary_quest_227_probe.py','tools/ordinary_quest_227_assets.py','tools/ordinary_quest_227_tests.py',
 'tools/ordinary_quest_227_package.py','docs/ORDINARY_QUEST_227.md']


def freeze():
    if(AREA/'handoff-v1.json').exists():raise ValueError('Preserve frozen quest227 handoff')
    checks=json.loads((AREA/'checks-v1.json').read_text())
    if len(checks['commands'])!=2 or any(r['returncode']for r in checks['commands']):raise ValueError('Successful original/public checks required')
    for p,digest in checks['inputSHA256'].items():
        if sha((ROOT/p).read_bytes())!=digest:raise ValueError('Checked quest227 input changed '+p)
    def write(name,data):
        p=AREA/name
        if p.exists():raise ValueError('Preserve existing receipt '+str(p))
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return p
    prior=[];seen={}
    for area in PRIOR:
        path=ROOT/f'analysis/raw/{area}-20261116/frozen-manifest-v1.json';d=json.loads(path.read_text())
        for r in d['files']:
            if sha((ROOT/r['path']).read_bytes())!=r['sha256']:raise ValueError('Previous frozen source changed '+r['path'])
            if r['path']in seen and seen[r['path']]!=r['sha256']:raise ValueError('Conflicting previous frozen source')
            seen[r['path']]=r['sha256']
        prior.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes()),'files':len(d['files'])})
    drafts={'tools/native_character_entry.py':'77a2f2b69bd846b1b96cbc68aee732c68f6959370c3dfe8826ddb08aae8cdd8a',
      'tools/standard_abc.py':'a93057561936010e5adf0249cc569b80e8c5924e58882e349ef368c599ba7152'}
    if any(sha((ROOT/p).read_bytes())!=h for p,h in drafts.items()):raise ValueError('Protected user draft changed')
    old=write('previous-freeze-verification-v1.json',{'format':'oc2-quest227-previous-freeze-v1','manifests':prior,'uniqueFiles':len(seen),'allUnchanged':True,'protectedDrafts':drafts})
    route=ROOT/'analysis/raw/ordinary-quest227-route-20261116/handoff-v1.json'
    source=AREA/'candidate-v2/source-v1.json';profile=AREA/'resource-review-v4/profile.json'
    links={str(p.relative_to(ROOT)):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}for p in[source,profile,route]}
    note=write('bounded-conclusion-v1.json',{'format':'oc2-quest227-bounded-conclusion-v1','sources':links,
      'independentQuestNot461Successor':True,'approvedForRuntime':False,'originalTaskOrActorStateSupplied':False,
      'tableAssociation':'638/type1 → loot88/filter63 → feature74 → items89/50051 count1; original Chance/BoxValue fields retained, evaluator not recovered',
      'assets':'7 exact models, 30 decoded original PNG; original NPC872 parts/idle and 638 idle request; exact Model32 base-only CPU proof reuse; no GPU claim',
      'remaining':['Crocodile original Camera01 type0 and signed/range conventions: parent owns follow-up; no relaxed decoder supplied',
        'Route to grave783 remains rejected by original slope gate in independent route handoff; entrance→872→2576 only is passed',
        'Original activity/filter/kill/drop approval, run-time scale, appearance completion and full render remain unknown'],
      'nextSpecificScope':'After parent animation/loot results, grave218 Type6/spell0 original interaction-to-finish-query caller is a possible separate source-backed next gate, not a task approval.',
      'noUserSavesBrowserServiceDockerGitOrDeployment':True})
    files=sorted({*(ROOT/p for p in OWN),*(p for p in AREA.rglob('*')if p.is_file())})
    records=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes()),'private':p.is_relative_to(AREA)}for p in files]
    manifest=write('frozen-manifest-v1.json',{'format':'oc2-quest227-frozen-review-v1','files':records,'includesIntermediateFailures':True,'runtimeEnabled':False})
    subset=[*(ROOT/p for p in OWN),source,profile,AREA/'checks-v1.json',AREA/'native-npc872-v1.json',old,note,manifest]
    subset += [p for sub in ['candidate-v2/original-resources','resource-review-v4']for p in(AREA/sub).rglob('*')if p.is_file()]
    subset=sorted(set(subset))
    package_manifest=write('review-package-manifest-v1.json',{'format':'oc2-quest227-review-subset-v1','runtimeEnabled':False,
      'fullOnDiskFrozenManifestIncludesPreservedIntermediateDirectoriesNotInThisArchive':True,
      'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in subset]})
    subset.append(package_manifest);archive=AREA/'quest227-private-review-v1.tar.gz'
    if archive.exists():raise ValueError('Preserve prior archive')
    with archive.open('wb')as target,gzip.GzipFile(fileobj=target,mode='wb',mtime=0,filename='')as zipped,tarfile.open(fileobj=zipped,mode='w')as tar:
        for p in sorted(subset):
            raw=p.read_bytes();info=tarfile.TarInfo(str(p.relative_to(ROOT)));info.size=len(raw);info.mode=0o644;info.mtime=0;info.uid=info.gid=0;tar.addfile(info,io.BytesIO(raw))
    with tarfile.open(archive,'r:gz')as tar:
        expected={str(p.relative_to(ROOT)):sha(p.read_bytes())for p in subset}
        if set(tar.getnames())!=set(expected):raise ValueError('Private package member set differs')
        for m in tar.getmembers():
            if not m.isfile()or sha(tar.extractfile(m).read())!=expected[m.name]:raise ValueError('Private package member differs')
    handoff=write('handoff-v1.json',{'format':'oc2-quest227-handoff-v1','runtimeEnabled':False,'sources':links,'checks':{'local':15,'publicPassed':2,'publicSkipped':13},
      'frozenFiles':len(records),'previousUniqueFilesUnchanged':len(seen),'protectedDraftsUnchanged':2,
      'manifest':{'path':str(manifest.relative_to(ROOT)),'sha256':sha(manifest.read_bytes())},
      'archive':{'path':str(archive.relative_to(ROOT)),'sha256':sha(archive.read_bytes()),'bytes':archive.stat().st_size,'members':len(subset),'verifiedEveryMember':True,'reviewOnlyNotDeployment':True},
      'publicSource':OWN,'remaining':['Original crocodile animation decoder input','Original route to grave','Original appearance/activity/filter/drop/quest approval'],'scope':'Data and strict asset review only; no full task, world actor or GPU admission'})
    return{'handoff':str(handoff),'sha256':sha(handoff.read_bytes()),'manifestSHA256':sha(manifest.read_bytes()),'archiveSHA256':sha(archive.read_bytes()),'frozenFiles':len(records),'archiveMembers':len(subset)}


if __name__=='__main__':print(json.dumps(freeze(),ensure_ascii=False,indent=2))
