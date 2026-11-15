"""Original human-male creation display selection and resource requests.

This follows the original creation controller, not an NPC appearance key.
Explicit controller/table/scene interfaces are research inputs; no role, server
reply, creation success, initial equipment grant or saved state is invented.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-human-male-creation-candidate-v1'
MODEL = 'model/npc/character/human/male/oc2_human_m_body_01.bdae'
ANIMATION = 'model/npc/character/human/male/anim/animations.bdae'
CREATION_SIZE = 1116
CREATION_SHA256 = '5d57b462b76204c0abacb1ee39f58fde53f6463bd1ce373f2387fd86cec2e3ad'


def original_selection(image, source):
    from tutorial_npc_soldier_probe import SoldierProbe
    from map_loading_evidence import Sources
    from skill_attachments import decode_ftable
    from unicorn import UC_HOOK_CODE

    if hashlib.sha256(image.read(0x542da4, CREATION_SIZE)).hexdigest() != CREATION_SHA256:
        raise ValueError('Pinned original creation controller differs')

    class Probe(SoldierProbe):
        def __init__(self, image, sources):
            self.selection_mode = False
            super().__init__(image, sources)
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=0x53d3e8, end=0x53d3e8)

        def hook(self, uc, at, size, data):
            if at == 0x53d3e8 and self.selection_mode:
                self.selection = {'displayId': self.get('W1'), 'arg2': self.get('W2'),
                                  'arg3': self.get('W3')}
                self.set('PC', self.EXIT)
                return
            return super().hook(uc, at, size, data)

        def choose(self, stage, profession_index=0):
            controller, ui = self.alloc(0x300), self.alloc(0x400)
            self.w(controller+0x5c, '3i', 0, 0, profession_index)
            self.w(0x2534300, 'Q', controller)
            self.w(0x2528db0, 'Q', ui)
            self.w(0x2534000, 'I', 1)
            self.selection_mode, self.selection = True, None
            try:
                self.call(0x542da4, {'X0': controller, 'W1': stage})
            finally:
                self.selection_mode = False
            if self.selection is None:
                raise ValueError('Original creation display handoff not reached')
            return {'stage': stage, 'professionIndex': profession_index, **self.selection,
                    'controllerInputsAreExplicit': True, 'modelLoaderExecuted': False}

    sources = Sources(source)
    p = Probe(image, sources)
    selections = [p.choose(0)] + [p.choose(stage, cls) for stage in (1, 2) for cls in range(5)]
    selected = selections[0]['displayId']
    if selected != 2038:
        raise ValueError('Original human male creation race display differs')
    parts = p.parts(selected)
    if parts['modelId'] != 1 or parts['slots'][:3] != [2, 1, 1] or any(parts['slots'][7:9]):
        raise ValueError('Original human male creation part inputs differ')
    requests = [p.part_resource(i, parts['slots'][i], parts['slots'][0]) for i in range(7)]
    requests += [p.part_resource(i, parts['slots'][i], parts['slots'][0])
                 for i in range(9, 37) if parts['slots'][i]]
    if any(r['path'] and r['sourceResourceCandidates'] != 1 for r in requests):
        raise ValueError('Original selected creation source is missing or ambiguous')
    displays = decode_ftable(sources.read('tables/creaturedisplayinfo.tbl'), 'ID')['rows']
    models = decode_ftable(sources.read('tables/creaturemodeldata.tbl'), 'ID')['rows']
    extra = decode_ftable(sources.read('tables/creaturedisplayinfoextra.tbl'), 'ID')['rows']
    display = next(r for r in displays if r['ID'] == selected)
    model = next(r for r in models if r['ID'] == display['Model'])
    if model['ModelPath'] != MODEL or display['ExtraDisplayInformation'] != 1949:
        raise ValueError('Original creation model/display link differs')
    feature = next(r for r in decode_ftable(sources.read('tables/race_features.tbl'), 'id')['rows']
                   if r['race'] == 0 and r['gender'] == 0)
    if feature['id'] != 1 or feature['face'] != 4 or feature['hair'] != 4 or feature['beard'] != 4:
        raise ValueError('Source human male feature bounds differ')
    metadata, assembly = image.routine(0x542da4)
    return {'format': FORMAT, 'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
            'creationEntry': {'address': '0x542da4', 'size': metadata['size'],
                              'sha256': hashlib.sha256(image.read(0x542da4, metadata['size'])).hexdigest()},
            'selectionTableAddresses': ['0x250ad08', '0x250ad30', '0x250adf8'],
            'selections': selections, 'selectedStage': 0, 'display': display, 'model': model,
            'extra': next(r for r in extra if r['ID'] == 1949),
            'featureBounds': feature, 'parts': parts, 'resourceRequests': requests,
            'sourceProofs': sources.proofs, 'nativeCPU': True,
            'scope': 'Original creation race-stage appearance; not a world-player equipment grant.',
            'initialServerAttributes': None, 'createdRole': False, 'savesReadOrWritten': False,
            'productionChanged': False, 'originalControllerAssembly': assembly}
