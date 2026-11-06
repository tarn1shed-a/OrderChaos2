"""Decode selected game texture containers into browser-readable PNGs."""
import argparse
import io
import struct
import zipfile
from pathlib import Path
from PIL import Image
import texture2ddecoder

def decode(data):
    if data.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            if 'rgb.pvr' not in names:
                raise ValueError(f'Unsupported ZIP texture members: {names}')
            rgb = decode(z.read('rgb.pvr'))
            if 'alpha.pvr' in names:
                alpha = decode(z.read('alpha.pvr'))
                if alpha.size != rgb.size:
                    raise ValueError('Split alpha size mismatch')
                rgb.putalpha(alpha.getchannel('R'))
            return rgb
    if len(data) >= 52 and data[44:48] == b'PVR!':
        hs, height, width, mips, flags, length, bpp, r, g, b, a, magic, surfaces = struct.unpack_from('<13I', data)
        if hs != 52 or surfaces != 1 or not (0 < width <= 8192 and 0 < height <= 8192):
            raise ValueError('Unsupported PVR v2 layout')
        encoding = flags & 0xff
        if encoding == 0x36:
            blocks = ((width + 3) // 4) * ((height + 3) // 4) * 8
        elif encoding in (0x18, 0x19):
            two = encoding == 0x18
            if bpp != (2 if two else 4):
                raise ValueError('PVRTC bit depth disagrees with pixel format')
            blocks = max(width, 16 if two else 8) * max(height, 8) * bpp // 8
        else:
            raise ValueError(f'Unsupported PVR encoding {encoding:#x}')
        if len(data) < hs + blocks:
            raise ValueError('Truncated ETC1 data')
        raw = texture2ddecoder.decode_etc1(data[hs:hs+blocks], width, height) if encoding == 0x36 else texture2ddecoder.decode_pvrtc(data[hs:hs+blocks], width, height, encoding == 0x18)
        # Decoder emits BGRA bytes (matches its reference tests).
        return Image.frombytes('RGBA', (width, height), raw, 'raw', 'BGRA')
    return Image.open(io.BytesIO(data)).convert('RGBA')

def convert(source, output):
    image = decode(Path(source).read_bytes())
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return {'width': image.width, 'height': image.height, 'output': str(output)}

if __name__ == '__main__':
    cli = argparse.ArgumentParser(); cli.add_argument('source', type=Path); cli.add_argument('output', type=Path)
    args = cli.parse_args(); print(convert(args.source, args.output))
