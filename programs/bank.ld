/* video.ap bank at file 0x3c00, mapped at 0x4005fe00, at most 0x800 bytes */
ENTRY(play)
SECTIONS
{
    . = 0x4005fe00;
    .text : {
        *(.text.entry)
        *(.text .text.*)
        *(.rodata .rodata.*)
    }
    /DISCARD/ : { *(.data*) *(.bss*) *(.sdata*) *(.sbss*) *(.MIPS.*) *(.reginfo) *(.pdr) *(.comment) *(.gnu.*) *(.note*) }
    ASSERT(SIZEOF(.text) <= 0x800, "player does not fit in the 0x800-byte bank")
}
