"""Read-only class/skill wiring audit; never opens saves, servers or browsers."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-choice-skill-20261115'
PANEL_PUBLIC=ROOT/'analysis/raw/character-progression-20261114/panel-candidate-final/public'
REVIEWED=ROOT/'analysis/raw/showcase-20261110/running-preview'
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
ANCHORS={
 'deploy/entry_ui.mjs':['profession:[1,3,2,5,4][draft.cls]','connect(role.name,credentials,role.profession)'],
 'deploy/player_choice_registry.mjs':['const PROFESSIONS=[1,3,2,5,4]','registry.check(record.sourceAvatar,record.profession)'],
 'deploy/quest_delivery.mjs':['/__delivery/quest_world.mjs'],
 'deploy/quest_world.mjs':["['field-inventory','field-skills','hotbar-settings','field-attack']",'msg.character?.sourceAvatar',"document.querySelectorAll('.hotbar-slot')",'createCharacterChoiceSkills','createCharacterSourcePanels'],
 'deploy/prepare_delivery.mjs':['stageCharacterHotbarEntry(stageCharacterPanelsEntry(entrySource))'],
 'tools/preview/character-source-state.mjs':['profile.catalogs?.[String(profession)]','learned:known?','locked:finite(level)?'],
 'tools/preview/character-source-panels.mjs':['sourceProfessionSkills(profile,role.profession','No original equipped snapshot','SkillSetting','SkillPassive'],
 'deploy/character_hotbar.mjs':['role.profession===2'],
 'tools/native_cast.py':["BINDINGS = {'fireball':17,'frost_blast':94,'arcane_missile':90}"],
}


def source_at(url):
    if url=='/character-source-panels.mjs':return ROOT/'tools/preview/character-source-panels.mjs'
    if url=='/character-source-state.mjs':return ROOT/'tools/preview/character-source-state.mjs'
    if url=='/character-source-panels.css':return ROOT/'tools/preview/character-source-panels.css'
    if url=='/source-ui-svg.js':return REVIEWED/'prototype/public/source-ui-svg.js'
    if url.startswith('/assets/character-source/'):return PANEL_PUBLIC/url.lstrip('/')
    if url.startswith('/assets/ui/'):return REVIEWED/'game-data/converted/ui'/url.removeprefix('/assets/ui/')
    return PANEL_PUBLIC/url.lstrip('/')


def skill_dependencies(profile):
    urls={'/assets/character-source/panels.json','/character-source-panels.mjs','/character-source-state.mjs',
          '/character-source-panels.css','/source-ui-svg.js',
          '/assets/ui/chineseText.woff','/assets/ui/chineseDisplay.woff','/assets/ui/leagueGothic.woff'}
    def visit(value):
        if isinstance(value,dict):
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
        elif isinstance(value,str)and value.startswith('/assets/'):urls.add(value)
    for key in ['catalogs','frame','tabs']:visit(profile[key])
    for name in ['SkillSetting','SkillPassive','WindowStack']:visit(profile['windows'][name])
    checked=set()
    while True:
        pending={url for url in urls-checked if url.endswith('.svg')}
        if not pending:break
        for url in pending:
            checked.add(url);path=source_at(url)
            if not path.is_file():continue
            for node in ET.fromstring(path.read_bytes()).iter():
                for key,value in node.attrib.items():
                    if(key=='href'or key.endswith('}href'))and value.startswith('/assets/'):urls.add(value)
    return {url:{'available':(path:=source_at(url)).is_file(),
                 **({'bytes':path.stat().st_size,'sha256':SHA(path.read_bytes()),'path':str(path.relative_to(ROOT))}if path.is_file()else{})}
            for url in sorted(urls)}


def audit(output):
    output=Path(output).resolve()
    if not output.is_relative_to(RAW.resolve())or output.exists():raise ValueError('Choose a new ignored character-choice-skill output directory')
    sources={}
    for name,needles in ANCHORS.items():
        raw=(ROOT/name).read_bytes();lines=raw.decode().splitlines()
        sources[name]={'sha256':SHA(raw),'anchors':{needle:[number for number,line in enumerate(lines,1)if needle in line]for needle in needles}}
    entry=(ROOT/'deploy/entry_ui.mjs').read_text()
    match=re.search(r'profession:(\[1,3,2,5,4\])\[draft\.cls\]',entry)
    profile_path=PANEL_PUBLIC/'assets/character-source/panels.json';private=None
    if profile_path.is_file():
        profile=json.loads(profile_path.read_text());dependencies=skill_dependencies(profile)
        private={'panelManifestSHA256':SHA(profile_path.read_bytes()),'catalogs':{key:{'firstSkillId':rows[0]['skillId'],
          'active':sum(row['kind']=='active'for row in rows),'passive':sum(row['kind']=='passive'for row in rows)}for key,rows in profile['catalogs'].items()},
          'dependencies':dependencies,'dependencyCount':len(dependencies),'allDependenciesPresent':all(row['available']for row in dependencies.values())}
    report={'format':'oc2-character-choice-skill-audit-v1','uiProfessionOrder':json.loads(match[1])if match else None,'sources':sources,
      'privateOriginalPanelClosure':private,'privateOriginalPanelStatus':'available'if private else'explicitly skipped: original panel material is private',
      'boundaries':['Static source audit and original exported panel material only; no original server input, save, credentials, browser, production or deployment accessed.',
       'Read-only helper accepts authenticated session identity through an injected reader; source learning/equipment remains unknown and no hotbar is filled.',
       'Current source hashes describe this audit instant; shared player/body integration is owned by root and may subsequently change.']}
    output.mkdir(parents=True);(output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();report=audit(args.output)
    print(json.dumps({'output':str(args.output/'audit.json'),'professions':report['uiProfessionOrder'],
      'dependencyCount':report['privateOriginalPanelClosure']['dependencyCount']if report['privateOriginalPanelClosure']else None,
      'realSavesOrServersUsed':False}))
