"""Append the original type2 map7 temple-interior material candidate.

The frozen139 background is read-only. This exports one original ITM placement,
source node/vertex/UV/index streams and selection DAT, never type15 visibility,
new walls, fallback images, guessed animation speed or changed lights.
"""
import argparse
import copy
import hashlib
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from bdae_convert import BDAE
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_collision import apply_scene_transforms
from terrain_convert import read_instances
from selection_scene_candidate import ROOT,local_output,binding_rows,settings
from tutorial_inside_models import recover_materials,verify as verify_materials

FORMAT='oc2-selection-scene-inside-append-v1'
MODEL='model/scene_generator_temple_000/god_temple01_inside01.bdae'
MODEL_SHA='a7d5ab9ec74318feaf1c518d8b4b5a94e3e847996c67c9a34e84ee34c3c23192'
OBJECT_ID=684990760
TILE=(-41,-2)
NAMESPACE='source-selection-inside'


def sha(data):return hashlib.sha256(data).hexdigest()


def build(image,base,output):
    from bres_world_bounds_evidence import inner_bres
    from native_part_lightmaps import PartLightmapProbe
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from texture_decode import decode
    from scene_dynamic_wind import NativeWind
    base=local_output(base);output=local_output(output)
    if output.exists():raise ValueError('Use a fresh independent append directory')
    base_file=base/'assets/source-selection-scene/manifest.json';base_bytes=base_file.read_bytes();manifest=json.loads(base_bytes)
    if manifest.get('world')!='selection'or len(manifest['models'])!=37 or sum(len(e['instances'])for e in manifest['models'])!=139:
        raise ValueError('Expected the frozen139 map7 source candidate')
    if not any(g.get('model')==MODEL and g.get('ids')==[OBJECT_ID]for g in manifest['gaps']):
        raise ValueError('Original source interior gap is not in the base candidate')
    source=Sources(DEFAULT_SOURCE);raw=source.read(MODEL)
    if sha(raw)!=MODEL_SHA:raise ValueError('Original temple interior changed')
    verify_materials(image);options,_=settings(image)
    itm=f'world/selection/items/{TILE[0]:04d}_{TILE[1]:04d}.itm';raw_itm=source.read(itm)
    with tempfile.TemporaryDirectory(prefix='oc2-selection-inside-')as td:
        p=Path(td)/Path(itm).name;p.write_bytes(raw_itm);rows=read_instances(p)
        original,=[r for r in rows if r['id']==OBJECT_ID]
        if original['model']!=MODEL or original['sourceType']!=2 or tuple(original['tile'])!=TILE:
            raise ValueError('Source type2 placement differs')
        levels=ET.fromstring(source.read('bdaeConfig.xml'))
        query=NativeDeviceInstanceProbe(image);gate=NativeDeviceInstanceProbe(image)
        if source.candidates('world/selection/bdaeInstanceConfig.xml'):raise ValueError('New local selection override needs recovery')
        query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),
            'exceptions':[e.attrib['name']for _ in e.findall('Instance')]}for e in levels.findall('Item')],[])
        gate.level_delegate=query.lookup;gate.load_itm(raw_itm)
        admission=gate.admission(next(i for i,r in enumerate(rows)if r['id']==OBJECT_ID),options['ModelDetailLevel'],options['DeviceLayer'])
        if admission!='admittedBeforeTypeFactory':raise ValueError('Original default rejects this placement')
        p=Path(td)/'source.bdae';p.write_bytes(raw);reader=BDAE(p)
        data=apply_scene_transforms(reader,reader.parse());recover_materials(source,reader,data,image)
    profile=data.pop('sourceInsideMaterials');profile['format']=FORMAT
    profile.update(sourceType=2,originalModel=MODEL,sourceSHA256=MODEL_SHA,
        type15VisibilityApplied=False,clockHostOrigin=True)
    data['selectionInsideMaterials']=profile;data['source']=MODEL
    for mesh in data['meshes']:mesh['selectionSecondaryUV']=mesh.pop('sourceInsideAttributes')
    if len(data['meshes'])!=1 or len(data['materials'])!=21:
        raise ValueError('Original interior mesh/material population differs')
    if any(r['missingSamplers']for r in profile['materials']):raise ValueError('No missing-sampler substitution permitted')
    order=[g['material']for g in data['meshes'][0]['groups']]
    part=PartLightmapProbe(image);refs=part.references(inner_bres(raw))
    if sorted(order)!=list(range(21))or[ref['localIndex']for ref in refs]!=order:
        raise ValueError('Original part/material order differs')
    record,bindings=binding_rows(source,original)
    if len(bindings)!=1:raise ValueError('Original selection single-binding branch changed')
    binding_proof=part.bindings(order,bindings)
    files=[];textures={};dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True)
    def write(name,obj):
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');files.append(name)
        return '/assets/'+NAMESPACE+'/'+name
    reused=[]
    def texture(name):
        if name in textures:return
        if len(source.candidates(name))!=1:raise ValueError('Original texture missing or ambiguous: '+name)
        encoded=source.read(name);im=decode(encoded);digest=sha(encoded)
        old=manifest['textures'].get(name)
        if old:
            if old.get('sourceSHA256')!=digest:raise ValueError('Frozen source texture identity differs')
            from PIL import Image
            old_file=base/old['url'].lstrip('/')
            if Image.open(old_file).convert('RGBA').tobytes()!=im.convert('RGBA').tobytes():
                raise ValueError('Frozen texture pixels differ from original source')
            textures[name]=copy.deepcopy(old);reused.append(name);return
        filename='textures/'+digest+'.png';p=dest/filename;p.parent.mkdir(parents=True,exist_ok=True);im.save(p);files.append(filename)
        textures[name]={'sourceSHA256':digest,'url':'/assets/'+NAMESPACE+'/'+filename,'width':im.width,'height':im.height,
            'adapter':'Source ETC1/split decoded RGBA; existing browser filter/mip adapter'}
    for r in profile['materials']:
        for key,sampler in r['samplers'].items():
            if key!='lightMap':texture(sampler['texture'])
    for b in bindings:texture(b['atlas'])
    wind=NativeWind(image)
    clock=[wind.time(t)for t in(0,1000,1000000)]
    entry={'model':MODEL,'sourceSHA256':MODEL_SHA,'url':write('model.json',data),
        'partToMaterial':order,'instances':[original]}
    overlay={'format':FORMAT,'world':'selection','mapId':7,'profile':'APK_Default',
        'baseManifestSHA256':sha(base_bytes),'entry':entry,'bindings':[{'objectId':OBJECT_ID,'model':MODEL,
            'tile':list(TILE),'recordPath':record,'bindings':bindings}],
        'textures':textures,'sourceType':2,'type15VisibilityApplied':False,'companionModelAdded':False,
        'lightingChanged':False,'savesChanged':False,'originalCompleteFrameRestored':False,
        'clock':{'sourceMillisecondsToSeconds':clock[-1]['seconds'],'hostOrigin':True,'existingUnpausedClockAdapter':True},
        'proposedCounts':{'models':38,'staticInstances':140,'remainingStaticInstances':11},
        'scope':'One original type2 selection placement with verified material/UV/DAT; independent append, not production deployment'}
    write('overlay.json',overlay)
    audit={'format':FORMAT,'sourceITM':itm,'instance':original,'originalModelSHA256':MODEL_SHA,
        'originalVertices':sum(m['vertexCount']for m in data['meshes']),
        'originalTriangles':sum(m['triangleCount']for m in data['meshes']),
        'partToMaterial':order,'originalPartReferences':refs,'nativePartBinding':binding_proof,
        'materialValuesAndSamplers':profile['materials'],'originalClockSamples':clock,
        'sourceProofs':source.proofs,'files':sorted(set(files)),'reusedFrozenTextures':sorted(reused),
        'admission':admission,'originalSlot':0,'originalType':2,'insideCompanionRequested':False,
        'frozenBaseUnchanged':base_file.read_bytes()==base_bytes,'sourceLightingChanged':False,'savesChanged':False,
        'limits':['Original native CPU material properties, part references, binding loop and clock math executed; no original GPU success.',
            'Shader expressions independently bridge the verified original defines and sampler data; browser precision/filter/mips remain adapters.',
            'Host clock epoch and draw scheduling are explicit interfaces; original pause/resume history is not reconstructed.',
            'Does not invoke type15 factory or apply inside-camera/PHY visibility rules to this source type2 placement.']}
    (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return audit


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output)
    print(json.dumps({'model':1,'sourceType':2,'materials':len(result['materialValuesAndSamplers']),
        'vertices':result['originalVertices'],'triangles':result['originalTriangles'],
        'sourceBindings':len({r['binding']for r in result['nativePartBinding']['calls']}),'baseUnchanged':result['frozenBaseUnchanged']}))
