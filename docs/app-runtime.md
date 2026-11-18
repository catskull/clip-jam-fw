# App runtime

Everything in this file was worked out by disassembly (`tools/apdis.py`) and confirmed by
running code on the device where marked ✅.

## `.ap` / `.drv` / `.al` file layout ("yqhx" modules)

| Offset | Field |
|---|---|
| `0x00` | `u16` type/flags, `u16 0x0004` |
| `0x04` | magic `"yqhx"` |
| `0x08` | text: file offset, size, load address (e.g. `0x2800`, `≤0x7e0`, `0xbfc1ee00` for apps) |
| `0x14` | data: file offset, size, load address (`0x9fc1d200` for apps) |
| `0x20` | bss: size, address |
| `0x28` | entry point (a bank address; MIPS16, so odd), e.g. `0x4001fe31` |
| `0x800`, `0x1000`, `0x1800`, `0x2000` | four **bank tables** (apps) |

Each bank-table entry is 12 bytes: `file_offset, load_address, size`. Bank code is
paged in by the kernel when executed, so an app is much larger than the RAM it occupies.

| Table | Address pattern | Typical size | Contents |
|---|---|---|---|
| `0x800` | `0x40XXfe00` | 0x800 | the app's own code ("control" banks) |
| `0x1000` | `0x48XXf600/f800` | 0x600–0x800 | the **app library** (each app has its own copy, at the same addresses) |
| `0x1800` | `0x78XX7000` | ≤ 0x800 | UI code |
| `0x2000` | `0x71XX7800` | ≤ 0x800 | UI code |

A bank occupies `[load_address, load_address + size)`, so `0x4005fe00`+0x800 runs up to
`0x40060600`. Banks call each other freely; the kernel swaps them in as needed. Constants
read from another bank's code may not be resident; keep data in resident text or RAM.

### Resident text and syscall stubs

An app's resident text (at `0xbfc1ee00`) ends with its **system-call stubs**, 4 bytes
each: `li v1, GROUP ; break` (`xx 6b 05 e8`). The kernel's `break` handler returns to `ra`,
so a stub behaves as a function: put the arguments in `a0`–`a2` and the function number in
`a3`, then call the stub (odd address, MIPS16).

`video.ap`'s stubs:

| Stub | Group | Purpose |
|---|---|---|
| `0xbfc1f5c9` | 7 | ? |
| `0xbfc1f5cd` | `0x10` | process control (`0x0e` = exit app) |
| `0xbfc1f5d1` | `0x40` | ? |
| `0xbfc1f5d5` | `0x0f` | **system**: see below |
| `0xbfc1f5d9` | 6 | resources / UI |
| `0xbfc1f5dd` | `0x11` | file system (used by the media engine: `0x0d` read, `0x0b` seek, `0x0c` tell) |

Other apps put the same stubs at different addresses (e.g. `mainmenu.ap`: group `0xf` at
`0xbfc1f031`, group 6 at `0xbfc1f035`).

### Group `0x0f` (system) functions

| `a3` | Call | Notes |
|---|---|---|
| `0x07` | `(1, 0, 0)` → `-1` if no SD card | used before opening the card |
| `0x0d` | `h = open(name)` | opens a file **inside FWIMAGE.FW** by name (e.g. `"config.bin"`, `"dumy4m.bin"`). Pass the name from RAM. ✅ |
| `0x0f` | `seek(h, 0, offset)` | absolute seek ✅ |
| `0x11` | `read(h, buf, len)` | returns `-1` on error ✅ |
| `0x12` | `vm_read(buf, addr, len)` | read **settings storage** (see below) |
| `0x13` | `vm_write(buf, addr, …)` | write settings storage |
| `0x1c` | `ms = timer()` | millisecond counter ✅ |
| `0x31` | `sleep(ticks)` | one tick ≈ 10 ms; yields to other tasks ✅ |
| `0x33`, `0x34` | | used by the app launcher stub |

Firmware files have no "close" call in practice; the manager never closes `config.bin`.

## App IDs and launching

`manager.ap` holds the app-name table (12-byte slots, file offset `0x4c34` in 1.16):

| ID | App | ID | App |
|---|---|---|---|
| 0 | music.ap | 8 | radio.ap |
| 1 | audible.ap | 9 | tools.ap |
| 2 | **video.ap** | 10 | setting.ap |
| 3 | picture.ap | 11–13 | user1–3.ap (11 is used by the menu for the SD card item) |
| 4 | ebook.ap | 14 | **manager.ap** |
| 5 | browser.ap | 15 | **mainmenu.ap** |
| 6 | voice.ap | 16+ | playlist, config, udisk, mengine, fmengine, alarm, mtp, mtpsync, fwupdate |
| 7 | record.ap | | |

Changing a slot's name (e.g. `audible.ap` → `video.ap`) changes which file that ID
launches ✅.

### Messages

Apps ask the manager (app 14) to start the next app with the app library's *send async
message* at `0x4849f989` (same address in every app) ✅:

```c
struct { u32 type; u8 app; u8 param; u8 pad[10]; } msg = { 0x201 /* create app */, 15 /* main menu */, 4 };
((int (*)(int, void *))0x4849f989)(14 /* manager */, &msg);
return 0;    /* from the app's main */
```

The main menu launches apps with `param = 1`. Apps return to the main menu with
`param = 4`.

### App startup (video.ap)

- Entry `0x4001fe31` (bank `0x4001fe00`, file `0x3800`) runs the framework start-up and
  creates the app task at `0x4001fe01`.
- That task loads the real `main` from a literal at **file offset `0x3828`**
  (`0x4006003d` = video's main) and calls it with `jalrc`, then calls exit with its return
  value.
- Pointing that literal at your own code (an even address = MIPS32) runs your program as the
  app ✅. The original main never runs, so the rest of video.ap's banks and most of its
  resident text are free.

## Settings storage ("VM")

A small persistent store, read and written with group `0xf` functions `0x12`/`0x13`.
Each block starts with the magic `0x55aa`, and an app initialises its block with defaults
when the magic is missing (which happens after a firmware update).

| Address | Owner | Contents |
|---|---|---|
| `0x0000` | system (shared) | 0x58 bytes: global settings. `+24` = **Customize** bits, `+25` = menu looping |
| `0x0200` | several apps | |
| `0x0400` | mainmenu.ap | main-menu item list: `{0x55aa, default, count, ids[]}` (0x22 bytes, up to 14 items) |
| `0x1000`–`0x3e00` | various | per-app state |
| `0x20b6`, `0x3800` | mainmenu.ap | other state |

The shared default-settings routine is in the app library (bank `0x40ddfe00`, a copy in
13 apps). It sets the Customize byte with `li v0, 0x3f` at `0x40ddff48`.

## `config.bin`

Compiled from `config.txt`:

- `"cfg\0"` header, then from `0x10` a table of `(u32 offset, u32 length)` pairs (`0x10`–`0x207`).
- List entries are `u16 default, u16 count, u16 values[count]`. Range entries
  (`default[min~max,step]` in the text file) use another layout that wasn't decoded.
- Entry 0 = `CFG_KEY_ARRAY`, entry 1 = `MAINMENU_AP_ID_ARRAY` (default list
  `[0, 8, 1, 5, 11, 9, 10]`).
- There's no checksum. Entries can be resized if the following offsets are shifted.
- Apps read entries through the library (`0x4851f8b9(key, buf, len)`).
