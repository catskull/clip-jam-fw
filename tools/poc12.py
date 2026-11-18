"""poc12: poc10 + live "Raiders: On/Off" Customize label, without poc11's jalx hook,
plus Raiders visible by default after a settings reset.

    poc12.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR BANK_BIN BANK2_BIN RES_BIN TOGGLE_BIN

TOGGLE_BIN (MIPS32, at setting.ap bank 0x4039fe00 + 0x600 = 0x403a0400):
  0x403a0400 raiders_toggle   Customize row 6 handler (flips bit 0x40, refreshes label)
  0x403a0440 customize_entry  wraps the stock Customize entry handler 0x4039fe01 and then
                              stores row 6's label at menu+30
Changes on top of poc10:
  setting.mcg  Customize node entry handler 0x4039fe01 -> 0x403a0440 (both menu trees)
  setting.ap   menu library dynamic-label limit rows<6 -> rows<7 (0x4879fa16)
  setting.sty  strings 132/133 -> 'Raiders: Off' / 'Raiders: On'
  *.ap         shared default-settings routine (bank 0x40ddfe00): Customize default
               0x3f -> 0x7f, so Raiders is on after a settings reset / firmware update
"""
import os
import struct
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
src, dst, bank, bank2, res, toggle = sys.argv[1:7]
subprocess.run([sys.executable, '-I', os.path.join(here, 'poc10.py'), src, dst, bank, bank2, res, toggle],
               check=True, stdout=subprocess.DEVNULL)


def path(n):
    return os.path.join(dst, n)


# setting.mcg: point Customize's entry handler at the wrapper
g = bytearray(open(path('setting.mcg'), 'rb').read())
old, new = struct.pack('<I', 0x4039fe01), struct.pack('<I', 0x403a0440)
hits = [i for i in range(0, len(g) - 3, 2) if g[i:i + 4] == old]
for i in hits:
    nid, sid = struct.unpack_from('<HH', g, i - 8)
    # tree records (node, str=7, 0, 0, fn) or other tables (..., u32 node 7, fn)
    assert sid == 7 or struct.unpack_from('<I', g, i - 4)[0] == 7, (hex(i), nid, sid)
    g[i:i + 4] = new
assert len(hits) >= 1
open(path('setting.mcg'), 'wb').write(g)

# setting.ap: library row limit 6 -> 7; check the stock entry handler is untouched
a = bytearray(open(path('setting.ap'), 'rb').read())
banks = []
for t in (0x800, 0x1000, 0x1800, 0x2000):
    for i in range(0x800 // 12):
        fo, la, sz = struct.unpack_from('<III', a, t + 12 * i)
        if la and fo and sz:
            banks.append((la, fo, sz))


def f(va):
    for la, fo, sz in banks:
        if la <= va < la + sz:
            return fo + va - la
    raise KeyError(hex(va))


o = f(0x4879fa16)
assert a[o:o + 2] == b'\x06\x52' and (a[o - 1] >> 3) != 0b11110
a[o] = 7
o = f(0x4039fe0c)
assert a[o:o + 6] == bytes.fromhex('016a5ec34099')      # stock: li v0,1; sb v0,30(v1); lw v0,0(s1)
code = open(toggle, 'rb').read()
assert a[0xae00:0xae00 + len(code)] == code             # written by poc10
open(path('setting.ap'), 'wb').write(a)

# setting.sty strings
z = bytearray(open(path('setting.sty'), 'rb').read())
for s_ in range(0x10, 0x100, 16):
    off_, cnt_, typ_ = struct.unpack_from('<IHB', z, s_)
    if typ_ == ord('S'):
        lt = off_
        break
L0 = struct.unpack_from('<I', z, lt)[0]
so, sl = struct.unpack_from('<II', z, L0 + 133 * 8)
assert z[so:so + sl] == 'slide_repeat_on\0'.encode('utf-16le')
for idx, text in ((132, 'Raiders: Off'), (133, 'Raiders: On')):
    b = (text + '\0').encode('utf-16le')
    z += b'\0' * (-len(z) % 4)
    toff = len(z)
    z += b
    struct.pack_into('<II', z, L0 + idx * 8, toff, len(b))
open(path('setting.sty'), 'wb').write(z)

# Customize default 0x3f -> 0x7f in every app's copy of the default-settings routine
pat = bytes.fromhex('3f6a58c36499016a59c3')  # li v0,0x3f; sb v0,24(v1); lw v1,..; li v0,1; sb v0,25(v1)
patched = []
for n in sorted(os.listdir(dst)):
    if not n.endswith('.ap'):
        continue
    b = bytearray(open(path(n), 'rb').read())
    idx = [i for i in range(len(b) - len(pat) + 1) if b[i:i + len(pat)] == pat]
    for i in idx:
        b[i] = 0x7f
    if idx:
        open(path(n), 'wb').write(b)
        patched.append(f'{n}x{len(idx)}')
print('poc12 built; mcg hits', len(hits), '; default 0x7f in', ', '.join(patched))
