"""Convert a video into the Clip Jam frame player's data file (replaces dumy4m.bin).

    frames.py INPUT OUT.bin [--fps N] [--threshold T] [--invert] [--preview DIR]

Layout (exactly SIZE bytes, padded with 0xFF like the original placeholder):
  0x000  b"FRMS", u32 nframes, u32 frame_us, u32 0, ... (512 bytes)
  0x200  nframes x 1024 bytes, SSD1306 page order: page p (rows 8p..8p+7),
         column x -> one byte, bit k = pixel (x, 8p+k), 1 = lit.
The fps defaults to the highest rate whose frames fit (capped at 30).
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import zlib

SIZE = 4280320           # size of dumy4m.bin in FWIMAGE.FW (must not change)
HDR = 512
W, H = 128, 64
FRAME = W * H // 8
MAXFR = (SIZE - HDR) // FRAME


def duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)['format']['duration'])


def pack(gray, th, invert):
    out = bytearray(FRAME)
    for p in range(8):
        for x in range(W):
            v = 0
            for k in range(8):
                lit = gray[(8 * p + k) * W + x] > th
                if lit != invert:
                    v |= 1 << k
            out[p * W + x] = v
    return bytes(out)


def png(path, gray, th, invert):
    rows = b''.join(b'\0' + bytes(255 if ((gray[y * W + x] > th) != invert) else 0 for x in range(W))
                    for y in range(H))

    def ch(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 0, 0, 0, 0)) +
                           ch(b'IDAT', zlib.compress(rows)) + ch(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('out')
    ap.add_argument('--fps', type=float)
    ap.add_argument('--threshold', type=int, default=128)
    ap.add_argument('--invert', action='store_true')
    ap.add_argument('--preview')
    a = ap.parse_args()

    dur = duration(a.input)
    fps = a.fps or min(30.0, int(MAXFR / dur * 100) / 100)
    # Fit the picture inside 128x64 keeping aspect ratio (4:3 -> 85x64).
    vf = (f'fps={fps},scale={W}:{H}:force_original_aspect_ratio=decrease:flags=area,'
          f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,format=gray')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', a.input, '-vf', vf, '-f', 'rawvideo', '-'],
                         capture_output=True, check=True).stdout
    n = min(len(raw) // (W * H), MAXFR)
    if len(raw) // (W * H) > MAXFR:
        print(f'warning: {len(raw) // (W * H)} frames at {fps} fps, truncated to {MAXFR}', file=sys.stderr)
    body = bytearray()
    for i in range(n):
        g = raw[i * W * H:(i + 1) * W * H]
        body += pack(g, a.threshold, a.invert)
        if a.preview and i % max(1, int(fps * 10)) == 0:
            os.makedirs(a.preview, exist_ok=True)
            png(os.path.join(a.preview, f'{i:05d}.png'), g, a.threshold, a.invert)
    us = round(1_000_000 / fps)
    hdr = b'FRMS' + struct.pack('<III', n, us, 0)
    out = hdr + b'\xff' * (HDR - len(hdr)) + body
    out += b'\xff' * (SIZE - len(out))
    assert len(out) == SIZE
    open(a.out, 'wb').write(out)
    print(f'{n} frames, {fps} fps ({us} us/frame), {n / fps:.1f} s of {dur:.1f} s -> {a.out}')


if __name__ == '__main__':
    main()
