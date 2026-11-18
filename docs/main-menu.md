# Main menu and *Customize*

The main menu (`mainmenu.ap`) is a carousel of 48×48 icons with a label. Stock 1.16 has
seven items: Music, Radio, Books, Folder, Card, Sport, Settings. *Settings → System
Settings → Customize* turns the first six on or off.

This page explains how that works and how `tools/poc12.py` adds an eighth item
("Raiders", app 2) with its own Customize switch.

## How the stock menu works

**Almost everything is indexed by position in the list, not by app ID.**

1. **The item list** comes from `config.bin` key 1 (`MAINMENU_AP_ID_ARRAY`, default
   `[0, 8, 1, 5, 11, 9, 10]`) the *first* time only. After that it lives in settings
   storage at `0x400` (`{0x55aa, default, count, ids[14]}`). The marker check is at
   `0x4001ffd4`/`0x4001ffe0`. Changing `config.bin` alone does nothing on a player that
   has already booted.
2. **Drawing.** For position *p*, three tables (bank `0x4011fe00`, file offsets
   `0x5e28`/`0x5e48`/`0x5e38`) give the UI style IDs for the frame (A), the icon (B) and
   the label (C):

   | p | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
   |---|---|---|---|---|---|---|---|
   | A (frame) | 0x1001 | 0x1003 | 0x1005 | 0x1008 | 0x100a | 0x100c | 0x100e |
   | B (icon)  | 0x1002 | 0x1004 | 0x1006 | 0x1009 | 0x100b | 0x100d | 0x100f |
   | C (label) | 0x2000 | 0x2001 | 0x2003 | 0x2004 | 0x2005 | 0x2006 | 0x2007 |

   Each table has 8 slots and the 8th is 0. The styles themselves are in
   `mainmenu.sty`'s style block (picture box = picture + position; text box = string).
3. **Visibility.** The cursor-movement code (`0x4015fe80` next, `0x4015ff04` previous)
   skips position *p* unless bit *p* of the **Customize byte** is set. That byte is at
   offset 24 of the global settings, reached through a pointer at `0x9fc1d42c`.
   **Position 6 is hard-coded as always visible** (`cmpi v0,6` at `0x4015febc` and
   `0x4015ff6e`), and the "first visible item" search stops at `count−1`. Both assume
   Settings is last.
4. **Launching.** The selection handler (`0x4015ffb4`) sends *create app* for
   `list[position]` with parameter 1, special-casing IDs 0, 1, 11 and 16 only.
5. **Customize** (setting.ap, node 7 in `setting.mcg`) has six rows. Each handler flips one
   bit (`0x01` Music … `0x20` Sport) of setting.ap's copy of the global settings at
   `0x9fc1d228`, and writes an On/Off label (common strings such as `0x803b`/`0x803a`) into
   the menu structure's dynamic-label slot. The factory default is `0x3f`.

## Adding an entry (what `poc12.py` does)

New layout: `[Music, Radio, Books, Folder, Card, Sport, Raiders, Settings]`. Raiders takes
position 6 / bit `0x40`, and Settings moves to the end.

| File | Change |
|---|---|
| `config.bin` | `MAINMENU_AP_ID_ARRAY` → `[0, 8, 1, 5, 11, 9, 2, 10]` (entry grows by 2 bytes; later offsets shifted) |
| `mainmenu.ap` | tables A/B/C: position 6 = new styles `0x1010`/`0x1011`/`0x2008`, position 7 = the Settings styles |
| `mainmenu.ap` | always-visible position `6 → 7` (two `cmpi` immediates) |
| `mainmenu.ap` | settings-storage marker `0x55aa → 0x55ac`, so the stored list rebuilds once from the new default |
| `mainmenu.sty` | new picture 17 (48×48 icon); picture boxes `0x1010` (frame) and `0x1011` (icon), text box `0x2008` (string 98); group 6 = new item, group 7 = Settings; all tables appended and repointed |
| `mainmenu.sty` | English string 98 (`video_s`) → "Raiders" |
| `setting.mcg` | Customize: 7 rows (written into the file's zero padding, both trees); row 6 = string 132 → handler `0x403a0400` |
| `setting.mcg` | Customize entry handler `0x4039fe01` → wrapper `0x403a0440` (all 7 references) |
| `setting.ap` | MIPS32 code at bank `0x4039fe00` + 0x600 (file `0xae00`, free space): `raiders_toggle` and `customize_entry` (`menu/toggle.c`) |
| `setting.ap` | library dynamic-label limit `rows < 6` → `rows < 7` |
| `setting.sty` | English strings 132/133 (unused `slide_repeat_off/on`) → "Raiders: Off"/"Raiders: On" |
| all `.ap` with the defaults routine | Customize default `0x3f → 0x7f` (Raiders visible after a settings reset) |

`raiders_toggle` flips bit `0x40` and writes label `0x84`/`0x85` into the halfword at
`menu+30`. `customize_entry` calls the stock entry handler, then writes the same label. The
label IDs are below 256 with a non-zero low byte, so the flag byte at `+30` stays set.

### Lessons

- The first attempt (poc9) only appended the app to the list. It didn't appear, because
  the stored list wasn't rebuilt, the style tables had no 8th entry, and bit 7 was never
  set.
- poc11 called the label helper with a **MIPS16 `jalx`** patched into Customize's
  handler. The player **rebooted** when entering Customize. The stock firmware never uses
  `jalx`; reaching MIPS32 code through function pointers (as in poc12) works.
- A firmware update resets settings storage, which is why Raiders defaults to on in poc12.

## Limitations

- The new strings are English only. Other languages show the original strings at those
  indices ("Video" or its translation; `slide_repeat_off/on`).
- Up to 14 items fit the stored list. Each additional item needs its own styles, table
  entries and Customize bit, and the tables in `mainmenu.ap` have only 8 slots.
