    .syntax unified
    .thumb
    .section .text._start,"ax",%progbits
    .global _start
    .type _start,%function
_start:
    push {r0, r1, r2, r3, r12, lr}
    sub  sp, #4
    bl   pin_gate
    add  sp, #4
    pop  {r0, r1, r2, r3, r12, lr}
    add.w r7, r5, #0x142
    b.w  0x0801B7AC
    .size _start, .-_start
