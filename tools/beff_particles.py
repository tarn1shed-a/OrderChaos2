"""Strict v9 particle stream decoder, cross-checked against the 3.1.3a ARM64 loader.

Old public BEFF templates describe part of the field vocabulary, not this version's
layout. Native reader widths/call order and complete EOF coverage establish v9.
Unidentified fields are retained as words instead of assigning invented semantics.
"""
import math
import struct

EMITTER_CURVES = ['outerX','outerY','outerZ','innerPercent','rotateX','rotateY','rotateZ',
                  'translateX','translateY','translateZ','volumeHigh','volumeMedium','volumeLow',
                  'radialSpeed','directedSpeed','coneAngle','direction']
PARTICLE_CURVES = ['red','green','blue','alpha','secondaryRed','secondaryGreen','secondaryBlue',
                   'unknownF0','uvLeft','uvTop','uvRight','uvBottom','sizeX','sizeY',
                   'rotateX','rotateY','rotateZ','scaleX','scaleY']


class ParticleReader:
    def __init__(self, data, dependencies):
        self.data, self.dependencies, self.at = data, dependencies, 0
        self.curve_count = self.key_count = self.emitter_count = 0

    def read(self, fmt):
        size = struct.calcsize('<'+fmt)
        if self.at + size > len(self.data): raise ValueError(f'Truncated particle stream at {self.at:#x}')
        result = struct.unpack_from('<'+fmt, self.data, self.at)
        self.at += size
        return result[0] if len(result) == 1 else list(result)

    def string(self):
        size = self.read('I')
        if size > 4096 or size % 4 or self.at + size > len(self.data): raise ValueError('Invalid particle string extent')
        if not size: return ''
        raw = self.data[self.at:self.at+size]; self.at += size
        end = raw.find(b'\0')
        if end < 0 or any(raw[end:]): raise ValueError('Invalid particle string padding')
        try: return raw[:end].decode('utf-8')
        except UnicodeDecodeError as error: raise ValueError('Invalid particle string encoding') from error

    def curve(self, kind='float'):
        offset = self.at
        count, loop = self.read('2I')
        if not 1 <= count <= 4096 or loop not in (0,1): raise ValueError('Invalid particle curve count or loop')
        self.curve_count += 1; self.key_count += count
        if self.key_count > 200000: raise ValueError('Particle key budget exceeded')
        times, values = [], []
        fmt = 'i' if kind == 'int' else '3f' if kind == 'vector3' else 'f'
        for _ in range(count):
            frame, value = self.read('i'), self.read(fmt)
            if frame < 0 or frame > 108000 or (times and frame <= times[-1]): raise ValueError('Non-monotonic particle curve frames')
            if not all(math.isfinite(v) for v in (value if isinstance(value,list) else [value])):
                raise ValueError('Non-finite particle curve value')
            times.append(frame); values.append(value)
        return {'kind':kind,'loop':bool(loop),'frames':times,'values':values,'sourceOffset':offset}

    def affector(self):
        offset = self.at
        identifier, kind = self.read('2i')
        result = {'sourceOffset':offset,'id':identifier,'type':kind}
        if kind in (0,3,4):
            result['strength'] = self.curve(); result['direction'] = self.curve('vector3')
        elif kind == 1: result['strength'] = self.curve()
        elif kind == 2:
            result['parameters'] = self.read('4f')
            if not all(math.isfinite(v) for v in result['parameters']): raise ValueError('Non-finite random affector')
        else: raise ValueError(f'Unsupported particle affector {kind}')
        if kind in (3,4): result['mode'] = self.read('i')
        return result

    def model_node(self):
        # eb46c0: parent string, 76 fixed bytes, three texture references,
        # nine float, seven integer, then three float curves. eaabe8 builds
        # the selected type-2 hemisphere; do not pretend it is an emitter.
        offset=self.at;parent=self.string();words=self.read('19i');refs=self.read('3i')
        f=struct.unpack('<19f',struct.pack('<19i',*words))
        if words[0]!=2 or parent or any(not math.isfinite(f[i]) for i in range(1,6)):
            raise ValueError('Unsupported BEFF procedural node')
        if not (f[1]>0 and f[2]>0 and 3<=int(f[4])<=128 and 1<=int(f[5])<=128):raise ValueError('Invalid BEFF hemisphere dimensions')
        if any(i<0 or i>=len(self.dependencies) for i in refs) or self.dependencies[refs[0]]=='.':raise ValueError('Invalid procedural texture reference')
        names=['translateX','translateY','translateZ','rotateX','rotateY','rotateZ','scaleX','scaleY','scaleZ','red','green','blue','alpha','secondaryRed','secondaryGreen','secondaryBlue','unknownF0','scrollU','scrollV']
        curves={name:self.curve('int' if 9<=i<16 else 'float') for i,name in enumerate(names)}
        if any(not 0<=v<=255 for name in names[9:16] for v in curves[name]['values']):raise ValueError('Invalid procedural color')
        return {'sourceOffset':offset,'sourceEnd':self.at,'parent':parent,'type':2,'headerWords':words,
            'height':f[1],'radius':f[2],'radialSegments':int(f[4]),'rings':int(f[5]),'materialId':words[6],
            'startFrame':words[7],'durationFrames':words[8],'uvRotation':words[11],
            'textureIndices':refs,'texture':'texture/'+self.dependencies[refs[0]],'curves':curves,
            'uvScroll':bool(words[10]),'flipH':bool(words[12]),'flipV':bool(words[13])}

    def emitter(self, depth=0):
        if depth > 8 or self.emitter_count >= 256: raise ValueError('Particle emitter nesting/count limit')
        self.emitter_count += 1
        offset = self.at
        parent, name, children = self.string(), self.string(), self.read('I')
        if children > 256: raise ValueError('Invalid child emitter count')
        header_offset = self.at
        header = self.read('20i')
        if header[0] not in range(4): raise ValueError('Unsupported emitter shape')
        if header[6] < 0 or header[7] < -1 or any(value < 0 for value in header[9:12]): raise ValueError('Invalid emitter timing')
        # The native loader reads exactly 80 bytes, then two padded strings.
        strings = [self.string(),self.string()]
        curves = {key:self.curve('int' if i == 3 else 'vector3' if i == 16 else 'float')
                  for i,key in enumerate(EMITTER_CURVES)}
        particle_offset = self.at
        particle_words = self.read('29i')  # Native read size 0x74.
        refs = self.read('3i')
        if particle_words[0] not in range(8): raise ValueError('Unsupported particle orientation type')
        if not 1 <= particle_words[3] <= 108000 or abs(particle_words[4]) > 100: raise ValueError('Invalid particle lifetime')
        if any(index < -1 or index >= len(self.dependencies) for index in refs): raise ValueError('Particle texture index out of range')
        if refs[0] < 0 or self.dependencies[refs[0]] == '.': raise ValueError('Particle has no renderable diffuse texture')
        particle_curves = {key:self.curve('int' if i < 7 else 'float') for i,key in enumerate(PARTICLE_CURVES)}
        for key in ['red','green','blue','alpha','secondaryRed','secondaryGreen','secondaryBlue']:
            if any(not 0 <= value <= 255 for value in particle_curves[key]['values']): raise ValueError('Invalid particle color channel')
        floats = struct.unpack('<29f',struct.pack('<29i',*particle_words))
        for index in (7,9,11,24,25,26,27):
            if not math.isfinite(floats[index]): raise ValueError('Non-finite particle header')
        affector_count = self.read('I')
        if affector_count > 64: raise ValueError('Invalid affector count')
        affectors = [self.affector() for _ in range(affector_count)]
        child_records = [self.emitter(depth+1) for _ in range(children)]
        return {'name':name,'parent':parent,'sourceOffset':offset,'sourceEnd':self.at,
                'headerOffset':header_offset,'headerWords':header,'auxiliaryStrings':strings,
                'shape':header[0],'followFlags':header[3], 'startFrame':header[6], 'durationFrames':header[7],
                'intervalFrames':header[9:12], 'curves':curves,
                'particle':{'sourceOffset':particle_offset,'headerWords':particle_words,'textureIndices':refs,
                    'texture':'texture/'+self.dependencies[refs[0]],'type':particle_words[0],
                    'followFlags':particle_words[1],'lifeFrames':particle_words[3],
                    'lifeRandomPercent':particle_words[4],'sizeRandomPercent':particle_words[5],
                    'keepXY':bool(particle_words[6]),'baseAngles':[floats[i] for i in (7,9,11)],
                    'baseAngleRandomPercent':[particle_words[i] for i in (8,10,12)],
                    'rotationRandomPercent':particle_words[14:17],'materialId':particle_words[18],
                    'pivot':particle_words[19:21], 'uvRotation':particle_words[21],
                    'flipH':bool(particle_words[22]&0xffff), 'flipV':bool((particle_words[22]>>16)&0xffff),
                    'curves':particle_curves}, 'affectors':affectors,'children':child_records}


