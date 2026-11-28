ENTRY(_start)
SECTIONS
{
  . = 0x0804A000;
  .text : {
    *(.text._start)
    *(.text*)
  }
  .rodata : {
    *(.rodata*)
  }
  .pinblob : {
    *(.pinblob)
  }
  .data : {
    *(.data*)
  }
  /DISCARD/ : {
    *(.ARM.exidx*)
    *(.ARM.attributes)
    *(.comment*)
    *(.note*)
  }
}
