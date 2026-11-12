"""Source-backed temple RGB audit; no brightness correction is inferred."""
import argparse
import json
from pathlib import Path
from scene_lighting import ZONE_SHA256, zone_targets, color_vector, lightmap_global
from skill_attachments import decode_ftable
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE


def audit(image, source=DEFAULT_SOURCE):
    import hashlib
    from native_temple_ambient import TempleAmbientProbe
    raw = Sources(source).read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest() != ZONE_SHA256: raise ValueError('Original zone table changed')
    rows = {r['ID']:r for r in decode_ftable(raw, id_column='ID')['rows']}
    probe = TempleAmbientProbe(image)
    results = []
    for ident in (194,195,196,197,199):
        row, base = rows[ident], rows[194]
        targets = zone_targets(row, None if ident == 194 else base)
        packed = [row[name] or base[name] for name in ('light_ambient','light_diffuse')]
        native = probe.produce(*packed, targets['intensities'])
        expected = lightmap_global(*map(color_vector,packed), targets['intensities']['model_intensity_lightMap'])
        actual = native['submitted']['light_model_lightMap']
        if actual != expected: raise ValueError('Complete original model RGB producer disagrees')
        results.append({'zone':ident,'native':native,'modelLight':actual,'targets':targets})
    return {'format':'oc2-temple-ambient-audit-v1','zones':results,
            'sourceTableSHA256':ZONE_SHA256,'sourceCPU':True,'lightingChanged':False,
            'originalAndroidGPUObserved':False,
            'limits':['Current intensities and zero weather additions are explicit settled APK_Default inputs.',
                      'Reflection indices and uniform submission are recording interfaces, not original driver execution.',
                      'The original LIGHTMAP fragment multiplies diffuse, atlas and vertex light; no extra ambient addition was found in this path.',
                      'No same-coordinate original Android frame or all later overrides have been observed.']}


if __name__ == '__main__':
    from analyze_native_resources import NativeImage
    from tutorial_map_geometry import local_output
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,required=True)
    args = cli.parse_args()
    out = local_output(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    result = audit(NativeImage(Path('analysis/raw/beff-native/library.so').read_bytes()))
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'zones':len(result['zones']),'lightingChanged':False,'output':str(out)}))
