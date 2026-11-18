"""Disassemble every code region of an ATJ2127 .ap/.drv at its load address.

    apdis.py FILE.ap > out.txt

Regions: the resident text section from the yqhx header plus every bank listed in
the four bank tables at 0x800/0x1000/0x1800/0x2000 (entries: file_off, addr, size).
Each region is introduced by a '==== region' line; uses m16.py for decoding.
"""
import os
import struct
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1]
b = open(path, 'rb').read()
to, ts, ta = struct.unpack_from('<III', b, 8)
regions = [(to, ts, ta, 'text')]
for t in (0x800, 0x1000, 0x1800, 0x2000):
    for i in range(0x800 // 12):
        fo, la, sz = struct.unpack_from('<III', b, t + 12 * i)
        if la and fo and sz:
            regions.append((fo, sz, la, f'bank@{t:#x}'))
for fo, sz, la, kind in regions:
    print(f'==== region {kind} file {fo:#x} size {sz:#x} addr {la:#010x}', flush=True)
    subprocess.run([sys.executable, '-I', os.path.join(here, 'm16.py'), path,
                    hex(fo), hex(fo + sz), hex(la)], check=True)
