"""Source pins and bounded preview/name evidence; original bytes stay local."""
import hashlib
import tempfile
from pathlib import Path

ROUTINES = {
    0x619a98: (120, 'c515ab73b3188d67f522cf3e196c73b618b35ae4c31f180be8ea30e95b2bdda0'),
    0x334efc: (88, 'bd124c48796d68695fb41261b3ba69441f65c7eca2becff875f98c6aab48f381'),
    0x332440: (496, 'd852cb3e36f8994802d2c067f8f946c5637225edb7cb5429bd02e99496912573'),
    0x550f08: (104, '202cb4b869cb9856cf7ee8b36553948e5444395d70b7b1344a125a6e64684869'),
    0x31f178: (1156, 'a4451ad9235004e34935a1d1e8e8b27849ffb09378574d9663cdd977fa064da5'),
    0x9d4c48: (1212, '9f5de1803d6480c53ddfdd8cd13d421c42566536af5b027102a293d8d6e83467'),
    0x3264fc: (468, 'ade8174ac3f600bc6c464b626f6919cc9f7450f156f0bccd392f9847c7edd2bc'),
    0x3266d0: (664, '0122d946568310137e92df8bca298ea1adf871b94b62a2728fbd2106011a3352'),
    0x33b854: (3092, '8d7808518b96e36d43a5bffadbf9e4fa87b42f9361573b99bc5dd9d6b72f2119'),
    0x34d228: (1440, 'b9ca1f350be5d7b49ad0c388976b25b850665cbddd2c32738408d2d0af97e80b'),
    0x91088c: (4436, 'f976ba1ce162f719c4741b74b8271748310fe1cc811b172cc66b960900c1b831'),
    0x904fdc: (1176, 'a8a34fc89b0afccaa5bc5f19264c1f321ee8b05119ca85291908d32d9663f015'),
    0xa94798: (276, 'aebf31ffd53d43fc2ba7675e033b6850fd702c3b05ec42243502e558e3706821'),
    0x3aa394: (444, '26cc695f6032c31b10b82e5b32f947cfeecd35a99c813c85cf7990b1bc54974d'),
    0x36a83c: (9108, 'b60aa233130993b24eec0dc8cb07eb88bea72e9d3fa528798fc2292dc3d6891e'),
}


def verify_native(image):
    from character_display_evidence import verify_native as previous
    previous(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original character presentation routine differs')
    if image.read(0x1e39a4c, 11) != b'Dummy_Name\0':
        raise ValueError('Original name anchor differs')
    return {'routines': len(ROUTINES), 'originalAndroidFrameObserved': False}


def assets(read):
    from hud_assets import document, named_path
    from attribute_page import source_bounds
    from bdae_convert import BDAE
    from character_materials import EFFECTS
    from scene_render_state import effect_render_state
    from scene_culling import cull_state
    import configparser
    doc = document(read('ui/Flash/AttributePage.swf'), 'ui/Flash/AttributePage.swf', True)
    lib = document(read('ui/Flash/library.swf'), 'ui/Flash/library.swf', False)
    display = named_path(doc, 106, 'CharacterDisplay', lib)
    bounds = source_bounds(doc, display['leafCharacterId'], lib)
    if bounds != [0, 0, 6059, 10307]:
        raise ValueError('Original Model3D viewport differs')
    cfg = configparser.ConfigParser(); cfg.read_string(read('ui/Config/character.ini').decode())
    camera = {k: [float(cfg['Elf_1'][k+axis]) for axis in 'xyz'] for k in ('camera', 'target')}
    effects = {}
    with tempfile.TemporaryDirectory(prefix='oc2-preview-evidence-') as tmp:
        for name in EFFECTS:
            raw = read(name); path = Path(tmp)/name; path.write_bytes(raw)
            record = effect_render_state(BDAE(path))
            record['cullEnabled'] = cull_state(record['profiles'], 'tech0')
            record['sha256'] = hashlib.sha256(raw).hexdigest()
            effects[name] = record
    return {'boundsTwips': bounds, 'display': display, 'camera': camera, 'effects': effects}


def main():
    import argparse, json
    from analyze_native_resources import NativeImage
    from native_character_presentation_probe import PresentationProbe
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    root = Path(__file__).resolve().parents[1]
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((root/'analysis/raw').resolve()):
        cli.error('Original evidence reports stay in ignored analysis/raw/')
    image = NativeImage((root/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes())
    probe = PresentationProbe(image)
    record = {'format': 'oc2-source-character-presentation-evidence-v1',
              'native': verify_native(image), 'assets': assets(Sources(DEFAULT_SOURCE).read),
              'newModel': probe.new_model(), 'dirtyRebuild': probe.rebuild_factory(),
              'light': probe.ui_light(), 'fontGeometry': probe.font_geometry_units(),
              'packedColorBlockExample': {'explicitInput': [0x12abef, 0xf05431],
                                          'result': probe.packed_colors(0x12abef, 0xf05431)},
              'limits': ['First UI frame only; continuous Model3D animation not restored.',
                         'Original packed colors use low-byte red; trial look selects an existing table entry.',
                         'Name actor relation/visibility and exact font atlas/billboard inputs not recovered.',
                         'Browser RTT, skeleton upload and PNG composition are host interfaces, not Android GPU capture.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2)+'\n')


if __name__ == '__main__':
    main()
