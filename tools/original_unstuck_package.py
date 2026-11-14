"""Validate and package private original BreakAway inspection resources."""
import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from tutorial_map_geometry import local_output

def package(candidate,native,output):
    candidate=local_output(candidate);native=local_output(native);output=local_output(output)
    rows=json.loads((candidate/'files.json').read_text())
    for row in rows:
        p=(candidate/row['path']).resolve()
        if not p.is_relative_to(candidate)or not p.is_file():raise ValueError('Invalid candidate member')
        raw=p.read_bytes()
        if len(raw)!=row['bytes']or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Original candidate hash mismatch')
    r=json.loads(native.read_text())
    if r['ordinaryMap5']['packets']!=[{'opcode':644,'payloadHex':'','bytes':0,'transportExecuted':False}]:raise ValueError('Original request evidence differs')
    members={str(p.relative_to(candidate)):p.read_bytes()for p in sorted(candidate.rglob('*'))if p.is_file()}
    if set(members)!={row['path']for row in rows}|{'files.json'}:raise ValueError('Unmanifested source candidate member')
    members['native-validated.json']=native.read_bytes();members['README.txt']=b'Private original BreakAway UI components and isolated ARM64 fixture evidence. Not a game menu, original server, live state, destination or cooldown implementation. Text metrics/transport remain boundaries. Do not publish source resources.\n'
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb')as stream:
        with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0)as gz:
            with tarfile.open(fileobj=gz,mode='w')as tar:
                for n,raw in sorted(members.items()):
                    info=tarfile.TarInfo(n);info.size=len(raw);info.mode=0o644;info.mtime=0;tar.addfile(info,io.BytesIO(raw))
    return {'path':str(output),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'members':len(members),'sourceResourcesPrivate':True}

if __name__=='__main__':
    c=argparse.ArgumentParser(description=__doc__);c.add_argument('--candidate',type=Path,required=True);c.add_argument('--native',type=Path,required=True);c.add_argument('--output',type=Path,required=True);a=c.parse_args();print(json.dumps(package(a.candidate,a.native,a.output)))
