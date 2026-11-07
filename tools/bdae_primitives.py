"""Source primitive indices are local to an inclusive vertex window.

The native per-primitive binding advances each attribute by firstVertex*stride.
The web shares one mesh-wide vertex buffer instead, so rebase indices once.
"""
import hashlib

FORMAT = 'oc2-primitive-index-windows-v1'
ROUTINES = {
    0x111aea8:(568,'fd866715e10cb7f7cb29a86ae736396c8203e6c7a91a772a85e875db8b2f422a'),
    0x112b270:(228,'9b0323a84b9a854d99061256cdb8a5e17f3c43868199169440cc067b08115b1b'),
    0x1130fd8:(3888,'bfddaeb6ac4b1257004aa4c9a10266ee6e2b1128b1227cb5aaf94561e1c4a69f'),
    0x12db214:(3828,'78146b401c2c6daa238ffec76562dbf8d603c5e14216b630db45cda96eac1d34'),
}


def verify_native(image):
    for address,(size,digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:
            raise ValueError('Primitive binding routine changed; retrace required')
    # Original source primitive kind 0 maps to the native triangle-list mode 4.
    if image.read(0x1f37810,4)!=b'\4\0\0\0':raise ValueError('Source primitive topology changed')
    return {'routineCount':len(ROUTINES),'firstVertexOffset':28,'lastVertexOffset':32,
            'lastVertexInclusive':True,'nativeAttributeOffset':'offset + firstVertex * stride',
            'webIndex':'firstVertex + localIndex'}


def primitive_indices(reader,primitive,vertex_count):
    reader.at(primitive,88)
    count=reader.u(primitive+36)
    if reader.u(primitive)!=0 or not count or count%3 or count!=reader.u(primitive+16)*3:
        raise ValueError('Only source indexed triangle lists supported')
    first,last=reader.unpack('2I',primitive+28)
    if not 0<=first<=last<vertex_count:
        raise ValueError('Primitive vertex window outside the mesh')
    if last-first+1>=65536:
        raise ValueError('32-bit source primitive indices require separate recovery')
    pointer,length=reader.q(primitive+48),reader.q(primitive+56)
    if count*2>length:raise ValueError('Index buffer too short')
    reader.at(pointer,length)
    local=reader.unpack('H'*count,pointer)
    if max(local)>last-first:
        raise ValueError('Local index outside primitive vertex window')
    return [first+i for i in local],{'sourceVertexStart':first,'sourceVertexEnd':last}
