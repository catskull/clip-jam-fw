"""poc11: poc10 + live "Raiders: On/Off" label on the Customize row.

    poc11.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR BANK_BIN BANK2_BIN RES_BIN TOGGLE_BIN

On top of poc10 (all in setting.ap / setting.sty):
  * menu library (setting.ap's copy, bank 0x4879f800): dynamic row labels allowed for
    rows < 7 instead of < 6  (slti v0,6 -> slti v0,7 at 0x4879fa16)
  * Customize entry handler 0x4039fe00: "li v0,1; sb v0,30(v1)" (sets the dynamic-label
    flag) -> "jalx label_hook", which stores row 6's label at menu+30 (non-zero low byte
    keeps the flag set; delay slot is the original next instruction)
  * TOGGLE_BIN at 0x403a0400: raiders_toggle (row handler, also refreshes the label)
    and label_hook at 0x403a0440
  * setting strings 132/133 (unused 'slide_repeat_off/on') -> 'Raiders: Off'/'Raiders: On'
    and the row's static string stays 132
"""
import os
import struct
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
src, dst, bank, bank2, res, toggle = sys.argv[1:7]
subprocess.run([sys.executable, '-I', os.path.join(here, 'poc10.py'), src, dst, bank, bank2, res, toggle],
               check=True, stdout=subprocess.DEVNULL)

HOOK = 0x403a0440
p = os.path.join(dst, 'setting.ap')
a = bytearray(open(p, 'rb').read())
code = open(toggle, 'rb').read()
assert len(code) == 0x60 and code[0x40:0x44] == bytes.fromhex('c29f083c'), code[0x40:0x44].hex()  # lui t0,0x9fc2
a[0xae00:0xae00 + len(code)] = code          # poc10 wrote the first 0x30 bytes; rest was zero

# bank table lookup: virtual address -> file offset
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


# 1. library row limit 6 -> 7
o = f(0x4879fa16)
assert a[o:o + 2] == b'\x06\x52' and (a[o - 1] >> 3) != 0b11110, a[o - 2:o + 2].hex()   # slti v0,6
a[o] = 7

# 2. Customize entry: li v0,1 ; sb v0,30(v1)  ->  jalx label_hook (delay slot = next insn)
o = f(0x4039fe0c)
assert a[o:o + 6] == bytes.fromhex('016a5ec34099'), a[o:o + 6].hex()
t = (HOOK >> 2) & 0x3ffffff
h1 = (0b00011 << 11) | (1 << 10) | (((t >> 16) & 0x1f) << 5) | ((t >> 21) & 0x1f)
struct.pack_into('<HH', a, o, h1, t & 0xffff)
open(p, 'wb').write(a)

# 3. strings
p = os.path.join(dst, 'setting.sty')
z = bytearray(open(p, 'rb').read())
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
open(p, 'wb').write(z)
print('poc11 built')
