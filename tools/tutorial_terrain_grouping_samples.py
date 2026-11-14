"""Compare current/native layer RGB with the same explicit base-level sampler.

This does not infer native device mip choice, lighting, visibility or pixels.
Images remain the frozen tutorial payloads; no images/materials are modified.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from selection_scene_candidate import local_output


def sample(image,uv,repeat):
 h,w=image.shape[:2];p=uv*np.array([w,h])-.5;lo=np.floor(p).astype(int);f=p-lo
 def read(x,y):
  if repeat:x=x%w;y=y%h
  else:x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
  return image[y,x]
 a=read(lo[:,0],lo[:,1]);b=read(lo[:,0]+1,lo[:,1]);c=read(lo[:,0],lo[:,1]+1);d=read(lo[:,0]+1,lo[:,1]+1)
 return (a*(1-f[:,0,None])+b*f[:,0,None])*(1-f[:,1,None])+(c*(1-f[:,0,None])+d*f[:,0,None])*f[:,1,None]


def layer_rgb(indices,mask,colors):
 active=[i for i,v in enumerate(indices)if v>=0]
 if not active:raise ValueError('No source active layer')
 out=colors[active[0]][:,:3].copy()
 for i in active[1:]:
  factor=mask[:,i-1,None]*(colors[i][:,3,None]if i==4 else 1)
  out=out*(1-factor)+colors[i][:,:3]*factor
 return out


def analyze(runtime,evidence):
 runtime=local_output(runtime);evidence=local_output(evidence);r=json.loads(evidence.read_text());base=runtime/'game-data/converted';mats=json.loads((base/'geometry-water/terrain-materials.json').read_text());cache={};rows=[];samples=0
 def image(url):
  if url not in cache:cache[url]=np.asarray(Image.open(base/url.removeprefix('/assets/')).convert('RGBA'),dtype=np.float64)/255.
  return cache[url]
 for row in r['tiles']:
  if not row['different']:continue
  mat=next(t for t in mats['tiles']if t['tile']==row['tile']);mask_image=image(mat['mask']['url'])if mat['mask']else np.zeros((1,1,4));chunks=[]
  for c in row['chunks']:
   if not c['indicesDiffer']and not c['macroDiffers']:continue
   cx,cz=c['chunk'];a=(np.arange(16)+.5)*.5;xx,zz=np.meshgrid(a,a);interior=np.stack([xx.ravel(),zz.ravel()],axis=1)
   # Just inside each chunk boundary, so a linear mask sees its neighbour lane.
   edges=np.concatenate([np.stack([a,np.full(16,.001)],axis=1),np.stack([a,np.full(16,7.999)],axis=1),
    np.stack([np.full(16,.001),a],axis=1),np.stack([np.full(16,7.999),a],axis=1)])
   coords=np.concatenate([interior,edges])+np.array([cx*8,cz*8]);mask=sample(mask_image,coords/64,False);uv=coords/8
   def color(indices):
    colors=[sample(image(mat['textures'][i]['url']if i>=0 else mats['fallback']),uv,True)for i in indices]
    return layer_rgb(indices,mask,colors)
   old=color(c['currentEffectiveIndices']);new=color(c['finalIndices']);diff=np.abs(old-new)*255.;norm=diff.max(axis=1);idx=int(np.argmax(norm));samples+=len(coords)
   point=[row['tile'][0]*64+float(coords[idx,0]),row['tile'][1]*64+float(coords[idx,1])]
   chunks.append({'chunk':c['chunk'],'wet':bool(c['nativeFlags']&0x10000),'sampleCount':len(coords),'interiorMaxRGBDelta255':float(diff[:256].max()),
    'boundaryMaxRGBDelta255':float(diff[256:].max()),'maxRGBDelta255':float(norm[idx]),'meanRGBDelta255':float(diff.mean()),
    'samplesOverOneRGBUnit':int((norm>1).sum()),'maximumWorldXZ':point,'maximumIsBoundarySample':idx>=256,
    'currentRGB255':list(old[idx]*255),'nativeRGB255':list(new[idx]*255),'currentIndices':c['currentEffectiveIndices'],'finalIndices':c['finalIndices'],
    'nativeMacro':c['textureLayerMask'],'distanceToApprovedEntryXZ':float(np.linalg.norm(np.array(point)-np.array([-2594,-64])))})
  rows.append({'tile':row['tile'],'chunks':chunks})
 flat=[{'tile':t['tile'],**c}for t in rows for c in t['chunks']];nonzero=[c for c in flat if c['maxRGBDelta255']>1]
 nearest=sorted(nonzero,key=lambda c:c['distanceToApprovedEntryXZ'])[:20];strongest=sorted(nonzero,key=lambda c:-c['maxRGBDelta255'])[:20]
 return {'format':'oc2-tutorial-terrain-grouping-base-sample-comparison-v1','inputEvidenceSHA256':hashlib.sha256(evidence.read_bytes()).hexdigest(),
  'comparedChunks':len(flat),'sampleCount':samples,'chunksOverOneRGBUnit':len(nonzero),'nearEntrySamples':nearest,'strongestSamples':strongest,'tiles':rows,
  'sampler':'Explicit identical base-level linear RGBA sampling; texture repeat and mask clamp. Native original device mip/filter unknown.',
  'claim':'Actual frozen texture/mask RGB algebra difference, not original Android pixels or visibility/lighting claim. No source data/image modified.'}


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=local_output(a.output)
 if out.exists():raise ValueError('Preserve prior sample evidence')
 r=analyze(a.runtime,a.evidence);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:r[k]for k in('comparedChunks','sampleCount','chunksOverOneRGBUnit','nearEntrySamples')},ensure_ascii=False))
