"""Append original settings drawings to the verified private runtime.

No existing payload or save is replaced. Full AS/native evidence stays private;
only the bounded drawing metadata needed by the web renderer is served.
"""
import argparse,gzip,hashlib,io,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'analysis/raw/tutorial-scene-effects-20261114/fire10-complete-v1.tar.gz'
BASE_SHA='2319ad6189a95f88ef5e556c69303217ba6d27464a1d3ed955675578817f121b'
CANDIDATE=ROOT/'analysis/raw/original-unstuck-20261114/ui-candidate-v5'
PROFILE_SHA='6a67f942ef345ac3593014176b94cbcb1ce880d0d409c2ff47ecc427d0154a2e'
DISABLED=ROOT/'analysis/raw/original-unstuck-20261114/disabled-overlay-candidate-v1/source-unstuck-disabled.svg'
DISABLED_SHA='fa6e534b4558c28a53fd31ef29bae71a766f30b0e45e4b65edfeee3c57d88a53'
PREFIX='game-data/converted/source-unstuck/'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def file_sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def private(path):
 path=Path(path).resolve()
 if not any(path.is_relative_to(ROOT/p) for p in ('analysis/raw','backups')):raise ValueError('Use ignored private output')
 if path.exists():raise ValueError('Preserve previous bundles')
 return path
def payload(candidate=CANDIDATE):
 candidate=Path(candidate).resolve(); raw=(candidate/'unstuck-ui.json').read_bytes()
 if sha(raw)!=PROFILE_SHA:raise ValueError('Original component profile identity differs')
 profile=json.loads(raw); listed={r['path']:r for r in json.loads((candidate/'files.json').read_text())}
 files={}
 for name in sorted({r['file'] for r in profile['drawings'].values()}|{r['file'] for r in profile['assets'].values()}):
  if Path(name).name!=name or Path(name).suffix not in ('.svg','.png'):raise ValueError('Unsafe original component member')
  data=(candidate/name).read_bytes(); meta=listed[name]
  if len(data)!=meta['bytes'] or sha(data)!=meta['sha256']:raise ValueError('Original component differs')
  if name.endswith('.svg'):
   # Adoption into HTML otherwise resolves the original relative bitmap href
   # against the game URL rather than the source SVG URL. Geometry stays exact.
   text=data.decode()
   for image in profile['assets'].values():text=text.replace('href="'+image['file']+'"','href="/assets/source-unstuck/'+image['file']+'"')
   data=text.encode()
  files[PREFIX+name]=data
 disabled=DISABLED.read_bytes()
 if sha(disabled)!=DISABLED_SHA:raise ValueError('Original disabled drawing differs')
 files[PREFIX+'source-unstuck-disabled.svg']=disabled
 compact={k:profile[k] for k in ('format','sourceStage','drawings','assets','strings','fields','sourceTabs','layoutBoundary','windowPositionEquations','gearBounds') if k in profile}
 compact['drawings']['breakaway-disabled']={'file':'source-unstuck-disabled.svg','viewBox':[-10,-15,300,130],
  'source':'SettingInfo _GroupBtn._Disable cid25/cid24/shape23, alpha77/256; separate source export'}
 compact['sourceProfileSHA256']=PROFILE_SHA
 # The source paragraph leading is extra spacing, not the total line height.
 # Full original CJK font hhea metrics supply the browser baseline advance;
 # the original engine's choice of hhea versus OS/2 is not yet recovered.
 from fontTools.ttLib import TTFont
 with tarfile.open(BASE,'r:gz') as original:
  raw_font=original.extractfile('game-data/converted/ui/chineseDisplay.woff').read()
 font=TTFont(io.BytesIO(raw_font));metrics=font['hhea']
 compact['browserFontMetrics']={'Alegreya':{'family':'EntryDisplay','unitsPerEm':font['head'].unitsPerEm,
  'ascent':metrics.ascent,'descent':metrics.descent,'lineGap':metrics.lineGap,
  'fontSHA256':sha(raw_font),'boundary':'Original full CJK font hhea plus source paragraph leading; browser adaptation, not recovered Flash line layout'}}
 compact['browserLayout']={'settingBtnHitBounds':[2.4,27.2,334.3921875,115.20048828125],
  'tabOrigins':[[0,0],[0,74.1],[0,148.2],[0,222.3]],'sourceMapID':5,'sourceMapType':2,'battleFieldType':4,
  'layoutEvidence':'Original PlaceObject records / SettingBtn._Hit tag37 rectangle and matrix; original-unstuck layout-final-readonly.json'}
 for row in compact['fields'].values():
  if row.get('textStyle'):row['textStyle']={k:v for k,v in row['textStyle'].items() if k not in ('initialHTML','variable')}

 compact['webBoundary']={'originalFirstSpawn':False,'destination':'User-authorized cinematic7 trial courtyard; original server selection unavailable','input':'Escape is a desktop adapter; original bottom-bar visibility not invented','font':'Original converted fonts with browser text measurement, not original Flash rasterization','originalRequest':{'opcode':644,'payloadBytes':0},'serverMovementCombatPolicyRecovered':False}
 files[PREFIX+'unstuck.json']=(json.dumps(compact,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 return files

def package(output):
 output=private(output)
 if file_sha(BASE)!=BASE_SHA:raise ValueError('Verified runtime identity differs')
 added=payload()
 with tarfile.open(BASE,'r:gz') as source:
  manifest=json.load(source.extractfile('bundle-manifest.json'))
  if set(added)&set(manifest['files']):raise ValueError('Cannot replace existing payloads')
  old_count=len(manifest['files']);manifest['files'].update({n:{'bytes':len(b),'sha256':sha(b)} for n,b in added.items()})
  output.parent.mkdir(parents=True,exist_ok=True)
  with output.open('xb') as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as target:
   for member in source:
    if member.name=='bundle-manifest.json':continue
    if not member.isfile():raise ValueError('Runtime member is not a file')
    target.addfile(member,source.extractfile(member))
   for name,raw in sorted({**added,'bundle-manifest.json':(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()}.items()):
    member=tarfile.TarInfo(name);member.size=len(raw);member.mode=0o600;target.addfile(member,io.BytesIO(raw))
 output.chmod(0o600)
 receipt={'archive':str(output),'sha256':file_sha(output),'bytes':output.stat().st_size,'baseSHA256':BASE_SHA,'originalPayloadsPreserved':old_count,'addedPayloads':len(added),'files':len(manifest['files']),'reviewedRuntimeFiles':len(manifest['runtimeIdentity']['files']),'localSavesImported':False}
 output.with_suffix(output.suffix+'.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();print(json.dumps(package(args.output)))
