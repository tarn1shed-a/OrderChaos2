"""Recover the original mage skill catalog, UI display lists and bounded art.

Read-only: no native/Flash scripts execute. Layout evidence is kept separate
from the desktop shell and from the web prototype's independently chosen skills.
"""
import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image
from hud_assets import document, named_path, rectangle_bitmap, sprite_frames, _ini_blocks
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names

CONFIG = 'ui/Config/interface_common_2.ini'
MAGE = 2
ART = {'passiveFrame': ('passivity_bg', 536, 535),
       'skillPoint': ('igm_skillpoint', 1965, 1964),
       'lock': ('itempanellocked', 496, 495),
       'arrow': ('button_skillarrow', 2267, 2266)}


def mage_catalog(protos, runes, unlocks, names):
    """Join checked IDs; never infer a learned/equipped state from level alone."""
    protos = {row['skillId']: row for row in protos}
    runes = {row['id']: row for row in runes}
    grouped = {}
    for row in unlocks:
        if row['needprofession'] == MAGE:
            key = (row['skill_id'], row['rune_id'])
            if key in grouped:
                raise ValueError('Duplicate mage skill unlock')
            if row['rune_id'] not in range(4) or row['category'] not in (0, 1):
                raise ValueError('Unsupported mage unlock category/rune')
            grouped[key] = row
    result = []
    for (skill_id, number), requirement in grouped.items():
        if number:
            continue
        proto = protos[skill_id]
        if proto['reqProfession'] not in (0, MAGE):
            raise ValueError('Mage proto profession mismatch')
        entries = []
        for index in range(4):
            unlock = grouped.get((skill_id, index))
            if not unlock:
                continue
            rune = runes[proto['rune'+str(index)]]
            name, description = names.get(rune['nameStrId']), names.get(rune['descStrId'])
            if not name or not description or not re.fullmatch(r'skill/[a-z0-9_]+\.png', rune['icon']):
                raise ValueError('Missing or unsafe source skill text/icon')
            entries.append({'index': index, 'runeId': rune['id'], 'name': name,
                'description': description, 'sourceIcon': rune['icon'],
                'sourceNameId': rune['nameStrId'], 'sourceDescriptionId': rune['descStrId'],
                'requirement': {'level': unlock['needlevel'], 'points': unlock['needskillpoints'],
                                'sourceRowId': unlock['id']}})
        if proto['filter'] not in (4, 74):
            raise ValueError('Unexpected source mage classification')
        passive = proto['filter'] == 74
        if len(entries) != (1 if passive else 4):
            raise ValueError('Unexpected number of mage inscriptions')
        result.append({'id': skill_id, 'kind': 'passive' if passive else 'active',
            'sourceEditName': proto['editName'], 'sourceFilterId': proto['filter'], 'base': entries[0], 'runes': entries[1:],
            'sourceStats': {key: proto[key] for key in ('powerCost','coolDownTime','chantTime','channelTime')},
            'sourceStatsAreNotWebCombatRules': True})
    return sorted(result, key=lambda row: (row['kind'], row['base']['requirement']['level'], row['id']))


