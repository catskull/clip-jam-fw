# SPDX-License-Identifier: GPL-2.0-or-later
# Derived from Rockbox utils/atj2137/atjboottool (fwu.c, afi.c, fw.c; this is the inverse),
# Copyright (C) 2017 Amaury Pouly. See LICENSES/GPL-2.0.txt.
"""Rebuild a SanDisk Clip Jam (ATJ2127, FWU v3) upgrade.hex from extracted files.

    fwpack.py ORIG_UPGRADE_HEX AFI_FILES_DIR FW_FILES_DIR OUT_HEX

Pipeline (the inverse of fwu_decrypt.py + fw_unpack.py):
  FW_FILES_DIR  -> FWIMAGE.FW   (LFI 55aa f00f: directory, block offsets, checksums)
  AFI_FILES_DIR -> AFI archive  (FWIMAGE.FW from the step above replaces the one on disk)
  AFI           -> FWU          (ATJ2127 sliding-XOR encryption with the original's
                                 session key; original sector 0 and ECIES blocks A/B
                                 spliced back in; FwuTail checksums recomputed)

Every offset, size and checksum is recomputed from the file contents; only the
directory metadata (names, types, load addresses, versions) is taken from the
original, so modified files of a different size are laid out correctly.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwu_decrypt import (ATJ2127_KEY, afi_checksum, decrypt_sector,  # noqa: E402
                         recover_session_key)

ALIGN = 512


def s32(b):
    return sum(struct.unpack_from('<%dI' % (len(b) // 4), b)) & 0xffffffff


def pad(b):
    return b + b'\0' * (-len(b) % ALIGN)


# ---------------------------------------------------------------- FWIMAGE.FW
def build_fw(orig_fw, files_dir):
    hdr = bytearray(orig_fw[:0x2000])            # header + 240-entry directory
    out = bytearray()
    pos = 0x2000
    seen = set()
    for i in range(240):
        eo = 0x200 + i * 32
        if hdr[eo] == 0:
            continue
        name = hdr[eo:eo + 8].decode('latin1').rstrip(' ').lower()
        ext = hdr[eo + 8:eo + 11].decode('latin1').rstrip(' ').lower()
        fn = f'{name}.{ext}'
        assert fn not in seen, f'duplicate FW entry {fn}'
        seen.add(fn)
        data = pad(open(os.path.join(files_dir, fn), 'rb').read())
        # block_offset, size, bytes(=0, unused here), checksum
        struct.pack_into('<IIII', hdr, eo + 16, pos >> 9, len(data), 0, s32(data))
        out += data
        pos += len(data)
    struct.pack_into('<I', hdr, 16, s32(bytes(hdr[0x200:0x2000])))          # directory checksum
    struct.pack_into('<H', hdr, 510, sum(struct.unpack_from('<255H', hdr, 0)) & 0xffff)
    return bytes(hdr) + bytes(out)


# ---------------------------------------------------------------- AFI
AFI_DIR_END = 32 + 126 * 32 + 32                 # header + entries + post header = 0x1000


def build_afi(orig_afi, files_dir, overrides):
    hdr = bytearray(orig_afi[:AFI_DIR_END])
    out = bytearray()
    pos = AFI_DIR_END
    for i in range(126):
        eo = 32 + i * 32
        if hdr[eo] == 0:
            continue
        name = hdr[eo:eo + 8].decode('latin1').rstrip(' ')
        ext = hdr[eo + 8:eo + 11].decode('latin1').rstrip(' ')
        fn = f'{name}.{ext}'
        data = overrides.get(fn)
        if data is None:
            data = open(os.path.join(files_dir, fn), 'rb').read()
        data = pad(data)
        struct.pack_into('<III', hdr, eo + 16, pos, len(data), 0)
        struct.pack_into('<I', hdr, eo + 28, afi_checksum(data))
        # keep desc (eo+24) from the original
        struct.pack_into('<4s', hdr, eo + 24, orig_afi[eo + 24:eo + 28])
        out += data
        pos += len(data)
    struct.pack_into('<I', hdr, 16, pos)                                      # afi_size
    struct.pack_into('<I', hdr, AFI_DIR_END - 4, afi_checksum(bytes(hdr[:AFI_DIR_END - 4])))
    return bytes(hdr) + bytes(out)


# ---------------------------------------------------------------- FWU
def encrypt_sector(pt, sk, rounds):
    w = list(struct.unpack('<128I', pt))
    key = [ATJ2127_KEY[i] ^ sk[i] for i in range(8)]
    for r in range(rounds):
        p = w[r * 8:r * 8 + 8]
        c = [p[i] ^ key[i + 1] for i in range(7)] + [p[7] ^ key[1] ^ key[4]]
        w[r * 8:r * 8 + 8] = c
        key = [key[0]] + key[2:8] + [c[7] ^ sk[7]]
    return struct.pack('<128I', *w)


def original_session_key(orig):
    """Same known-plaintext recovery as fwu_decrypt.py, checked against 'AFI\\0'."""
    import collections
    fw_size = struct.unpack_from('<I', orig, 16)[0]
    A, B = orig[0x1ee] & 15, orig[0x1fe] & 15
    offA, offB = 512 * (1 + A), 512 * (1 + B)
    body = (orig[512:512 + offA] + orig[512 + offA + 1024:512 + offA + 1024 + offB]
            + orig[512 + offA + 1024 + offB + 512:])[:fw_size - 2048]
    rounds = max(1, 16 - (len(orig) >> 25))
    for sec, _ in collections.Counter(body[o:o + 512] for o in range(0, len(body) - 511, 512)).most_common(4):
        for fill in (0, 0xffffffff):
            sk = recover_session_key(sec, fill)
            if sk and decrypt_sector(body[:512], sk, rounds)[:4] == b'AFI\0':
                return sk
    raise SystemExit('could not recover session key from original')


def build_fwu(orig, afi):
    assert len(afi) % ALIGN == 0
    sk = original_session_key(orig)
    ofw_size = struct.unpack_from('<I', orig, 16)[0]
    otail = orig[ofw_size:ofw_size + 512]
    assert otail[0x14:0x18] == b'\xaa\x55\xaa\x55' and otail[0x18:0x1f] == b'FwuTail'
    A, B = orig[0x1ee] & 15, orig[0x1fe] & 15
    offA, offB = 512 * (1 + A), 512 * (1 + B)
    assert len(afi) >= offA + offB

    fw_size = 2048 + len(afi)
    file_size = fw_size + 512
    # NB: the cipher's round count depends on the *file* size (one 32-byte chunk per
    # sector is left in clear for every 32 MiB); same rule the decryptor uses.
    rounds = max(1, 16 - (file_size >> 25))
    enc = b''.join(encrypt_sector(afi[o:o + 512], sk, rounds) for o in range(0, len(afi), 512))

    out = bytearray(orig[:512])                                # sector 0 (header + ECIES key)
    out += enc[:offA]
    out += orig[512 + offA:512 + offA + 1024]                  # crypto block A
    out += enc[offA:offA + offB]
    out += orig[512 + offA + 1024 + offB:512 + offA + 1024 + offB + 512]   # crypto block B
    out += enc[offA + offB:]
    struct.pack_into('<I', out, 16, fw_size)
    assert len(out) == fw_size
    tail = bytearray(otail)
    struct.pack_into('<I', tail, 0x10, s32(bytes(out)))
    struct.pack_into('<I', tail, 508, s32(bytes(tail[:508])))
    return bytes(out + tail)


def read_orig_afi(orig, off, n):
    """Decrypt n bytes at AFI offset `off` straight out of the original FWU
    (sectors decrypt independently, so only the needed ones are touched)."""
    sk = original_session_key(orig)
    A, B = orig[0x1ee] & 15, orig[0x1fe] & 15
    offA, offB = 512 * (1 + A), 512 * (1 + B)
    rounds = max(1, 16 - (len(orig) >> 25))

    def raw_off(body_off):  # body offset -> file offset (skip blocks A and B)
        r = 512 + body_off
        if body_off >= offA:
            r += 1024
        if body_off >= offA + offB:
            r += 512
        return r
    out = bytearray()
    for s in range(off // 512 * 512, off + n, 512):
        ro = raw_off(s)
        out += decrypt_sector(orig[ro:ro + 512], sk, rounds)
    start = off % 512
    return bytes(out[start:start + n])


def main(orig_path, afi_dir, fw_dir, out_path):
    orig = open(orig_path, 'rb').read()
    here = os.path.dirname(os.path.abspath(out_path))
    # Directory metadata (names, types, addresses, versions) from the original.
    orig_afi = read_orig_afi(orig, 0, AFI_DIR_END)
    fw_off = next(struct.unpack_from('<I', orig_afi, 32 + i * 32 + 16)[0] for i in range(126)
                  if orig_afi[32 + i * 32:32 + i * 32 + 11] == b'FWIMAGE FW ')
    orig_fw = read_orig_afi(orig, fw_off, 0x2000)
    fw = build_fw(orig_fw, fw_dir)
    afi = build_afi(orig_afi, afi_dir, {'FWIMAGE.FW': fw})
    fwu = build_fwu(orig, afi)
    os.makedirs(here, exist_ok=True)
    open(os.path.join(here, 'rebuilt_FWIMAGE.FW'), 'wb').write(fw)
    open(os.path.join(here, 'rebuilt.afi'), 'wb').write(afi)
    open(out_path, 'wb').write(fwu)
    print(f'FWIMAGE.FW {len(fw):#x}  AFI {len(afi):#x}  FWU {len(fwu):#x} -> {out_path}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
