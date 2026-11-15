"""Inventory the nine original player bodies and their real material references."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from player_choice_matrix import ROOT, RAW


def export():
    from resource_packs import DEFAULT_SOURCE
    from map_loading_evidence import Sources
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_materials import read_material_record
    source = RAW / 'matrix-source-v1.json'
    matrix = json.loads(source.read_text())
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    old_human = ROOT/'analysis/raw/character-human-creation-defaults-20261115/candidate-v1/manifest.json'
    keys = ['human-male','human-female','mendel-male','mendel-female','elf-male','elf-female','orc-male','orc-female','kartan']
    registry = {'format':'oc2-original-player-choice-registry-v1','sourceMatrixSHA256':source_sha,
                'originalAccountAdmissionKnown':False,'initialEquipmentKnown':False,'learnedSkillsKnown':False,'bodies':[]}
    inventory = []
    sources = Sources(DEFAULT_SOURCE)
    with tempfile.TemporaryDirectory(prefix='oc2-choice-source-') as temporary:
        for index, row in enumerate(matrix['bodyChoices']):
            key = keys[index]
            choices = []
            for c in row['choices']:
                draft = c['stages'][1]['freshAppearance']
                choices.append({'professionIndex':c['uiProfessionIndex'],'profession':c['profession'],
                                'creationDisplayId':draft['displayId'],'appearance':{
                                    'face':draft['face'],'hair':draft['hair'],'beard':draft['beard'],
                                    'skinColor':draft['skinColorWord'],'hairColor':draft['hairColorWord']}})
            registry['bodies'].append({'key':key,'uiRace':row['uiRace'],'gender':row['gender'],'race':row['internalRace'],
                'sourceModelId':row['sourceModel']['ID'],'sourceProfileSHA256':hashlib.sha256(old_human.read_bytes()).hexdigest() if key=='human-male' else source_sha,
                'choices':choices})
            path = row['sourceModel']['ModelPath']
            raw = sources.read(path)
            local = Path(temporary)/(key+'.bdae');local.write_bytes(raw)
            reader = BDAE(local);data = reader.parse()
            materials = []
            for material in data['materials']:
                record = read_material_record(reader, material['name'])
                references = {name:{'path':p,'candidates':len(sources.candidates(p))} for name,p in record['samplers'].items()}
                materials.append({'name':material['name'],'effectPath':record['effectPath'],
                                  'effectCandidates':len(sources.candidates(record['effectPath'])),
                                  'samplers':references})
            animation_path = row['sameDirectoryAnimationCandidate']
            animation_raw = sources.read(animation_path)
            animation_local = Path(temporary)/(key+'-animation.bdae');animation_local.write_bytes(animation_raw)
            animation = BDAEAnimation(animation_local)
            names = {}
            for clip in animation.ranges(): names.setdefault(clip['name'],[]).append(clip)
            wanted = ['idle','walk_forward','run_normal_front','run_idle','jump_start','jump_air','jump_air_drop','jump_land','jumplandrun','swim_idle','swim_forward']
            inventory.append({'key':key,'sourceModelId':row['sourceModel']['ID'],'sourceModelPath':path,
                'modelSHA256':hashlib.sha256(raw).hexdigest(),'modelBytes':len(raw),'meshes':len(data['meshes']),
                'materialCount':len(materials),'materials':materials,
                'sourceAnimationPath':animation_path,'animationSHA256':hashlib.sha256(animation_raw).hexdigest(),
                'animationBytes':len(animation_raw),'animationRangeCount':sum(map(len,names.values())),
                'basicSourceRanges':{name:names.get(name,[]) for name in wanted},
                'sourceRangesNotYetSamplingAdmission':True,'rigAndWeightsNotYetNewlyVerified':True,
                'originalWorldOrCombatNotNewlyAdmitted':True})
    for name,value in [('registry-v1.json',registry),('resource-inventory-v1.json',{'format':'oc2-player-choice-resource-inventory-v1','bodies':inventory,'sourceProofs':sources.proofs})]:
        target=RAW/name
        if target.exists():raise ValueError('Preserve previous choice inventory')
        target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'key':r['key'],'meshes':r['meshes'],'materials':r['materialCount'],'ranges':r['animationRangeCount'],
                      'missingBasicNames':[k for k,v in r['basicSourceRanges'].items()if not v],
                      'missingOrAmbiguousSamplers':sum(s['candidates']!=1 for m in r['materials'] for s in m['samplers'].values())}for r in inventory]))


def export_features():
    from resource_packs import DEFAULT_SOURCE
    from map_loading_evidence import Sources
    from bdae_convert import BDAE
    from character_materials import read_material_record
    proof=json.loads((RAW/'world-appearance-source-v1.json').read_text())
    paths=sorted({q['path'] for row in proof['choices'] for q in row['resourceRequests'] if q.get('path')})
    sources=Sources(DEFAULT_SOURCE);records=[]
    with tempfile.TemporaryDirectory(prefix='oc2-choice-features-') as temporary:
        for i,path in enumerate(paths):
            raw=sources.read(path);local=Path(temporary)/(str(i)+'.bdae');local.write_bytes(raw)
            reader=BDAE(local);data=reader.parse();materials=[]
            for material in data['materials']:
                record=read_material_record(reader,material['name'])
                materials.append({'name':material['name'],'effectPath':record['effectPath'],
                    'effectCandidates':len(sources.candidates(record['effectPath'])),
                    'samplers':{name:{'path':p,'candidates':len(sources.candidates(p))}for name,p in record['samplers'].items()}})
            records.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'materials':materials})
    target=RAW/'feature-material-inventory-v1.json'
    if target.exists():raise ValueError('Preserve original feature material inventory')
    result={'format':'oc2-player-choice-feature-materials-v1','sourcePlayerChoices':45,'featureModels':records,
        'sourceDescriptorOverrides':sorted({p for row in proof['choices']for q in row['resourceRequests']for p in q.get('textureOverrides',[])if p}),
        'sourceProofs':sources.proofs,'geometrySamplingOrRigAdmissionClaimed':False}
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'featureModels':len(records),'unresolvedSamplers':[(r['path'],s)for r in records for m in r['materials']for s in m['samplers'].values()if s['candidates']!=1]}))


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--features',action='store_true');args=cli.parse_args()
    export_features() if args.features else export()
