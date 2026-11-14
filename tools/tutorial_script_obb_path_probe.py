"""One original AndroidUtils.RetrieveObbPath method, no Android execution."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-obb-path-20261115'
APK = Path('/Users/kevin/Downloads/com.gameloft.android.anmp.glofto2hm.apk')
APK_SHA = '4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe'
DEX_SHA = '088acd2c5cd39bb7da0a193a4cada1d6a10bdf9deaba2c70b27280174a5fd2e3'
CLASS = 'Lcom/gameloft/android/ANMP/GloftO2HM/PackageUtils/AndroidUtils;'


def run():
    from loguru import logger
    logger.remove()
    from androguard.core.dex import DEX
    assert hashlib.sha256(APK.read_bytes()).hexdigest() == APK_SHA
    with zipfile.ZipFile(APK) as archive:
        source = archive.read('classes.dex')
    assert hashlib.sha256(source).hexdigest() == DEX_SHA
    cls = DEX(source).get_class(CLASS)
    methods = [m for m in cls.get_methods()
               if m.get_name() == 'RetrieveObbPath' and m.get_descriptor() == '()Ljava/lang/String;']
    assert len(methods) == 1
    method = methods[0]
    instructions = [(offset, instruction.get_name(), instruction.get_output())
                    for offset, instruction in method.get_instructions_idx()]
    assert instructions == [(0, 'const-string', 'v0, "NA"'), (4, 'return-object', 'v0')]
    bytecode = method.get_code().get_bc().get_raw()
    assert len(bytecode) == 6
    text = '## ' + CLASS + '->RetrieveObbPath()Ljava/lang/String;\n'
    text += '\n'.join(f'{at:04x} {kind} {args}' for at, kind, args in instructions) + '\n'
    result = {'format': 'oc2-original-obb-path-method-v1', 'apkPath': str(APK),
        'apkSHA256': APK_SHA, 'dex': 'classes.dex', 'dexSHA256': DEX_SHA,
        'method': CLASS + '->RetrieveObbPath()Ljava/lang/String;', 'completeMethod': True,
        'bytecodeBytes': len(bytecode), 'bytecodeSHA256': hashlib.sha256(bytecode).hexdigest(),
        'instructions': [{'offset': offset, 'mnemonic': name, 'operands': operands}
                         for offset, name, operands in instructions],
        'returnedLiteral': 'NA', 'directMethodCalls': [], 'directGetterToFollow': None,
        'getObbDirCalled': False, 'contextOrPreferenceRead': False,
        'androidVmOrNativeCallerExecuted': False, 'actualSessionInvocationObserved': False,
        'actualFilesystemDirectoryOrObbExistenceEstablished': False,
        'wholeDexCandidateScanRepeated': False, 'otherOriginalSourceBodiesRetested': False,
        'networkOrSaveOrServiceChanged': False,
        'nativeLinkOwnedByParent': '309a8c -> 2526fb8 -> 2f8728; not re-executed in this method-only batch'}
    return result, text


if __name__ == '__main__':
    RAW.mkdir(parents=True, exist_ok=True); target = RAW / 'obb-path-v1.json'
    if target.exists():
        raise ValueError('Preserve the previous method checkpoint')
    result, text = run()
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (RAW / 'RetrieveObbPath.dalvik.txt').write_text(text)
    print(json.dumps({'completeOriginalInstructions': 2, 'returnedLiteral': 'NA',
                      'getObbDirOrPreferencesCalled': False, 'androidExecuted': False}))
