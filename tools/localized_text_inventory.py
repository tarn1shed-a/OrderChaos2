"""Read shipping localized FTABLE physical rows, including empty/no-SQL tables.

Separate from strict icon/quest exporters: missing SQL is recorded, and invalid
UTF-8 is retained as an explicit byte/error row, never guessed or replaced.
This is an offline inventory reader, not a game localization fallback.
"""
import hashlib
import re
import struct


def read_localized_rows(raw):
    if len(raw) < 47 or raw[:8] != b'FTABLE\0\0':
        raise ValueError('Unsupported localized table header')
    version, count, columns, ids, types, rows, stride, pool, reserved = struct.unpack_from('<9I', raw, 8)
    if (version != 0x100000 or reserved or columns != 2 or count > 100000 or ids < 44
            or types != ids+count*4 or rows != types+3
            or stride != (10 if count else 0) or pool != rows+count*stride
            or pool > len(raw) or raw[types:rows] != b'us\0'):
        raise ValueError('Invalid localized physical sections')
    if not count and pool != len(raw):
        raise ValueError('Unexpected payload in empty localized table')
    schema = raw[44:ids].split(b'\0', 1)[0].decode('utf-8')
    columns_sql = re.findall(r'^\s*`([^`]+)`\s+', schema, re.MULTILINE)
    if schema and (not columns_sql or columns_sql[0] != 'ID' or len(set(columns_sql)) != len(columns_sql)):
        raise ValueError('Unexpected localized SQL schema')
    identifiers = struct.unpack_from('<'+str(count)+'I', raw, ids)
    if len(set(identifiers)) != count:
        raise ValueError('Duplicate localized identifier')
    values, invalid = {}, []
    for i, ident in enumerate(identifiers):
        actual, pointer, length = struct.unpack_from('<IIH', raw, rows+i*stride)
        size = length or 1
        if actual != ident or pointer < pool or pointer >= len(raw) or pointer+size > len(raw):
            raise ValueError('Invalid localized record/index/string extent')
        data = raw[pointer:pointer+size]
        if data[-1:] != b'\0' or b'\0' in data[:-1]:
            raise ValueError('Invalid localized terminator')
        try:
            values[ident] = data[:-1].decode('utf-8')
        except UnicodeDecodeError as error:
            invalid.append({'id': ident, 'pointer': pointer, 'length': length,
                            'rawHex': data.hex(), 'error': str(error)})
    return {'values': values, 'invalidUTF8': invalid,
            'verification': {'sourceSHA256': hashlib.sha256(raw).hexdigest(),
                             'rows': count, 'validTextRows': len(values), 'empty': count == 0,
                             'rowStride': stride, 'sqlPresent': bool(schema),
                             'sqlLanguageColumns': columns_sql[1:],
                             'physicalLanguageSelectedByCallerSourcePath': True,
                             'invalidRowsSubstituted': False}}
