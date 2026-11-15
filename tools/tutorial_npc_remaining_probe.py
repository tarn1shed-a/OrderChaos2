"""Private22-template coverage and bounded973/1013 original defaults."""
import argparse,hashlib,json
from pathlib import Path
from tutorial_npc_robe_probe import RobeProbe
from tutorial_npc_inventory import audit
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output
from skill_attachments import decode_ftable

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-npc-remaining-defaults-v1'
FOCUS=(973,1013)
PRIOR={747:'tutorial-npc-additional-20261114',749:'tutorial-npc-soldiers-20261114',750:'tutorial-npc-weapons-20261114',
 849:'tutorial-npc-elements-20261114',867:'tutorial-npc-binding-20261114',970:'tutorial-npc-weapons-20261114',971:'tutorial-npc-binding-20261114',
 972:'tutorial-npc-robes-20261114',983:'tutorial-npc-catalog-20261114',984:'tutorial-npc-catalog-20261114',
 1018:'tutorial-npc-robes-20261114',1029:'tutorial-npc-elements-20261114',1632:'tutorial-npc-soldiers-20261114',1672:'tutorial-npc-elements-20261114'}


def coverage(inventory,reviewed_additions=()):
    if not set(reviewed_additions)<=set(FOCUS):raise ValueError('Only this bounded batch can be appended')
    rows=[]
    for original in inventory['creatures']:
        entry=original['entry'];display=original['appearance']['creaturedisplayinfo_id'];candidate=next(c for c in original['appearanceCandidates']if c['display']['ID']==display)
        ref=PRIOR.get(entry);reviewed=entry in PRIOR or entry in reviewed_additions;limits=[]
        if entry in[849,1029,1672]:stage='rigid-source-diagnostic-only';ordinary=False;material='source-direct-RGBA-alpha-branch-only';skin='rigid-no-skin';animation='no-source-animation-in-scoped-resource';limits=['Actual compiled prefixes/split-alpha/visibility and application stream input unknown.']
        elif entry==984:stage='body-reviewed-weapon-UT-gap';ordinary=True;material='body-source-profile-reviewed;weapon-diffuse-diagnostic-only';skin='body-strict-source-binding-reviewed';animation='independent-source-idle';limits=['Original weapon200029 UT global/reflection/override input gap.']
        elif entry==972:stage='visible-default-reviewed-hidden-source-gap';ordinary=True;material='visible-default-materials-reviewed';skin='strict-source-binding-reviewed';animation='independent-source-idle';limits=['Original hood hides beard with missing source skinColorMask; no substitute.']
        elif reviewed:stage='default-visible-asset-reviewed';ordinary=True;material='independent-source-default-materials-reviewed';skin='strict-source-binding-reviewed';animation='independent-source-idle'
        else:stage='native-default-request-and-BDAE-CRC-only';ordinary=True;material='template-composition-unreviewed';skin='shared-base-known;template-pieces-unreviewed';animation='original-idle-request;template-preview-unreviewed'
        evidence=None
        if ref:
            path=ROOT/'analysis/raw'/ref/'handoff.json'
            if not path.is_file():raise ValueError('Prior local evidence is required; do not infer a review from directory names')
            record=json.loads(path.read_text())
            if record.get('frozen')is not True:raise ValueError('Prior source batch is not frozen')
            evidence={'handoff':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        rows.append({'entry':entry,'sourceName':original['name'],'defaultDisplay':display,'defaultModel':candidate['model']['ID'],
          'defaultBDAEMemberCandidates':candidate['modelLocalCandidates'],'stage':stage,'ordinaryNPCAsset':ordinary,
          'sourceDefaultRequestEvidence':'tutorial-npc-catalog-20261114/candidate-v6/native-private.json',
          'priorAssetEvidence':evidence,'currentBatchReviewed':entry in reviewed_additions,
          'defaultMaterialStatus':material,'skinStatus':skin,'animationStatus':animation,'directoryIndexOnly':False,'knownGaps':limits,
          'actualGUID':None,'actualAppearance':None,'questAvailability':None})
    return {'format':'oc2-map5-template-coverage-v1','templates':rows,'summary':{'templates':len(rows),
      'stages':{key:sum(r['stage']==key for r in rows)for key in sorted({r['stage']for r in rows})},
      'directoryIndexOnly':sum(r['directoryIndexOnly']for r in rows),'currentBatchReviewed':list(reviewed_additions)},
      'scope':'Derived asset coverage, not actor existence, original GPU completion or quest state. Full source rows stay private.',
      'excludedOldFields':['Frozen catalog feature.textureOverrides ELF-header strings are not texture evidence; see soldier correction.']}


def recover(image,source=DEFAULT_SOURCE):
    inventory=audit(source);sources=Sources(source);p=RobeProbe(image,sources);originals={r['entry']:r for r in inventory['creatures']};entries=[]
    logic=decode_ftable(sources.read('tables/quest_objective_logic.tbl'),'id')['rows']
    if any(r['quest_id']==202 and r['entry']in FOCUS for r in logic):raise ValueError('Bounded remaining202 relationship scope changed')
    for entry in FOCUS:
        original=originals[entry];display=original['appearance']['creaturedisplayinfo_id'];selection=p.entry_selection(entry)
        if selection['result']['selectedDisplayAtD60']!=display:raise ValueError('Original remaining default display differs')
        parts=p.parts(display)
        if any(parts['slots'][i]for i in[7,8]):raise ValueError('Uncovered unnamed source feature')
        requests=[p.part_resource(i,parts['slots'][i],parts['slots'][0])for i in range(7)]
        requests.extend(p.part_resource(i,parts['slots'][i],parts['slots'][0])for i in range(9,15)if parts['slots'][i])
        candidate=next(c for c in original['appearanceCandidates']if c['display']['ID']==display)
        entries.append({'entry':entry,'name':original['name'],'original':original,'defaultCandidate':candidate,'entrySelection':selection,
          'parts':parts,'resourceRequests':requests,'defaultIdle':p.idle(entry,display),'sourceScriptKey':original['prototype']['script'],
          'quest202Start':202 in original['questStartReferences'],'quest202ObjectiveReferences':[],
          'actualGUID':None,'actualAppearanceOverrides':None,'questAvailability':None})
    return {'format':FORMAT,'entries':entries,'families':[{'model':entries[0]['defaultCandidate']['model'],'entries':list(FOCUS)}],
      'coverageBeforeThisBatchBrowserReview':coverage(inventory),'sourceProofs':sources.proofs,'inventorySourceProofs':inventory['sourceProofs'],
      'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'actualActivityObserved':False,'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing coverage/default evidence stays preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':len(result['entries']),'coverageTemplates':22}))