def decode_particle_payload(data, start, dependencies, count):
    if not 1 <= count <= 256: raise ValueError('Invalid root emitter count')
    reader = ParticleReader(data,dependencies);reader.at = start
    emitters = [];model_nodes=[]
    for _ in range(count):
        kind = reader.read('i')
        if kind==0:emitters.append(reader.emitter())
        elif kind==3:model_nodes.append(reader.model_node())
        else:raise ValueError(f'Unsupported BEFF node type {kind}')
    if reader.at != len(data): raise ValueError(f'Unconsumed particle payload at {reader.at:#x}')
    return {'emitters':emitters,'modelNodes':model_nodes,'sampleRate':30,'keySampling':'integer-frame-linear',
            'verification':{'bytesConsumed':reader.at,'fileSize':len(data),'completePayload':True,
                            'emitters':reader.emitter_count,'modelNodes':len(model_nodes),'curves':reader.curve_count,'keys':reader.key_count}}


def recover_materials(path):
    """Resolve selected numeric material IDs through the actual ordered source FX library."""
    import hashlib
    from bdae_convert import BDAE
    reader = BDAE(path)
    count, table = reader.section(164)
    if count != 21: raise ValueError('Unsupported Efflib material library')
    expected = {0:'eff_unlit_textured_alpha-fx',2:'eff_unlit_textured_alpha_DS-fx',6:'eff_unlit_textured_additive-fx',7:'eff_unlit_textured_additive_NDT-fx',8:'eff_unlit_textured_additive_DS-fx',
                12:'eff_unlit_textured_mix_2color-fx',16:'eff_unlit_textured_mix_2color_additive-fx',17:'eff_unlit_textured_mix_2color_additive_NDT-fx'}
    result = {}
    for index, name in expected.items():
        at = table + index*56
        if reader.string(reader.q(at)) != name: raise ValueError('Effect material index/name mismatch')
        # Both relative pointers must address real source technique blocks.
        reader.at(reader.rel(at+32),16);reader.at(reader.rel(at+36),16)
        result[index] = {'id':index,'name':name,'blend':'additive' if index in (6,7,8,16,17) else 'alpha',
                         'twoColor':index in (12,16,17),'noDepthTest':index in (7,17),'source':'EfflibEffects.bdae',
                         'sourceSHA256':hashlib.sha256(reader.b).hexdigest()}
    return result
