"""Extract pictures from Actions 'RU3' .sty resource files to PNG (stdlib only).

usage: sty_extract.py OUTDIR file.sty [file.sty ...]
"""
import collections
import os
import struct
import sys
import zlib


def png(path, w, h, rows):
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\0' + r for r in rows)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def rgb565(v):
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))


def sections(b):
    out = []
    for o in range(0x10, 0x400, 0x10):
        off, cnt, typ = struct.unpack_from('<IHB', b, o)
        if off == 0:
            break
        out.append((chr(typ), off, cnt, b[o:o + 16].hex()))
    return out


def main(outdir, files):
    stats = collections.Counter()
    for path in files:
        b = open(path, 'rb').read()
        name = os.path.splitext(os.path.basename(path))[0]
        secs = sections(b)
        print(f'{name}: magic={b[:4]!r} sections=' + ', '.join(f'{t}@0x{o:x}x{c}' for t, o, c, _ in secs))
        d = os.path.join(outdir, name)
        os.makedirs(d, exist_ok=True)
        for t, off, cnt, _ in secs:
            if t != 'P':
                continue
            for i in range(cnt):
                po, sz, ty, w, h = struct.unpack_from('<IIHHH', b, off + i * 16)
                stats[(ty, 'ok' if sz == w * h * 2 else f'sz={sz} wh2={w*h*2}')] += 1
                if ty != 2 or sz != w * h * 2 or w == 0 or h == 0:
                    continue
                px = struct.unpack_from(f'<{w*h}H', b, po)
                rows = [b''.join(rgb565(v) for v in px[y * w:(y + 1) * w]) for y in range(h)]
                png(os.path.join(d, f'{i:03d}_{w}x{h}.png'), w, h, rows)
    print('picture type/size stats:', dict(stats))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
