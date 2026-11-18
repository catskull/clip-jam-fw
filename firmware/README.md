# Stock firmware archive

Unmodified SanDisk Clip Jam firmware, kept here for archival purposes because the
official downloads are old and could disappear. These files are **SanDisk's**, not part of
this project, and are **not** covered by this repository's licence.

| Version | Model | File | Size | SHA-256 |
|---|---|---|---|---|
| 1.16 (latest) | Clip Jam (standard, `1.xx`) | [`clipjam-1.16/upgrade.hex`](clipjam-1.16/upgrade.hex) | 27,078,144 | `0d2718bcae80db4f783d1af18247bace3ab549a6e963dcf7d4ebe36c82927b38` |
| 1.15 | Clip Jam (standard, `1.xx`) | [`clipjam-1.15/upgrade.hex`](clipjam-1.15/upgrade.hex) | 27,078,144 | `5ee3739bae44cda789b4bf9437e10c1682c4af32ff7f995a580e953ebeba852d` |

- 1.16 is byte-identical to `https://downloads.sandisk.com/firmware/clipjam/116/upgrade.hex`.
- Both decrypt with `tools/fwu_decrypt.py` and every internal checksum verifies.
- **Not for the "E" model** (firmware `0.0xE`). Its firmware (0.02E) is not archived here.

To restore stock firmware, copy `upgrade.hex` to the root of the player's internal
storage, eject and unplug (see [../docs/flashing-and-recovery.md](../docs/flashing-and-recovery.md)).
Check the SHA-256 first: `shasum -a 256 clipjam-1.16/upgrade.hex`.
