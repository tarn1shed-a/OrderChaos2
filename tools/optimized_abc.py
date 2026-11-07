"""Static reader for this client's length-delimited, reordered ABC 46.16.

The standard constant pool is followed by a method-count reservation,
metadata/classes/scripts, length-prefixed signatures, then method-id/length-
prefixed bodies. No original bytecode is executed. Standard field/opcode facts:
https://github.com/adobe/avmplus/blob/master/doc/abcFormat-46-16.txt
https://github.com/adobe/avmplus/blob/master/core/opcodes.tbl
"""
import hashlib
import struct

from character_portraits import _ABC, decode_abc_metadata
from ui_assets import Bits, tags


def extract_abc(raw):
    if raw[:3] != b'FWS' or len(raw) < 12 or struct.unpack_from('<I', raw, 4)[0] != len(raw):
        raise ValueError('Expected complete uncompressed SWF')
    bits = Bits(raw, 8); bits.rect()
    blocks = []
    for kind, at, size in tags(raw, bits.pos()+4, len(raw)):
        if kind != 300:
            continue
        payload = raw[at:at+size]
        end = payload.find(b'\0', 4)
        if end < 4:
            raise ValueError('Invalid optimized ABC wrapper')
        blocks.append(payload[end+1:])
    if len(blocks) != 1:
        raise ValueError('Expected one optimized ABC block')
    return blocks[0]


def parse_abc(data):
    meta = decode_abc_metadata(data)
    r = _ABC(data); r.at = meta['constantPoolBytes']
    names = ['*'] + meta['multinames']; strings = meta['strings']
    method_count = r.count()

    def ref(pool):
        index = r.variable()
        if index >= len(pool):
            raise ValueError('ABC reference outside pool')
        return index

    def method():
        index = r.variable()
        if index >= method_count:
            raise ValueError('ABC method outside reservation')
        return index

    def traits():
        result = []
        for _ in range(r.count()):
            name = names[ref(names)]; flags = r.byte(); kind = flags & 15
            item = {'name': name, 'kind': kind}
            if flags & 0x80:
                raise ValueError('Unsupported ABC trait flags')
            if kind in (0, 6):
                item.update(slot=r.variable(), type=names[ref(names)], value=r.variable())
                if item['value']:
                    item['valueKind'] = r.byte()
            elif kind in (1, 2, 3):
                item.update(disp=r.variable(), method=method())
            elif kind == 4:
                item.update(slot=r.variable(), classIndex=r.variable())
            elif kind == 5:
                item.update(slot=r.variable(), method=method())
            else:
                raise ValueError('Unsupported ABC trait kind')
            if flags & 0x40:
                item['metadata'] = [r.variable() for _ in range(r.count())]
            result.append(item)
        return result

    metadata = []
    for _ in range(r.count()):
        name = ref(strings); count = r.count()
        metadata.append({'name': name, 'keys': [ref(strings) for _ in range(count)],
                         'values': [ref(strings) for _ in range(count)]})
    classes = []
    for _ in range(r.count()):
        name, parent, flags = names[ref(names)], names[ref(names)], r.byte()
        if flags & ~15:
            raise ValueError('Unsupported ABC instance flags')
        namespace = r.variable() if flags & 8 else None
        interfaces = [names[ref(names)] for _ in range(r.count())]
        classes.append({'name': name, 'super': parent, 'flags': flags, 'namespace': namespace,
                        'interfaces': interfaces, 'iinit': method(), 'traits': traits()})
    for cls in classes:
        cls.update(cinit=method(), staticTraits=traits())
    scripts = [{'init': method(), 'traits': traits()} for _ in range(r.count())]
    if r.count() != method_count:
        raise ValueError('ABC signature count differs from reservation')
    signatures = []
    for _ in range(method_count):
        size = r.count(); start = r.at
        count = r.count(); returns = names[ref(names)]
        params = [names[ref(names)] for _ in range(count)]
        name, flags = strings[ref(strings)], r.byte()
        optional = [(r.variable(), r.byte()) for _ in range(r.count())] if flags & 8 else []
        if len(optional) > count:
            raise ValueError('ABC optional arguments exceed parameter count')
        param_names = [strings[ref(strings)] for _ in range(count)] if flags & 128 else []
        if r.at-start != size:
            raise ValueError('ABC signature length mismatch')
        signatures.append({'params': params, 'return': returns, 'name': name, 'flags': flags,
                           'optional': optional, 'paramNames': param_names})
    bodies = {}
    for _ in range(r.count()):
        mid, size = method(), r.variable(); start = r.at
        if mid in bodies:
            raise ValueError('Duplicate ABC method body')
        stack, locals_, scope, max_scope = [r.variable() for _ in range(4)]
        length = r.count(); offset = r.at; code = r.take(length)
        exceptions = []
        for _ in range(r.count()):
            begin, end, target = [r.variable() for _ in range(3)]
            type_, name = ref(names), ref(names)
            if not 0 <= begin < end <= length or not 0 <= target < length:
                raise ValueError('ABC exception outside method')
            exceptions.append([begin, end, target, type_, name])
        activation = traits()
        if r.at-start != size or scope > max_scope or locals_ < len(signatures[mid]['params'])+1:
            raise ValueError('Invalid ABC method body extent/frame')
        bodies[mid] = {'offset': offset, 'code': code, 'maxStack': stack, 'locals': locals_,
                       'scope': scope, 'maxScope': max_scope, 'exceptions': exceptions, 'traits': activation}
    if r.at != len(data):
        raise ValueError('Trailing optimized ABC bytes')
    for container in [*classes, *scripts, *bodies.values()]:
        for trait in container.get('traits', []) + container.get('staticTraits', []):
            if trait.get('classIndex', 0) >= max(1, len(classes)):
                raise ValueError('ABC class reference outside table')
            if any(index >= len(metadata) for index in trait.get('metadata', [])):
                raise ValueError('ABC metadata reference outside table')
    # Retain scalar constant pools for disassembly; never execute the code.
    pool = _ABC(data); pool.take(4)
    ints = [0] + [pool.variable(0xffffffff) for _ in range(max(0, pool.count()-1))]
    ints = [v-(1 << 32) if v & (1 << 31) else v for v in ints]
    uints = [0] + [pool.variable(0xffffffff) for _ in range(max(0, pool.count()-1))]
    doubles = [float('nan')] + [struct.unpack('<d', pool.take(8))[0] for _ in range(max(0, pool.count()-1))]
    return {'classes': classes, 'scripts': scripts, 'signatures': signatures, 'bodies': bodies,
            'names': names, 'strings': strings, 'ints': ints, 'uints': uints, 'doubles': doubles,
            'sourceSHA256': hashlib.sha256(data).hexdigest(), 'bytesConsumed': r.at}


