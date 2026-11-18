"""Synthetic test frames for the Clip Jam player: border, bouncing ball, seconds counter.

    frames_test.py OUT.bin [SECONDS] [FPS]
The counter should tick once per real second if timing is right; the 'up' arrow in
the top-left corner checks orientation; the border checks the visible area.
"""
import struct
import sys

SIZE, HDR, W, H = 4280320, 512, 128, 64
FONT = {  # 3x5 digits
    '0': '111101101101111', '1': '010110010010111', '2': '111001111100111',
    '3': '111001111001111', '4': '101101111001001', '5': '111100111001111',
    '6': '111100111101111', '7': '111001001001001', '8': '111101111101111',
    '9': '111101111001111'}

out, secs, fps = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30, int(sys.argv[3]) if len(sys.argv) > 3 else 20
n = secs * fps
body = bytearray()
bx, by, dx, dy = 20.0, 20.0, 1.7, 1.1
for f in range(n):
    px = [[0] * W for _ in range(H)]
    for x in range(W):
        px[0][x] = px[H - 1][x] = 1
    for y in range(H):
        px[y][0] = px[y][W - 1] = 1
    for i in range(7):                       # up arrow, top-left
        px[3 + i][8] = 1
        if i < 3:
            px[3 + i][8 - i] = px[3 + i][8 + i] = 1
    s = str(f // fps)
    for ci, ch in enumerate(s):               # seconds counter, 4x scale, right side
        for r in range(5):
            for c in range(3):
                if FONT[ch][r * 3 + c] == '1':
                    for yy in range(4):
                        for xx in range(4):
                            px[22 + r * 4 + yy][70 + ci * 16 + c * 4 + xx] = 1
    bx += dx
    by += dy
    if not 6 <= bx <= 58:
        dx = -dx
    if not 6 <= by <= 57:
        dy = -dy
    for y in range(H):
        for x in range(W):
            if (x - bx) ** 2 + (y - by) ** 2 <= 25:
                px[y][x] = 1
    fr = bytearray(1024)
    for p in range(8):
        for x in range(W):
            fr[p * W + x] = sum(px[8 * p + k][x] << k for k in range(8))
    body += fr
hdr = b'FRMS' + struct.pack('<III', n, 1_000_000 // fps, 0)
data = hdr + b'\xff' * (HDR - len(hdr)) + body
data += b'\xff' * (SIZE - len(data))
open(out, 'wb').write(data)
print(f'{n} frames at {fps} fps -> {out}')
