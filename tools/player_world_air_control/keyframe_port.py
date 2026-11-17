"""Pinned c_keyframe rows as loaded-cache storage for original a50900 lookup.

This is the same explicit table/container storage boundary as the original
state/action host. Source rows are not source pose, actor permission or a
successful file/resource service. Actual name/lookup/output arithmetic execute
ARM64, with original a4bfcc..a4bfe4 field mapping retained as evidence.
"""
from skill_attachments import decode_ftable

def install(engine,raw):
    table=decode_ftable(raw,'id');rows=table['rows'];seen={};duplicates=[]
    for row in rows:
        path=row['path']
        if path in seen:
            # a4bfac find -> existing path emits diagnostic then a4bfe8,
            # without replacing the first source row's three words.
            duplicates.append({'kept':seen[path]['id'],'skipped':row['id'],'path':path});continue
        if not path.isascii():raise ValueError('NonASCII keyframe is outside this source container port')
        seen[path]=row
    header=0x2544508
    # Actual original static initialization of the map, not an all-zero root
    # passed off as a loaded original runtime cache.
    engine.original_fragment(0x2ba514,0x2ba52c,{'X1':0x2544500})
    nodes={}
    def build(ordered,parent):
        if not ordered:return 0
        i=len(ordered)//2;path,row=ordered[i];p=engine.alloc(0x38);nodes[path]=p
        left=build(ordered[:i],p);right=build(ordered[i+1:],p)
        engine.w(p,'I',1);engine.w(p+8,'3Q',parent,left,right);engine.w(p+0x20,'Q',engine.string(path.encode()))
        engine.w(p+0x28,'3I',row['keyframe'],row['blade_start_frame'],row['blade_end_frame']);return p
    ordered=sorted(seen.items());root=build(ordered,header)
    engine.w(0x2544510,'4Q',root,nodes[ordered[0][0]],nodes[ordered[-1][0]],len(ordered))
    return{'scope':'explicit original loaded-table container port, native a50900 reads it','rows':len(rows),'uniquePaths':len(ordered),'duplicates':duplicates,'sourceSHA256':table['verification']['sourceSHA256'],'nativeImportMapping':'a4bfac..a4bfe8','nativeStaticInit':'2ba514..2ba52c','nativeTableGetter':'c993b8','AndroidSessionCacheClaimed':False}
