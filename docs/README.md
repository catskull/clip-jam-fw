# Documentation

Notes from reverse engineering the SanDisk Clip Jam firmware (version 1.16, standard model)
and building custom code for it. Addresses are **virtual addresses** as seen by the CPU
unless they are called *file offsets*. "1.16" files were checked; 1.10 is identical where
noted.

| Document | Covers |
|---|---|
| [firmware-format.md](firmware-format.md) | `upgrade.hex` (FWU v3) container, the cipher, AFI archive, `FWIMAGE.FW` (LFI), every checksum |
| [hardware.md](hardware.md) | SoC, OLED display and how to drive it, buttons, bootloader, memory map |
| [app-runtime.md](app-runtime.md) | `.ap`/`.drv` file layout, code banks, system-call stubs and known functions, inter-app messages, settings storage |
| [resources.md](resources.md) | `.sty` resource files (pictures, strings, UI styles), `.mcg` menu files, `config.bin` |
| [main-menu.md](main-menu.md) | Main-menu internals, the *Customize* switches, and the extra menu entry |
| [writing-native-code.md](writing-native-code.md) | Toolchain, placing code in an app, linker scripts, MIPS16/MIPS32 interworking, pitfalls, host testing |
| [programs.md](programs.md) | The frame player, the 3D cube, Sky Raiders |
| [flashing-and-recovery.md](flashing-and-recovery.md) | Updating, recovery mode (ADFU), lessons learned |
| [tools.md](tools.md) | Reference for every script in `tools/` |

## Conventions

- `0x4005fe00`-style addresses in the `0x40…`–`0x48…` and `0x7…` ranges are **bank**
  addresses (paged code, see app-runtime.md). `0xbfc1…` is resident code, `0x9fc1…` is RAM,
  `0xc0…` is hardware registers.
- MIPS16 function pointers are odd (bit 0 = ISA mode). MIPS32 entry points are even.
- "Group *g*, function *f*" means a system call made with `v1 = g` and `a3 = f`.
