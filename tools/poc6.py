"""poc6: frame (1-bit video) player. Builds on poc5 (apple menu entry that launches video.ap).

    poc6.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR PLAYER_BIN FRAMES_BIN

video.ap : bank at file 0x3c00 (0x4005fe00, 0x800 bytes) <- PLAYER_BIN (MIPS32)
           launcher literal at file 0x3828 (0x4006003d, video main) -> 0x4005fe00
dumy4m.bin <- FRAMES_BIN (same size; it was an all-0xFF placeholder)
"""
import os
import struct
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
src, dst, player, frames = sys.argv[1:5]
subprocess.run([sys.executable, '-I', os.path.join(here, 'poc5.py'), src, dst], check=True,
               stdout=subprocess.DEVNULL)

p = os.path.join(dst, 'video.ap')
v = bytearray(open(p, 'rb').read())
# bank table entry for this bank: (file 0x3c00, 0x4005fe00, 0x800)
ent = [struct.unpack_from('<III', v, 0x800 + 12 * i) for i in range(16)]
assert (0x3c00, 0x4005fe00, 0x800) in ent, ent
assert struct.unpack_from('<I', v, 0x3828)[0] == 0x4006003d
code = open(player, 'rb').read()
assert len(code) <= 0x800, len(code)
v[0x3c00:0x4400] = code + b'\0' * (0x800 - len(code))
struct.pack_into('<I', v, 0x3828, 0x4005fe00)
open(p, 'wb').write(v)

d = os.path.join(dst, 'dumy4m.bin')
fr = open(frames, 'rb').read()
assert len(fr) == os.path.getsize(d), (len(fr), os.path.getsize(d))
assert set(open(os.path.join(src, 'dumy4m.bin'), 'rb').read()) <= {0xff, 0x20, 0x00}
open(d, 'wb').write(fr)
print(f'player {len(code)} bytes into video.ap bank 0x4005fe00; frames -> dumy4m.bin')
