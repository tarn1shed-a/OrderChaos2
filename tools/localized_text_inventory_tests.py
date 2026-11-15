import struct
import unittest

from localized_text_inventory import read_localized_rows


def table(values):
    count=len(values);ids=44;types=ids+4*count;rows=types+3;pool=rows+10*count
    prefix=b'FTABLE\0\0'+struct.pack('<9I',0x100000,count,2,ids,types,rows,10 if count else 0,pool,0)
    entries=bytearray();strings=bytearray()
    for ident,value in values:
        data=value+b'\0';entries.extend(struct.pack('<IIH',ident,pool+len(strings),len(data)));strings.extend(data)
    return prefix+struct.pack('<'+str(count)+'I',*[v[0]for v in values])+b'us\0'+entries+strings


class InventoryTests(unittest.TestCase):
    def test_shipping_table_without_sql_retains_chinese_and_literal_placeholder(self):
        result=read_localized_rows(table([(1995,b'test'),(2435,'箱子'.encode())]))
        self.assertEqual(result['values'],{1995:'test',2435:'箱子'})
        self.assertFalse(result['verification']['sqlPresent'])

    def test_empty_table_is_not_a_failed_decoder_or_missing_file(self):
        result=read_localized_rows(table([]))
        self.assertTrue(result['verification']['empty'])
        self.assertEqual(result['verification']['rows'],0)

    def test_one_bad_utf8_row_is_reported_without_replacing_text_or_losing_other_rows(self):
        result=read_localized_rows(table([(1,b'\xff'),(2,'中文'.encode())]))
        self.assertEqual(result['values'],{2:'中文'})
        self.assertEqual(result['invalidUTF8'][0]['id'],1)
        self.assertEqual(result['invalidUTF8'][0]['rawHex'],'ff00')
        self.assertFalse(result['verification']['invalidRowsSubstituted'])

    def test_pointer_and_terminator_damage_are_not_treated_as_encoding_choices(self):
        raw=bytearray(table([(1,b'test')]))
        struct.pack_into('<I',raw,55,0)
        with self.assertRaises(ValueError):read_localized_rows(bytes(raw))
        with self.assertRaises(ValueError):read_localized_rows(table([(1,b'test')])[:-1]+b'X')


if __name__=='__main__':unittest.main()
