"""Read the original creation UI and execute its 45 reachable display choices.

This establishes client choices, body IDs and fresh UI appearance tuples. It
does not assert original account approval, starter equipment or learned skills.
Existing original-method exports are reused with their current source SWF hash;
no frozen parser, candidate or runtime file is rewritten.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/player-choice-recovery-20261115'
PROFESSIONS = (1, 3, 2, 5, 4)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def recover(image, source):
    from map_loading_evidence import Sources
    from skill_attachments import decode_ftable
    from tutorial_npc_robe_probe import RobeProbe
    from character_human_male_probe import CREATION_SIZE, CREATION_SHA256
    from unicorn import UC_HOOK_CODE

    if sha(image.read(0x542da4, CREATION_SIZE)) != CREATION_SHA256:
        raise ValueError('Original creation stage controller differs')
    sources = Sources(source)
    export_root = ROOT / 'analysis/raw/character-entry-20261113'
    previous_proofs = json.loads((export_root / 'source-proofs.json').read_text())
    ui = {}
    for name in ('CharacterChooseRace', 'CharacterChooseClass'):
        path = 'ui/Flash/' + name + '.swf'
        raw = sources.read(path)
        proof = previous_proofs[path]
        expected = proof.get('sha256') or proof.get('rawSHA256')
        if sha(raw) != expected:
            raise ValueError('Previously exported original UI source differs: ' + path)
        methods_file = export_root / (name + '-methods.json')
        methods = json.loads(methods_file.read_text())
        selected = [m for m in methods if m['class'].startswith('Window_') and
                    m['method'] in ('Init', 'seleteCharacter', 'onFemaleClick', 'onMaleClick')]
        ui[name] = {'source': path, 'sha256': sha(raw),
                    'methodExportSHA256': sha(methods_file.read_bytes()),
                    'methods': selected}
    race_select = next(m['code'] for m in ui['CharacterChooseRace']['methods']
                       if m['method'] == 'seleteCharacter')
    # The real AS hides both gender controls on race4, selects Male, and calls
    # Character_Race(selectedRace,0). Other races preserve gender (-1 argument).
    if [(i['op'], i['args']) for i in race_select if 100 <= i['at'] < 144] != [
        ('getlocal0', []), ('getproperty', ['_SelectedRace']), ('pushbyte', [4]),
        ('ifne', [148]), ('getlocal0', []), ('getproperty', ['_FemaleBtn']),
        ('pushfalse', []), ('setproperty', ['Selected']), ('getlocal0', []),
        ('getproperty', ['_MaleBtn']), ('pushtrue', []), ('setproperty', ['Selected']),
        ('getlocal0', []), ('pushstring', ['Character_Race']),
        ('getproperty', ['<runtime-name>']), ('getlocal0', []), ('getlocal0', []),
        ('getproperty', ['_SelectedRace']), ('pushbyte', [0]),
        ('callpropvoid', ['call', 3])]:
        raise ValueError('Original single-gender branch changed')
    class_select = next(m['code'] for m in ui['CharacterChooseClass']['methods']
                        if m['method'] == 'seleteCharacter')
    if [i['op'] for i in class_select if i['targets']] != ['iffalse'] or \
       ('pushstring', ['Character_Class']) not in [(i['op'], i['args']) for i in class_select]:
        raise ValueError('Original class selection branch changed')

    class Probe(RobeProbe):
        def __init__(self, image, sources):
            self.creation_active = False
            super().__init__(image, sources)
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=0x53d3e8, end=0x53d3e8)

        def hook(self, uc, at, size, data):
            if at == 0x53d3e8 and self.creation_active:
                self.requests.append({'displayId': self.get('W1'),
                                      'arg2': self.get('W2'), 'arg3': self.get('W3')})
                self.set('W0', 0)
                self.set('PC', self.get('X30'))
                return
            return super().hook(uc, at, size, data)

        def fresh(self, race, gender, profession, stage):
            controller, window = self.alloc(0x300), self.alloc(0x400)
            self.w(controller + 0x5c, '3i', race, gender, profession)
            self.w(0x2534300, 'Q', controller)
            self.w(0x2528db0, 'Q', window)
            self.w(0x2534000, 'I', 1)
            self.requests = []
            self.creation_active = True
            try:
                self.call(0x542da4, {'X0': controller, 'W1': stage})
            finally:
                self.creation_active = False
            if len(self.requests) != 1:
                raise ValueError('Unique original model request not reached')
            d = {name: self.r(window + off, 'I')[0] for name, off in
                 [('displayId', 0x2b0), ('face', 0x2e0), ('hair', 0x2cc),
                  ('beard', 0x2e4), ('skinColorWord', 0x2d8), ('hairColorWord', 0x2d0)]}
            return {'stage': stage, 'request': self.requests[0],
                    'freshAppearance': d if stage == 2 else None}

    p = Probe(image, sources)
    displays = {r['ID']: r for r in decode_ftable(sources.read('tables/creaturedisplayinfo.tbl'), 'ID')['rows']}
    models = {r['ID']: r for r in decode_ftable(sources.read('tables/creaturemodeldata.tbl'), 'ID')['rows']}
    features = decode_ftable(sources.read('tables/race_features.tbl'), 'id')['rows']
    rows = []
    for ui_race in range(5):
        for gender in ((0,) if ui_race == 4 else (0, 1)):
            race_stage = p.fresh(ui_race, gender, 0, 0)
            base_display = displays[race_stage['request']['displayId']]
            model = models[base_display['Model']]
            internal = p.model_race_gender(model['ModelPath'])
            feature = [r for r in features if (r['race'], r['gender']) == tuple(internal)]
            if len(feature) != 1:
                raise ValueError('Original body feature mapping absent or ambiguous')
            choices = []
            for index, profession in enumerate(PROFESSIONS):
                stages = [p.fresh(ui_race, gender, index, stage) for stage in (1, 2)]
                d = stages[1]['freshAppearance']
                display = displays[d['displayId']]
                if display['Model'] != model['ID']:
                    raise ValueError('Original editable body changed: ' + repr((ui_race, gender, index, model['ID'], display['Model'])))
                class_display = displays[stages[0]['request']['displayId']]
                choices.append({'uiProfessionIndex': index, 'profession': profession,
                                'stages': stages, 'creationDisplayId': d['displayId'],
                                'extraDisplayInformation': display['ExtraDisplayInformation'],
                                'classStageModel': models[class_display['Model']]})
            path = model['ModelPath']
            animation = path.rsplit('/', 1)[0] + '/anim/animations.bdae'
            rows.append({'uiRace': ui_race, 'gender': gender,
                         'internalRace': internal[0], 'internalGender': internal[1],
                         'raceStage': race_stage, 'baseDisplayId': base_display['ID'],
                         'sourceModel': model, 'featureBounds': feature[0],
                         'modelRecordCandidates': len(sources.candidates(path)),
                         'sameDirectoryAnimationCandidate': animation,
                         'animationRecordCandidates': len(sources.candidates(animation)),
                         'choices': choices})
    return {'format': 'oc2-original-player-choice-matrix-v1',
            'nativeSHA256': sha(image.data), 'originalController': '0x542da4 -> 0x53d3e8',
            'ui': ui, 'bodyChoices': rows, 'combinationCount': sum(len(r['choices']) for r in rows),
            'originalCPUExecuted': True, 'sourceProofs': sources.proofs,
            'sourceAccountAdmissionKnown': False, 'sourceStarterEquipmentKnown': False,
            'sourceLearnedOrEquippedSkillsKnown': False, 'modelCompletionSupplied': False,
            'savesReadOrWritten': False, 'scope': 'Original client UI reachable combinations and fresh draft; not whole playable admission.'}


if __name__ == '__main__':
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, default=RAW / 'matrix-source-v1.json')
    args = cli.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing source matrix')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = recover(NativeImage((ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes()), DEFAULT_SOURCE)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'bodyChoices': len(result['bodyChoices']), 'combinationCount': result['combinationCount'],
                      'rows': [{k: r[k] for k in ('uiRace', 'gender', 'internalRace', 'sourceModel', 'baseDisplayId')} for r in result['bodyChoices']]}, ensure_ascii=False))
