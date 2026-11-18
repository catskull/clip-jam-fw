# Writing native code for the Clip Jam

## Toolchain

LLVM/Clang with the MIPS backend and LLD (`brew install llvm lld` on macOS).

```sh
clang --target=mipsel-unknown-elf -march=mips32 -Oz \
      -ffreestanding -fno-builtin -fno-pic -mno-abicalls -G0 \
      -fno-jump-tables -fno-asynchronous-unwind-tables -mno-check-zero-division \
      -c prog.c -o prog.o
ld.lld -m elf32ltsmip -T prog.ld -e entry --no-undefined -static prog.o -o prog.elf
llvm-objcopy -O binary -j .bank prog.elf prog_bank.bin
```

- **Use MIPS32, not MIPS16.** LLVM's MIPS16 support fails on simple code ("expected an
  immediate"). MIPS32 runs fine on the 4KEc and interworks with the firmware's MIPS16 code.
- `-G0 -mno-abicalls -fno-pic`: no `$gp`, no GOT. The firmware doesn't set up `$gp`
  for you. Check with `llvm-objdump -d … | grep -c '\$gp'`.
- `-fno-jump-tables`: jump tables are constant data that could land in another bank.
- `-mno-check-zero-division` saves space (no `teq` traps).
- No libc: write your own loops. With `--no-undefined`, the link fails if the compiler emits
  `memset`/`memcpy` or 64-bit division helpers. Avoid 64-bit `/` and `%`.

## Where code can live inside video.ap

App 2 (`video.ap`) is a good host: its original main never runs once you redirect the
launcher (literal at file `0x3828`), so all of this is free:

| Region | Address | File offset | Size | Notes |
|---|---|---|---|---|
| bank | `0x4005fe00` | `0x3c00` | 0x800 | entry: the launcher jumps to its start |
| bank | `0x4009fe00` | `0x4400` | 0x800 | more code (`0x400dfe00`, `0x4011fe00`, … also exist) |
| resident text | `0xbfc1ee00` | `0x2800` | 0x7c8 | **keep the stubs at `0xbfc1f5c8`–`0xbfc1f5df`** |
| RAM | `0x9fc1d208`–`0x9fc1d6cc` | – | ~1.2 KB | video.ap's `.bss`; `0x9fc1d200/204` belong to the launcher |
| data | `dumy4m.bin` | (FWIMAGE file) | 4,280,320 B | read with system calls `0x0d`/`0x0f`/`0x11` |

The stack is the app task's stack. Keep frames small; put big buffers in the bss area.

### Linker script (two banks + resident text)

```ld
SECTIONS
{
    .bank  0x4005fe00 : { *(.text.entry) *(.text .text.*) *(.rodata .rodata.*) }
    .bank2 0x4009fe00 : { *(.bank2) }
    .res   0xbfc1ee00 : { *(.res) *(.res.data) }
    /DISCARD/ : { *(.data*) *(.bss*) *(.sdata*) *(.sbss*) *(.MIPS.*) *(.reginfo) *(.pdr) *(.comment) *(.gnu.*) *(.note*) }
    ASSERT(SIZEOF(.bank)  <= 0x800, "bank too big")
    ASSERT(SIZEOF(.bank2) <= 0x800, "bank2 too big")
    ASSERT(SIZEOF(.res)   <= 0x7c8, "would overwrite the syscall stubs")
}
```

Put functions in sections with attributes (`__attribute__((section(".res"), noinline,
long_call)))`). Keep constant data (sprites, fonts, tables) in `.res`, which is always
resident.

## Pitfalls (all hit during development)

1. **`jal` can't leave its 256 MB region.** Bank code (`0x4…`) calling resident code
   (`0xbfc…`) with `jal` lands at `0x4fc…`. LLD doesn't complain. Mark resident functions
   `long_call` (or use `-mlong-calls`), then check every direct jump in the disassembly
   lands inside one of your regions (see `docs/tools.md`).
2. **`-Os` inlines helpers into every caller** and blows the 2 KB bank budget. Use `-Oz`
   and `noinline` helpers placed in `.res`.
3. **Calling MIPS16 firmware code:** call through a function pointer with the odd address
   (`jalr`). Calling into your MIPS32 code: let the firmware call it through a function
   pointer (even address). **Don't patch a MIPS16 `jalx` into firmware code.** It rebooted
   the player; the stock firmware never uses `jalx`.
4. **System-call stubs return via `ra`.** Never fall through a stub.
5. **The OLED and NAND share pins.** Always take the LCD lock around screen writes.
6. **Busy-waiting starves the system.** Pace frames with the millisecond timer and sleep in
   ticks (`sys(0x31, n)`) when more than ~12 ms remain.
7. **Pass file names from RAM**, not from bank memory, when calling the kernel.
8. **Return to the main menu** by sending the *create app* message for app 15 before
   returning from main, as the stock apps do. Returning without it wasn't tested.

## Calling conventions (C)

```c
typedef int (*fn4)(int, int, int, int);
#define SYS(a0, a1, a2, f)  (((fn4)0xbfc1f5d5)((int)(a0), (int)(a1), (int)(a2), (f)))  /* group 0xf */
#define LCD_LOCK()          (((void (*)(void))0xbfc21331)())
#define LCD_UNLOCK()        (((void (*)(void))0xbfc21379)())
#define SEND_MSG(app, msg)  (((fn4)0x4849f989)((app), (int)(msg), 0, 0))
#define LCD_CTL  (*(volatile unsigned *)0xc00d0008)
#define LCD_DATA (*(volatile unsigned *)0xc00d0010)
#define KEY_ADC  (*(volatile unsigned char *)0xc002003c)
```

## Testing on the Mac first

`programs/host_raiders.c` compiles the *same* `raiders.c` for the host with `-DHOST`. The
hardware macros become arrays, the clock is simulated, and a script supplies button
presses. Frames are saved as PBM images. Run it with AddressSanitizer:

```sh
cc -O1 -fsanitize=address,undefined -DHOST programs/host_raiders.c -o host_raiders && ./host_raiders
```

This caught real bugs before flashing (sprites drawn off-screen, a broken jump target). Write
the game so that `#ifndef HOST` guards only the hardware definitions.

## Verifying a build

Before packaging:

- section sizes within limits (the linker `ASSERT`s);
- no `$gp` use;
- every direct `j`/`jal` target inside your regions;
- every `lui` constant is one you expect.

After packaging: decrypt and unpack the new `upgrade.hex` with the normal tools, and diff
every file against stock. Only the intended files should differ.
