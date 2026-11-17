"""Assemble frozen private NPC review runtimes; never create actors or alter source assets."""
import argparse
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw'
FORMAT = 'oc2-npc-source-resource-library-v1'
FAMILIES = {
    'weapons': ('tutorial-npc-weapons-20261114', 'candidate-v4', [750, 970]),
    'additional': ('tutorial-npc-additional-20261114', 'candidate-v2', [747]),
    'binding': ('tutorial-npc-binding-20261114', 'candidate-v3', [867, 971]),
    'catalog': ('tutorial-npc-catalog-20261114', 'candidate-v6', [983, 984]),
    'soldiers': ('tutorial-npc-soldiers-20261114', 'candidate-v3', [749, 1632]),
    'robes': ('tutorial-npc-robes-20261114', 'candidate-v4', [972, 1018]),
    'remaining': ('tutorial-npc-remaining-20261114', 'candidate-v1', [973, 1013]),
    'final-pair': ('tutorial-npc-final-pair-20261114', 'candidate-v5', [982, 1017]),
    'next': ('tutorial-npc-final-pair-20261114/next', 'candidate-v2', [1005, 1006]),
    'last': ('tutorial-npc-final-pair-20261114/last', 'candidate-v1', [1007, 1008]),
}


def digest(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def private_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(RAW.resolve()):
        raise ValueError('Private resource library must remain under ignored analysis/raw/')
    return path


def asset_strings(value):
    if isinstance(value, str):
        if value.startswith('/assets/'):
            yield value[1:]
    elif isinstance(value, dict):
        for item in value.values():
            yield from asset_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from asset_strings(item)


def rebase(value, prefix='./'):
    if isinstance(value, str):
        return prefix + value[1:] if value.startswith('/assets/') else value
    if isinstance(value, dict):
        return {k: rebase(v, prefix) for k, v in value.items()}
    if isinstance(value, list):
        return [rebase(v, prefix) for v in value]
    return value


def verify_frozen_candidate(source):
    receipt = json.loads((source / 'package-files.json').read_text())
    if receipt.get('privateOnly') is not True:
        raise ValueError('Expected private source candidate receipt')
    for name, expected in receipt['files'].items():
        path = source / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink():
            raise ValueError('Unsafe frozen candidate member')
        if digest(path) != expected:
            raise ValueError('Frozen candidate bytes changed: ' + str(path))
    return receipt


def json_write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def build(output):
    output = private_path(output)
    if output.exists():
        raise ValueError('Existing candidate is preserved; choose a new private output')
    # Validate every input before creating a new review tree.
    inputs = {}
    for key, (folder, version, entries) in FAMILIES.items():
        base = RAW / folder
        source = base / version
        receipt = verify_frozen_candidate(source)
        handoff = json.loads((base / 'handoff.json').read_text())
        package = handoff.get('privatePackage') or handoff['package']
        if digest(ROOT / package['path']) != {k: package[k] for k in ('bytes', 'sha256')}:
            raise ValueError('Frozen source archive changed')
        manifest = json.loads((source / 'manifest.json').read_text())
        if manifest.get('liveActor') is not False:
            raise ValueError('Only independent source reviews are allowed')
        inputs[key] = source, receipt, manifest, package
    coverage_path = RAW / 'tutorial-npc-final-pair-20261114/last/coverage-local-cumulative.json'
    coverage = json.loads(coverage_path.read_text())
    matrix = {r['entry']: r for r in coverage['templates']}
    if len(matrix) != 22:
        raise ValueError('Expected original22-template coverage')
    output.mkdir(parents=True)
    entries_out, family_out, lineage = [], {}, {}
    for key, (source, receipt, original, package) in inputs.items():
        selected = FAMILIES[key][2]
        manifest = copy.deepcopy(original)
        manifest['entries'] = [e for e in manifest['entries'] if e['entry'] in selected]
        if {e['entry'] for e in manifest['entries']} != set(selected):
            raise ValueError('Missing requested original template')
        dest = output / 'families' / key
        dest.mkdir(parents=True)
        files = set(asset_strings(manifest))
        files.update(p.name for p in source.glob('*.js'))
        files.add('index.html')
        lineage[key] = {'sourceCandidate': str(source.relative_to(ROOT)),
                        'sourceArchive': package, 'sourceReceipt': digest(source / 'package-files.json'),
                        'byteIdentical': {}, 'hostURLAdapters': {}, 'entries': selected}
        for name in sorted(files):
            if name not in receipt['files']:
                raise ValueError('Unreceipted runtime dependency: ' + name)
            path = source / name
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            text = raw.decode() if path.suffix in ('.js', '.html') else None
            changed = text
            if path.suffix == '.js' and "fetch('/manifest.json')" in text:
                if text.count("fetch('/manifest.json')") != 1:
                    raise ValueError('Unexpected frozen preview manifest loader')
                changed = text.replace("fetch('/manifest.json')", "fetch(new URL('./manifest.json',import.meta.url))")
            if path.suffix == '.html':
                changed = re.sub(r'src="/([^"/]+\.js)"', r'src="./\1"', text)
            if changed is not None and changed != text:
                target.write_text(changed)
                lineage[key]['hostURLAdapters'][name] = {
                    'source': digest(path), 'adapted': digest(target),
                    'only': 'manifest fetch URL / HTML script src made relative; renderer unchanged'}
            else:
                target.write_bytes(raw)
                lineage[key]['byteIdentical'][name] = digest(target)
        json_write(dest / 'manifest.json', rebase(manifest))
        lineage[key]['hostURLAdapters']['manifest.json'] = {
            'source': digest(source / 'manifest.json'), 'adapted': digest(dest / 'manifest.json'),
            'only': 'root /assets URLs made relative; additional family selects747 only; source values unchanged'}
        family_out[key] = {'preview': f'./families/{key}/index.html',
                           'manifest': f'./families/{key}/manifest.json', 'entries': selected,
                           'sourceArchiveSHA256': package['sha256']}
        for entry in manifest['entries']:
            record = copy.deepcopy(matrix[entry['entry']])
            record.update({'name': entry['name'], 'family': key,
                           'preview': family_out[key]['preview'],
                           'manifest': family_out[key]['manifest'],
                           'model': f'./families/{key}' + entry['model'],
                           'parentAccepted': False, 'productionActor': False})
            entries_out.append(record)
    entries_out.sort(key=lambda e: e['entry'])
    if len(entries_out) != 19 or len({e['entry'] for e in entries_out}) != 19:
        raise ValueError('Expected19 distinct ordinary resource candidates')
    library = {'format': FORMAT, 'privateOnly': True, 'liveActor': False,
               'entries': entries_out, 'families': family_out,
               'coverage': coverage, 'sourceCoverageSHA256': digest(coverage_path)['sha256'],
               'sourceMaterialChanges': False, 'originalModelOrPNGChanges': False,
               'actorAdmissionProvided': False, 'modelReadyProduced': False,
               'scope': 'Frozen independently visible original asset candidates; browser renderer is a review adapter.',
               'unknown': ['Original activity/GUID/location/appearance overrides/pose/quest state',
                           'Compiled Android GPU effect program and genuine wrapper/node completion',
                           '982/984 source200029 UT weapon rendering inputs; hidden mask gaps remain in coverage']}
    json_write(output / 'library.json', library)
    json_write(output / 'lineage.json', {'format': FORMAT, 'families': lineage,
                                      'onlyNewHostOperations': ['relative URL rebasing', 'resource entry selection', 'iframe mount/dispose']})
    shutil.copyfile(ROOT / 'tools/preview/source-npc-resource-resolve-library.js', output / 'source-npc-resource-resolve-library.js')
    (output / 'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>原NPC独立资源库</title>
<style>html,body{margin:0;height:100%;background:#14191d;color:#e8e7df;font:14px sans-serif}body{display:flex;flex-direction:column}header{padding:12px 18px;background:#202b30}h1{font-size:18px;margin:0 0 6px}p{margin:5px 0;color:#c1ced1}nav{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}button{background:#26373f;color:#e8e7df;border:1px solid #53666c;padding:6px;cursor:pointer}button[aria-pressed=true]{border-color:#cfb075}#view{flex:1;min-height:500px}iframe{border:0;width:100%;height:100%}#gap{color:#eed2a0;font-size:12px}</style>
<header><h1>原NPC独立资源库 · 19条普通模板候选</h1><p>原模型／材质／蒙皮／idle；活动演员、位置、姿态与任务状态仍未知。3条Mark仅列覆盖诊断。</p><nav></nav><p id="gap"></p></header><main id="view"></main><script type="module">
import {loadSourceNPCLibrary,mountSourceNPCPreview} from './source-npc-resource-resolve-library.js';
const library=await loadSourceNPCLibrary(),nav=document.querySelector('nav'),gap=document.querySelector('#gap');
let current;
async function select(entry){
 for(const b of nav.children)b.setAttribute('aria-pressed',String(Number(b.dataset.entry)===entry.entry));
 gap.textContent=entry.knownGaps.length?entry.knownGaps.join(' / '):'本条默认资产已作独立审阅；不代表生产活动演员。';
 try{current=await mountSourceNPCPreview(document.querySelector('#view'),entry.entry);await current.ready;}catch(error){gap.textContent=error.message;console.error(error);}
}
for(const entry of library.entries){const b=document.createElement('button');b.dataset.entry=entry.entry;b.textContent=entry.entry+' '+entry.name;b.onclick=()=>select(entry);nav.append(b);}
select(library.entries.find(e=>e.entry===750));
const qa=document.createElement('script');qa.id='npc-library-review-state';qa.type='application/json';document.body.append(qa);
setInterval(()=>{qa.textContent=JSON.stringify(current?.readState()??{loading:true});},200);
</script></html>''')
    records = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    json_write(output / 'package-files.json', {'format': FORMAT, 'privateOnly': True, 'files': records})
    return {'candidate': str(output.relative_to(ROOT)), 'entries': 19, 'coverage': 22,
            'families': len(family_out), 'files': len(records) + 1,
            'sourceAssetsUnmodified': True, 'activityOrNodeSuccessCreated': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    print(json.dumps(build(cli.parse_args().output), ensure_ascii=False))
