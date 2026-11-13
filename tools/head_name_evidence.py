"""Read bounded overhead-text evidence; never infer missing live actor state.

Original code, fonts, shaders and complete reports remain private. This reader
does not enable names, modify characters or claim an Android frame was captured.
"""
import hashlib
import struct
import tempfile
from pathlib import Path

ROUTINES = {
    0xa09b20: (464, '4a1def0723fd362c60efd90f6729bb4e74b912c8e5bd3affa429bfd167dddda2'),
    0x82f09c: (32, '358ebc8be43b82e9d819edff43c152ad878fe38a2123e8204cecfbb836fe5d0a'),
    0x3a9498: (1884, '653c5a6c1a505d6aee10dc47c1e801f8008adf5f8fb0ab91eeb0a5f8d5425c35'),
    0x3a9bf4: (324, '2b339a9712745f0e698f9c7a309cf0a27ccff43c2380176f114db9a5e7fa23db'),
    0x3aa2b4: (224, '853a191085762f9b7c298ecbb3c01040a69529aa205c648bdd6c447818ade7ce'),
    0x36a218: (1268, '5fc768bb069632e3d2ae9d7669794a5f8f230fb577ca568290bb05b8fae3941e'),
    0x36d344: (3620, '3d3628c904f121475c8955d5d7b00e31b00a32cc330e7f2c406ef17b826a8412'),
    0x1364640: (8, 'da8e434aac24641c2ccf1a5923875612a22897c4dbe65cc13c69c8c1362c0420'),
    0x1363f10: (8, '8b76550b46c70b11361b4b5459607845c5ff8b6f985b740747e2bbdd2a4b11da'),
    0x36e18c: (28, '2860f90ff87d9b23ecddce21ed3ba6fe8fe9069b81b8630d410d270717402f55'),
    0x91088c: (4436, 'f976ba1ce162f719c4741b74b8271748310fe1cc811b172cc66b960900c1b831'),
    0x900234: (5752, '337e2fbf7d2b5ed1b5c85a104b961ca74b1ca38f364b6de849d8b4d650b9c24f'),
    0x55469c: (424, '5415be6a0f1593b10ac6615e5ac821bfe5eb47fa08a2c784884fa21a4fcc4638'),
}
ASSETS = {
    'CustomEffects.bdae': '59287bd2eba7f53c6f68b2b20b96eabf23f1eccd883ea75070a0ad5f710cb3ae',
    'UnlitTexturedVP.glsl': '3a08d697c016db060ba59de169d7bf129b006587bff51e4cf2ee8917a03d1f98',
    'FontTexturedFP.glsl': '822f569f939e5de40e877d0f8a8c013f3198df62d939f2f35788a8ca5858d10a',
}
FONTS = {
    'Alegreya-Bold': '361512a5a3e337bf3f57d998451831539363497390440be0250f00d5d53e5ba4',
    'Matisse-B': 'cdc58d00cee42df454cee52570a8f015850ee934d9c3fa290918926b9393ccde',
    'LeagueGothic-Regular': '2ce848b3e46f0bf41b937ea2d6bb59fb2c0485c9d05e8b229eb24d2d21b7434f',
}


def verify_native(image):
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original overhead-text routine differs')
    reloc = {r['r_offset']: r['r_addend'] for r in
             image.elf.get_section_by_name('.rela.dyn').iter_relocations()
             if r['r_info_type'] == 1027}
    for slot, target in {0x240e098: 0x1364640, 0x240e158: 0x1363f10,
                         0x240dfd0: 0x36e18c, 0x2422a10: 0xa09b20}.items():
        if reloc.get(slot) != target:
            raise ValueError('Original overhead-text virtual slot differs')
    fonts = [image.read(0x1e148c8+i*64, 64).split(b'\0')[0].decode('ascii')
             for i in range(15)]
    if fonts != ['Matisse-B' if i == 6 else 'Alegreya-Bold' for i in range(15)]:
        raise ValueError('Original overhead-text language table differs')
    return {'routines': len(ROUTINES), 'primaryFontByLanguageIndex': fonts,
            'glyphUnitFactors': list(struct.unpack('<2f', image.read(0x1df7aac, 8))),
            'farDistanceFactors': list(struct.unpack('<2f', image.read(0x1df7ac4, 8))),
            'originalAndroidFrameObserved': False, 'webNamesEnabled': False}


def read_assets(read, loose_root):
    from bdae_convert import BDAE
    from scene_render_state import _shader, read_pass_state
    data = {}
    for name, digest in ASSETS.items():
        raw = read(name)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Original overhead-text asset differs')
        data[name] = raw
    fonts = {}
    for name, digest in FONTS.items():
        raw = (Path(loose_root)/'ui/Font'/f'{name}.ttf').read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Original overhead-text font differs')
        fonts[name] = {'bytes': len(raw), 'sha256': digest}
    effects = []
    wanted = {'TTFBILLBOARD_Blend_Texture_Alpha_No_Culling', 'Font Blend No Depth'}
    with tempfile.TemporaryDirectory(prefix='oc2-name-evidence-') as tmp:
        path = Path(tmp)/'CustomEffects.bdae'; path.write_bytes(data['CustomEffects.bdae'])
        reader = BDAE(path)
        count, table = reader.section(164)
        for index in range(count):
            effect = table+index*56
            name = reader.string(reader.q(effect))
            if name not in wanted:
                continue
            for field in (32, 36):
                profile = reader.rel(effect+field)
                if reader.u(profile) != 1:
                    raise ValueError('Unsupported font technique count')
                technique = reader.rel(profile+4)
                if reader.u(technique+8) != 1:
                    raise ValueError('Unsupported font pass count')
                source_pass = reader.rel(technique+12)
                effects.append({'name': name, 'profileField': field,
                                'vertex': _shader(reader, source_pass),
                                'fragment': _shader(reader, source_pass+24),
                                'state': read_pass_state(reader, source_pass+72)})
    if len(effects) != 4 or {r['name'] for r in effects} != wanted:
        raise ValueError('Expected both original font materials and profiles')
    return {'fonts': fonts, 'effects': effects, 'GPUExecuted': False}


def main():
    import argparse
    import json
    from analyze_native_resources import NativeImage
    from native_head_name_probe import HeadNameProbe
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    root = Path(__file__).resolve().parents[1]
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((root/'analysis/raw').resolve()):
        cli.error('Original evidence reports stay in ignored analysis/raw/')
    image = NativeImage((root/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes())
    probe = HeadNameProbe(image)
    record = {'format': 'oc2-source-head-name-evidence-v1',
              'native': verify_native(image), 'assets': read_assets(Sources(DEFAULT_SOURCE).read, DEFAULT_SOURCE),
              'fontRequests': [probe.font_request(i) for i in range(15)],
              'secondaryFontRequest': probe.font_request(0, secondary=True),
              'faceSelection': [probe.glyph_face(secondary=flag, secondary_available=exists)
                                for flag in (False, True) for exists in (False, True)],
              'matrices': [probe.matrix(camera=(0, 0, d)) for d in (1, 5, 5.01, 10, 50)],
              'limits': ['Font initialization and cache misses are explicit host fixtures; no font face or glyph rasterization succeeds in this probe.',
                         'Empty-text draw exercises the original matrix path, stopping at its upload; no GPU text draw is claimed.',
                         'Relationship, actor-ready state, guild/title and original live camera/scene state remain unobserved in the trial.',
                         'No game runtime, save, role position or Railway change.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'webNamesEnabled': False}))


if __name__ == '__main__':
    main()
