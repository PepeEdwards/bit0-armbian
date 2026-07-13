#!/usr/bin/env python3
"""Convert PNG icons/sprites to the Bit0 `.565` blob the launcher blits
at runtime (audit 6.3 color-asset path).

The device is stdlib-only with 128 MB RAM, so it never decodes PNG or
scales images: this runs at build time (or on your dev machine) and
emits a tiny raw blob the launcher reads with a plain file read.

Pure stdlib (zlib) - no Pillow needed. Handles 8-bit RGB and RGBA,
non-interlaced PNG, which is what every pixel-art tool exports by
default. That keeps PNG the editable source format while the committed
tree carries no generated blobs (the build hook regenerates them).

Usage:
  png-to-565.py in.png out.565 [SIZE]      # one file, square SIZE px
  png-to-565.py --dir DIR [SIZE]           # every *.png in DIR -> *.565

.565 layout: b'B565', u16 w, u16 h (LE), then w*h RGB565 LE pixels,
then a 1-bpp opacity mask (row-major, bit7 first; 1 = opaque).
"""

import os
import struct
import sys
import zlib

MAGIC = b'B565'
DEFAULT_SIZE = 48


def _unfilter(raw, w, h, bpp):
    """Reverse PNG scanline filters -> flat RGBA/RGB bytes (h*w*bpp)."""
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:      # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:    # Average
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:    # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError(f'unsupported filter {ft}')
        out += line
        prev = line
    return out


def decode_png(data):
    """(w, h, bpp, pixels) for an 8-bit RGB/RGBA non-interlaced PNG."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    pos, idat = 8, bytearray()
    w = h = bpp = 0
    while pos < len(data):
        (ln,) = struct.unpack('>I', data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB',
                                                                 body)
            if depth != 8 or ctype not in (2, 6) or interlace:
                raise ValueError('need 8-bit RGB/RGBA, non-interlaced')
            bpp = 4 if ctype == 6 else 3
        elif typ == b'IDAT':
            idat += body
        elif typ == b'IEND':
            break
    return w, h, bpp, _unfilter(zlib.decompress(bytes(idat)), w, h, bpp)


def to_565(png_bytes, size):
    """PNG -> (out_w, out_h, rgb565 bytes, alpha-mask bytes) box-averaged
    to fit `size` (keeps aspect; downscale only)."""
    w, h, bpp, px = decode_png(png_bytes)
    scale = max(1, (max(w, h) + size - 1) // size)  # integer box factor
    ow, oh = max(1, w // scale), max(1, h // scale)
    rgb = bytearray()
    mask = bytearray((ow * oh + 7) // 8)
    for oy in range(oh):
        for ox in range(ow):
            r = g = b = a = n = 0
            for sy in range(oy * scale, min((oy + 1) * scale, h)):
                base = (sy * w + ox * scale) * bpp
                for sx in range(min(scale, w - ox * scale)):
                    o = base + sx * bpp
                    r += px[o]
                    g += px[o + 1]
                    b += px[o + 2]
                    a += px[o + 3] if bpp == 4 else 255
                    n += 1
            r, g, b, a = r // n, g // n, b // n, a // n
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            rgb += struct.pack('<H', v)
            if a >= 128:
                idx = oy * ow + ox
                mask[idx >> 3] |= 0x80 >> (idx & 7)
    return ow, oh, bytes(rgb), bytes(mask)


def convert(src, dst, size):
    ow, oh, rgb, mask = to_565(open(src, 'rb').read(), size)
    with open(dst, 'wb') as f:
        f.write(MAGIC + struct.pack('<HH', ow, oh) + rgb + mask)
    print(f'{src} -> {dst} ({ow}x{oh})')


def main(argv):
    if len(argv) >= 2 and argv[0] == '--dir':
        d = argv[1]
        size = int(argv[2]) if len(argv) > 2 else DEFAULT_SIZE
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.png'):
                convert(os.path.join(d, fn),
                        os.path.join(d, fn[:-4] + '.565'), size)
    elif len(argv) >= 2:
        size = int(argv[2]) if len(argv) > 2 else DEFAULT_SIZE
        convert(argv[0], argv[1], size)
    else:
        print(__doc__.strip().splitlines()[-6], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
