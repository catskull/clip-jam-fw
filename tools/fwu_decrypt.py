# SPDX-License-Identifier: GPL-2.0-or-later
# Derived from Rockbox utils/atj2137/atjboottool (fwu.c and afi.c),
# Copyright (C) 2017 Amaury Pouly. See LICENSES/GPL-2.0.txt.
"""Decrypt an Actions ATJ2127 FWU v3 firmware (SanDisk Clip Jam upgrade.hex)
and unpack the inner AFI archive.

Algorithm ported from Rockbox utils/atj2137/atjboottool (fwu.c, afi.c).
Instead of doing the ECIES key exchange, the 32-byte session key is
recovered by known plaintext: the cipher is a linear sliding XOR, so one
all-zero (or all-0xFF) sector reveals it. Every AFI entry checksum is
verified afterwards, so a wrong key cannot pass silently.
"""
import collections
import os
import struct
import sys

ATJ2127_KEY = [0x42146ea2, 0x892c8e85, 0x9f9f6d27, 0x545fedc3,
               0x09e5c0ca, 0x2dfa7e61, 0x4e5322e6, 0xb19185b9]


def decrypt_sector(ct, sk, rounds):
    w = list(struct.unpack('<128I', ct))
    key = [ATJ2127_KEY[i] ^ sk[i] for i in range(8)]
    for r in range(rounds):
        b = w[r * 8:r * 8 + 8]
        roll = b[7] ^ sk[7]
        out = [b[i] ^ key[i + 1] for i in range(7)] + [b[7] ^ key[1] ^ key[4]]
        w[r * 8:r * 8 + 8] = out
        key = [key[0]] + key[2:8] + [roll]
    return struct.pack('<128I', *w)


def recover_session_key(ct, fill):
    """Assume the sector's plaintext is all `fill` (a 32-bit word)."""
    c = struct.unpack('<8I', ct[:32])
    k = [0] + [c[i] ^ fill for i in range(7)]          # key[1..7]
    if (c[7] ^ fill) != (k[1] ^ k[4]):
        return None
    sk = [0] * 8
    for i in range(1, 8):
        sk[i] = k[i] ^ ATJ2127_KEY[i]
    return sk


def afi_checksum(b):
    n = len(b) // 4
    s = sum(struct.unpack_from('<%dI' % n, b)) if n else 0
    rem = b[n * 4:]
    if rem:
        s += int.from_bytes(rem, 'little')
    return s & 0xffffffff


def main(path, outdir):
    raw = open(path, 'rb').read()
    assert raw[:16] == bytes.fromhex('112233445566778899aabbccddeeff75')
    fw_size, block_size = struct.unpack_from('<II', raw, 16)
    print(f'FWU: fw_size=0x{fw_size:x} block_size={block_size} '
          f'version=0x{raw[24]:02x} file_size=0x{len(raw):x}')

    A = raw[0x1ee] & 15
    B = raw[0x1fe] & 15
    offA, offB = 512 * (1 + A), 512 * (1 + B)
    print(f'crypto blocks: A at 0x{512 + offA:x} (1024B), '
          f'B at 0x{512 + offA + 1024 + offB:x} (512B)')
    size = fw_size - 2048
    body = (raw[512:512 + offA]
            + raw[512 + offA + 1024:512 + offA + 1024 + offB]
            + raw[512 + offA + 1024 + offB + 512:])[:size]
    rounds = max(1, 16 - (len(raw) >> 25))
    print(f'rounds per sector: {rounds}')

    # Known-plaintext key recovery from the most common ciphertext sectors.
    sectors = collections.Counter(body[o:o + 512] for o in range(0, size - 511, 512))
    sk = None
    for sec, _ in sectors.most_common(4):
        for fill in (0, 0xffffffff):
            cand = recover_session_key(sec, fill)
            if cand and decrypt_sector(body[:512], cand, rounds)[:4] == b'AFI\0':
                sk = cand
                break
        if sk:
            break
    if not sk:
        sys.exit('could not recover session key')
    print('session key (words 1..7):', ' '.join(f'{x:08x}' for x in sk[1:]))

    plain = bytearray()
    for o in range(0, size, 512):
        chunk = body[o:o + 512]
        if len(chunk) < 512:
            plain += chunk  # trailing partial sector (none expected)
        else:
            plain += decrypt_sector(chunk, sk, rounds)
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, 'decrypted.afi'), 'wb').write(plain)

    # AFI header
    sig, vid, pid, ver, ever, year, mon, day, afi_size = struct.unpack_from(
        '<4sHH2s2s2sBBI', plain, 0)
    print(f'AFI: vendor=0x{vid:04x} product=0x{pid:04x} ver={ver.hex()} '
          f'ext_ver={ever.hex()} date={year.hex()[::-1] if False else year[::-1].hex()}-'
          f'{mon:02x}-{day:02x} afi_size=0x{afi_size:x}')
    files_dir = os.path.join(outdir, 'files')
    os.makedirs(files_dir, exist_ok=True)
    bad = 0
    for i in range(126):
        e = plain[32 + i * 32:64 + i * 32]
        if e[0] == 0:
            continue
        name = e[:8].decode('latin1').rstrip(' ')
        ext = e[8:11].decode('latin1').rstrip(' ')
        typ = chr(e[11])
        addr, off, sz = struct.unpack_from('<III', e, 12)
        desc = e[24:28]
        chk = struct.unpack_from('<I', e, 28)[0]
        data = bytes(plain[off:off + sz])
        ok = afi_checksum(data) == chk
        bad += not ok
        fn = f'{name}.{ext}'
        print(f'  {fn:14s} type={typ} addr=0x{addr:08x} off=0x{off:08x} '
              f'size=0x{sz:08x} desc={desc!r} chk={"OK" if ok else "BAD"}')
        open(os.path.join(files_dir, fn), 'wb').write(data)
    hdr_chk = struct.unpack_from('<I', plain, 32 + 126 * 32 + 28)[0]
    print('AFI header checksum:',
          'OK' if afi_checksum(bytes(plain[:32 + 126 * 32 + 28])) == hdr_chk else 'BAD')
    print('entries with bad checksum:', bad)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
