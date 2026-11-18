# Resource files

## `.sty`: pictures, strings and UI styles

Every app has a `.sty` file (`mainmenu.sty`, `setting.sty`, …) plus the shared `common.sty`.

### Header

| Offset | Field |
|---|---|
| `0x00` | `"RU3\x19"`, …, `"V100"` at `0x0c` |
| `0x10` | section table, 16 bytes per entry: `u32 offset, u16 count, u8 type, …` |

Section types: `'P'` pictures, `'S'` strings, `'X'` XML resource descriptor. The compiled
**style block** isn't in the section table; it follows the XML (see below).

### Pictures (`'P'`)

The index is `count` entries × 16 bytes: `u32 offset, u32 size, u16 type (2), u16 width,
u16 height, …`. Picture data is raw little-endian **RGB565**, uncompressed (839 pictures
across all files in 1.10). Only `0xFFFF` pixels light up on this display.

Pictures can be **added** by appending the data and a copy of the index (one entry longer)
to the end of the file, then updating the `'P'` section's offset and count ✅.

### Strings (`'S'`)

The `'S'` section has one entry per language (32): `u32 offset, …`. Each points to a table
of `(u32 offset, u32 length)` pairs, one per string ID. Strings are UTF-16LE,
NUL-terminated (the length includes the NUL). Language 0 is English.

The number of strings is fixed per file, so to **change** a string, append the new text
and repoint its table entry. Nothing else moves ✅.

**String IDs:** an app's own strings are referred to by their index (e.g. `98` =
`video_s` in mainmenu.sty). **Common strings** (from `common.sty`) are `0x8000 | index`
(e.g. `0x8028` = "File format not supported!", `0x803b` = "Music: On").

### Resource descriptor (`'X'`)

A UTF-8 XML `<ResDescriptor>` listing picture names (`PIC0`, `PIC1`, …) and string names per
language (`music_s`, `setting_s`, …). It's useful for finding string indices; the device
doesn't need it.

### Style block

Right after the XML, at a 16-byte boundary (`0x51a00` in 1.16 `mainmenu.sty`):

```
"sty\0"  u32 1  u32 ptr -> table list
table list: (u32 offset, u32 count) x 3
   [0] groups       20 bytes each
   [1] picture boxes 32 bytes each   style IDs 0x1000 + n
   [2] text boxes    20 bytes each   style IDs 0x2000 + n
```

| Record | Layout |
|---|---|
| picture box | `u16 pic, s16 x, s16 y, u16 flags (0x0101), u16 pic, 0xffff…` |
| text box | `u16 string, s16 x, s16 y, u16 w, u16 h, …, 0xffff, u16 flags` |
| group | `u16 0xef7d, s16 -80, s16 -10, u16 100, u16 200, u16 1, u16 count, u32 list_ptr (unaligned, at +14)` |
| group list | `count` × `(u16 1, u16 style_id)` |

Apps draw by **style ID** (`0x1000+n` picture box *n*, `0x2000+n` text box *n*). All
pointers are absolute file offsets, so tables can be extended by appending enlarged copies
and repointing the header ✅.

## `.mcg`: menu trees

Settings-style menus (`setting.mcg`, `music.mcg`, …). The file starts with `"test"`.

- **Menu headers**, 12 bytes each from `0x30` (a second tree from `0xc0`):
  `u16 tree, u16 index, u16 title_string, u16 row_count, u32 rows_offset`.
- **Rows**, 20 bytes each: `u16 0xffff, u16 string, u16 0, u16 0, u32 handler, 8 × 0`.
  `handler` is called with the menu structure in `a0` when the row is chosen.
- **Nodes** (submenu entries), e.g. `u16 node, u16 string, u16 0, u16 0, u32 entry_handler, …`.
  The entry handler runs when the submenu opens. Some other tables in the file also hold
  node handlers, after a `u32` node number.

String IDs `≥ 0x8000` refer to `common.sty`, smaller ones to the app's own `.sty`.

### Dynamic row labels

Handlers can override a row's label at run time. The menu structure passed in `a0` holds
`u16 label[6]` at `+18` and a flag byte at `+30`. If the flag is non-zero, row *r* shows
`label[r]` (unless it's `0xffff`). The app library only honours rows `< 6`
(`slti v0,6` at `0x4879fa16` in setting.ap). Raising that to 7 and storing row 6's label
in the halfword at `+30`, with a non-zero low byte so the flag stays set, works ✅.

Row handlers end by setting `+2 = 0xffff`, `+8 = 0`, `+12 = 0xffff` and returning `0x8207`
(redraw).

## `config.txt` / `config.bin`

See [app-runtime.md](app-runtime.md#configbin).
