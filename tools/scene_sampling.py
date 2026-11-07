"""Read source 2D sampler requests without claiming the final runtime state.

Material requests and FX defaults are separate inputs. 255 skips a setter;
it is not a texture address mode. Texture construction, caching and quality
selection must be traced before applying the result to a browser material.
"""
import hashlib

ROUTINES = {
    0x112920c: (5272, 'bfa22c8dab60d55b7a6e5034441a4cf85ae28858875b0b28dc9b7cb6c25607c6'),
    0x114c2dc: (4376, 'ec44bde8f037ddb1fa22d7cbe2fe4672090c8ab78505973863a469415b5fa2e1'),
    0x146f58c: (240, '9382b1b3101fa6cc9b235c3d51e9a49eb36ad14d4e2482a484b57e17acec1942'),
    0x14450a4: (76, '6abd67191a827106f33a7c086a16b24c243e261b7c121d0db7c1458aecde34aa'),
    0x14450f0: (48, 'e92c3275eee3188bcb6acfb5f060110edc755c4da3f9fd1036f1afaedce241f3'),
    0x1126d7c: (4, '110f46b5b35c069160560c6ad6786f647dd44e8760a52a46fc22dbbcd7630b91'),
}
LOADER_VPTRS = (0x2412700, 0x2416430, 0x24407a0, 0x24493e8,
                0x244d308, 0x244d5c0, 0x245aa88, 0x2488f60)
FIELDS = ('addressU', 'addressV', 'minFilter', 'magFilter')


def verify_native(image):
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene sampler routine changed; retrace required')
    relocations = {r['r_offset']: r['r_addend'] for r in
                   image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    # Every vtable using the checked material loader has the same no-op
    # texture-state hook at +0x48. Check the neighboring material entry too.
    for vptr in LOADER_VPTRS:
        if relocations.get(vptr + 0x48) != 0x1126d7c or relocations.get(vptr + 0x88) != 0x1129190:
            raise ValueError('Scene sampler loader hook changed; retrace required')
    if relocations.get(0x245a4a8) != 0x1f2f8ff or image.read(0x1f2f8ff, 10) != b'sampler2D\0':
        raise ValueError('Source sampler2D name changed')
    if image.read(0x1f310ac + 16*4, 4) != b'\0\0\x02\0':
        raise ValueError('Sampler source/runtime type acceptance changed')
    return {'routineCount': len(ROUTINES), 'checkedLoaderHooks': len(LOADER_VPTRS),
            'sourceType': 17, 'runtimeType': 16, 'skipSetterValue': 255,
            'appliedAsActiveSamplerState': False}


def read_sampler_2d(reader, value):
    """20 bytes: self-relative texture reference, U, V, min, mag uint32."""
    reader.at(value, 20)
    words = reader.unpack('4I', value + 4)
    result = {}
    for field, word, maximum in zip(FIELDS, words, (4, 4, 5, 5)):
        if word != 255 and word > maximum:
            raise ValueError('Unsupported source 2D sampler enum')
        result[field] = None if word == 255 else word
    return result


def _property(reader, at, state_offset, value_offset, count_offset):
    if reader.u(at + count_offset) != 1:
        raise ValueError('Only scalar source sampler properties are supported')
    state = reader.rel(at + state_offset)
    if reader.unpack('2I', state) != (1, 0):
        raise ValueError('Unsupported source sampler property state')
    return reader.rel(at + value_offset)


def material_samplers(reader):
    count, table = reader.section(172)
    reader.at(table, count*80)
    texture_count, textures = reader.section(148)
    reader.at(textures, texture_count*32)
    result, names = [], set()
    for index in range(count):
        at = table + index*80
        name = reader.string(reader.q(at))
        if name in names:
            raise ValueError('Ambiguous source material name')
        names.add(name)
        size, properties = reader.u(at + 32), reader.rel(at + 36)
        if size > 256:
            raise ValueError('Excessive source material property count')
        reader.at(properties, size*32)
        samplers = {}
        for item in range(size):
            prop = properties + item*32
            if reader.u(prop + 16) != 17:
                continue
            field = reader.string(reader.q(prop))
            if field in samplers:
                raise ValueError('Duplicate source sampler property')
            value = _property(reader, prop, 24, 28, 20)
            texture = reader.rel(value)
            if not textures <= texture < textures + texture_count*32 or (texture - textures) % 32:
                raise ValueError('Sampler texture reference outside source table')
            samplers[field] = {'texture': reader.string(reader.q(texture + 16)),
                               'request': read_sampler_2d(reader, value)}
        result.append({'material': name, 'effectPath': reader.string(reader.q(at + 8)),
                       'effectName': reader.string(reader.q(at + 16)), 'samplers': samplers})
    return result


def effect_profile_samplers(reader):
    """Read both source FX profile blocks, retaining them as separate inputs.

    This bounded reader handles one FX with sampler2D-only parameter lists;
    it does not assign device/platform names to the two profile pointers or
    choose a current technique. No shader source is copied into this module.
    """
    count, table = reader.section(164)
    if count != 1:
        raise ValueError('Expected one source scene effect')
    reader.at(table, 56)
    profiles = []
    for field_offset in (32, 36):
        profile = reader.rel(table + field_offset)
        reader.at(profile, 16)
        size, parameters = reader.u(profile + 8), reader.rel(profile + 12)
        if not 1 <= size <= 64:
            raise ValueError('Unsupported source FX sampler parameter count')
        reader.at(parameters, size*32)
        samplers = {}
        for index in range(size):
            prop = parameters + index*32
            field = reader.string(reader.q(prop))
            if field in samplers or reader.u(prop + 8) != 17:
                raise ValueError('Unsupported or duplicate source FX sampler parameter')
            value = _property(reader, prop, 20, 24, 16)
            if reader.i(value) != 0:
                raise ValueError('Source FX sampler has a default texture; needs separate resolution')
            samplers[field] = {'texture': None, 'request': read_sampler_2d(reader, value)}
        profiles.append({'sourcePointerField': field_offset, 'samplers': samplers})
    return {'effectName': reader.string(reader.q(table)), 'profiles': profiles,
            'appliedAsActiveSamplerState': False}
