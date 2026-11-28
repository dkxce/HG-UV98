#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PIN-патч прошивки Lanchonlh HG-UV98 (V1.1, дамп 507 904 байт).

При включении рация показывает экран "PIN" и не запускается, пока не введён
правильный код с клавиатуры.  Код (4-6 цифр) задаётся при запуске этого скрипта
и зашивается в образ.

Как это устроено:
  * в свободную область флеша 0x0804A000 (файл 0x46000) кладётся payload 2924 Б;
  * в загрузочной сцене инструкция по адресу 0x0801B7A8 заменяется на
    "b.w 0x0804A000"; payload отрисовывает экран, ждёт код, затем выполняет
    вытесненную инструкцию и возвращается в 0x0801B7AC.

Примеры:
    python patch_password.py dump.bin
    python patch_password.py dump.bin --pin 1234 -o locked.bin
    python patch_password.py locked.bin --check

Откат: залить исходный дамп тем же способом (IAP "Download Image").
"""

import argparse
import base64
import hashlib
import re
import sys
from pathlib import Path

IMAGE_SIZE = 0x7C000          # 507 904 байта
APP_BASE = 0x08004000

HOOK_ADDR = 0x0801B7A8        # "adds.w r7, r5, #0x142" в загрузочной сцене
HOOK_ORIG = bytes.fromhex("15f5a177")
HOOK_NEW = bytes.fromhex("2ef02abc")   # b.w 0x0804A000 (проверено дизассемблером)

PAYLOAD_ADDR = 0x0804A000
PAYLOAD_OFF = PAYLOAD_ADDR - APP_BASE          # 0x46000
FREE_FROM = 0x45B50                            # первый байт стёртой области
PIN_MAGIC = b"PWN1"

PAYLOAD_MD5 = "bf655547ad9869fdcc9c4df9b8f2f636"

PAYLOAD_HEX = (
    "2de90f5081b000f0d5f901b0bde80f5005f5a177d1f7cabb80b582b000af164b98470346fb71154b1b78dbb2012b05d1"
    "fb7903f00703124ad35c19e0114b1b78dbb2012b05d1fb7903f007030e4ad35c0ee00e4b1b78dbb2012b08d1fb79022b"
    "03d8fb790a4ad35c02e0ff2300e0ff2318460837bd4680bd9b8102086051002058a504086151002060a5040862510020"
    "68a50408b0b584b000af0446084611461a462346fb800346bb800b467b8013463b807b883a8802fb03f3fb60184b0222"
    "1a60fa883b8813449bb2013b9cb2ba887b8813449bb2013b9bb2b988f888114d2246a847104b2c2098470ee03b8c1b0a"
    "9bb2dbb20d4a184690473b8cdbb20b4a18469047fb68013bfb60fb68002bedd1074b02221a6000bf1037bd46b0bd00bf"
    "14100140b1b9010853ba010875ba01081010014090b587b000afba601a460346fb810b46bb811346fb803a4b02221a60"
    "fb890f339ab2bb8907339bb2b989f889354ca047354b2c2098470023fb7527e00023bb751ee0bb7dba6813441b781a46"
    "fb7d42fa03f303f00103002b01d0fb8800e03b8d7b827b8a1b0a9bb2dbb2284a184690477b8adbb2254a18469047bb7d"
    "0133bb75bb7d072bddd9fb7d0133fb75fb7d072bd4d90023fb7528e00023bb751fe0bb7d0833ba6813441b781a46fb7d"
    "42fa03f303f00103002b01d0fb8800e03b8dbb82bb8a1b0a9bb2dbb2104a18469047bb8adbb20e4a18469047bb7d0133"
    "bb75bb7d072bdcd9fb7d0133fb75fb7d072bd3d9074b02221a6000bf1c37bd4690bd00bf14100140b1b9010853ba0108"
    "75ba01081010014090b589b002afba601a460346fb810b46bb811346fb801ce0bb685a1cba601b78fb75fb7d1f2b11d9"
    "fb7d7e2b0ed8fb7d9bb2203b9bb21b010a4a1a44fc88b989f8893b8d00932346fff750ffbb890833bb81bb681b78002b"
    "ded100bf00bf1c37bd4690bd6ca5040880b586b002af0346fb71002300931023502228214420fff7e5fe0023fb730ee0"
    "fa7bfb799a4201d22a2200e02022fb7b10333b4403f8082cfb7b0133fb73fb7b052bedd90023bb7307f1080200230093"
    "4ff6ff7338214420fff79eff00bf1037bd4680bd80b582b002af002300938023a02200210020fff7b5fe002300934ff4"
    "78430d4a1c211820fff786ff002300934ff6e073094a2c213020fff77dff0023009348f21043064a16216c20fff774ff"
    "00bfbd4680bd00bf1ca504082ca5040838a5040880b582b002af002300934ff47843044a18215820fff75eff00bfbd46"
    "80bd00bf48a5040880b582b002af002300931023702218215820fff773fe00bfbd4680bd90b587b002af524b1b79bb71"
    "0023fb7300233b73bb79032b40f29580bb79062b00f291804b4b1b6803f00103002b01d1494b9847fff794ff0020fff7"
    "5fffff237b7303e0fff70efe03467b737b7bff2bf8d00023bb6002e0bb680133bb60fff701fe0346ff2b03d0bb683c4a"
    "9342f3d93b7b002b03d0fff7b5ff00233b737b7b092b10d8fb7b052bd9d8fb7b10333b447a7b03f8102cfb7b0133fb73"
    "fb7b1846fff72cffcbe77b7b0d2b0ad1fb7b002bc5d0fb7b013bfb73fb7b1846fff71effbde77b7b0a2bbad1fb7b002b"
    "b7d0fa7bbb799a4201d1012300e00023fb71fb79002b17d00023bb7310e0bb7b10333b4413f8102cbb7b05331549cb5c"
    "dbb29a4201d00023fb71bb7b0133bb73ba7bbb799a42ead3fb79002b0bd04ff4204301930f4b00930f4ca02380220021"
    "0020a0470ae00023fb730020fff7e0fefff740ff01233b737be700bf1437bd4690bd00bf5cab040808280140f9940208"
    "ff083d00304100081dd30108524144494f204953204c4f434b00000050415353574f52443a000000454e544552205041"
    "5353574f5244000057524f4e472050415353574f524400000a0b0c0d0102030e040506000708090f1213140000000000"
    "000000000000000000000000000038fcfc3800000000000d0d000000000e1e00001e0e00000000000000000020f8f820"
    "f8f82000020f0f020f0f0200387c444747cc98000306041c1c07030030300080c06030000c060301000c0c0080d87ce4"
    "bcd84000070f0808070f080000101e0e0000000000000000000000000000f0f80c040000000003070c0800000000040c"
    "f8f000000000080c0703000080a0e0c0c0e0a0800002030101030200008080e0e0808000000000030300000000000000"
    "000000000000101e0e0000008080808080808000000000000000000000000000000000000000000c0c00000000000080"
    "c06030000c06030100000000f8fc04c424fcf800070f0908080f0700001018fcfc0000000008080f0f080800080c84c4"
    "643c18000e0f0908080c0c00080c444444fcb800040c0808080f0700c0e0b098fcfc8000000000080f0f08007c7c4444"
    "c4c48400040c0808080f0700f0f84c4444c08000070f0808080f07000c0c0484c47c3c0000000f0f00000000b8fc4444"
    "44fcb800070f0808080f0700387c444444fcf800000808080c0703000000003030000000000000060600000000000030"
    "300000000000080e060000000080c0603018080000000103060c08004040404040404000020202020202020000081830"
    "60c0800000080c0603010000181c04c4e43c18000000000d0d000000000c12120c0000000000000000000000e0f0988c"
    "98f0e0000f0f0000000f0f0004fcfc4444fcb800080f0f08080f0700f0f80c04040c180003070c08080c060004fcfc04"
    "0cf8f000080f0f080c07030004fcfc44e40c1c00080f0f08080c0e0004fcfc44e40c1c00080f0f0800000000f0f80c84"
    "848c980003070c0808070f00fcfc404040fcfc000f0f0000000f0f00000004fcfc0400000000080f0f08000000000004"
    "fcfc0400070f08080f07000004fcfcc0f03c0c00080f0f00010f0e0004fcfc0400000000080f0f08080c0e00fcfc3870"
    "38fcfc000f0f0000000f0f00fcfc3870e0fcfc000f0f0000000f0f00f0f80c040cf8f00003070c080c07030004fcfc44"
    "447c3800080f0f0800000000f8fc040404fcf800070f080e3c3f270004fcfc44c4fc3800080f0f00000f0f00183c6444"
    "c49c1800060e0808080f0700001c0cfcfc0c1c000000080f0f080000fcfc000000fcfc00070f0808080f0700fcfc0000"
    "00fcfc000103060c06030100fcfc008000fcfc00030f0e030e0f03000c3cf0c0f03c0c000c0f0300030f0c00003c7cc0"
    "c07c3c000000080f0f0800001c0c84c4643c1c000e0f0908080c0e000000fcfc0404000000000f0f080800003870e0c0"
    "800000000000000103070e0000000404fcfc0000000008080f0f0000080c0603060c0800000000000000000000000000"
    "0000000020202020202020200000030704000000000000000000000000a0a0a0e0c00000070f0808070f080004fcfc20"
    "60c08000080f0708080f0700c0e0202020604000070f0808080c040080c06024fcfc0000070f0808070f0800c0e0a0a0"
    "a0e0c000070f0808080c040040f8fc440c180000080f0f0800000000c0e02020c0e02000276f48487f3f000004fcfc40"
    "20e0c000080f0f00000f0f00000020ecec0000000000080f0f0800000000000020ecec0000307040407f3f0004fcfc80"
    "c0602000080f0f01030e0c00000004fcfc0000000000080f0f080000e0e060c060e0c0000f0f000f000f0f0020e0c020"
    "20e0c000000f0f00000f0f00c0e0202020e0c000070f0808080f070020e0c02020e0c000407f7f48080f0700c0e02020"
    "c0e02000070f08487f7f400020e0c0602060c000080f0f080000000040e0a02020604000040c09090b0e04002020f8fc"
    "202000000000070f080c0400e0e00000e0e00000070f0808070f080000e0e00000e0e0000003070c0c070300e0e00000"
    "00e0e000070f0c070c0f07002060c080c0602000080c0703070c0800e0e0000000e0e000474f4848683f1f00606020a0"
    "e06020000c0e0b09080c0c00004040f8bc040400000000070f080800000000bcbc0000000000000f0f000000000404bc"
    "f84040000008080f07000000080c040c080c0400000000000000000050574e31000000000000000000000000"
)

PAYLOAD = bytes.fromhex(PAYLOAD_HEX)
if hashlib.md5(PAYLOAD).hexdigest() != PAYLOAD_MD5:
    raise SystemExit("Error: embedded payload is corrupted.")


def encode_bw(addr, target):
    """Thumb-2 B.W (T4)."""
    off = target - (addr + 4)
    if not (-0x1000000 <= off < 0x1000000):
        raise ValueError("branch out of B.W range")
    s = (off >> 24) & 1
    i1 = (off >> 23) & 1
    i2 = (off >> 22) & 1
    imm10 = (off >> 12) & 0x3FF
    imm11 = (off >> 1) & 0x7FF
    j1 = (~(i1 ^ s)) & 1
    j2 = (~(i2 ^ s)) & 1
    hw1 = 0xF000 | (s << 10) | imm10
    hw2 = 0x9000 | (j1 << 13) | (j2 << 11) | imm11
    return hw1.to_bytes(2, "little") + hw2.to_bytes(2, "little")


def build_payload(pin):
    blob = bytearray(PAYLOAD)
    pos = blob.find(PIN_MAGIC)
    if pos < 0:
        raise RuntimeError("no PIN slot in payload")
    blob[pos + 4] = len(pin)
    for i, ch in enumerate(pin):
        blob[pos + 5 + i] = ord(ch) - 0x30
    for i in range(len(pin), 6):
        blob[pos + 5 + i] = 0
    chk = 0
    for b in blob[pos + 4:pos + 11]:
        chk ^= b
    blob[pos + 11] = chk
    return blob, pos


def ask_pin(value):
    if value is not None:
        pin = value.strip()
        if not re.fullmatch(r"[0-9]{4,6}", pin):
            raise SystemExit("Error: PIN must be 4-6 digits.")
        return pin
    while True:
        try:
            pin = input("Radio password (4-6 digits): ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("\nCancelled.")
        if re.fullmatch(r"[0-9]{4,6}", pin):
            return pin
        print("  Exactly 4, 5 or 6 digits are required.")


def md5(data):
    return hashlib.md5(data).hexdigest()


def check(image):
    hook = image[HOOK_ADDR - APP_BASE:HOOK_ADDR - APP_BASE + 4]
    if hook == HOOK_NEW:
        print("Image: PATCHED (PIN lock active).")
        return True
    if hook == HOOK_ORIG:
        print("Image: original, no PIN lock.")
        return False
    print("Image: unknown version (hook bytes: %s)." % hook.hex())
    return None


def main():
    ap = argparse.ArgumentParser(
        description="PIN lock patch for the HG-UV98 firmware (V1.1).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Revert: flash the original dump via IAP 'Download Image'.")
    ap.add_argument("image", help="firmware image .bin (507904 bytes)")
    ap.add_argument("--pin", help="4-6 digit PIN (otherwise prompted)")
    ap.add_argument("-o", "--out", help="output file")
    ap.add_argument("--check", action="store_true", help="only check the image")
    ap.add_argument("--force", action="store_true", help="skip version checks")
    args = ap.parse_args()

    src = Path(args.image)
    if not src.is_file():
        raise SystemExit("File not found: %s" % src)
    data = bytearray(src.read_bytes())

    if len(data) != IMAGE_SIZE:
        raise SystemExit("Error: size is %d bytes, expected %d (0x%X)."
                         % (len(data), IMAGE_SIZE, IMAGE_SIZE))

    if args.check:
        check(data)
        return 0

    hooked = check(data)
    if hooked is None and not args.force:
        raise SystemExit("Wrong image. Only V1.1 (dump) is supported.")
    if hooked is None:
        print("  --force: patching an unknown image.")

    pin = ask_pin(args.pin)
    payload, pin_pos = build_payload(pin)

    if not hooked:
        region = data[PAYLOAD_OFF:PAYLOAD_OFF + len(payload)]
        if any(b != 0xFF for b in region):
            raise SystemExit("Error: payload region 0x%X is not blank." % PAYLOAD_OFF)

    data[PAYLOAD_OFF:PAYLOAD_OFF + len(payload)] = payload
    hook = encode_bw(HOOK_ADDR, PAYLOAD_ADDR)
    if hook != HOOK_NEW:
        raise SystemExit("Internal error: branch encoding changed.")
    data[HOOK_ADDR - APP_BASE:HOOK_ADDR - APP_BASE + 4] = hook

    out = Path(args.out) if args.out else src.with_name(src.stem + "_locked.bin")
    out.write_bytes(data)

    print()
    print("Done.")
    print("  image:      %s" % out)
    print("  size:       %d bytes" % len(data))
    print("  PIN:        %d digits (stored in the image, plaintext)" % len(pin))
    print("  payload:    0x%08X, %d bytes" % (PAYLOAD_ADDR, len(payload)))
    print("  hook:       0x%08X -> %s" % (HOOK_ADDR, hook.hex()))
    print("  input md5:  %s" % md5(bytes(src.read_bytes())))
    print("  output md5: %s" % md5(bytes(data)))
    print()
    print("Flash via IAP 'Download Image', COM 115200 8N1, file %s" % out.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
