# Tools

All tools are standard-library Python 3. Run them with `python3 -I` (isolated mode), which
is a good habit when the input comes from a download.

## Firmware

| Script | Usage | Does |
|---|---|---|
| `fwu_decrypt.py` | `fwu_decrypt.py upgrade.hex OUTDIR` | recovers the session key by known plaintext, decrypts the FWU body, writes `OUTDIR/decrypted.afi` and `OUTDIR/files/*`, and verifies every AFI checksum |
| `fw_unpack.py` | `fw_unpack.py FWIMAGE.FW OUTDIR` | unpacks the LFI archive (lowercase file names) and verifies checksums |
| `fwpack.py` | `fwpack.py ORIG.hex AFI_DIR FW_DIR OUT.hex` | rebuilds `FWIMAGE.FW` → AFI → encrypted FWU, recalculating all offsets and checksums (directory metadata comes from `ORIG.hex`; files may change size). Also writes `rebuilt_FWIMAGE.FW` and `rebuilt.afi` next to the output |

A round trip of an unmodified image is byte-identical to the original.

## Analysis

| Script | Usage | Does |
|---|---|---|
| `m16.py` | `m16.py FILE START END BASE` | small MIPS16e disassembler: branches with targets, PC-relative literal loads with values, a constant tracker that annotates memory accesses and call targets (`-> 0x…`), and function boundaries at `save` |
| `apdis.py` | `apdis.py app.ap > out.txt` | disassembles an app's resident text and every bank at its load address (wraps `m16.py`) |
| `sty_extract.py` | `sty_extract.py OUTDIR file.sty…` | exports `.sty` pictures as PNG |

The disassembler decodes data as code too. Treat "instructions" inside literal pools with
suspicion (for example, the `jalx` with nonsense targets seen in stock code are data).

## Content

| Script | Usage | Does |
|---|---|---|
| `frames.py` | `frames.py VIDEO OUT.bin [--fps N] [--threshold T] [--invert] [--preview DIR]` | video → frame-player data (exact `dumy4m.bin` size) |
| `frames_test.py` | `frames_test.py OUT.bin [SECONDS] [FPS]` | synthetic test frames (border, orientation arrow, bouncing ball, seconds counter) |
| `to_amv.sh` | `to_amv.sh IN OUT.amv [WxH]` | ffmpeg AMV export (the stock video player still rejects these) |

## Patch scripts

Each takes a pristine unpacked `fwimage/` directory and writes a patched copy. Then pack
with `fwpack.py`. They `assert` the bytes they expect before changing anything, so they
refuse to run on a different firmware version.

| Script | Builds on | Result |
|---|---|---|
| `poc5.py` | stock | Books slot launches `video.ap`; apple icon; "Video" label |
| `poc6.py` | poc5 | + a player binary in video.ap's main bank + frame data in `dumy4m.bin` |
| `poc8.py` | poc5 | + a three-section program (bank, bank2, resident text) in video.ap |
| `poc9.py` | stock | (historical, doesn't work) 8th menu item via the list only |
| `poc10.py` | stock | Books kept + "Raiders" main-menu item + Customize row (fixed label) |
| `poc11.py` | poc10 | (historical, **crashes**) live label via a `jalx` hook |
| `poc12.py` | poc10 | live "Raiders: On/Off" label via a wrapper, Customize default on. **Current.** |

## Verifying an image before flashing

```sh
python3 -I tools/fwu_decrypt.py NEW.hex check
python3 -I tools/fw_unpack.py check/files/FWIMAGE.FW check/fwimage
for f in out116/fwimage/*; do cmp -s "$f" "check/fwimage/$(basename "$f")" || echo "differs: $(basename "$f")"; done
for f in out116/files/*; do [ "$(basename "$f")" = FWIMAGE.FW ] || cmp -s "$f" "check/files/$(basename "$f")" || echo "AFI differs: $f"; done
```

The second loop must print nothing (bootloaders untouched). The first should list only the
files you meant to change.
