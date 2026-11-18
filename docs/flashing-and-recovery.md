# Flashing and recovery

## Updating (stock or modified)

1. Battery above 50%. Remove the microSD card.
2. Copy `upgrade.hex` to the **root of the internal storage**.
   On macOS, avoid `._` resource-fork files: `COPYFILE_DISABLE=1 cp -X upgrade.hex "/Volumes/Clip Jam/"`.
3. Eject and unplug. The player installs the update and switches off; the file is deleted.
4. Switch on. A firmware update **resets settings** (language prompt, Customize switches,
   saved menu list).

Reinstalling the same version is allowed, and modified images are accepted as long as the
FwuTail checksums are right.

To go back to stock, copy SanDisk's original `upgrade.hex` the same way. Copies of 1.16
and 1.15 are archived in [`firmware/`](../firmware/).

## Two hardware models

| Model | Firmware | Latest |
|---|---|---|
| Clip Jam (standard) | `1.xx` | 1.16 – `downloads.sandisk.com/firmware/clipjam/116/upgrade.hex` |
| Clip Jam "E" | `0.0xE` | 0.02E – `downloads.sandisk.com/firmware/clipjam/002e/upgrade.hex` |

Check *Settings → System Settings → Info*. Everything here was done on the standard model
with 1.16.

## Recovery mode (ADFU)

- With the player **off**, hold **Vol+ and Vol−** and switch it on. A firmware-upgrade
  screen appears and the player shows up on USB as **`10d6:10d6`** (normal mode is
  `0781:74f0`). Check on macOS with `ioreg -p IOUSB -l -w0 | grep -A2 4310`.
- This is in the bootloader (BREC), which none of these tools modify.
- To leave it, unplug and hold power for about 15 seconds.
- Reflashing over USB in this mode needs community tools (ilyakurdyukov/actions_flash,
  nfd/atj2127decrypt's `actions_adfu_upgrade.py`), documented for the Clip Sport (same SoC).
  It hasn't been needed or tested here: every failure so far was fixed by a normal update.

## If a modified image misbehaves

| Symptom | What to do |
|---|---|
| Freezes in an app | hold power ~15 s; reinstall stock or a known-good image |
| Reboots when opening a menu | the main firmware still boots; reinstall a known-good image |
| Doesn't boot at all | recovery mode, then reflash with the ADFU tools |

## History of on-device tests (1.16)

| Build | Change | Result |
|---|---|---|
| round trip | unmodified re-pack | byte-identical |
| poc1 | English "Music" → "Hello" | ✅ accepted, shown |
| poc2 | patch the driver's LCD init table (inverse) | ❌ no effect: the init table is dead code (the bootloader initialises the panel) |
| poc3 | `config.bin` menu list + video app | ❌ no change: the main menu keeps its own saved list |
| poc4 | inverse video via the contrast routine | ✅ |
| poc5 | Books slot launches `video.ap`, apple icon, "Video" label | ✅ (video.ap: "File format not supported!") |
| poc6 | native frame player + synthetic frames | ✅ |
| poc7 | real-time cube | ✅ |
| poc8 | Sky Raiders | ✅ |
| poc9 | 8th menu item, list only | ❌ not shown (no styles, bit 7 never set) |
| poc10 | Books restored + Raiders item + Customize row (fixed label) | ✅ (hidden until switched on) |
| poc11 | live On/Off label via a MIPS16 `jalx` hook | ❌ **reboot** when opening Customize |
| poc12 | live label via a wrapper handler + default on | ✅ |
