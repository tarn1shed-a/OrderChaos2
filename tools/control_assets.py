"""Verify original control methods and export their art/parameter evidence.

Hashes identify the exact method bodies manually traced in the supplied build.
Changed methods require a fresh trace rather than silently reusing constants.
Decoded scripts, tables and PNGs remain in the ignored local asset directory.
"""
import hashlib
import io
import json

from PIL import Image
from hud_assets import document, named_path, sprite_frames, vector_shape
from optimized_abc import extract_abc, parse_abc, named_method
from skill_attachments import decode_ftable

PROGRAMS = {
    'Joystick': '1da8adfa22db978c1c4c26912301b01843012facb8b1818fbed5b9c3d4758057',
    'OperationPanel2': 'fe64a39c4af16b7cb53f9e13330f1c4dc90e05414eb2233f7c7ed9f69105cdc0',
}

METHODS = {
    'SpellPanel2.onSlotPress':'575f6642bf347f187c69d1fa26527de08f40babaef70ae6cf78c18faa90fc884',
    'SpellPanel2.onSlotRelease':'2333ba280f8d6233ee666236b832739938129ebdaeb1b2521548a995cb91aa55',
    'SpellPanel2.onSlotReleaseOut':'2dfe62bdd67f3ce72662dadd52bb9daceced32d9ee1c29dcf0296aebe239faca',
    'Joystick.init': 'ece0cc09776a2ee62d83a2a1a44cc7d3a9f41b3360e6f41e8240ed55043f8eb3',
    'Joystick.OnMouseMove': '4bb61f695bdea3e4da8cda73b4e5f218b556da51f12ff022640ee886053e6708',
    'Joystick.StartMove': '02726cd9d430a9bc7b2e584bb2226a4e2b9842514d884a7b0c91dba86c7d1445',
    'Joystick.endMove': '53043e28d490998caa9f516cb39f53a9056075caf68411bec6613aeae30ddde0',
    'Joystick.OnRelease': '9578baf8b03a01e1100b3f6e77817251bc1509785e8d3e49fa84a167c07dc862',
    'OperationPanel2.init': '1cfe9c1f0980541eaad4785fbe8f1393c1e869939aabe9602397c3f9a8416bcf',
    'OperationPanel2.onJumpPress': '0e6fbb6bbfd966efcf55aad6ee6437c0cd14fbe0940ac7f19156e3198f07e4f5',
    'OperationPanel2.onJumpRelease': '4de38af28912f79072a0674b0f96a32642d111463c438f2ab52be2ee8541ea33',
    'OperationPanel2.onEventInteraction': 'c00334196188f37654403540d18d22681a433a0daad9a9279b26a24d3351745d',
    'OperationPanel2.onInteractChangeMid': 'b393a41113c7434c4db339d24626ccb692638367d959805947a0cffcbf6dc18e',
    'OperationPanel2.onInteractionClick':'737ba313fd06a0a6308f009a9542a59e369a32a29ac33270ab670f0efd6c8e13',
    'SpellPanel2.onRotateMidCallback': 'a9e41109ba59da2ecf2ae7cb0bf11f571d3221ae257ff0e0067bdbde75a1bac9',
}


