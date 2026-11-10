"""Install the original Default postprocess adapter in an ignored preview only."""
import argparse
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def connect(runtime):
    runtime=Path(runtime).resolve()
    if not runtime.is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Only an ignored isolated preview may be modified')
    public=runtime/'prototype/public'
    js=(public/'explore-source.js').read_text()
    old='hdrRenderer=createRecoveredHDR(THREE,renderer,renderProfile,await texture(renderProfile.lut.url));'
    if js.count(old)!=1:raise ValueError('Archived HDR entry differs; refusing a guessed edit')
    js="import {createOriginalDefaultPostprocess} from './original-default-postprocess-v1.js?audit=3';\n"+js
    js=js.replace(old,"if(!assets.defaultPostprocess)throw new Error('原 APK 默认后处理资料缺失');\n    hdrRenderer=await createOriginalDefaultPostprocess(THREE,renderer,await json(assets.defaultPostprocess));")
    js=js.replace('hdrRenderer.render(scene,camera,zone);',
                  'hdrRenderer.render(scene,camera,zone);canvas.dataset.sourcePostprocess=JSON.stringify(hdrRenderer.state());')
    js=js.replace('document.title=`原文件配置预览 · ${sourceProfile}（非雷电实测）`;',
                  "document.title='原 APK 默认配置 · 材质与光照核对';")
    (public/'explore-default.js').write_text(js)
    shutil.copyfile(ROOT/'tools/preview/original-default-postprocess.js',public/'original-default-postprocess-v1.js')
    html=(public/'explore.html').read_text().replace('src="/explore.js"','src="/explore-default.js?audit=3"')
    (public/'explore-default.html').write_text(html)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    args=parser.parse_args();connect(args.runtime)
    print('Original Default shader adapter installed in isolated preview.')
