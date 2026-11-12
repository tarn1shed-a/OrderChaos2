"""Preserve original RGB8 scene-target reads in the ignored browser preview."""
import hashlib
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output

BEFORE = '7b46e5cf7a93e1bc2efde618f149b93de27d449c3b97fa273c56eaf8a5e2a32c'

def connect(runtime):
    target = local_output(runtime)/'prototype/public/original-default-postprocess-v1.js'
    old = target.read_bytes()
    if hashlib.sha256(old).hexdigest() != BEFORE:
        raise ValueError('Preserve unexplained or already-connected postprocess changes')
    new = (ROOT/'tools/preview/original-default-postprocess.js').read_bytes()
    if b'export function sourceRGBInputFragment(' not in new:
        raise ValueError('RGB8 sampler adapter missing')
    target.write_bytes(new)
    return {'files': 1, 'sourceSceneFormat': 'RGB8', 'webStorage': 'RGBA8',
            'sceneSamplerAlpha': 1, 'bloomRGBAReadChanged': False,
            'sourcePixelsChanged': False, 'lightingChanged': False}

if __name__ == '__main__':
    import argparse
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--runtime', type=Path, required=True)
    print(connect(cli.parse_args().runtime))
