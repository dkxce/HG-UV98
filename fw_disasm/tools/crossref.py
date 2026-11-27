#!/usr/bin/env python3
"""Cross-check the address anchors published in agamez/hg-uv98-firmware
(docs/README/RESEARCH_LOG, "label" convention = file + 0x08000000) against
this analysis of V1.2_211026 and V1.0.1_190619-KT (device = file + 0x08004000).

Output: out/crossref.csv
"""
import sys, csv, bisect
sys.path.insert(0, "tools")
import re_disasm as R

LBL = 0x08000000      # their convention
DEV = 0x08004000      # device / linked

ANCHORS = [
    ("main", 0x08029120),
    ("hw_init", 0x080290D0),
    ("hw_init/sub (GPIO+RF+USART1 init)", 0x08029080),
    ("ui_state_set(screen)", 0x08010530),
    ("dual-pane redraw", 0x08010CD4),
    ("value clamp", 0x0801715C),
    ("USART2 init", 0x0801F810),
    ("USART2 RX ISR", 0x0801F920),
    ("USART2 TX", 0x0801FEAA),
    ("AT dispatcher", 0x08010128),
    ("'$A01,' sender", 0x08016702),
    ("USART1 init (GPS)", 0x0802932C),
    ("USART1 RX ISR (GPS)", 0x080292F8),
    ("OSTaskCreateExt", 0x080249A4),
    ("OSTaskNameSet", 0x08024A6C),
    ("OSStart", 0x08027392),
    ("UI task loop", 0x08029178),
    ("protocol bridge ($A00/$A01)", 0x0800FE58),
    ("protocol state machine", 0x08010302),
    ("per-pass routine", 0x08015DCC),
    ("every-17th-pass housekeeping", 0x0800ED24),
    ("key_scan", 0x080281A6),
    ("key_get_code", 0x080282FC),
    ("UI key task body", 0x08019DCC),
    ("memcpy-like", 0x080198E0),
    ("memset-like", 0x080198C0),
    ("memcmp", 0x0801F610),
    ("mem helper 0x080199A0", 0x080199A0),
    ("RF chip init", 0x080227AA),
    ("SystemInit slice", 0x08029008),
    ("fine-tune key 11", 0x08014660),
    ("fine-tune key 12", 0x0801471E),
    ("NVIC_Init", 0x08026E26),
    ("USART_Init", 0x08026C5C),
    ("irq_install", 0x08026E18),
]


def load(path):
    fw = R.Firmware(path)
    fw.scan_strings()
    fw.mark_fill()
    fw.sweep()
    fw.build_symbols()
    return fw


def locate(fw, dev_addr):
    """(kind, function_start_or_None) for a device address."""
    off = dev_addr - DEV
    if not fw.valid_off(off):
        return "outside image", None
    if off in fw.insns:
        if off in fw.func_starts:
            return "exact function start", off
        starts = [s for s in fw.func_starts if s <= off]
        if starts and off - starts[-1] < 0x800:
            return "inside function", starts[-1]
        return "inside code (no function)", None
    if off in fw.strings:
        return "string", None
    return "not code", None


def main():
    v12 = load("Lanchonlh HG-UV98 Radio Firmware V1.2_211026.bin")
    kt = load("v101/V1.0.1_190619-KT.bin")

    # identical-body map: KT function -> V1.2 function
    kt2v12 = {}
    with open("out/diff_functions.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kt2v12[int(row["old_addr"], 16)] = int(row["new_addr"], 16)

    rows = []
    for name, lbl in ANCHORS:
        dev = lbl + 0x4000
        k_kind, k_fn = locate(kt, dev)
        v_kind, v_fn = locate(v12, dev)
        equiv = kt2v12.get(k_fn) if k_fn is not None else None
        if equiv is None and v_fn is not None:
            equiv = v_fn
        rows.append([
            name, "%08X" % lbl, "%08X" % dev,
            k_kind, ("%08X" % (DEV + k_fn)) if k_fn is not None else "",
            v_kind, ("%08X" % (DEV + v_fn)) if v_fn is not None else "",
            ("%08X" % (DEV + equiv)) if equiv is not None else "",
            "identical body" if (k_fn is not None and equiv == kt2v12.get(k_fn)
                                 and k_fn in kt2v12) else
            ("present, shifted" if equiv is not None else ""),
        ])

    with open("out/crossref.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["anchor", "their_label", "device_addr", "kt_status",
                    "kt_function", "v12_status", "v12_function",
                    "v12_equivalent", "note"])
        w.writerows(rows)

    for r in rows:
        print("%-38s %s  KT:%-22s V1.2:%-22s eq:%s" % (
            r[0][:38], r[2], r[3], r[5], r[8] or "-"))


if __name__ == "__main__":
    main()
