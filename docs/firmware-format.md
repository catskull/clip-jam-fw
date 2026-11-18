# Firmware format

The official update file is `upgrade.hex` (about 26–27 MB). It has three layers:

```
upgrade.hex  (FWU v3: encrypted container)
└── AFI archive (decrypted payload)
    ├── MBREC.BIN, BRECFxxx.BIN, CARDBREC.BIN   bootloaders (one per NAND type)
    ├── FWSCFxxx.BIN, NANDHWSC.BIN, CARDFWSC.BIN, FLASH_ID.BIN
    └── FWIMAGE.FW (LFI archive)
        └── 122 files: kernel, drivers (.drv), apps (.ap), codecs (.al),
            resources (.sty/.mcg), fonts, config.bin, ...
```

## 1. FWU v3 container

| Offset | Size | Field |
|---|---|---|
| `0x00` | 16 | signature `11 22 33 44 55 66 77 88 99 aa bb cc dd ee ff 75` |
| `0x10` | 4 | `fw_size`: bytes covered by the body checksum (everything before the tail) |
| `0x14` | 4 | block size (512) |
| `0x18` | 1 | version (`0x7e`) |
| `0x1ee` | 1 | low nibble *A*: position of crypto block A |
| `0x1fe` | 1 | low nibble *B*: position of crypto block B |

Sector 0 (512 bytes) is the header. After it come encrypted body sectors, with two crypto
blocks spliced in:

- **Block A** (1024 bytes) at file offset `512 + 512·(1+A)`
- **Block B** (512 bytes) at `512 + 512·(1+A) + 1024 + 512·(1+B)`

The body is what remains when you remove sector 0 and the two blocks, truncated to
`fw_size − 2048` bytes.

Blocks A and B carry an ECIES exchange (curve sect233k1) that yields a 32-byte **session
key**. The private key needed is itself stored in the file, so this is obfuscation, not
real security. The tools don't do the ECIES maths at all; see *Session key recovery* below.

### FwuTail

Immediately **after** `fw_size` there is a 512-byte trailer:

| Offset | Field |
|---|---|
| `+0x10` | `u32` sum of all 32-bit little-endian words in `file[0 : fw_size]` |
| `+0x14` | `aa 55 aa 55` |
| `+0x18` | `"FwuTail"` |
| `+0x1fc` | `u32` sum of the tail's first 508 bytes as 32-bit words |

The stock updater checks both sums. No signature is checked: modified images with correct
sums are accepted (confirmed on the device).

### Cipher

Every 512-byte body sector is encrypted independently with a *sliding XOR* keyed by
`key[i] = ATJ2127_KEY[i] ^ session_key[i]` (8 × 32-bit words):

```
ATJ2127_KEY = 42146ea2 892c8e85 9f9f6d27 545fedc3 09e5c0ca 2dfa7e61 4e5322e6 b19185b9

rounds = max(1, 16 - (file_size >> 25))       # 16 for files < 32 MiB
for r in range(rounds):                       # one 32-byte chunk per round
    for i in 0..6:  ct[i] = pt[i] ^ key[i+1]
    ct[7] = pt[7] ^ key[1] ^ key[4]
    key = [key[0], key[2], ..., key[7], ct[7] ^ session_key[7]]   # shift left, feed back
```

Only the first `rounds × 32` bytes of each sector are encrypted (all 512 when there are 16
rounds). Decryption is the same with the feedback taken from the ciphertext.

### Session key recovery

Because the cipher is linear, one sector of known plaintext reveals the key. The body
contains many runs of `0x00`/`0xFF` padding, so the most common ciphertext sector *is* an
encrypted all-zero (or all-`0xFF`) sector. Words 1–7 of the key come straight out of it,
and the result is checked by decrypting sector 0 and looking for `"AFI\0"`. Session key
words 1..7 of the 1.10 image, for example:
`4db11a88 5c975b94 4510f822 b5879c99 45068c74 a71d6786 58548328`.

The packer reuses the original file's session key, sector 0 and crypto blocks, so the
updater's key exchange still produces the same key.

## 2. AFI archive

| Offset | Field |
|---|---|
| `0x00` | `"AFI\0"` |
| `0x04` | vendor / product IDs, version (`"1.10"`/`"1.16"`), build date |
| `0x10` | `u32 afi_size` |
| `0x20` | 126 entries × 32 bytes |
| `0xffc` | `u32` checksum = 32-bit word sum of bytes `0x000 .. 0xffb` |

Entry (32 bytes): `name[8] ext[3] type[1] load_addr[4] file_offset[4] size[4] desc[4] checksum[4]`.
Files are stored sequentially from `0x1000`, each padded to 512 bytes. The entry checksum
is the 32-bit word sum of the file's bytes.

## 3. FWIMAGE.FW (LFI)

| Offset | Field |
|---|---|
| `0x000` | signature `55 aa f0 0f`, version strings (`"1.10"`, `"1.16"`, build tag `20121228_SVN9494_Formal_AddUHost`) |
| `0x010` | `u32` directory checksum = 32-bit word sum of `0x200 .. 0x1fff` |
| `0x1fe` | `u16` header checksum = 16-bit sum of the 255 halfwords at `0x000 .. 0x1fd` |
| `0x200` | 240 directory entries × 32 bytes |
| `0x2000` | file data, sequential, 512-byte aligned, zero padded |

Directory entry: `name[8] ext[3] attr[1] reserved[2] version[2] block_offset[4] size[4] bytes[4] checksum[4]`.

- `block_offset` is in 512-byte units from the start of `FWIMAGE.FW`.
- `size` is the padded size; `bytes` is always 0 in SanDisk's images, so the real length
  is `size`.
- `checksum` is the 32-bit word sum of the (padded) file.

The firmware reads files by name through this directory, so files may change size: the
packer recalculates every offset and checksum (tested on the device with growing
`.sty` files).

## Contents of FWIMAGE.FW (1.16)

| Kind | Files |
|---|---|
| Kernel | `ker_init.bin` (MIPS32), `ker_text.bin`, `ker_data.bin`, `kernel.drv` |
| Drivers | `drv_lcd.drv`, `drv_ui.drv`, `key.drv`, `nand.drv`, `card.drv`, `cards.drv`, `uhost.drv`, `aud_dev.drv`, `drv_fm.drv`, `fat16n/fat32n/exfatn.drv` |
| Apps | `manager.ap`, `mainmenu.ap`, `music.ap`, `audible.ap`, `video.ap`, `picture.ap`, `ebook.ap`, `browser.ap`, `record.ap`, `radio.ap`, `tools.ap`, `setting.ap`, `alarm.ap`, `playlist.ap`, `config.ap`, `udisk.ap`, `mengine.ap`, `fmengine.ap`, `fwupdate.ap` |
| Codecs / media | `ad*.al` (audio decoders), `ae*.al` (encoders), `mmm_mp/mr/vp/id.al`, `fwdec.al` |
| Resources | `*.sty` (pictures + strings + styles), `*.mcg` (menu trees), `unicode*.fon`, code-page tables |
| Config | `config.bin` (compiled), `config.txt` (source, GBK comments), `config.spc` |
| Other | `legal.txt`, `m_type.txt`, `devinfo.bin`, `fmtdata.bin`, `alarm1.mp3`, `timer.wav`, **`dumy4m.bin`** (4,280,320 bytes of `0xFF`, a placeholder: free space for your own data) |
