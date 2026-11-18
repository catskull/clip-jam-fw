#!/bin/sh
# Build player.c into a raw MIPS32 blob for video.ap's bank at 0x4005fe00.
set -e
cd "$(dirname "$0")"
LLVM=/opt/homebrew/opt/llvm/bin
$LLVM/clang --target=mipsel-unknown-elf -march=mips32 -Os -ffreestanding -fno-builtin \
  -fno-pic -mno-abicalls -G0 -fno-jump-tables -fno-asynchronous-unwind-tables \
  -Wall -Wextra -c player.c -o player.o
/opt/homebrew/opt/lld/bin/ld.lld -m elf32ltsmip -T bank.ld --no-undefined -static player.o -o player.elf
$LLVM/llvm-objcopy -O binary -j .text player.elf player.bin
$LLVM/llvm-objdump -d --no-show-raw-insn player.elf > player.lst
$LLVM/llvm-nm -n player.elf | head
ls -l player.bin
