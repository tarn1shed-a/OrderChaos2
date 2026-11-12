"""Check source character UVs/texture rows without editing source art."""
import hashlib
import json
import tempfile
from pathlib import Path
from PIL import Image
from bdae_convert import BDAE
from character_materials import SHADER_SHA256, VERTEX_SHADER, read_material_record
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from texture_decode import decode
from tutorial_map_geometry import ROOT


def audit(runtime,source=DEFAULT_SOURCE):
    sources=Sources(source);assets=Path(runtime)/'game-data/converted'
    data=json.loads((assets/'source-layers/elf-female.json').read_text())
    shader=sources.read(VERTEX_SHADER)
    if hashlib.sha256(shader).hexdigest()!=SHADER_SHA256[VERTEX_SHADER]:raise ValueError('Original character shader changed')
    # Original source assigns the unchanged model UV to its sampler varying.
    import re
    if not re.search(rb'vCoord0\.xy\s*=\s*TexCoord0\s*;',shader):raise ValueError('Original character UV consumer needs retracing')
    original=sources.read(data['source'])
    with tempfile.TemporaryDirectory()as d:
        p=Path(d)/'body.bdae';p.write_bytes(original);reader=BDAE(p)
        record=read_material_record(reader,'body');head=next(m for m in reader.parse()['meshes']if m['name']=='head-mesh')
    current=next(m for m in data['meshes']if m['name']=='head-mesh')
    if current['uvs']!=head['uvs']:raise ValueError('Head UV differs from original model')
    checked=[]
    for slot,name in record['samplers'].items():
        original_texture=sources.read(name);image=decode(original_texture).convert('RGBA')
        row=data['characterMaterials']['materials'][0]
        if row['samplerMetadata'][slot]['sourcePath']!=name:raise ValueError('Character texture association changed')
        path=assets/row['samplers'][slot].removeprefix('/assets/')
        if Image.open(path).convert('RGBA').tobytes()!=image.tobytes():raise ValueError('Converted character texture rows differ')
        checked.append({'slot':slot,'source':name,'sourceSHA256':hashlib.sha256(original_texture).hexdigest(),
                        'pixelSHA256':hashlib.sha256(image.tobytes()).hexdigest(),'url':row['samplers'][slot],
                        'size':list(image.size),'convertedRowsEqualSourceDecode':True})
    return {'format':'oc2-character-texture-orientation-v1','model':data['source'],
            'modelSHA256':hashlib.sha256(original).hexdigest(),'shaderSHA256':SHADER_SHA256[VERTEX_SHADER],
            'originalHeadUVPreserved':True,'textures':checked,'sourceProofs':sources.proofs,
            'fix':'Remove TextureLoader flipY only on private character texture clones; no UV or pixel edits.',
            'limits':['Source PVR decode rows and source shader/model UVs checked; not an Android GPU capture.',
                      'Existing character palette colors, global lights, gamma bridge and original full material state remain partially adapted.']}

if __name__=='__main__':
    import argparse
    from tutorial_map_geometry import local_output
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    out=local_output(args.output);out.write_text(json.dumps(audit(args.runtime),ensure_ascii=False,indent=2)+'\n');print(str(out))
