/* Code split across video.ap's banks 0x4005fe00 (file 0x3c00) and 0x4009fe00
 * (file 0x4400), 0x800 bytes each, and its resident text section (0xbfc1ee00,
 * file 0x2800, up to the syscall stubs at 0xbfc1f5c8 -> 0x7c8 bytes). */
SECTIONS
{
    .bank 0x4005fe00 : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.*)
    }
    .bank2 0x4009fe00 : { *(.bank2) }
    .res 0xbfc1ee00 : {
        *(.res)
        *(.res.data)
    }
    /DISCARD/ : { *(.data*) *(.bss*) *(.sdata*) *(.sbss*) *(.MIPS.*) *(.reginfo) *(.pdr) *(.comment) *(.gnu.*) *(.note*) }
    ASSERT(SIZEOF(.bank) <= 0x800, "bank code exceeds 0x800 bytes")
    ASSERT(SIZEOF(.bank2) <= 0x800, "bank2 code exceeds 0x800 bytes")
    ASSERT(SIZEOF(.res) <= 0x7c8, "resident code would overwrite the syscall stubs")
}
