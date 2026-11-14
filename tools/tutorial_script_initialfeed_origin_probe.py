"""InitialFeed origin: original ZIP/GBMP indexes, DEX consumers and export copy.

No all-payload scan, speculative codec, network, file modification or gameplay.
Only original DEX and any actual matching named resource are opened.
"""
import hashlib
import json
import os
import re
import zipfile
import zlib
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, index, normalize_resource_name, read_entry
from tutorial_script_initialfeed_probe import SOURCE_SHA, InitialFeedProbe, SO

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-initialfeed-origin-20261115'
APK = Path('/Users/kevin/Downloads/com.gameloft.android.anmp.glofto2hm.apk')
APK_SHA = '4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe'
PUBLIC = Path('/Users/kevin/Public/com.gameloft.android.ANMP.GloftO2HM/files/InitialFeed.dat')


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'crc32': zlib.crc32(raw) & 0xffffffff}


def match_name(name):
    canonical = normalize_resource_name(name)
    similar = re.sub('[^a-z0-9]', '', canonical.rsplit('/', 1)[-1])
    return canonical.rsplit('/', 1)[-1] == 'initialfeed.dat' or similar == 'initialfeeddat'


def dex_sources(archive):
    from loguru import logger
    logger.remove()
    from androguard.core.dex import DEX
    metadata = []; target_strings = []; candidates = []; path_methods = []; examined = 0
    for info in archive.infolist():
        if not re.fullmatch(r'classes(?:\d+)?\.dex', info.filename):
            continue
        raw = archive.read(info); dex = DEX(raw); strings = dex.get_strings()
        metadata.append({'dex': info.filename, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                         'strings': len(strings), 'classes': len(dex.get_classes())})
        names = [s for s in strings if 'initialfeed' in re.sub('[^a-z0-9]', '', s.lower())]
        target_strings.extend({'dex': info.filename, 'name': s} for s in names)
        for cls in dex.get_classes():
            for method in cls.get_methods():
                if not method.get_code():
                    continue
                examined += 1
                instructions = [(at, instruction.get_name(), instruction.get_output())
                                for at, instruction in method.get_instructions_idx()]
                text = '\n'.join(x[2] for x in instructions)
                root_getter = (cls.get_name() == 'Lcom/gameloft/android/ANMP/GloftO2HM/PackageUtils/AndroidUtils;'
                               and method.get_name() in ('RetrieveDataPath', 'RetrieveSavePath', 'RetrieveTempPath'))
                preference = (cls.get_name() == 'Lcom/gameloft/android/ANMP/GloftO2HM/GLUtils/SUtils;'
                              and method.get_name() == 'getPreferenceString'
                              and method.get_descriptor() == '(Landroid/content/Context; Ljava/lang/String; Ljava/lang/String;)Ljava/lang/String;')
                prefs_name = (cls.get_name() == 'Lcom/gameloft/android/ANMP/GloftO2HM/installer/GameInstaller;'
                              and method.get_name() == '<clinit>')
                if root_getter or preference or prefs_name:
                    selected = [x for x in instructions if not prefs_name or x[0] <= 0x1c]
                    name = cls.get_name() + '->' + method.get_name() + method.get_descriptor()
                    body = '## ' + name + '\n' + '\n'.join(f'{at:04x} {kind} {args}' for at, kind, args in selected) + '\n'
                    path_methods.append({'method': name, 'dex': info.filename,
                        'sourceFile': f'java-path-producer-{len(path_methods):02d}.dalvik.txt',
                        'sourceSHA256': hashlib.sha256(body.encode()).hexdigest(),
                        'completeMethod': not prefs_name, 'source': body})
                installer = '/installer/' in cls.get_name()
                asset = 'Landroid/content/res/AssetManager;->open(' in text
                copy = (installer and 'Ljava/io/FileOutputStream;-><init>' in text
                        and '->read(' in text and '->write(' in text)
                member = installer and 'Ljava/util/zip/ZipFile;->getInputStream(' in text
                if not (asset or copy or member):
                    continue
                name = cls.get_name() + '->' + method.get_name() + method.get_descriptor()
                source = f'java-candidate-{len(candidates):02d}.dalvik.txt'
                body = '## ' + name + '\n' + '\n'.join(f'{at:04x} {kind} {args}' for at, kind, args in instructions) + '\n'
                candidates.append({'method': name, 'dex': info.filename, 'instructions': len(instructions),
                    'assetOpen': asset, 'installerCopy': copy, 'zipMemberRead': member,
                    'sourceFile': source, 'sourceSHA256': hashlib.sha256(body.encode()).hexdigest(),
                    'initialFeedLiteral': any(s in text for s in names), 'source': body})
    installer_candidates = [c for c in candidates if c['installerCopy'] and c['zipMemberRead']]
    assert len(installer_candidates) == 2
    for item in installer_candidates:
        assert '01b4 invoke-virtual v8, v2, v10, v11, Ljava/io/BufferedInputStream;->read([B I I)I' in item['source']
        assert '01cc invoke-virtual v4, v2, v11, v10, Ljava/io/BufferedOutputStream;->write([B I I)V' in item['source']
    return {'dex': metadata, 'methodsWithCodeExamined': examined,
        'initialFeedStrings': target_strings, 'specificInitialFeedJavaProducerFound': False,
        'copyCandidates': candidates, 'pathProducerMethods': path_methods,
        'dynamicFilenameOrNativeProducerRuledOut': False,
        'networkExecuted': False}


