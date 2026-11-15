"""Audit shared original creation references; write full recipes only to private raw output.

This consumes frozen source executions, not filename guesses or a new role definition.
It does not select a VFS winner, construct a mesh, grant skills or touch saves.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

PINS = {
    'class': 'ae5517200752946de28884cdebc38dd38fa016ffe1a8930a7a6041e984491d9f',
    'part': '9393456552781fd03791e8368ffa3fc5ac64be75d3f0e0d422bc09b6f8f8c3a0',
    'panels': 'e1b37882282ed312db06b4c8b3e1b91ec0aca4baee01af80316a420c82abee23',
}
NATIVE = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'


def read_source(path, kind):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINS[kind]:
        raise ValueError('Frozen source differs: ' + kind)
    data = json.loads(raw)
    if data.get('nativeSHA256') != NATIVE:
        raise ValueError('Original client version differs: ' + kind)
    return data


def choice_key(row):
    return row['uiRace'], row['gender'], row['uiProfessionIndex']


def choice_index(data, stage):
    result = {choice_key(row): row for row in data['choices']}
    expected = {(race, gender, profession) for race in range(5)
                for gender in range(1 if race == 4 else 2) for profession in range(5)}
    if len(data['choices']) != 45 or set(result) != expected or data['originalStage'] != stage:
        raise ValueError('Original stage choice coverage differs')
    for row in result.values():
        if row['stage'] != stage or row['request']['displayId'] != row['display']['ID']:
            raise ValueError('Original display/stage reference differs')
        if row['display']['Model'] != row['model']['ID']:
            raise ValueError('Original display/model reference differs')
    return result


def summarize(index):
    paths = lambda field: {r['path'] for c in index.values() for r in c[field] if r.get('path')}
    body_paths = {c['model']['ModelPath'] for c in index.values()}
    resources, weapons = paths('resourceRequests'), paths('weaponResources')
    effect_cases = [key for key, c in index.items() if any(
        value for field, value in c['model'].items() if field.startswith('eff_mod_eff'))]
    return {'choices': len(index), 'bodyFiles': len(body_paths),
            'modelConfigurations': len({c['model']['ID'] for c in index.values()}),
            'slotFiles': len(resources), 'weaponFiles': len(weapons),
            'weaponRequests': sum(bool(r.get('path')) for c in index.values() for r in c['weaponResources']),
            'allReferencedFiles': len(body_paths | resources | weapons),
            'modelEffectCases': len(effect_cases)}


def audit(class_source, part_source, panel_source):
    classes, parts = choice_index(class_source, 1), choice_index(part_source, 2)
    panel_rows = {row['panel']: row for row in panel_source['panels']}
    if [(panel_rows[i]['screen'], panel_rows[i]['cameraGroup']) for i in range(3)] != [
            ('CharacterChooseRace', 3), ('CharacterChooseClass', 3), ('CharacterChoosePart', 2)]:
        raise ValueError('Original shared screen/camera contract differs')
    recipes, bodies = [], []
    for race, gender in sorted({key[:2] for key in classes}):
        rows = [classes[race, gender, p] for p in range(5)]
        part_rows = [parts[race, gender, p] for p in range(5)]
        paths = {r['model']['ModelPath'] for r in rows + part_rows}
        if len(paths) != 1:
            raise ValueError('Body file reuse differs; do not silently merge')
        bodies.append({'race': race, 'gender': gender, 'bodyPath': next(iter(paths)),
                       'classModelIDs': [r['model']['ID'] for r in rows],
                       'partModelIDs': [r['model']['ID'] for r in part_rows]})
    for stage, index in [(1, classes), (2, parts)]:
        for key, row in sorted(index.items()):
            if row['profession'] != (classes if stage == 2 else parts)[key]['profession']:
                raise ValueError('Class/Part profession mapping differs')
            recipes.append({'key': [stage, *key], 'screen': panel_rows[stage]['screen'],
                            'cameraGroup': panel_rows[stage]['cameraGroup'],
                            'profession': row['profession'], 'request': row['request'],
                            'model': row['model'], 'parts': row['parts'],
                            'resourceRequests': row['resourceRequests'],
                            'weaponSlots': row['weaponSlots'], 'weaponResources': row['weaponResources']})
    materials = [m for resource in class_source['resources'] for m in resource.get('materials', [])]
    summary = {'bodyGroups': len(bodies), 'recipes': len(recipes),
               'class': summarize(classes), 'part': summarize(parts),
               'classInventorySnapshot': {
                   'resourceRows': len(class_source['resources']),
                   'materialRows': len(materials),
                   'effectFamilies': dict(sorted(Counter(m['effectPath'] for m in materials).items())),
                   'multipleArchiveCandidates': sum(r['candidateCount'] > 1 for r in class_source['resources']),
                   'rowsWithoutParsedMaterials': sum(not r.get('materials') for r in class_source['resources'])}}
    return {'format': 'oc2-creation-shared-reference-audit-v1', 'nativeSHA256': NATIVE,
            'sources': PINS, 'summary': summary, 'bodyGroups': bodies, 'recipes': recipes,
            'limits': ['Reference audit only; 90 recipes do not prove 90 rendered actors.',
                       'Material counts describe the frozen early inventory, not resolved VFS winners.',
                       'Geometry/controller classification requires the actual selected original bytes.',
                       'No new role/world permissions, VFS selection, GPU success or save mutation.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for kind in PINS:
        parser.add_argument('--' + kind, dest=kind + '_path', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if 'analysis' not in output.parts or 'raw' not in output.parts or output.exists():
        raise ValueError('New ignored analysis/raw output required')
    report = audit(*(read_source(getattr(args, kind + '_path'), kind) for kind in PINS))
    raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)
    output.chmod(0o600)
    print(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(), 'summary': report['summary']}, ensure_ascii=False))