def recover_controls(extract, output, hud):
    output.mkdir(parents=True, exist_ok=True)
    loaded = {}
    def load(path):
        if path not in loaded:
            value = extract(path)
            loaded[path] = bytes(value) if isinstance(value, (bytes, bytearray)) else value.read_bytes()
        return loaded[path]

    programs = {name: parse_abc(extract_abc(load(f'ui/Flash/{name}.swf')))
                for name in ['Joystick', 'OperationPanel2']}
    # Method code hashes alone do not cover the constant-pool values they index.
    for name, program in programs.items():
        if program['sourceSHA256'] != PROGRAMS[name]:
            raise ValueError('Original control container changed; trace required: '+name)
    proofs = {}
    for key, expected in METHODS.items():
        cls, name = key.split('.')
        result = named_method(programs['Joystick' if cls == 'Joystick' else 'OperationPanel2'], cls, name)
        if result['codeSHA256'] != expected:
            raise ValueError('Original control method changed; trace required: '+key)
        proofs[key] = {k: v for k, v in result.items() if k != 'instructions'}
        proofs[key].update(sourceSWF=f'ui/Flash/{"Joystick" if cls == "Joystick" else "OperationPanel2"}.swf',
                           offsetBasis='zero-based ABC payload')
    proto = {r['skillId']: r for r in decode_ftable(load('tables/skill_proto.tbl'), 'skillId')['rows']}
    runes = {r['id']: r for r in decode_ftable(load('tables/skill_runes.tbl'), 'id')['rows']}
    icons = {}
    selections = {'sword': (70, 280, 'right_sword_01', 'skill/sword.png'),
                  'unarmed': (4, 16, 'fist_01', 'skill/no_weapon.png')}
    for key, (pid, rid, name, icon) in selections.items():
        if proto.get(pid, {}).get('rune0') != rid or proto[pid]['editName'] != name or runes.get(rid, {}).get('icon') != icon:
            raise ValueError('Original basic attack proto/rune/icon mismatch')
        icons[key] = {'sourceSkillId': pid, 'sourceRuneId': rid, 'sourceEditName': name,
                      'sourcePath': 'ui/icons/'+icon, 'sourcePack': 'ui_icon_1.bin'}
    for key, filename in [('jump', 'jumpicon.png'), ('fly', 'fly.png'),('loot','loot.png')]:
        icons[key] = {'sourcePath': 'ui/icons/interactive/'+filename, 'sourcePack': 'ui_icon_2.bin'}
    for key, entry in icons.items():
        raw = load(entry['sourcePath'])
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.size != (96, 96) or image.mode != 'RGBA':
                raise ValueError('Unexpected original control icon format')
            image.verify()
        filename = 'control-'+key+'.png'; (output/filename).write_bytes(raw)
        entry.update(url='/assets/ui/'+filename, width=96, height=96,
                     mode='unchanged-full-source-png', sourceSHA256=hashlib.sha256(raw).hexdigest())
    lib = document(load('ui/Flash/library.swf'), 'ui/Flash/library.swf', root=False)
    icon_placements = {}
    hit_zones = {}
    for key, sprite, size in [('attack', 2307, 138), ('interaction', 2286, 102)]:
        matrix = named_path(lib, sprite, 'Icon', lib)['matrixPixels']
        if matrix[1:3] != [0, 0]:
            raise ValueError('Unexpected original icon affine transform')
        icon_placements[key] = {'sourceSpriteId': sprite, 'sourceSlotPixels': size,
            'matrixPixels': matrix, 'boundsFraction': [matrix[4]/size, matrix[5]/size,
                                                     96*matrix[0]/size, 96*matrix[3]/size]}
        hit = named_path(lib, sprite, 'hitzone', lib)
        children = sprite_frames(lib, hit['leafCharacterId'])[0]
        if len(children) != 1 or children[0]['matrixPixels'] != [1, 0, 0, 1, 0, 0]:
            raise ValueError('Unexpected original hit zone display list')
        kind, raw = lib['records'][children[0]['characterId']]
        shape = vector_shape(kind, raw)
        hit_zones[key] = {'sourceShapeId': children[0]['characterId'], 'pathPixels': shape['pathPixels'],
            'matrixFraction': [v/size for v in hit['matrixPixels']]}
    result = {'format': 'oc2-original-controls-v1', 'methods': proofs, 'icons': icons,
        'containers': {name: {'signatureCount': len(p['signatures']), 'bodyCount': len(p['bodies']),
            'bytesConsumed': p['bytesConsumed'], 'abcSHA256': p['sourceSHA256']} for name, p in programs.items()},
        'iconPlacements': icon_placements, 'hitZones': hit_zones,
        'joystick': {'diameter': 48, 'radius': 24, 'baseFollowFraction': .1,
            'activationMaxXFraction': .25, 'activationMinYFraction': .5, 'moveEventGate': 3,
            'nativeRegionSizeFraction': [.33, .4], 'stopArguments': [-1000, False, False, 0],
            'hiddenWhileIdle': True, 'activation': 'first-touch point; StartMove guard',
            'insideRadius': 'nonfinite distance argument; native wrapper rejects it; retain last accepted direction',
            'speedRatioOutsideRadiusAtScale1': 2,
            'webAdaptations': ['Pointer Events replace native touch-controller APIs; gate counts captured pointer moves.',
                'Uniform HUD scale; local server speed/world scale retained; native speed ratio is not a world velocity.',
                'Native camera-region exclusion is recorded separately; its intersection with the Flash guard is unproven.',
                'No Flash VM is executed; behavior is reconstructed from static method/native-wrapper analysis.']},
        'attack': {'iconCallback': 'Spell_GetSpellInfo → Icon → IconImage',
            'webEquipmentSelection': {'trainingSword': 'sword', 'emptyMainHand': 'unarmed'},
            'nativeWeaponToSkillSelectionRecovered': False},
        'interaction': {'default': 'jump', 'pressCallback': 'Hero_SetJumpState(true)',
            'releaseCallback': 'Hero_SetJumpState(false)', 'releaseOutReleases': True,
            'contextualFunctionOverridesJump': True, 'flyIconRecovered': True,
            'webGameplay': 'default jump; server-owned local corpse loot overrides it with contextual tap; flying/other quest functions not implemented',
            'nativeJumpPhysicsRecovered': False},
        'sources': {path: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for path, raw in loaded.items()},
        'scriptExecution': False}
    hud['nativeControls']['format'] = 'oc2-original-mobile-controls-v2'
    hud['nativeControls']['joystick'].pop('runtimePositionAndSizeAreNotProvenBySWF', None)
    hud['nativeControls']['joystick']['runtimeEvidenceProfile'] = result['format']
    hud['provenance']['limitations'] = [v.replace('Original MP/vehicle/interaction/consumable systems are not added',
        'Original MP/vehicle/contextual-interaction/consumable systems are not added') for v in hud['provenance']['limitations']]
    (output/'controls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    (output/'hud.json').write_text(json.dumps(hud, ensure_ascii=False, indent=2, allow_nan=False))
    return result
