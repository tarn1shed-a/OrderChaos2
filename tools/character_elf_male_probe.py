"""Original elf-male creation display selection and resource requests.

This follows the original creation controller, not an NPC appearance key.
Explicit controller/table/scene interfaces are research inputs; no role, server
reply, creation success, initial equipment grant or saved state is invented.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-elf-male-creation-candidate-v1'
MODEL = 'model/npc/character/elf/male/oc2_elf_m_body_01.bdae'
ANIMATION = 'model/npc/character/elf/male/anim/animations.bdae'
CREATION_SIZE = 1116
CREATION_SHA256 = '5d57b462b76204c0abacb1ee39f58fde53f6463bd1ce373f2387fd86cec2e3ad'


def original_selection(image, source, *, stage=0, profession_index=0, allow_unresolved=False):
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
            if at == 0x9d4c48 and self.mode == 'parts':
                descriptor = self.get('X1')
                weapon = {'mainHand': self.r(descriptor+0x94, 'I')[0],
                          'offHand': self.r(descriptor+0x98, 'I')[0],
                          'armedParameter': self.r(descriptor+0xa4, 'B')[0]}
                super().hook(uc, at, size, data)
                self.part_result['weapons'] = weapon
                self.part_result['originalCreationRequestArgs'] = [3, 0, 'idle', 1, 0]
                return
            if at == 0x53d3e8 and self.selection_mode:
                self.selection = {'displayId': self.get('W1'), 'arg2': self.get('W2'),
                                  'arg3': self.get('W3')}
                self.set('PC', self.EXIT)
                return
            return super().hook(uc, at, size, data)

        def parts(self, display_id):
            owner = self.alloc(256)
            self.mode, self.part_result, self.lookup_calls = 'parts', None, []
            try:
                self.call(0x9d40cc, {'X0': owner, 'W1': display_id, 'W2': 3,
                                    'W3': 0, 'X4': self.cpp_string(b'idle'), 'W5': 1, 'W6': 0})
            finally:
                self.mode = None
            if self.part_result is None:
                raise ValueError('Original elf creation part handoff absent')
            return {**self.part_result, 'tableLookups': list(self.lookup_calls),
                    'actorOwnerSupplied': False, 'modelLoaderExecuted': False}

        def part_resource(self, slot, value, face):
            # Same original consumer as the male review, with its real elf-male
            # model path. The source consumer derives race/gender from this path.
            owner, holder, model, vt = self.alloc(256), self.alloc(8), self.alloc(256), self.alloc(64)
            self.w(owner+0x40, 'Q', holder); self.w(holder, 'Q', model)
            self.w(model, 'Q', vt); self.w(vt+0x10, 'Q', self.MODEL_KIND)
            self.w(model+0x90, 'Q', self.cpp_string(MODEL.encode()))
            self.w(owner+0x4c, 'I', face)
            self.weapon_mode, self.resource_request = 'resource', None
            self.lookup_calls, self.exists_queries = [], []
            try:
                self.call(0x9d64e8, {'X0': owner, 'W1': slot, 'W2': value, 'W3': 1})
            finally:
                self.weapon_mode = None
            if self.resource_request is None:
                raise ValueError('Original elf-male part request boundary absent')
            path = self.resource_request.get('path')
            count = len(self.sources.candidates(path)) if path else 0
            if path and count == 1:
                self.sources.read(path)
            return {**self.resource_request, 'sourceResourceCandidates': count,
                    'inputValue': value, 'explicitCurrentFace': face,
                    'tableLookups': list(self.lookup_calls), 'sourceExistsQueries': list(self.exists_queries),
                    'noActorOwner': True, 'explicitLoadedModelKind': 3,
                    'sourceModelPathFixture': MODEL, 'forcePartParameter': 1}

        def choose(self, stage, profession_index=0):
            controller, ui = self.alloc(0x300), self.alloc(0x400)
            self.w(controller+0x5c, '3i', 2, 0, profession_index)
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
    avatar_race_gender = p.model_race_gender(MODEL)
    if avatar_race_gender != [1,0]:
        raise ValueError('Original avatar race/gender differs from creation controller order')
    selections = [p.choose(0)] + [p.choose(stage, cls) for stage in (1, 2) for cls in range(5)]
    selected = next(r['displayId'] for r in selections if r['stage']==stage and r['professionIndex']==profession_index)
    if stage == 0 and selected != 2046:
        raise ValueError('Original elf male creation race display differs')
    parts = p.parts(selected)
    if (stage == 0 and (parts['modelId'] != 33 or parts['slots'][:3] != [0, 3, 0])) or any(parts['slots'][7:9]):
        raise ValueError('Original elf male creation part inputs differ')
    requests = [p.part_resource(i, parts['slots'][i], parts['slots'][0]) for i in range(7)]
    requests += [p.part_resource(i, parts['slots'][i], parts['slots'][0])
                 for i in range(9, 37) if parts['slots'][i]]
    if not allow_unresolved and any(r['path'] and r['sourceResourceCandidates'] != 1 for r in requests):
        raise ValueError('Original selected creation source is missing or ambiguous')
    displays = decode_ftable(sources.read('tables/creaturedisplayinfo.tbl'), 'ID')['rows']
    models = decode_ftable(sources.read('tables/creaturemodeldata.tbl'), 'ID')['rows']
    extra = decode_ftable(sources.read('tables/creaturedisplayinfoextra.tbl'), 'ID')['rows']
    display = next(r for r in displays if r['ID'] == selected)
    model = next(r for r in models if r['ID'] == display['Model'])
    if model['ModelPath'] != MODEL or stage == 0 and display['ExtraDisplayInformation'] != 1957:
        raise ValueError('Original creation model/display link differs')
    feature = next(r for r in decode_ftable(sources.read('tables/race_features.tbl'), 'id')['rows']
                   if r['race'] == 1 and r['gender'] == 0)
    if feature['id'] != 3 or feature['face'] != 3 or feature['hair'] != 3 or feature['beard'] != 0:
        raise ValueError('Source elf male feature bounds differ')
    metadata, assembly = image.routine(0x542da4)
    return {'format': FORMAT, 'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
            'creationEntry': {'address': '0x542da4', 'size': metadata['size'],
                              'sha256': hashlib.sha256(image.read(0x542da4, metadata['size'])).hexdigest()},
            'selectionTableAddresses': ['0x250ad08', '0x250ad30', '0x250adf8'],
            'selections': selections, 'selectedStage': stage, 'professionIndex': profession_index,
            'creationRace': 2, 'avatarRace': avatar_race_gender[0], 'gender': avatar_race_gender[1],
            'avatarRaceGenderConsumer':'0x9d75e8','display': display, 'model': model,
            'extra': next(r for r in extra if r['ID'] == display['ExtraDisplayInformation']),
            'featureBounds': feature, 'parts': parts, 'resourceRequests': requests,
            'sourceProofs': sources.proofs, 'nativeCPU': True,
            'scope': 'Original creation race-stage appearance; not a world-player equipment grant.',
            'initialServerAttributes': None, 'createdRole': False, 'savesReadOrWritten': False,
            'productionChanged': False, 'originalControllerAssembly': assembly}