def run():
    current = DEFAULT_SOURCE / 'InitialFeed.dat'; source = current.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA
    project = identity(current); original_export = {'path': str(PUBLIC), 'exists': PUBLIC.is_file()}
    if PUBLIC.is_file():
        original_export.update(identity(PUBLIC)); original_export.update({
            'sameInodeAsProject': os.path.samefile(PUBLIC, current),
            'exportDirectorySymlink': PUBLIC.parents[1].is_symlink(),
            'sameBytesAsProject': PUBLIC.read_bytes() == source})
    assert hashlib.sha256(APK.read_bytes()).hexdigest() == APK_SHA
    copies = []; source_bodies = {}
    with zipfile.ZipFile(APK) as archive:
        members = archive.infolist()
        apk_matches = [{'path': x.filename, 'bytes': x.file_size, 'crc32': x.CRC}
                       for x in members if match_name(x.filename)]
        apk_same_size = [{'path': x.filename, 'bytes': x.file_size, 'crc32': x.CRC}
                         for x in members if x.file_size == len(source)]
        for item in apk_matches:
            copies.append(('APK/' + item['path'], archive.read(item['path'])))
        java = dex_sources(archive)
        for row in java['copyCandidates'] + java['pathProducerMethods']:
            source_bodies[row['sourceFile']] = row.pop('source')
    entries = index(DEFAULT_SOURCE)
    gbmp_matches = [x for x in entries if match_name(x['path'])]
    gbmp_same_size = [x for x in entries if x['size'] == len(source)]
    for item in gbmp_matches:
        copies.append((item['pack'] + '/' + item['path'], read_entry(item, DEFAULT_SOURCE)))
    candidate_results = []
    if copies:
        from analyze_native_resources import NativeImage
        probe = InitialFeedProbe(NativeImage(SO.read_bytes()))
        for name, data in copies:
            status, output, _ = probe.decode(data)
            candidate_results.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                                      'originalEnvelopeReturn': status, 'outputBytes': len(output),
                                      'privateOutputOmitted': True})
    return {'format': 'oc2-initialfeed-origin-v1', 'projectLooseFile': project,
        'initialPublicExportCopy': original_export,
        'apk': {'path': str(APK), 'sha256': APK_SHA, 'members': len(members), 'namedMatches': apk_matches,
                'sameUnpackedSizeMembers': apk_same_size, 'allPayloadRescanned': False},
        'gbmp': {'records': len(entries), 'packs': len(set(x['pack'] for x in entries)),
                 'namedOrCanonicalMatches': gbmp_matches, 'sameUnpackedSizeRecords': gbmp_same_size,
                 'allPayloadRescanned': False},
        'java': java, 'newNamedCopyOriginalEnvelopeControls': candidate_results,
        'movedIntoProjectChangedBytesEvidence': False,
        'actualLogicalNativeStreamComparedToDisk': False,
        'actualSourceProducerOrGenerationEstablished': False,
        'limits': ['No same-name or same-size member in the inspected original indexes is not proof against another encoded/nested representation.',
                   'Generic Java copy consumers are not attributed to InitialFeed without an original matching input.',
                   'Equal exported copies do not establish original Android inner stream selection or logical length.',
                   'No whole Downloads directory inventory, payload rescan, codec/key trials or external requests.'],
        'networkOrSaveOrGameRuntimeChanged': False}, source_bodies


if __name__ == '__main__':
    RAW.mkdir(parents=True, exist_ok=True); target = RAW / 'origin-v2.json'
    if target.exists():
        raise ValueError('Preserve the original origin checkpoint')
    result, bodies = run()
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for name, body in bodies.items():
        candidate = RAW / name
        if candidate.exists() and candidate.read_text() != body:
            raise ValueError('Do not overwrite a differing original source dump')
        candidate.write_text(body)
    print(json.dumps({'independentPublicCopy': result['initialPublicExportCopy'].get('sameBytesAsProject', False),
                      'apkNamedMatches': len(result['apk']['namedMatches']),
                      'gbmpNamedMatches': len(result['gbmp']['namedOrCanonicalMatches']),
                      'directJavaProducerFound': False,
                      'genericJavaConsumers': len(result['java']['copyCandidates']),
                      'pathProducerMethods': len(result['java']['pathProducerMethods'])}))
