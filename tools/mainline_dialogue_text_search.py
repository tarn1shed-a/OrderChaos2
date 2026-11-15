"""Inventory original Chinese localization, including no-SQL shipping tables.

Keyword hits are evidence candidates, not interchangeable dialogue. All rows,
text, byte errors and archive proofs are written only to a new ignored report.
"""
import argparse
import json
from pathlib import Path

from localized_text_inventory import read_localized_rows
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output

TERMS=('斯宾塞','史宾塞','斯賓塞','Spencer','皮尔斯','皮爾斯','Pierce',
       '噩梦','当班','海难','巨大的锤子','货箱','箱子')


def search(source=DEFAULT_SOURCE,terms=TERMS):
    s=Sources(source)
    result={'format':'oc2-mainline-chinese-dialogue-search-v1','terms':list(terms),
            'tables':[],'matches':[],'errors':[],
            'referenceEquivalenceAsserted':False,'taskApprovalProduced':False}
    for path in sorted(p for p in s.lookup if p.startswith('tables/')and p.endswith('_zh.tbl')):
        try:
            parsed=read_localized_rows(s.read(path));matches=[]
            for ident,text in parsed['values'].items():
                hit=[term for term in terms if term.lower()in text.lower()]
                if hit:matches.append({'table':path,'id':ident,'terms':hit,'text':text})
            result['matches'].extend(matches)
            result['tables'].append({'path':path,'verification':parsed['verification'],
                                     'invalidUTF8':parsed['invalidUTF8'],'matches':len(matches)})
        except ValueError as error:
            result['errors'].append({'path':path,'error':str(error)})
    result['sourceProofs']=s.proofs
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=local_output(args.output)
    if output.exists():parser.error('Preserve previous source reports')
    result=search(args.source);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'tables':len(result['tables']),
        'rows':sum(t['verification']['rows']for t in result['tables']),
        'matches':len(result['matches']),'tableErrors':len(result['errors']),
        'invalidTextRows':sum(len(t['invalidUTF8'])for t in result['tables']),
        'taskApprovalProduced':False}))
