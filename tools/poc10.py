"""poc10: Books restored + 8th main-menu item "Raiders" (app 2 = video.ap = Sky Raiders),
with a Customize row for it.

    poc10.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR BANK_BIN BANK2_BIN RES_BIN TOGGLE_BIN

Main menu internals (mainmenu.ap, all position-indexed, Settings assumed last):
  * stored list (settings storage 0x400, marker 0x55aa) is built once from config key 1
  * per-position style tables A(frame) B(icon) C(label) at bank 0x4011fe00 +0x628/0x648/0x638
  * cursor movement skips position p unless Customize bit p is set; position 6 was the
    hard-coded always-visible Settings slot (cmpi v0,6 at 0x4015febc / 0x4015ff6e)
Changes:
  config.bin    menu list [0,8,1,5,11,9,10] -> [0,8,1,5,11,9,2,10] (Raiders at 6, Settings at 7)
  mainmenu.ap   tables: pos6 = new styles (0x1010,0x1011,0x2008), pos7 = Settings styles;
                always-visible position 6 -> 7; stored-list marker 0x55aa -> 0x55ac (rebuild once)
  mainmenu.sty  + picture 17 (48x48 icon), + picbox 0x1010 (frame) / 0x1011 (icon),
                + textbox 0x2008 (string 98, English 'Video' -> 'Raiders'), groups reordered
                (tables relocated to the end of the file; header pointers updated)
  setting.mcg   Customize submenu: 6 -> 7 rows (+ "Raiders on/off" -> handler 0x403a0400)
  setting.ap    TOGGLE_BIN (MIPS32) at bank 0x4039fe00 + 0x600 (file 0xae00): flips bit 0x40
  setting.sty   English string 132 ('slide_repeat_off', unused) -> 'Raiders on/off'
  video.ap      Sky Raiders (as poc8/poc9)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
src, dst, bank, bank2, res, toggle = sys.argv[1:7]
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)


def rd(n):
    return bytearray(open(os.path.join(dst, n), 'rb').read())


def wr(n, b):
    open(os.path.join(dst, n), 'wb').write(b)


def align4(b):
    b += b'\0' * (-len(b) % 4)
    return len(b)


# ------------------------------------------------------------------ video.ap
with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as tmp:
    t = os.path.join(tmp, 'fw')
    subprocess.run([sys.executable, '-I', os.path.join(here, 'poc8.py'), src, t, bank, bank2, res],
                   check=True, stdout=subprocess.DEVNULL)
    shutil.copy(os.path.join(t, 'video.ap'), os.path.join(dst, 'video.ap'))

# ------------------------------------------------------------------ config.bin
c = rd('config.bin')
tab = [(o,) + struct.unpack_from('<II', c, o) for o in range(0x10, 0x208, 8)]
assert tab[1][1:] == (0x21e, 18)
assert list(struct.unpack_from('<9H', c, 0x21e)) == [0, 7, 0, 8, 1, 5, 11, 9, 10]
end = max(off + ln for _, off, ln in tab)
assert end + 2 <= len(c) and not any(c[end:end + 2])
rest = bytes(c[0x21e + 18:end])
c[0x21e:0x21e + 20] = struct.pack('<10H', 0, 8, 0, 8, 1, 5, 11, 9, 2, 10)
c[0x21e + 20:end + 2] = rest
for to, off, ln in tab:
    if off > 0x21e:
        struct.pack_into('<I', c, to, off + 2)
struct.pack_into('<II', c, tab[1][0], 0x21e, 20)
orig = open(os.path.join(src, 'config.bin'), 'rb').read()
for i, (to, off, ln) in enumerate(tab):
    if i != 1:
        noff = struct.unpack_from('<I', c, to)[0]
        assert c[noff:noff + ln] == orig[off:off + ln], i
wr('config.bin', c)
s = open(os.path.join(dst, 'config.txt'), 'rb').read()
s2 = s.replace(b'MAINMENU_AP_ID_ARRAY = 0[0, 8, 1, 5, 11, 9, 10];',
               b'MAINMENU_AP_ID_ARRAY = 0[0, 8, 1, 5, 11, 9, 2, 10];')
assert s2 != s
wr('config.txt', s2)

# ------------------------------------------------------------------ mainmenu.ap
m = rd('mainmenu.ap')
A, C, B = 0x5e28, 0x5e38, 0x5e48          # file offsets of the three position tables
assert list(struct.unpack_from('<8H', m, A)) == [0x1001, 0x1003, 0x1005, 0x1008, 0x100a, 0x100c, 0x100e, 0]
assert list(struct.unpack_from('<8H', m, C)) == [0x2000, 0x2001, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0]
assert list(struct.unpack_from('<8H', m, B)) == [0x1002, 0x1004, 0x1006, 0x1009, 0x100b, 0x100d, 0x100f, 0]
struct.pack_into('<2H', m, A + 12, 0x1010, 0x100e)
struct.pack_into('<2H', m, C + 12, 0x2008, 0x2007)
struct.pack_into('<2H', m, B + 12, 0x1011, 0x100f)
for off in (0x60bc, 0x616e):                 # cmpi v0,6 -> cmpi v0,7 (not EXTENDed)
    assert m[off:off + 2] == b'\x06\x72' and (m[off - 1] >> 3) != 0b11110, hex(off)
    m[off] = 7
assert m[0x39d2:0x39d6] == bytes.fromhex('aaf50a72') and m[0x39de:0x39e2] == bytes.fromhex('aaf50a6a')
m[0x39d4] = m[0x39e0] = 0x0c                 # stored-list marker 0x55aa -> 0x55ac
wr('mainmenu.ap', m)

# ------------------------------------------------------------------ mainmenu.sty


def invader_icon():
    """Original 8x6 alien (Sky Raiders type B, frame 0) scaled x5, centred in 48x48."""
    cols = [0x0e, 0x1b, 0x3e, 0x1b, 0x1b, 0x3e, 0x1b, 0x0e]
    px = bytearray()
    for y in range(48):
        for x in range(48):
            cx, cy = (x - 4) // 5, (y - 9) // 5
            on = 0 <= cx < 8 and 0 <= cy < 6 and 4 <= x < 44 and 9 <= y < 39 and cols[cx] >> cy & 1
            px += struct.pack('<H', 0xffff if on else 0)
    return bytes(px)


y = rd('mainmenu.sty')
assert y[0x10:0x18] == bytes.fromhex('0004000011005010')        # P: off 0x400, 17 entries
pics = [bytes(y[0x400 + 16 * i:0x400 + 16 * i + 16]) for i in range(17)]
assert struct.unpack_from('<IIHHH', pics[2])[1:] == (4608, 2, 48, 48)
# new picture data
poff = align4(y)
y += invader_icon()
newpic = bytearray(pics[2])
struct.pack_into('<I', newpic, 0, poff)
pics.append(bytes(newpic))
# relocated picture index
ioff = align4(y)
y += b''.join(pics)
struct.pack_into('<IH', y, 0x10, ioff, 18)
# English string 98 'Video' -> 'Raiders'
LANG0 = 0x21cb0
so, sl = struct.unpack_from('<II', y, LANG0 + 98 * 8)
assert y[so:so + sl] == 'Video\0'.encode('utf-16le')
txt = 'Raiders\0'.encode('utf-16le')
toff = align4(y)
y += txt
struct.pack_into('<II', y, LANG0 + 98 * 8, toff, len(txt))
# styles
S = 0x51a00
assert y[S:S + 4] == b'sty\0' and struct.unpack_from('<I', y, S + 8)[0] == 0x51a10
(go, gn), (po, pn), (xo, xn) = [struct.unpack_from('<II', y, 0x51a10 + 8 * i) for i in range(3)]
assert (gn, pn, xn) == (7, 16, 8)
groups = [bytearray(y[go + 20 * i:go + 20 * i + 20]) for i in range(gn)]
pbox = [bytes(y[po + 32 * i:po + 32 * i + 32]) for i in range(pn)]
tbox = [bytes(y[xo + 20 * i:xo + 20 * i + 20]) for i in range(xn)]
assert struct.unpack_from('<2H', pbox[0xe])[0] == 1 and struct.unpack_from('<H', pbox[0xf])[0] == 8
p10 = bytes(pbox[0xe])                                  # frame (pic 1 at 0,0)
p11 = bytearray(pbox[0xf])                              # icon: pic 8 -> pic 17
assert p11[0:2] == b'\x08\x00' and p11[8:10] == b'\x08\x00'
p11[0:2] = p11[8:10] = struct.pack('<H', 17)
t8 = bytearray(tbox[7])
assert struct.unpack_from('<H', t8)[0] == 58           # 'Settings' label -> string 98
struct.pack_into('<H', t8, 0, 98)
# style list for the new group: frame, label, icon (same shape as group 6)
loff = align4(y)
y += struct.pack('<6H', 1, 0x1010, 1, 0x2008, 1, 0x1011)
g_new = bytearray(groups[6])
struct.pack_into('<HI', g_new, 12, 3, loff)   # count @12, list ptr @14 (unaligned)
new_groups = groups[:6] + [g_new, groups[6]]           # position 6 = Raiders, 7 = Settings
off_g = align4(y)
y += b''.join(bytes(g) for g in new_groups)
off_p = align4(y)
y += b''.join(pbox) + p10 + bytes(p11)
off_x = align4(y)
y += b''.join(tbox) + bytes(t8)
struct.pack_into('<IIIIII', y, 0x51a10, off_g, 8, off_p, 18, off_x, 9)
wr('mainmenu.sty', y)

# ------------------------------------------------------------------ setting.mcg
g = rd('setting.mcg')
size0 = len(g)
cur = (len(bytes(g).rstrip(b'\0')) + 3) & ~3           # write into the zero padding at the end
for hdr in (0x60, 0xf0):
    a, idx, sid, cnt, off = struct.unpack_from('<HHHHI', g, hdr)
    assert (idx, sid, cnt) == (4, 7, 6), (hex(hdr), idx, sid, cnt)
    rows = bytes(g[off:off + 20 * 6])
    assert struct.unpack_from('<H', rows, 2)[0] == 0x803b        # 'Music: On'
    new = struct.pack('<HHHHI8x', 0xffff, 132, 0, 0, 0x403a0400)
    blob = rows + new
    assert not any(g[cur:cur + len(blob)]) and cur + len(blob) <= size0
    g[cur:cur + len(blob)] = blob
    struct.pack_into('<HI', g, hdr + 6, 7, cur)
    cur += len(blob)
assert len(g) == size0
wr('setting.mcg', g)

# ------------------------------------------------------------------ setting.ap
a = rd('setting.ap')
code = open(toggle, 'rb').read()
ents = [struct.unpack_from('<III', a, 0x800 + 12 * i) for i in range(32)]
assert (0xa800, 0x4039fe00, 0x800) in ents
assert not any(a[0xae00:0xb000]) and len(code) <= 0x200
a[0xae00:0xae00 + len(code)] = code
wr('setting.ap', a)

# ------------------------------------------------------------------ setting.sty
z = rd('setting.sty')
for s_ in range(0x10, 0x100, 16):
    off_, cnt_, typ_ = struct.unpack_from('<IHB', z, s_)
    if typ_ == ord('S'):
        lt = off_
        break
L0 = struct.unpack_from('<I', z, lt)[0]
so, sl = struct.unpack_from('<II', z, L0 + 132 * 8)
assert z[so:so + sl] == 'slide_repeat_off\0'.encode('utf-16le'), z[so:so + sl]
txt = 'Raiders on/off\0'.encode('utf-16le')
toff = align4(z)
z += txt
struct.pack_into('<II', z, L0 + 132 * 8, toff, len(txt))
wr('setting.sty', z)
print('poc10 built')