# Opcode, mnemonic and encoded operand count. Branches/debug have special layouts.
_OPCODES = '''01:bkpt:0 02:nop:0 03:throw:0 04:getsuper:1 05:setsuper:1 06:dxns:1 07:dxnslate:0 08:kill:1 09:label:0
0c:ifnlt:1 0d:ifnle:1 0e:ifngt:1 0f:ifnge:1 10:jump:1 11:iftrue:1 12:iffalse:1 13:ifeq:1 14:ifne:1 15:iflt:1 16:ifle:1 17:ifgt:1 18:ifge:1 19:ifstricteq:1 1a:ifstrictne:1 1b:lookupswitch:2
1c:pushwith:0 1d:popscope:0 1e:nextname:0 1f:hasnext:0 20:pushnull:0 21:pushundefined:0 23:nextvalue:0 24:pushbyte:1 25:pushshort:1 26:pushtrue:0 27:pushfalse:0 28:pushnan:0 29:pop:0 2a:dup:0 2b:swap:0 2c:pushstring:1 2d:pushint:1 2e:pushuint:1 2f:pushdouble:1 30:pushscope:0 31:pushnamespace:1 32:hasnext2:2
35:li8:0 36:li16:0 37:li32:0 38:lf32:0 39:lf64:0 3a:si8:0 3b:si16:0 3c:si32:0 3d:sf32:0 3e:sf64:0 40:newfunction:1 41:call:1 42:construct:1 43:callmethod:2 44:callstatic:2 45:callsuper:2 46:callproperty:2 47:returnvoid:0 48:returnvalue:0 49:constructsuper:1 4a:constructprop:2 4c:callproplex:2 4e:callsupervoid:2 4f:callpropvoid:2
50:sxi1:0 51:sxi8:0 52:sxi16:0 53:applytype:1 55:newobject:1 56:newarray:1 57:newactivation:0 58:newclass:1 59:getdescendants:1 5a:newcatch:1 5d:findpropstrict:1 5e:findproperty:1 5f:finddef:1 60:getlex:1 61:setproperty:1 62:getlocal:1 63:setlocal:1 64:getglobalscope:0 65:getscopeobject:1 66:getproperty:1 67:getouterscope:1 68:initproperty:1 6a:deleteproperty:1 6c:getslot:1 6d:setslot:1 6e:getglobalslot:1 6f:setglobalslot:1
70:convert_s:0 71:esc_xelem:0 72:esc_xattr:0 73:convert_i:0 74:convert_u:0 75:convert_d:0 76:convert_b:0 77:convert_o:0 78:checkfilter:0 80:coerce:1 81:coerce_b:0 82:coerce_a:0 83:coerce_i:0 84:coerce_d:0 85:coerce_s:0 86:astype:1 87:astypelate:0 88:coerce_u:0 89:coerce_o:0
90:negate:0 91:increment:0 92:inclocal:1 93:decrement:0 94:declocal:1 95:typeof:0 96:not:0 97:bitnot:0 a0:add:0 a1:subtract:0 a2:multiply:0 a3:divide:0 a4:modulo:0 a5:lshift:0 a6:rshift:0 a7:urshift:0 a8:bitand:0 a9:bitor:0 aa:bitxor:0 ab:equals:0 ac:strictequals:0 ad:lessthan:0 ae:lessequals:0 af:greaterthan:0 b0:greaterequals:0 b1:instanceof:0 b2:istype:1 b3:istypelate:0 b4:in:0
c0:increment_i:0 c1:decrement_i:0 c2:inclocal_i:1 c3:declocal_i:1 c4:negate_i:0 c5:add_i:0 c6:subtract_i:0 c7:multiply_i:0 d0:getlocal0:0 d1:getlocal1:0 d2:getlocal2:0 d3:getlocal3:0 d4:setlocal0:0 d5:setlocal1:0 d6:setlocal2:0 d7:setlocal3:0 ef:debug:4 f0:debugline:1 f1:debugfile:1 f2:bkptline:1 f3:timestamp:0'''
OPS = {int(code, 16): (name, int(count)) for code, name, count in (part.split(':') for part in _OPCODES.split())}
NAME_OPS = {4, 5, 0x45, 0x46, 0x4a, 0x4c, 0x4e, 0x4f, 0x59, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x66, 0x68, 0x6a, 0x80, 0x86, 0xb2}


