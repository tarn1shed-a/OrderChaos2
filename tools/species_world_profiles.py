"""Per-model loaded-track inputs, verified against original BDAE ranges.

This does not create a character or supply an original server appearance. It
prevents the web host from running every species on the elf-female stop clock.
"""
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-source-species-motion-v1'
CANDIDATES = {
    'human-male': 'character-world-motion-20261115/male-v4-final',
    'human-female': 'character-world-motion-20261115/female-v4-final',
    'elf-male': 'character-elf-male-world-20261115/candidate-v2',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def profile_digest(profile):
    clean = {k: v for k, v in profile.items() if k != 'sha256'}
    return digest(json.dumps(clean, sort_keys=True, separators=(',', ':')).encode())


def validate_profile(profile, native_sha):
    if (profile.get('format') != FORMAT or profile.get('nativeSHA256') != native_sha
            or profile.get('sha256') != profile_digest(profile)
            or profile.get('engineFlags') != 3 or profile.get('channels') != 2
            or profile.get('originalServerAppearanceKnown') is not False):
        raise ValueError('Unverified original species motion inputs')
    ranges = profile.get('ranges', {})
    required = {'idle', 'walk_forward', 'run_normal_front', 'run_idle', 'swim_idle', 'swim_forward'}
    if not required.issubset(ranges) or not set(ranges).issubset(profile.get('sourceClipNames', [])):
        raise ValueError('Original species locomotion ranges missing')
    for name, row in ranges.items():
        if (row.get('name') != name or not row.get('sourceName')
                or any(type(row.get(k)) is not int for k in ('startMs', 'endMs', 'originMs'))
                or not 0 <= row['originMs'] <= row['startMs'] < row['endMs']):
            raise ValueError('Invalid original species range')
    return profile


def recover(image, sources, key):
    from bdae_animation import BDAEAnimation
    from skill_attachments import decode_ftable
    from source_stop_queue import SourceStopQueue
    from layer_queue_assets import model_flags

    if key not in CANDIDATES:
        raise ValueError('Species has not passed its independent body/track checks')
    folder = ROOT/'analysis/raw'/CANDIDATES[key]
    manifest_raw = (folder/'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    model_raw = (folder/manifest['model'].lstrip('/')).read_bytes()
    data = json.loads(model_raw)
    body = data.get('sourceHumanWorld') or data.get('sourceElfMaleWorld')
    if not body or manifest.get('sourceMotionClock') != body.get('motionClock'):
        raise ValueError('Final original clock candidate required')
    native = json.loads((folder/'native-private.json').read_text())
    rows = decode_ftable(sources.read('tables/creaturemodeldata.tbl'), 'ID')['rows']
    selected = next(row for row in rows if row['ID'] == body['sourceModelId'])
    if selected != native['model'] or selected['ModelPath'] != data['source']:
        raise ValueError('Original selected model row differs')
    animation = str(Path(data['source']).parent/'anim/animations.bdae')
    animation_raw = sources.read(animation)
    with tempfile.TemporaryDirectory(prefix='oc2-species-ranges-') as temp:
        path = Path(temp)/'source.bdae'
        path.write_bytes(animation_raw)
        ranges = {row['name']: row for row in BDAEAnimation(path).ranges()}
    admitted = {name: ranges[name] for name in manifest['actions']}
    if admitted != manifest['clipRanges']:
        raise ValueError('Converted actions do not retain original model ranges')
    for clip in data['clips']:
        row = admitted[clip['name']]
        if (clip['sourceRangeMs'] != [row['startMs'], row['endMs']]
                or clip['duration'] != (row['endMs']-row['startMs'])/1000):
            raise ValueError('Original per-model range duration differs')
    flags = model_flags(SourceStopQueue(image), selected['Flags'])
    result = {
        'format': FORMAT, 'nativeSHA256': digest(image.data), 'key': key,
        'race': manifest['race'], 'gender': manifest['gender'],
        'sourceModelId': selected['ID'], 'modelPath': selected['ModelPath'],
        'modelFlags': selected['Flags'], 'engineFlags': flags, 'channels': 2,
        'sourceAnimation': animation, 'sourceAnimationSHA256': digest(animation_raw),
        'modelTableSHA256': digest(sources.read('tables/creaturemodeldata.tbl')),
        'manifestSHA256': digest(manifest_raw), 'dataSHA256': digest(model_raw),
        'sourceClipNames': sorted(ranges), 'ranges': admitted,
        'originalServerAppearanceKnown': False,
        'boundary': 'Explicit verified loaded-track views; no original GPU, role creation or server appearance claim',
    }
    result['sha256'] = profile_digest(result)
    return validate_profile(result, digest(image.data))


if __name__ == '__main__':
    import argparse
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to(ROOT/'analysis/raw') or target.exists():
        raise ValueError('New ignored output required')
    library = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
    image, sources = NativeImage(library.read_bytes()), Sources(DEFAULT_SOURCE)
    result = {key: recover(image, sources, key) for key in CANDIDATES}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'profiles': len(result), 'sourceRangesVerified': True}))
