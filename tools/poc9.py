"""poc9: keep Books, add an 8th main-menu entry (app 2 = video.ap = Sky Raiders).

    poc9.py SRC_FWIMAGE_DIR DST_FWIMAGE_DIR BANK_BIN BANK2_BIN RES_BIN

Starts from stock (manager.ap / mainmenu.sty untouched, so Books is back) and:
  video.ap     Sky Raiders code (same layout as poc8)
  config.bin   MAINMENU_AP_ID_ARRAY  [0,8,1,5,11,9,10] -> [0,8,1,5,11,9,10,2]
               (entry grows 18 -> 20 bytes; later entries shifted, offsets fixed)
  config.txt   same change, for consistency
  mainmenu.ap  marker of its saved menu list (settings storage 0x400) 0x55aa -> 0x55ab,
               so the saved 7-item list is rebuilt once from the new default
  mainmenu.sty English 'Video' (string 98) -> 'Raiders' (appended, entry repointed)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
src, dst, bank, bank2, res = sys.argv[1:6]
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)

# video.ap with Sky Raiders: reuse poc8 (which also applies poc5) and take only video.ap
with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as tmp:
    t = os.path.join(tmp, 'fw')
    subprocess.run([sys.executable, '-I', os.path.join(here, 'poc8.py'), src, t, bank, bank2, res],
                   check=True, stdout=subprocess.DEVNULL)
    shutil.copy(os.path.join(t, 'video.ap'), os.path.join(dst, 'video.ap'))

# config.bin: grow entry 1
p = os.path.join(dst, 'config.bin')
c = bytearray(open(p, 'rb').read())
tab = []
o = 0x10
while o < 0x208:
    off, ln = struct.unpack_from('<II', c, o)
    tab.append((o, off, ln))
    o += 8
e1 = tab[1]
assert (e1[1], e1[2]) == (0x21e, 18)
vals = list(struct.unpack_from('<9H', c, 0x21e))
assert vals == [0, 7, 0, 8, 1, 5, 11, 9, 10], vals
end = max(off + ln for _, off, ln in tab)
new = struct.pack('<10H', 0, 8, 0, 8, 1, 5, 11, 9, 10, 2)
data = bytes(c[0x21e + 18:end])
assert end + 2 <= len(c) and not any(c[end:end + 2])
c[0x21e:0x21e + 20] = new
c[0x21e + 20:end + 2] = data
for to, off, ln in tab:
    if off > 0x21e:
        struct.pack_into('<I', c, to, off + 2)
struct.pack_into('<II', c, e1[0], 0x21e, 20)
open(p, 'wb').write(c)
# self-check: every other entry's bytes unchanged
orig = open(os.path.join(src, 'config.bin'), 'rb').read()
for i, (to, off, ln) in enumerate(tab):
    if i == 1:
        continue
    noff = struct.unpack_from('<I', c, to)[0]
    assert c[noff:noff + ln] == orig[off:off + ln], i

p = os.path.join(dst, 'config.txt')
s = open(p, 'rb').read()
s2 = s.replace(b'MAINMENU_AP_ID_ARRAY = 0[0, 8, 1, 5, 11, 9, 10];',
               b'MAINMENU_AP_ID_ARRAY = 0[0, 8, 1, 5, 11, 9, 10, 2];')
assert s2 != s
open(p, 'wb').write(s2)

# mainmenu.ap: saved-list marker 0x55aa -> 0x55ab (check + write in bank 0x4001fe00)
p = os.path.join(dst, 'mainmenu.ap')
m = bytearray(open(p, 'rb').read())
assert m[0x39d2:0x39d6] == bytes.fromhex('aaf50a72')   # extend; cmpi v0,0x55aa
assert m[0x39de:0x39e2] == bytes.fromhex('aaf50a6a')   # extend; li v0,0x55aa
m[0x39d4] = 0x0b
m[0x39e0] = 0x0b
open(p, 'wb').write(m)

# mainmenu.sty: English string 98 'Video' -> 'Raiders'
p = os.path.join(dst, 'mainmenu.sty')
y = bytearray(open(p, 'rb').read())
LANG0 = 0x21cb0
so, sl = struct.unpack_from('<II', y, LANG0 + 98 * 8)
assert y[so:so + sl] == 'Video\0'.encode('utf-16le'), y[so:so + sl]
txt = 'Raiders\0'.encode('utf-16le')
y += b'\0' * (-len(y) % 4)
noff = len(y)
y += txt
struct.pack_into('<II', y, LANG0 + 98 * 8, noff, len(txt))
open(p, 'wb').write(y)
print('poc9: video.ap=Sky Raiders, menu list +app 2, marker 0x55ab, Video->Raiders')
