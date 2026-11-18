# SPDX-License-Identifier: GPL-2.0-or-later
# Derived from Rockbox utils/atj2137/atjboottool (fw.c),
# Copyright (C) 2017 Amaury Pouly. See LICENSES/GPL-2.0.txt.
"""Unpack an Actions 'LFI' FWIMAGE.FW (55 aa f0 0f variant). Ported from Rockbox fw.c."""
import os
import struct
import sys


def chk(b):
    n = len(b) // 4
    return sum(struct.unpack_from('<%dI' % n, b)) & 0xffffffff


def main(path, outdir):
    buf = open(path, 'rb').read()
    assert buf[:4] == b'\x55\xaa\xf0\x0f', buf[:4].hex()
    dir_chk = struct.unpack_from('<I', buf, 16)[0]
    print('directory checksum', 'OK' if chk(buf[0x200:0x2000]) == dir_chk else 'BAD')
    hsum = sum(struct.unpack_from('<255H', buf, 0)) & 0xffff
    print('header checksum', 'OK' if hsum == struct.unpack_from('<H', buf, 510)[0] else 'BAD')
    os.makedirs(outdir, exist_ok=True)
    bad = 0
    for i in range(240):
        e = buf[0x200 + i * 32:0x220 + i * 32]
        if e[0] == 0:
            continue
        name = e[:8].decode('latin1').rstrip(' ').lower()
        ext = e[8:11].decode('latin1').rstrip(' ').lower()
        attr = e[11]
        ver, blk, size, nbytes, c = struct.unpack_from('<HIIII', e, 14)
        nbytes = nbytes or size
        off = blk << 9
        region = bytearray(buf[off:off + size])
        region[nbytes:] = b'\0' * (size - nbytes)
        ok = chk(bytes(region)) == c
        bad += not ok
        fn = f'{name}.{ext}'
        print(f'{fn:14s} attr=0x{attr:02x} ver=0x{ver:04x} off=0x{off:08x} '
              f'bytes={nbytes:9d} {"OK" if ok else "BAD"}')
        open(os.path.join(outdir, fn), 'wb').write(buf[off:off + nbytes])
    print('bad entries:', bad)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
