"""poc8: Sky Raiders. Builds on poc5 (apple menu entry that launches video.ap).

    poc8.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR BANK_BIN BANK2_BIN RES_BIN

video.ap:
  bank  0x4005fe00  file 0x3c00  (<= 0x800)  <- BANK_BIN  (entry point at its start)
  bank  0x4009fe00  file 0x4400  (<= 0x800)  <- BANK2_BIN
  text  0xbfc1ee00  file 0x2800  (<= 0x7c8)  <- RES_BIN   (syscall stubs at +0x7c8 kept)
  launcher literal at file 0x3828 (video main 0x4006003d) -> 0x4005fe00
"""
import os
import struct
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
src, dst, bank, bank2, res = sys.argv[1:6]
subprocess.run([sys.executable, '-I', os.path.join(here, 'poc5.py'), src, dst], check=True,
               stdout=subprocess.DEVNULL)

p = os.path.join(dst, 'video.ap')
v = bytearray(open(p, 'rb').read())
to, ts, ta = struct.unpack_from('<III', v, 8)
assert (to, ts, ta) == (0x2800, 0x7e0, 0xbfc1ee00), (hex(to), hex(ts), hex(ta))
stubs = bytes(v[0x2800 + 0x7c8:0x2800 + 0x7e0])
assert stubs == bytes.fromhex('076b05e8106b05e8406b05e80f6b05e8066b05e8116b05e8'), stubs.hex()
ent = [struct.unpack_from('<III', v, 0x800 + 12 * i) for i in range(16)]
assert (0x3c00, 0x4005fe00, 0x800) in ent and (0x4400, 0x4009fe00, 0x800) in ent, ent
assert struct.unpack_from('<I', v, 0x3828)[0] == 0x4006003d


def put(off, limit, path):
    b = open(path, 'rb').read()
    assert len(b) <= limit, (path, len(b), limit)
    v[off:off + limit] = b + b'\0' * (limit - len(b))
    return len(b)


n1 = put(0x3c00, 0x800, bank)
n2 = put(0x4400, 0x800, bank2)
n3 = put(0x2800, 0x7c8, res)
assert bytes(v[0x2800 + 0x7c8:0x2800 + 0x7e0]) == stubs
struct.pack_into('<I', v, 0x3828, 0x4005fe00)
open(p, 'wb').write(v)
print(f'video.ap: bank {n1} B, bank2 {n2} B, resident {n3} B; launcher -> 0x4005fe00')