def disassemble(code, abc):
    r = _ABC(code); result = []; destinations = []
    while r.at < len(code):
        at = r.at; opcode = r.byte()
        if opcode not in OPS:
            raise ValueError(f'Unsupported ABC opcode {opcode:#x}')
        name, count = OPS[opcode]; targets = []
        if 0x0c <= opcode <= 0x1a:
            offset = int.from_bytes(r.take(3), 'little', signed=True)
            args = [r.at + offset]; targets = args
        elif opcode == 0x1b:
            default = at + int.from_bytes(r.take(3), 'little', signed=True)
            cases = r.count()+1
            args = [default] + [at + int.from_bytes(r.take(3), 'little', signed=True) for _ in range(cases)]
            targets = args
        elif opcode in (0x24, 0x65):
            args = [int.from_bytes(r.take(1), 'little', signed=opcode == 0x24)]
        elif opcode == 0x25:
            value = r.variable(0xffffffff)
            args = [value-(1 << 32) if value & (1 << 31) else value]
        elif opcode == 0xef:
            args = [r.byte(), r.variable(), r.byte(), r.variable()]
        else:
            args = [r.variable() for _ in range(count)]
        operands = list(args)
        pool = 'names' if opcode in NAME_OPS else {0x2c: 'strings', 0x2d: 'ints', 0x2e: 'uints', 0x2f: 'doubles'}.get(opcode)
        if pool:
            if not args or args[0] >= len(abc[pool]):
                raise ValueError('ABC instruction reference outside pool')
            args[0] = abc[pool][args[0]]
        result.append({'at': at, 'end': r.at, 'op': name, 'args': args, 'operands': operands, 'targets': targets})
        destinations.extend(targets)
    boundaries = {item['at'] for item in result}
    if any(target not in boundaries for target in destinations):
        raise ValueError('ABC branch target is not an instruction')
    return result


def named_method(abc, class_name, method_name):
    classes = [cls for cls in abc['classes'] if cls['name'] == class_name]
    if len(classes) != 1:
        raise ValueError('ABC class missing or ambiguous')
    cls = classes[0]
    found = [trait['method'] for trait in cls['traits'] if trait['name'] == method_name and 'method' in trait]
    if len(found) != 1 or found[0] not in abc['bodies']:
        raise ValueError('ABC method missing or ambiguous')
    mid = found[0]; body = abc['bodies'][mid]
    return {'methodId': mid, 'codeOffset': body['offset'], 'codeBytes': len(body['code']),
            'codeSHA256': hashlib.sha256(body['code']).hexdigest(),
            'instructions': disassemble(body['code'], abc)}
