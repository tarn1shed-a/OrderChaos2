"""Connect verified manifests to an existing ignored archived viewer copy.

No server or gameplay code is created in the active repository. No assets are
modified in the archived backup. The caller must first export explicit profiles.
"""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def connect(runtime, verified):
    runtime,verified = Path(runtime).resolve(),Path(verified).resolve()
    for path in (runtime,verified):
        if not path.is_relative_to((ROOT/'analysis/raw').resolve()):
            raise ValueError('Only ignored local preview copies may be modified')
    public = runtime/'prototype/public'
    assets = runtime/'game-data/converted'
    if assets.is_symlink():
        # Detach first so writing verified outputs cannot mutate the backup.
        target = assets.resolve()
        assets.unlink()
        shutil.copytree(target,assets)
    shutil.copytree(verified,assets/'verified',dirs_exist_ok=True)
    source = public/'explore.js'
    text = source.read_text()
    before = "assets = await json('/assets/manifest.json');"
    after = """const sourceProfile=new URLSearchParams(location.search).get('sourceProfile');
    if(sourceProfile&&!/^GPU_[A-Za-z0-9_]+$/.test(sourceProfile))throw new Error('无效原配置分支');
    assets = await json(sourceProfile?`/assets/verified/${sourceProfile}/manifest.json`:'/assets/manifest.json');
    if(sourceProfile){
      const evidence=await json(assets.sourceSelection.url);
      if(evidence.profile!==sourceProfile||evidence.actualDeviceObserved!==false||evidence.phase!==0||
        assets.sourceSelection.modelSlot!==evidence.settings.ForceModelLodLevel)throw new Error('原文件选择证据不匹配');
      document.title=`原文件配置预览 · ${sourceProfile}（非雷电实测）`;
      const note=document.getElementById('showcase-notice');
      if(note)note.textContent=`原文件配置预览 · ${sourceProfile} 条件分支 · 未确定雷电实际档位 · 仍使用历史显示适配`;
      canvas.dataset.sourceProfile=sourceProfile;canvas.dataset.sourceActualDevice='false';
      canvas.dataset.sourceModelSlot=String(evidence.settings.ForceModelLodLevel);
      canvas.dataset.sourceOmittedInstances=String(evidence.preview.omitted.length);
    }"""
    if after not in text:
        if text.count(before)!=1:
            raise ValueError('Unexpected archived viewer entry; refusing a guessed patch')
        source.with_suffix('.js.before-source-selection').write_text(text)
        source.write_text(text.replace(before,after))
    lighting = public/'scene-baked-lighting.js'
    text = lighting.read_text()
    old = 'config?.modelSlot!==0'
    if old in text:
        lighting.with_suffix('.js.before-source-selection').write_text(text)
        text = text.replace(old,'![0,1].includes(config?.modelSlot)')
        text = text.replace('mode:0,slot:0','mode:0,slot:config.modelSlot')
        text = text.replace('slot:0,materials:owned.size','slot:lighting.profile.configuration.modelSlot,materials:owned.size')
        lighting.write_text(text)
    # Use distinct module/document URLs as well: an already-open WebView may
    # retain its earlier module graph even after the source files are changed.
    source_text = source.read_text().replace("'./scene-baked-lighting.js'", "'./scene-baked-lighting.js?source-selection=1'")
    (public/'explore-source.js').write_text(source_text)
    html = (public/'explore.html').read_text().replace('src="/explore.js"','src="/explore-source.js"')
    (public/'explore-source.html').write_text(html)
    return {'runtime':str(runtime),'assetsAreDetachedFromBackup':not assets.is_symlink(),
            'profiles':sorted(p.name for p in verified.iterdir()if(p/'manifest.json').exists()),
            'originalSaveUsed':False,'gameplayOrUILayoutChanged':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--verified',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(connect(args.runtime,args.verified),ensure_ascii=False))