def recover_skill_ui(extract, output):
    loaded = {}
    def load(path):
        if path not in loaded:
            value = extract(path)
            loaded[path] = value if isinstance(value, bytes) else Path(value).read_bytes()
        return loaded[path]
    docs = {name: document(load('ui/Flash/'+name+'.swf'), 'ui/Flash/'+name+'.swf', root=name!='library')
            for name in ('library', 'SkillSetting', 'SkillPassive')}
    library = docs['library']
    config = _ini_blocks(load(CONFIG))
    # Assert the actual page route; a similarly named editor table is not UI evidence.
    for name, url in [('SkillSetting','SkillSetting.swf'), ('SkillPassive','SkillPassive.swf')]:
        if not any(row.get('name') == name and row.get('url') == url and row.get('parent') == 'Skill'
                   for row in config):
            raise ValueError('Original skill page configuration changed')
    layouts = {}
    for key, stem, symbol, fields in (
        ('active','SkillSetting','symWindowSkillSetting',
         ['_SkillList','_SkillList.item_0.btnItemX','_SkillList.item_6.btnItemX',
          '_RuneList.item_0.btnItemX','_RuneList.item_1.btnItemX','_RuneList.item_2.btnItemX',
          'detailSkill','detailRune','_CtrlPack.btnVariable']),
        ('passive','SkillPassive','symWindowSkillPassive',
         ['_SkillList','_SkillList.item_0.btnItemX','_SkillList.item_3.btnItemX',
          'detailSkill','_SkillSlot0','_SkillSlot1','btnLearn'])):
        doc = docs[stem]; cid = doc['symbols'][symbol]
        layouts[key] = {'sourceSWF': doc['path'], 'sourceSHA256': doc['sourceSHA256'],
            'sourceSymbol': symbol, 'sourceSpriteId': cid, 'stagePixels': doc['stagePixels'],
            'fields': {field: named_path(doc, cid, field, library) for field in fields},
            'visibleSkills': 7 if key=='active' else 4}
    destination = Path(output)/'ui'; destination.mkdir(parents=True, exist_ok=True)
    assets = {}
    for key, (symbol, cid, shape) in ART.items():
        if library['symbols'].get(symbol)!=cid or shape not in [v.get('characterId') for v in sprite_frames(library,cid)[0]]:
            raise ValueError('Original skill UI art reference changed')
        kind, payload = library['records'][shape]
        if kind != 2:
            raise ValueError('Unsupported skill art shape')
        bitmap, rect, matrix, bounds, _ = rectangle_bitmap(payload)
        names = [name for name, identifier in library['symbols'].items() if identifier == bitmap]
        if len(names)!=1 or Path(names[0]).name!=names[0]:
            raise ValueError('Unsafe source skill atlas name')
        path = 'ui/Texture/'+names[0]; raw = load(path)
        image = Image.open(io.BytesIO(raw))
        if image.size != library['bitmaps'][bitmap] or image.mode != 'RGBA':
            raise ValueError('Source skill atlas metadata mismatch')
        left, top, right, bottom = rect
        if not 0 <= left < right <= image.width or not 0 <= top < bottom <= image.height:
            raise ValueError('Skill art crop outside atlas')
        crop = image.crop(rect)
        if matrix[0]<0: crop=crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if matrix[3]<0: crop=crop.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        filename = 'skill-ui-'+key+'.png'; crop.save(destination/filename)
        assets[key] = {'url':'/assets/ui/'+filename, 'width':crop.width, 'height':crop.height,
            'sourceSWF':library['path'], 'sourceSWFSHA256':library['sourceSHA256'],
            'sourceSymbol':symbol, 'sourceSpriteId':cid, 'sourceShapeId':shape,
            'sourceAtlas':path, 'sourceSHA256':hashlib.sha256(raw).hexdigest(),
            'sourceRect':rect, 'sourceMatrixTwips':matrix, 'mode':'lossless-source-atlas-crop'}
    tables = {name: decode_ftable(load('tables/'+name+'.tbl'), identifier) for name, identifier in
              [('skill_proto','skillId'), ('skill_runes','id'), ('skill_unlock','id'), ('skill_tree_filter','Id')]}
    filters = {row['Id']:row['filterName'] for row in tables['skill_tree_filter']['rows']}
    if filters.get(4)!='Mage' or filters.get(74)!='Passive Skills':
        raise ValueError('Original skill category labels changed')
    names = decode_localized_names(load('tables/String_Skill_zh.tbl'), 'SC')
    catalog = mage_catalog(tables['skill_proto']['rows'], tables['skill_runes']['rows'],
                           tables['skill_unlock']['rows'], names['values'])
    if len([row for row in catalog if row['kind']=='active'])!=9 or len(catalog)!=14:
        raise ValueError('Mage catalog differs from the verified source build')
    icons = {}
    for skill in catalog:
        for entry in [skill['base'], *skill['runes']]:
            path = 'ui/icons/'+entry['sourceIcon']
            if path not in icons:
                raw = load(path)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format!='PNG' or image.mode not in ('RGB','RGBA') or image.size!=(96,96):
                        raise ValueError('Original skill catalog icon format mismatch')
                    image.verify()
                filename = 'skill-catalog-'+Path(path).stem+'.png'
                (destination/filename).write_bytes(raw)
                icons[path] = {'url':'/assets/ui/'+filename,'width':96,'height':96,
                    'sourcePath':path,'sourcePack':'ui_icon_1.bin',
                    'sourceSHA256':hashlib.sha256(raw).hexdigest(),'mode':'unchanged-full-source-png'}
            entry['icon'] = icons[path]
    profile = {'format':'oc2-original-skill-ui-v1','professionId':MAGE,
        'layouts':layouts,'assets':assets,'skills':catalog,
        'sources':{**{'tables/'+name+'.tbl':{'pack':'tables.bin',**table['verification']}
                     for name,table in tables.items()},
                   'tables/String_Skill_zh.tbl':{'pack':'tables.bin',**names['verification']},
                   CONFIG:{'pack':'conf.bin','sourceSHA256':hashlib.sha256(load(CONFIG)).hexdigest()}},
        'provenance':{'swfScriptExecution':False,'nativeProgressionImplemented':False,
            'layout':'source-named-display-lists; 950x600 content stage',
            'limitations':['The desktop title bar, tabs, keyboard navigation, pagination and text styling are web adaptations.',
                'Source layout supports seven active/four passive visible icons and three inscription options; runtime dynamic visibility and typography are not fully recovered.',
                'Skill learning, equipped passives, inscription schemes and server skill points are not implemented. No learned state is inferred from level.',
                'Catalog numbers and descriptions are original reference data; they do not replace web combat rules.']}}
    (destination/'skill-ui.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2))
    return profile
