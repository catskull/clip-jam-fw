SECTIONS {
  .text 0x403a0400 : { *(.text.entry) . = ALIGN(0x40); *(.text.wrap) *(.text*) }
  /DISCARD/ : { *(.data*) *(.bss*) *(.rodata*) *(.MIPS.*) *(.reginfo) *(.pdr) *(.comment) *(.gnu.*) *(.note*) }
  ASSERT(SIZEOF(.text) <= 0x200, "too big")
}
