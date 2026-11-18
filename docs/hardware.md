# Hardware notes

| Part | Details |
|---|---|
| SoC | Actions Semiconductor **ATJ2127**: MIPS32 4KEc core with the MIPS16e ASE |
| Firmware ISA | Almost entirely MIPS16e. The kernel init (`ker_init.bin`) is MIPS32. MIPS32 code runs fine. |
| Display | 128×64 monochrome **OLED**, SSD1306-compatible controller |
| Storage | 8 GB SanDisk NAND (SDTNQFAMA-008G); microSD slot |
| USB IDs | normal: `0781:74f0` "SanDisk Clip Jam"; recovery (ADFU): `10d6:10d6` |

## Display

The OLED is driven through the SoC's LCD interface:

| Register | Use |
|---|---|
| `0xc00d0008` bit 0 | D/C line: `0` = command, `1` = data |
| `0xc00d0010` | write a byte (as a 32-bit store) to the controller |

Standard SSD1306 *page addressing*: send `0xB0+page`, `0x00 | (col & 0xF)`,
`0x10 | (col >> 4)` as commands, then 128 data bytes per page. Each data byte is one column
of 8 pixels, **bit 0 = top**. A full frame is 8 pages × 128 bytes = 1024 bytes.

**The LCD pins are shared with the NAND.** Wrap screen writes in the LCD driver's
lock/unlock routines (resident code, callable from anywhere):

| Address | Function |
|---|---|
| `0xbfc21331` | acquire the LCD bus (reference counted) |
| `0xbfc21379` | release it |
| `0xbfc20f01` | stock "write command byte" |

```c
LCD_LOCK();
for (page = 0; page < 8; page++) {
    LCD_CTL &= ~1;  LCD_DATA = 0xb0 + page;  LCD_DATA = 0x00;  LCD_DATA = 0x10;
    LCD_CTL |= 1;   for (x = 0; x < 128; x++) LCD_DATA = *p++;
}
LCD_UNLOCK();
```

### How the stock UI draws

The UI renders into an RGB565 framebuffer and the driver's blit (`0xbfc20f2c`) lights a
pixel **only when its value is exactly `0xFFFF`**. Many leftover colour images in the
resources therefore show up black. Artwork for this device must be pure white on black.

### Display initialisation lives in the bootloader

The SSD1306 init sequence (`AE, D5 80, A8 3F, … A4, A6, AF` as `FD xx` command /
`FE xx` delay / `FF` end bytes) appears both in `drv_lcd.drv` (file offset `0x2a9c`) and in
every `BREC*.BIN` (`0x152d`). **Only the bootloader's copy runs**; the driver's copy is
dead code. The main firmware never re-initialises the panel, so patching the driver's table
does nothing.

To change display state from the main firmware, hook a live driver path instead. Example
(display inversion, tested): the contrast routine at bank address `0x17064c88`
(`drv_lcd.drv` file offset `0x2488`, driver API table entry at file `0x1804`) begins with
"wait 1 ms, send `0x81`". Replacing the 8-byte wait with `li a0,0xA7; lw v0,lit(pc);
jalrc v0; nop` makes it send *inverse display* every time brightness is applied.

## Buttons

The key driver (`key.drv`) reads three sources:

| Source | Keys |
|---|---|
| PMU `0xc0020054` (a status bit) | one key (table index 0) |
| Resistor-ladder ADC `0xc002003c & 0x3f` | seven keys, thresholds `4, 10, 16, 26, 32, 40, 50` (ADC below the threshold selects that band; ≥ 50 = no key) |
| GPIO A22 (`0xc0090008` bit 22, active low) | one key (table index 8) |

`config.txt` maps physical keys to key codes: `CFG_KEY_ARRAY = [5, 6, 4, 3, 10, 8, 7, 11, 1]`.
Only one ladder key can be read at a time.

For custom code the simplest approach is to read the ADC byte and classify it into a band
0–6 (7 = none). Which band is which physical button wasn't mapped; Sky Raiders asks the
player to press its keys instead (see programs.md).

## Bootloader / boot ROM

- Boot ROM → **MBREC** (first stage) → **BREC** (second stage: shows the logo, initialises
  the display, holds recovery mode) → kernel + apps from `FWIMAGE.FW`.
- BREC loads at `0xbfc1d000` (MIPS16). Its entry checks VBUS (`0xc008041a & 0x40`,
  `0xc0020050 & 0x80`) and GPIO A22.
- **Recovery mode:** with the player off, hold **Vol+ and Vol−** and switch it on → firmware
  upgrade screen, USB `10d6:10d6`.
- The update file contains 11 BREC variants (`BRECF644`…`BRECF654`, one per flash type) plus
  `CARDBREC`. All tools here leave every bootloader file byte-identical.

## Memory map (as used by apps)

| Range | Contents |
|---|---|
| `0x9fc19000`… | kernel data |
| `0x9fc1d200`… | the running app's `.data` + `.bss` (video.ap: 8 + 0x4c4 bytes) |
| `0xbfc1a000`… | kernel resident text |
| `0xbfc1ee00`… | the running app's **resident text** (≤ ~2 KB, ends with its syscall stubs) |
| `0xbfc20600`… | `key.drv` resident text |
| `0xbfc20f00`… | `drv_lcd.drv` resident text |
| `0xc0000000`… | CMU (clocks) |
| `0xc0020000`… | PMU (power, key ADC) |
| `0xc0090000`… | GPIO |
| `0xc00d0000`… | LCD interface |
| `0x4…`, `0x48…`, `0x7…` | paged code banks (see app-runtime.md) |
