"""One bounded, read-only original name draw; no save or network access."""
import json
import sys
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from native_font_draw import FontDrawCPU, full_font_from_woff


def main():
    config = Path(sys.argv[1]).resolve(); root = Path(__file__).resolve().parents[1]
    if not config.is_relative_to(root/'analysis/raw'):
        raise ValueError('Font input configuration must be in private runtime')
    cfg = json.loads(config.read_text())
    if cfg['nativeSHA256'] != NATIVE_SHA256:
        raise ValueError('Different original library')
    request = json.loads(sys.stdin.readline(4096))
    font = config.parent.parent/'game-data/converted/ui/chineseDisplay.woff'
    image = NativeImage(Path(cfg['library']).read_bytes())
    engine = FontDrawCPU(image, full_font_from_woff(font.read_bytes()))
    print(json.dumps(engine.text(request['name']), separators=(',', ':')))


if __name__ == '__main__':
    main()
