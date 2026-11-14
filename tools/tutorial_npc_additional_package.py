"""Validate and package the private747/970 review tree; never deploy it."""
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-tutorial-npc-additional-candidate-v1'


def private_path(path):
    path=Path(path).resolve()
    if not path.is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Private NPC assets must stay in ignored analysis/raw/')
    return path


def package(candidate,output):
    candidate,output=map(private_path,(candidate,output));proof=output.with_suffix(output.suffix+'.json')
    if output.exists()or proof.exists():raise ValueError('Existing private package is preserved')
    metadata=json.loads((candidate/'package-files.json').read_text())
    if metadata.get('format')!=FORMAT or metadata.get('privateOnly')is not True:
        raise ValueError('Expected private additional NPC candidate')
    expected=set(metadata['files'])|{'package-files.json'}
    actual={str(p.relative_to(candidate))for p in candidate.rglob('*')if p.is_file()}
    if expected!=actual:raise ValueError('Candidate has missing/additional files')
    records={}
    for name in sorted(expected):
        path=candidate/name
        if Path(name).is_absolute()or'..'in Path(name).parts or path.is_symlink()or not path.resolve().is_relative_to(candidate):
            raise ValueError('Unsafe candidate member')
        raw=path.read_bytes();record={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if name!='package-files.json'and record!=metadata['files'][name]:raise ValueError('Candidate SHA/length changed')
        records[name]=record
    result=io.BytesIO()
    with gzip.GzipFile(fileobj=result,mode='wb',mtime=0,filename='')as compressed:
        with tarfile.open(fileobj=compressed,mode='w')as archive:
            for name in records:
                raw=(candidate/name).read_bytes();info=tarfile.TarInfo('npc-additional-source-candidate/'+name)
                info.size=len(raw);info.mode=0o644;info.mtime=0;archive.addfile(info,io.BytesIO(raw))
    encoded=result.getvalue()
    with tarfile.open(fileobj=io.BytesIO(encoded),mode='r:gz')as archive:
        for member in archive.getmembers():
            name=member.name.removeprefix('npc-additional-source-candidate/')
            if hashlib.sha256(archive.extractfile(member).read()).hexdigest()!=records[name]['sha256']:
                raise ValueError('Private archive roundtrip failed')
    report={'format':FORMAT,'package':str(output),'bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest(),
            'files':records,'privateOnly':True,'deployed':False,'runtimeActorsCreated':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(encoded)
    proof.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return {'package':str(output),'sha256':report['sha256'],'bytes':len(encoded),'files':len(records),'privateOnly':True}


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--candidate',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();print(json.dumps(package(args.candidate,args.output)))
