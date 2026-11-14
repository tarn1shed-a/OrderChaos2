"""Package only a validated private NPC asset-review candidate, without deploy."""
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

from tutorial_map_geometry import local_output
from tutorial_npc_candidate import FORMAT


def package(candidate, output):
    candidate,output=map(local_output,(candidate,output))
    if output.exists():raise ValueError('Existing package is preserved')
    metadata=json.loads((candidate/'package-files.json').read_text())
    if metadata.get('format')!=FORMAT or metadata.get('privateOnly')is not True:
        raise ValueError('Only a checked private NPC candidate can be packaged')
    expected=set(metadata['files'])|{'package-files.json'}
    actual={str(p.relative_to(candidate)) for p in candidate.rglob('*')if p.is_file()}
    if expected!=actual:raise ValueError('Candidate contains missing or additional unreviewed files')
    records={}
    for name in sorted(expected):
        if Path(name).is_absolute()or'..'in Path(name).parts:raise ValueError('Unsafe candidate path')
        raw=(candidate/name).read_bytes()
        item={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if name!='package-files.json'and item!=metadata['files'][name]:
            raise ValueError('Candidate SHA/length differs: '+name)
        records[name]=item
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',mtime=0,filename='')as compressed:
        with tarfile.open(fileobj=compressed,mode='w')as archive:
            for name,item in records.items():
                raw=(candidate/name).read_bytes();info=tarfile.TarInfo('npc750-source-candidate/'+name)
                info.size=len(raw);info.mode=0o644;info.mtime=0;archive.addfile(info,io.BytesIO(raw))
    encoded=buffer.getvalue()
    with tarfile.open(fileobj=io.BytesIO(encoded),mode='r:gz')as archive:
        for member in archive.getmembers():
            name=member.name.removeprefix('npc750-source-candidate/')
            raw=archive.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest()!=records[name]['sha256']:
                raise ValueError('Archive roundtrip differs')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(encoded)
    report={'format':FORMAT,'privateOnly':True,'package':str(output),'bytes':len(encoded),
            'sha256':hashlib.sha256(encoded).hexdigest(),'files':records,
            'deploymentPerformed':False,'runtimeActorCreated':False}
    proof=output.with_suffix(output.suffix+'.json');proof.write_text(json.dumps(report,indent=2)+'\n')
    return {'package':str(output),'sha256':report['sha256'],'files':len(records),'privateOnly':True}


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--candidate',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();print(json.dumps(package(args.candidate,args.output)))
