"""Original972/1018 modular default requests with nullable descriptors."""
import argparse,hashlib,json
from pathlib import Path
from tutorial_npc_soldier_probe import SoldierProbe
from tutorial_npc_inventory import audit
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output
from skill_attachments import decode_ftable

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-npc-robe-native-v1'


class RobeProbe(SoldierProbe):
    def hook(self,uc,at,size,data):
        if at==0x323b44 and self.weapon_mode=='resource':
            descriptor=self.get('X2');path=self.r(descriptor,'Q')[0]
            if not path:raise ValueError('Expected nonempty original robe/staff resource path')
            pointers=[self.r(descriptor+i*8,'Q')[0]for i in range(1,4)];anchor=self.r(descriptor+64,'Q')[0]
            self.resource_request={'slot':self.get('W1'),'path':self.cstr(path).decode(),
              'textureOverrides':[self.cstr(p).decode()if p else None for p in pointers],
              'positionAnchor':self.cstr(anchor).decode()if anchor else None,'itemKey':self.get('W3'),
              'raceSelector':self.get('W4'),'genderSelector':self.get('W5'),'resourceLoaderExecuted':False,
              'originalOverridePointers':pointers,'overrideNullPointers':[p==0 for p in pointers],
              'nullPointerDecodedAsString':False,'overrideNullPointersNotDereferenced':True}
            self.set('PC',self.EXIT);return
        return super().hook(uc,at,size,data)


def recover(image,source=DEFAULT_SOURCE):
    sources=Sources(source);probe=RobeProbe(image,sources);inventory=audit(source);originals={r['entry']:r for r in inventory['creatures']};entries=[]
    logic=decode_ftable(sources.read('tables/quest_objective_logic.tbl'),'id')['rows']
    if any(r['quest_id']==202 and r['entry']in[972,1018]for r in logic):raise ValueError('Selected robe202 relationship scope changed')
    for entry,display in[(972,951),(1018,995)]:
        selection=probe.entry_selection(entry)
        if selection['result']['selectedDisplayAtD60']!=display:raise ValueError('Original robe default display differs')
        parts=probe.parts(display)
        if any(parts['slots'][i]for i in[7,8]):raise ValueError('Uncovered unnamed source feature slots')
        requests=[probe.part_resource(i,parts['slots'][i],parts['slots'][0])for i in range(7)]
        requests.extend(probe.part_resource(i,parts['slots'][i],parts['slots'][0])for i in range(9,15)if parts['slots'][i])
        original=originals[entry];candidate=next(r for r in original['appearanceCandidates']if r['display']['ID']==display)
        entries.append({'entry':entry,'name':original['name'],'original':original,'defaultCandidate':candidate,'entrySelection':selection,
          'parts':parts,'resourceRequests':requests,'defaultIdle':probe.idle(entry,display),'sourceScriptKey':original['prototype']['script'],
          'quest202Start':202 in original['questStartReferences'],'quest202ObjectiveReferences':[],
          'actualGUID':None,'actualAppearanceOverrides':None,'questAvailability':None})
    return {'format':FORMAT,'entries':entries,'families':[{'model':entries[0]['defaultCandidate']['model'],'entries':[972,1018]}],
      'sourceProofs':sources.proofs,'inventorySourceProofs':inventory['sourceProofs'],'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
      'actualActivityObserved':False,'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing robe evidence stays preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':len(result['entries'])}))
