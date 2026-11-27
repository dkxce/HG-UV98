#!/usr/bin/env python3
"""
HG-UV98 Main-MCU (GD32F103RET6, Cortex-M3) firmware disassembler / annotator.

Address conventions of the vendor image:
  * "label" address  = file_offset + 0x08000000   (used for this listing)
  * "linked" address = file_offset + 0x08004000   (contents of the vector table
    and of literal pools; the application is linked to run at 0x08004000, the
    bootloader at 0x08000000..0x08003FFF is not part of the .bin)

Method: the image is table-driven (menu/handler pointer tables), so plain
call-graph descent only covers a fraction of the code.  Instead the code is
recovered by a resynchronising linear sweep that skips, and reports as data:
  * the vector table,
  * ASCII / GB2312 string table entries,
  * 0xFF / 0x00 / 0xBEEF fill runs (vendor "wiped" areas),
  * literal pools referenced by "ldr rX, [pc, #imm]".

Usage:  python re_disasm.py <image.bin> [outdir]
"""

import capstone
import collections
import csv
import os
import struct
import sys

BASE = 0x08004000      # listing base = the vendor link base (device addresses)
LINK = 0x08004000      # vendor link base (vector table + pool values)

PERIPH = {
    0x40000000: "TIMER1", 0x40000400: "TIMER2", 0x40000800: "TIMER3",
    0x40000C00: "TIMER4", 0x40001000: "TIMER5", 0x40001400: "TIMER6",
    0x40003000: "WWDG", 0x40003400: "IWDG", 0x40003800: "SPI1",
    0x40003C00: "SPI2", 0x40004400: "USART1", 0x40004800: "USART2",
    0x40004C00: "UART3", 0x40005000: "UART4", 0x40005400: "I2C0",
    0x40005800: "I2C1", 0x40005C00: "USBFS", 0x40006000: "CAN0",
    0x40006400: "BKP", 0x40006800: "PWR", 0x40006C00: "DAC",
    0x40020000: "DMA0", 0x40020400: "DMA1", 0x40021000: "RCU",
    0x40022000: "FMC", 0x40023000: "CRC",
    0x40010000: "AFIO", 0x40010400: "EXTI", 0x40010800: "GPIOA",
    0x40010C00: "GPIOB", 0x40011000: "GPIOC", 0x40011400: "GPIOD",
    0x40011800: "GPIOE", 0x40011C00: "GPIOF", 0x40012000: "GPIOG",
    0x40012400: "ADC0", 0x40012800: "ADC1", 0x40012C00: "TIMER0",
    0x40013400: "SPI0", 0x40013800: "USART0",
    0xE000E000: "NVIC", 0xE000E010: "SysTick", 0xE000ED00: "SCB",
    0xA0000000: "EXMC", 0xB0000000: "FMC_BANK", 0x20000000: "RAM",
}

IRQ_NAMES = [
    # GD32F10x / STM32F103 high-density IRQ 0..59 (vector table entries 16..75)
    "WWDG", "LVD", "TAMPER", "RTC", "FMC", "RCU",
    "EXTI0", "EXTI1", "EXTI2", "EXTI3", "EXTI4",
    "DMA0_Ch0", "DMA0_Ch1", "DMA0_Ch2", "DMA0_Ch3", "DMA0_Ch4",
    "DMA0_Ch5", "DMA0_Ch6", "ADC0_1", "CAN0_TX", "CAN0_RX0",
    "CAN0_RX1", "CAN0_EWMC", "EXTI5_9", "TIMER0_BRK", "TIMER0_UP",
    "TIMER0_TRG_CMT", "TIMER0_CC", "TIMER1", "TIMER2", "TIMER3",
    "I2C0_EV", "I2C0_ER", "I2C1_EV", "I2C1_ER", "SPI0",
    "SPI1", "USART0", "USART1", "USART2", "EXTI10_15",
    "RTC_ALARM", "USBFS_WKUP", "TIMER7_BRK", "TIMER7_UP", "TIMER7_TRG_CMT",
    "TIMER7_CC", "DMA0_Ch7", "DMA1_Ch0", "DMA1_Ch1", "DMA1_Ch2",
    "DMA1_Ch3", "DMA1_Ch4", "ADC2", "EXMC", "SDIO",
    "TIMER4", "SPI2", "UART3", "UART4",
]
# Recovered code zones (file offsets).  Everything else is data/assets:
#   0x00130-0x0A100  bitmap font + splash/screen assets
#   0x29B60-0x3E000  vendor-wiped 0xBEEF zone + icon bitmaps
#   0x42BD0-0x7C000  0xFF (erased / not distributed)
CODE_ZONES = [(0x0A100, 0x29B60), (0x3E000, 0x42BD0)]

