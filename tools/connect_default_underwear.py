"""Connect source-backed empty underwear slots without changing original art."""
import hashlib
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output
from connect_map_geometry import replace_once

def connect(runtime):
    public=local_output(runtime)/'prototype/public'
    target=public/'character-equipment.js';old=target.read_bytes()
    # Filled with the reviewed pre-change module identity below.
    if hashlib.sha256(old).hexdigest()!=BEFORE:
        raise ValueError('Preserve unexplained or already-connected equipment changes')
    helper=public/'source-default-underwear.js'
    if helper.exists():raise ValueError('Preserve existing underwear adapter')
    text=old.decode()
    text="import{sourceDefaultBaseMeshes}from './source-default-underwear.js';\n"+text
    text=replace_once(text,'const visible = new Set(appearance.baseMeshIndices), worn = [];',
                     'const visible = new Set(sourceDefaultBaseMeshes(appearance)), worn = [];')
    helper.write_bytes((ROOT/'tools/preview/source-default-underwear.js').read_bytes())
    target.write_text(text)
    return {'files':2,'emptyNativeSlots':[7,8],'removedFixedLeafOverlays':2,
            'bodyMeshesRemoved':0,'sourceTexturesChanged':False,
            'nonzeroArmorCoverageRestored':False}

BEFORE='699708204adaf0cadb0e521016cc4dcc320b6bcad5982fa0ce69c9bed099da3e'

if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True)
    print(connect(cli.parse_args().runtime))
