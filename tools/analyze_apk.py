"""Read-only static inventory and focused Dalvik disassembly. No network calls."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from loguru import logger
logger.remove()
from androguard.core.apk import APK
from androguard.core.dex import DEX

p = argparse.ArgumentParser()
p.add_argument('apk', type=Path)
p.add_argument('--output', type=Path, default=Path('analysis/raw'))
args = p.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
a = APK(str(args.apk))
manifest = a.get_android_manifest_xml()
from lxml import etree
(args.output / 'AndroidManifest.xml').write_bytes(etree.tostring(manifest, pretty_print=True, encoding='utf-8'))
summary = {'sha256': hashlib.sha256(args.apk.read_bytes()).hexdigest(), 'package': a.get_package(), 'version': a.get_androidversion_name(), 'version_code': a.get_androidversion_code(), 'main_activity': a.get_main_activity(), 'permissions': a.get_permissions()}
with zipfile.ZipFile(args.apk) as z:
    summary['assets'] = [n for n in z.namelist() if n.startswith('assets/')]
    summary['obb'] = [n for n in z.namelist() if n.endswith('.obb')]
    lines, classes = [], []
    for dn in a.get_dex_names():
        dex = DEX(z.read(dn))
        for c in dex.get_classes():
            name = c.get_name()
            if 'gameloft' not in name.lower():
                continue
            classes.append(name)
            for m in c.get_methods():
                ins = [f'{offset:04x} {i.get_name()} {i.get_output()}' for offset, i in m.get_instructions_idx()]
                text = '\n'.join(ins)
                if any(s.lower() in name.lower() for s in ['MainActivity;', 'GameInstaller', 'SilentInstaller', 'ApplicationSetUp;', 'FrameworkApplication;', 'GLUtils;', 'Download', 'Unzip', 'DataPath', 'FileUtils', 'NativeBridge', 'JNIBridge']) or re.search(r'loadLibrary|\.obb|/Android/|setDataPath|nativeInit|dataPath|resourcePath', text, re.I):
                    lines.append(f'\n## {name}->{m.get_name()}{m.get_descriptor()}\n{text}')
    (args.output / 'resource-flow.dalvik.txt').write_text('\n'.join(lines))
    (args.output / 'classes.txt').write_text('\n'.join(classes))
    native = z.read('lib/arm64-v8a/libOrderChaos2.so')
    strings = [s.decode('ascii') for s in re.findall(rb'[\x20-\x7e]{6,}', native)]
    selected = [s for s in strings if re.search(r'\.obb|/Android/|\.pak\b|\.zip\b|\.gla\b|\.pvr\b|GameOptions|resource.{0,12}(path|load)|download.{0,12}(file|pack)|data.{0,6}path|\.gfs\b', s, re.I)]
    (args.output / 'native-resource-strings.txt').write_text('\n'.join(selected))
(args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('Focused disassembly and resource strings saved to', args.output)