SYS_NAMES = ["MSP", "RESET", "NMI", "HARDFAULT", "MEMMANAGE", "BUSFAULT",
             "USAGEFAULT", "RSVD7", "RSVD8", "RSVD9", "RSVD10", "SVCALL",
             "DEBUGMON", "RSVD13", "PENDSV", "SYSTICK"]


def periph_name(addr):
    best = None
    for base in PERIPH:
        if base <= addr < base + 0x400:
            if best is None or base > best:
                best = base
    if best is not None:
        return "%s+0x%X" % (PERIPH[best], addr - best)
    return None


class FakeInsn:
    """Stand-in for the few Thumb-2 special-register instructions that this
    capstone build refuses to decode (MRS/MSR with a system register)."""

    def __init__(self, address, mnemonic, op_str, size=4):
        self.address = address
        self.mnemonic = mnemonic
        self.op_str = op_str
        self.size = size
        self.operands = []


SYSM = {0: "apsr", 1: "ipsr", 2: "epsr", 3: "iepsr", 4: "msp", 5: "psp",
        6: "primask", 7: "basepri", 8: "basepri_max", 9: "faultmask",
        10: "control"}


class Firmware:
    def __init__(self, path):
        self.path = path
        self.d = open(path, "rb").read()
        self.size = len(self.d)
        self.md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        self.md.detail = True
        self.insns = {}
        self.data = bytearray(self.size)      # 1 = known data byte
        self.strings = {}                     # off -> (text, enc, nbytes)

    # ------------------------------------------------------------ utils
    def u32(self, off):
        if off < 0 or off + 4 > self.size:
            return None
        return struct.unpack_from("<I", self.d, off)[0]

    @staticmethod
    def label(off):
        return BASE + off

    @staticmethod
    def off_of(linked):
        return linked - LINK

    def valid_off(self, off):
        return 0 <= off < self.size

    # ------------------------------------------------------------ strings
    def scan_strings(self):
        d, n = self.d, self.size
        i = 0
        while i < n:
            start = i
            chars = []
            enc = "ascii"
            nb = 0
            while i < n:
                b = d[i]
                if 0x20 <= b < 0x7F:
                    chars.append(chr(b))
                    i += 1
                    nb += 1
                elif 0xA1 <= b <= 0xF7 and i + 1 < n and 0xA1 <= d[i + 1] <= 0xFE:
                    try:
                        chars.append(bytes(d[i:i + 2]).decode("gb2312"))
                        enc = "gb2312"
                    except Exception:
                        break
                    i += 2
                    nb += 2
                else:
                    break
            text = "".join(chars)
            # real string records in this image are NUL terminated and start
            # after a non-text byte; anything else is data that happens to
            # decode as text (short branch stubs decode as GB2312 otherwise)
            terminated = i >= n or d[i] == 0
            preceded = start == 0 or not (0x20 <= d[start - 1] < 0x7F or
                                          (0xA1 <= d[start - 1] <= 0xF7))
            if len(text) >= 4 and terminated and preceded and                     any(c.isalnum() for c in text):
                self.strings[start] = (text, enc, nb)
                for k in range(nb):
                    self.data[start + k] = 1
                i = max(i, start + 1)
            else:
                i = start + 1

    # ------------------------------------------------------------ vectors
    def vectors(self):
        out = []
        for i in range(76):
            v = self.u32(i * 4)
            if v is None:
                continue
            if i == 0:
                out.append((i, "MSP", v, None))
                continue
            nm = SYS_NAMES[i] if i < 16 else (
                IRQ_NAMES[i - 16] if i - 16 < len(IRQ_NAMES) else "IRQ%d" % (i - 16))
            off = self.off_of(v & ~1)
            out.append((i, nm, v, off if self.valid_off(off) else None))
        return out

    # ------------------------------------------------------------ fill map
    def mark_fill(self):
        d = self.d
        for i in range(self.size):
            self.data[i] = 1
        # unmarked later by the sweep; here we only pre-mark non-code zones
        self.noncode = bytearray(self.size)
        i = 0
        while i < self.size - 1:
            if d[i] == 0xFF:
                j = i
                while j < self.size and d[j] == 0xFF:
                    j += 1
                if j - i >= 4:
                    for k in range(i, j):
                        self.noncode[k] = 1
                i = j
            elif d[i] == 0 and i + 1 < self.size and d[i + 1] == 0:
                j = i
                while j < self.size - 1 and d[j] == 0 and d[j + 1] == 0:
                    j += 2
                if j - i >= 4:
                    for k in range(i, j):
                        self.noncode[k] = 1
                i = j
            elif d[i:i + 2] == b"\xef\xbe" or d[i:i + 2] == b"\xef\x9e":
                j = i
                while j + 1 < self.size and d[j:j + 2] in (b"\xef\xbe", b"\xef\x9e"):
                    j += 2
                if j - i >= 4:
                    for k in range(i, j):
                        self.noncode[k] = 1
                i = j
            else:
                i += 1
        for k in range(0x130):
            self.noncode[k] = 1                    # vector table
        for off, (t, e, nb) in self.strings.items():
            for k in range(nb + 1):
                if off + k < self.size:
                    self.noncode[off + k] = 1

    # ------------------------------------------------------------ sweep
    @staticmethod
    def in_code(off):
        for a, b in CODE_ZONES:
            if a <= off < b:
                return True
        return False

    def poolish(self, off):
        """A literal-pool candidate: the word must look like data, not code.

        Guards against bogus ldr instructions produced by mis-decoding, which
        would otherwise mask real instructions at the referenced address.
        """
        v = self.u32(off)
        if v is None:
            return False
        if v in (0, 0xFFFFFFFF, 0x7FFFFFFF):
            return True
        if 0x08000000 <= v < 0x08080000:      # flash pointer
            return True
        if 0x20000000 <= v < 0x20010000:      # RAM pointer
            return True
        if 0x40000000 <= v < 0x50000000 or 0xE0000000 <= v < 0xE0010000:
            return True                        # peripheral / SCB
        if v < 0x10000:                        # small constant
            return True
        if 0x3F000000 <= v < 0x40800000:       # float 0.5 .. 4.0
            return True
        return False

    def decode_at(self, off):
        chunk = self.d[off:off + 4]
        if len(chunk) < 2:
            return None
        hw = struct.unpack_from("<H", chunk, 0)[0]
        if hw in (0xFFFF, 0x0000, 0xBEEF, 0x9EEF, 0xBF00):
            if hw != 0xBF00:                       # 0xBF00 = nop, legal
                return None
        ins = next(self.md.disasm(chunk, self.label(off)), None)
        if ins is not None:
            return ins
        if len(chunk) == 4:
            h1, h2 = struct.unpack_from("<HH", chunk, 0)
            if h1 == 0xF3EF and (h2 & 0xF000) == 0x8000:
                rd, sysm = (h2 >> 8) & 0xF, h2 & 0xFF
                return FakeInsn(self.label(off), "mrs", "r%d, %s" % (
                    rd, SYSM.get(sysm, "sysm%d" % sysm)))
            if h1 == 0xF380 and (h2 & 0xFF00) == 0x8800:
                rn, sysm = (h2 >> 8) & 0xF, h2 & 0xFF
                return FakeInsn(self.label(off), "msr", "%s, r%d" % (
                    SYSM.get(sysm, "sysm%d" % sysm), rn))
            if h1 == 0xF3BF and h2 in (0x8F4F, 0x8F5F, 0x8F6F):
                return FakeInsn(self.label(off), "barrier", {
                    0x8F4F: "dsb sy", 0x8F5F: "dmb sy", 0x8F6F: "isb sy"}[h2])
        return None

    def sweep(self):
        pools = set()
        for iteration in range(3):
            self.insns = {}
            self.pools = pools
            off = 0
            bad_run = 0
            while off < self.size - 1:
                if self.noncode[off] or off in pools or not self.in_code(off):
                    off += 2
                    bad_run = 0
                    continue
                ins = self.decode_at(off)
                if ins is None:
                    bad_run += 1
                    off += 2
                    continue
                bad_run = 0
                self.insns[off] = ins
                # literal pool reference
                if ins.mnemonic.startswith("ldr") and ins.operands and \
                        ins.operands[0].type == capstone.arm.ARM_OP_REG and \
                        len(ins.operands) > 1 and ins.operands[1].type == capstone.arm.ARM_OP_MEM:
                    m = ins.operands[1].mem
                    if m.base == capstone.arm.ARM_REG_PC and not m.index:
                        lit = ((ins.address + 4) & ~3) + m.disp - BASE
                        if self.valid_off(lit) and self.poolish(lit):
                            pools.add(lit)
                off += ins.size

    # ------------------------------------------------------------ symbols
    def build_symbols(self):
        starts, labels = set(), set()
        for i, nm, v, off in self.vectors():
            if off is not None and off in self.insns:
                starts.add(off)
        for off, ins in self.insns.items():
            for op in ins.operands:
                if op.type == capstone.arm.ARM_OP_IMM and ins.mnemonic in (
                        "bl", "blx", "b", "b.w", "beq", "bne", "bcc", "bcs",
                        "bmi", "bpl", "bvs", "bvc", "bhi", "bls", "bge", "blt",
                        "bgt", "ble", "cbz", "cbnz"):
                    t = op.imm - BASE
                    if self.valid_off(t) and t in self.insns:
                        labels.add(t)
                        if ins.mnemonic in ("bl", "blx"):
                            starts.add(t)
            if ins.mnemonic in ("push", "stmdb") and any(
                    o.type == capstone.arm.ARM_OP_REG and o.reg == capstone.arm.ARM_REG_LR
                    for o in ins.operands):
                # a prologue only starts a function when it follows a
                # terminator / padding, not in the middle of a body
                prev = off - 2
                ok = True
                if prev in self.insns:
                    p = self.insns[prev]
                    ok = p.mnemonic in ("b", "b.w", "bx", "pop", "ldm") or (
                        p.mnemonic == "pop" and any(
                            o.type == capstone.arm.ARM_OP_REG and o.reg == capstone.arm.ARM_REG_PC
                            for o in p.operands))
                if ok:
                    starts.add(off)
        self.func_starts = sorted(starts)
        self.labels = sorted(labels - starts)
        self.sym = {}
        for off in self.func_starts:
            self.sym[off] = "FUN_%08X" % self.label(off)
        for off in self.labels:
            self.sym[off] = "LAB_%08X" % self.label(off)
        for off in sorted(self.strings):
            self.sym.setdefault(off, "STR_%08X" % self.label(off))
        # vector handlers keep their hardware name
        for i, nm, v, off in self.vectors():
            if off is not None and off in self.insns:
                self.sym[off] = "IRQ_%s" % nm if i >= 16 else "SYS_%s" % nm

    def sym_at(self, off):
        if off in self.sym:
            return self.sym[off]
        best = None
        for s in self.sym:
            if s <= off and (best is None or s > best):
                best = s
        if best is not None and off - best < 0x2000:
            return "%s+0x%X" % (self.sym[best], off - best)
        return "loc_%08X" % self.label(off)

    def func_end(self, fn):
        idx = self.func_starts.index(fn)
        nxt = self.func_starts[idx + 1] if idx + 1 < len(self.func_starts) else self.size
        end = fn
        for off in range(fn, nxt):
            if off in self.insns:
                end = off + self.insns[off].size
        return end

    # ------------------------------------------------------------ comments
    def comment(self, ins):
        cs = []
        if ins.mnemonic.startswith("ldr"):
            for op in ins.operands:
                if op.type == capstone.arm.ARM_OP_MEM and \
                        op.mem.base == capstone.arm.ARM_REG_PC and not op.mem.index:
                    lit = ((ins.address + 4) & ~3) + op.mem.disp - BASE
                    val = self.u32(lit)
                    if val is None:
                        continue
                    tgt = self.off_of(val)
                    if self.valid_off(tgt) and not (val & 1):
                        if tgt in self.strings:
                            cs.append('"%s"' % self.strings[tgt][0][:44])
                        elif tgt in self.sym:
                            cs.append("&" + self.sym[tgt])
                        else:
                            cs.append("%08X" % val)
                    elif self.valid_off(tgt) and (val & 1):
                        cs.append("%08X (thumb)" % val)
                    else:
                        nm = periph_name(val)
                        cs.append("%08X%s" % (val, " " + nm if nm else ""))
        if ins.mnemonic in ("ldr", "str", "ldrb", "strb", "ldrh", "strh",
                            "ldrsh", "ldrsb", "ldm", "stm", "ldmia", "stmia",
                            "ldrd", "strd") and ins.operands:
            m = None
            for op in ins.operands:
                if op.type == capstone.arm.ARM_OP_MEM:
                    m = op.mem
            if m is not None and not m.index and m.base in (
                    0, capstone.arm.ARM_REG_PC) and m.disp >= 0x40000000:
                nm = periph_name(m.disp)
                if nm:
                    cs.append(nm)
        if ins.mnemonic in ("bl", "blx", "b", "b.w") and ins.operands and \
                ins.operands[0].type == capstone.arm.ARM_OP_IMM:
            t = ins.operands[0].imm - BASE
            if t in self.sym:
                cs.append(self.sym[t])
        return ("; " + " | ".join(cs)) if cs else ""


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "out"
    os.makedirs(outdir, exist_ok=True)
    fw = Firmware(path)
    name = os.path.splitext(os.path.basename(path))[0]
    fw.scan_strings()
    fw.mark_fill()
    fw.sweep()
    fw.build_symbols()

    # ---------------------------------------------------------- regions
    regions = []
    cur = None
    for off in range(fw.size):
        if off in fw.insns:
            kind = "code"
        elif off < 0x130:
            kind = "vectors"
        elif off in fw.strings:
            kind = "string"
        elif fw.d[off] == 0xFF:
            kind = "fill-FF"
        elif fw.d[off] == 0x00:
            kind = "fill-00"
        elif fw.d[off:off + 2] in (b"\xef\xbe", b"\xef\x9e"):
            kind = "fill-BEEF"
        elif off in fw.pools:
            kind = "pool"
        else:
            kind = "data"
        if cur and cur[2] == kind:
            cur[1] = off + 1
        else:
            if cur:
                regions.append(cur)
            cur = [off, off + 1, kind]
    regions.append(cur)
    with open(os.path.join(outdir, "regions.txt"), "w", encoding="utf-8") as f:
        f.write("# file offset   label addr   size    kind\n")
        for s, e, k in regions:
            if e - s < 16:
                continue
            f.write("%08X  %08X  %7d  %s\n" % (s, fw.label(s), e - s, k))

    # ---------------------------------------------------------- listing
    lst = os.path.join(outdir, name + ".lst")
    with open(lst, "w", encoding="utf-8") as f:
        f.write(";; HG-UV98 main MCU (GD32F103RET6, Cortex-M3 / Thumb-2)\n")
        f.write(";; %s, %d bytes (0x%X)\n" % (
            os.path.basename(path), fw.size, fw.size))
        f.write(";; listing address = file offset + 0x%08X\n" % BASE)
        f.write(";; uploaded/linked base = 0x%08X (vector + literal pool values)\n" % LINK)
        f.write(";; %d instructions, %d functions, %d strings\n\n" % (
            len(fw.insns), len(fw.func_starts), len(fw.strings)))
        off = 0
        while off < fw.size:
            if off in fw.insns:
                if off in fw.sym:
                    f.write("\n%s:" % fw.sym[off])
                    if off in fw.strings:
                        f.write('   ; "%s"' % fw.strings[off][0])
                    f.write("\n")
                ins = fw.insns[off]
                raw = fw.d[off:off + ins.size].hex()
                f.write("    %08X  %-10s %-9s %-30s %s\n" % (
                    fw.label(off), raw, ins.mnemonic, ins.op_str, fw.comment(ins)))
                off += ins.size
                continue
            # non-code: skip to next instruction, note the block
            start = off
            while off < fw.size and off not in fw.insns:
                off += 1
            n = off - start
            if n >= 8:
                kinds = collections.Counter()
                for k in range(start, off):
                    b = fw.d[k]
                    if k in fw.strings:
                        kinds["string"] += 1
                    elif b == 0xFF:
                        kinds["FF"] += 1
                    elif b == 0:
                        kinds["00"] += 1
                    elif fw.d[k:k + 2] in (b"\xef\xbe", b"\xef\x9e"):
                        kinds["BEEF"] += 1
                    elif k in fw.pools:
                        kinds["pool"] += 1
                    else:
                        kinds["data"] += 1
                desc = ",".join("%s:%d" % (a, b) for a, b in kinds.most_common(3))
                f.write("\n; ---- %d bytes of non-code at %08X (%s) ----\n" % (
                    n, fw.label(start), desc))
            else:
                for k in range(start, off, 2):
                    f.write("    %08X  .byte %s\n" % (
                        fw.label(k), " ".join("%02X" % x for x in fw.d[k:k + 2])))
        f.write("\n;; end of listing\n")

    # ---------------------------------------------------------- functions
    with open(os.path.join(outdir, "functions.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entry", "file_off", "size", "insns", "callers",
                    "callees", "strings"])
        callers = collections.Counter()
        for off, ins in fw.insns.items():
            if ins.mnemonic in ("bl", "blx") and ins.operands and \
                    ins.operands[0].type == capstone.arm.ARM_OP_IMM:
                callers[ins.operands[0].imm - BASE] += 1
        for fn in fw.func_starts:
            end = fw.func_end(fn)
            calls, strs, cnt = set(), [], 0
            for off in range(fn, end):
                ins = fw.insns.get(off)
                if ins is None:
                    continue
                cnt += 1
                if ins.mnemonic in ("bl", "blx") and ins.operands and \
                        ins.operands[0].type == capstone.arm.ARM_OP_IMM:
                    t = ins.operands[0].imm - BASE
                    if t != fn and t in fw.sym:
                        calls.add(fw.sym[t][:12])
                if ins.mnemonic.startswith("ldr"):
                    for op in ins.operands:
                        if op.type == capstone.arm.ARM_OP_MEM and \
                                op.mem.base == capstone.arm.ARM_REG_PC and not op.mem.index:
                            lit = ((ins.address + 4) & ~3) + op.mem.disp - BASE
                            val = fw.u32(lit)
                            if val is None:
                                continue
                            t = fw.off_of(val)
                            if fw.valid_off(t) and t in fw.strings:
                                strs.append(fw.strings[t][0][:40])
            w.writerow(["%08X" % fw.label(fn), "0x%X" % fn, end - fn, cnt,
                        callers.get(fn, 0), ";".join(sorted(calls)),
                        " | ".join(strs[:6])])

    # ---------------------------------------------------------- symbols
    with open(os.path.join(outdir, "symbols.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["addr", "file_off", "name", "kind"])
        for off in sorted(fw.sym):
            kind = "func" if off in fw.func_starts else (
                "string" if off in fw.strings else "label")
            w.writerow(["%08X" % fw.label(off), "0x%X" % off, fw.sym[off], kind])
        w.writerow(["%08X" % BASE, "0x0", "VECTOR_TABLE", "vectors"])

    # ---------------------------------------------------------- strings
    with open(os.path.join(outdir, "strings.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["addr", "file_off", "encoding", "chars", "text"])
        for off, (text, enc, nb) in sorted(fw.strings.items()):
            w.writerow(["%08X" % fw.label(off), "0x%X" % off, enc, len(text), text])

    # ---------------------------------------------------------- vectors
    with open(os.path.join(outdir, "vector_table.txt"), "w", encoding="utf-8") as f:
        f.write("idx  handler        value       file_off  target\n")
        for i, nm, v, off in fw.vectors():
            f.write("[%2d] %-13s %08X   %s  %s\n" % (
                i, nm, v,
                ("0x%06X" % off) if off is not None else "  --   ",
                (fw.sym.get(off) or "FUN_%08X" % fw.label(off)) if off is not None else
                ("RAM 0x%08X" % v if i == 0 else "outside image")))

    print("image        :", os.path.basename(path))
    print("instructions :", len(fw.insns))
    print("functions    :", len(fw.func_starts))
    print("strings      :", len(fw.strings))
    print("pool words   :", len(fw.pools))
    print("code bytes   :", sum(i.size for i in fw.insns.values()))
    print("listing      :", lst)


if __name__ == "__main__":
    main()
