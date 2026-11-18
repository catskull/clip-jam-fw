"""poc5: turn the main menu's Books slot into a "Video" entry that opens video.ap.

    poc5.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR

1. manager.ap   : app-name slot 1 (12 bytes) 'audible.ap' -> 'video.ap'
2. mainmenu.sty : picture 2 (48x48 book icon) -> apple icon (pure 0xFFFF on 0x0000)
3. mainmenu.sty : English string 1 ('Books') -> 'Video' (new string appended at
                  end of file, table entry repointed; nothing else moves)
"""
import math
import os
import shutil
import struct
import sys

src, dst = sys.argv[1:3]
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)

# 1. manager.ap app-name table
p = os.path.join(dst, 'manager.ap')
m = bytearray(open(p, 'rb').read())
assert m[0x4c34:0x4c40] == b'music.ap\0\0\0\0'
assert m[0x4c40:0x4c4c] == b'audible.ap\0\0'
assert m[0x4c4c:0x4c58] == b'video.ap\0\0\0\0'
m[0x4c40:0x4c4c] = b'video.ap\0\0\0\0'
open(p, 'wb').write(m)

# 2 + 3. mainmenu.sty
p = os.path.join(dst, 'mainmenu.sty')
s = bytearray(open(p, 'rb').read())
off, size, typ, w, h = struct.unpack_from('<IIHHH', s, 0x400 + 2 * 16)
assert (size, typ, w, h) == (4608, 2, 48, 48)


def apple(x, y):
    """Original apple silhouette in a 48x48 cell."""
    fx, fy = x + 0.5, y + 0.5
    # body: two overlapping circles plus a filled lower half, slight top notch
    body = ((fx - 18) ** 2 + (fy - 28) ** 2 <= 13 ** 2 or
            (fx - 30) ** 2 + (fy - 28) ** 2 <= 13 ** 2 or
            (fx - 24) ** 2 / 15 ** 2 + (fy - 33) ** 2 / 12 ** 2 <= 1)
    notch = (fx - 24) ** 2 + (fy - 13) ** 2 <= 4.5 ** 2
    bottom_notch = (fx - 24) ** 2 + (fy - 46.5) ** 2 <= 3 ** 2
    stem = 23 <= fx <= 26 and 6 <= fy <= 16 and abs((fx - 24.5) - (16 - fy) * 0.15) <= 1.6
    # leaf: ellipse rotated ~ -30 degrees, to the right of the stem
    a = math.radians(-30)
    lx, ly = fx - 32, fy - 9
    rx, ry = lx * math.cos(a) + ly * math.sin(a), -lx * math.sin(a) + ly * math.cos(a)
    leaf = rx ** 2 / 6.5 ** 2 + ry ** 2 / 3 ** 2 <= 1
    return ((body and not notch and not bottom_notch) or stem or leaf)


pix = b''.join(struct.pack('<H', 0xffff if apple(x, y) else 0) for y in range(48) for x in range(48))
s[off:off + size] = pix

LANG0 = 0x21cb0
so, sl = struct.unpack_from('<II', s, LANG0 + 1 * 8)
assert s[so:so + sl] == 'Books\0'.encode('utf-16le')
new = 'Video\0'.encode('utf-16le')
s += b'\0' * (-len(s) % 4)
noff = len(s)
s += new
struct.pack_into('<II', s, LANG0 + 1 * 8, noff, len(new))
open(p, 'wb').write(s)

# preview of the icon
for y in range(0, 48, 2):
    print(''.join('#' if apple(x, y) or apple(x, y + 1) else '.' for x in range(48)))
print('Books ->', bytes(s[noff:noff + len(new)]).decode('utf-16le'), 'at', hex(noff))
