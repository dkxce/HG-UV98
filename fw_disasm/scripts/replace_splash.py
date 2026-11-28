#!/usr/bin/env python3
"""Замена загрузочной картинки (splash) в файле прошивки Lanchonlh HG-UV98.

Зона заставки: файл 0x00130..0x0A130, ровно 40 960 байт, формат RGB565,
старший байт первым, 160 пикселей в строке, 128 строк. Сразу за зоной
(0x0A130) начинается код, поэтому размер записи фиксирован.

Как это используется прошивкой (см. REPORT.md §5.6):
    0801B7F4  bl FUN_0801D368(x=0, y=0, w=128, h=160, src=0x08004130, len=0xA000)
FUN_0801D368 ставит окно 128x160, шлёт команду 0x2C и выводит len/2
16-битных пикселей подряд. Панель повёрнута, поэтому картинка хранится
как 160x128 — ровно в том виде, в каком она выглядит на экране.

Запуск без аргументов открывает диалоговое ASCII-меню: там доступны все
операции (выбор прошивки и картинки, извлечение, замена, настройки зоны и
вписывания, обмен с рацией), ничего не нужно помнить.

Пункт 9 меню ставит или снимает PIN-блокировку — пароль, который рация
спрашивает при включении (payload вшит в pin_lock.py, сборка не нужна).
Патч собран под дамп V1.1; чужой образ отклоняется.

    python tools/replace_splash.py

Те же операции аргументами (для скриптов):
    # вытащить текущую заставку в PNG
    python tools/replace_splash.py extract "Lanchonlh HG-UV98 Radio Firmware V1.2_211026.bin" splash.png

    # заменить (результат в новый файл, исходник не трогаем)
    python tools/replace_splash.py replace fw.bin logo.png --out fw_patched.bin

    # заменить на месте, с резервной копией
    python tools/replace_splash.py replace fw.bin logo.png --in-place --backup

    # если на экране картинка повёрнута/зеркальна
    python tools/replace_splash.py replace fw.bin logo.png --out out.bin --rotate 90 --flip-h

Вход: PNG читается своей реализацией (без зависимостей). Если установлен
Pillow, дополнительно поддерживаются JPEG/BMP/GIF/WebP и т.п.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys
import time
import zlib

try:                                    # кириллица в консоли Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SPLASH_OFF = 0x130
SPLASH_W = 160          # ширина в файле = 160 (панель 128x160, повёрнута)
SPLASH_H = 128
SPLASH_LEN = SPLASH_W * SPLASH_H * 2      # 0x0A000
FIRMWARE_MIN_SIZE = SPLASH_OFF + SPLASH_LEN
MAGIC_HINTS = (b"HG-UV98", b"Lanchonlh", b"V1.2", b"IiNHSG0NNiNHSG0NP")


# --------------------------------------------------------------------------
# PNG: чтение (stdlib) и запись
# --------------------------------------------------------------------------
class PngError(Exception):
    pass


def read_png(path):
    """PNG -> (width, height, rows), rows[y] = bytearray RGB (3 байта/пиксель)."""
    data = open(path, "rb").read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PngError("%s: not a PNG" % path)

    pos = 8
    idat = bytearray()
    width = height = depth = ctype = interlace = None
    palette = b""
    trns = b""
    while pos + 8 <= len(data):
        length, ctag = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctag == b"IHDR":
            width, height, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            if comp != 0 or filt != 0:
                raise PngError("unsupported IHDR compression/filter")
            if interlace != 0:
                raise PngError("interlaced PNG is not supported - re-save without interlace")
        elif ctag == b"PLTE":
            palette = chunk
        elif ctag == b"tRNS":
            trns = chunk
        elif ctag == b"IDAT":
            idat += chunk
        elif ctag == b"IEND":
            break

    if width is None:
        raise PngError("no IHDR chunk")
    if ctype not in (0, 2, 3, 4, 6):
        raise PngError("unknown color type %d" % ctype)
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bits_pp = nch * depth
    stride = (width * bits_pp + 7) // 8

    raw = zlib.decompress(bytes(idat))
    if len(raw) < (stride + 1) * height:
        raise PngError("IDAT data is shorter than expected")

    # дефильтрация
    prev = bytearray(stride)
    lines = []
    p = 0
    for _ in range(height):
        ftype = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ftype == 1:      # Sub
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xFF
        elif ftype == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:    # Average
            for i in range(stride):
                left = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:    # Paeth
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise PngError("bad filter type %d" % ftype)
        lines.append(line)
        prev = line

    rows = []
    for line in lines:
        out = bytearray(width * 3)
        if depth == 8:
            for x in range(width):
                s = x * nch
                if ctype in (0, 4):
                    g = line[s]
                    out[3 * x:3 * x + 3] = bytes((g, g, g))
                elif ctype == 2:
                    out[3 * x:3 * x + 3] = line[s:s + 3]
                elif ctype == 6:
                    out[3 * x:3 * x + 3] = line[s:s + 3]
                else:                      # palette
                    idx = line[s]
                    out[3 * x:3 * x + 3] = palette[3 * idx:3 * idx + 3] or b"\0\0\0"
        elif depth == 16:
            step = 2 * nch
            for x in range(width):
                s = x * step
                if ctype in (0, 4):
                    g = line[s]
                    out[3 * x:3 * x + 3] = bytes((g, g, g))
                else:
                    out[3 * x:3 * x + 3] = bytes((line[s], line[s + 2], line[s + 4]))
        else:                              # 1/2/4 бита: gray или palette
            per_byte = 8 // depth
            mask = (1 << depth) - 1
            for x in range(width):
                byte = line[x // per_byte]
                shift = 8 - depth * (x % per_byte + 1)
                val = (byte >> shift) & mask
                if ctype == 3:
                    out[3 * x:3 * x + 3] = palette[3 * val:3 * val + 3] or b"\0\0\0"
                else:
                    g = val * 255 // mask
                    out[3 * x:3 * x + 3] = bytes((g, g, g))
        rows.append(out)
    return width, height, rows


def write_png(path, width, height, rows):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rows[y]

    def chunk(tag, payload):
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


# --------------------------------------------------------------------------
# загрузка произвольной картинки
# --------------------------------------------------------------------------
def load_image(path):
    try:
        from PIL import Image  # необязательная зависимость
    except ImportError:
        if path.lower().endswith(".png"):
            return read_png(path)
        raise SystemExit("Formats other than PNG need Pillow:  pip install pillow")
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im).convert("RGB")
    else:
        im = im.convert("RGB")
    w, h = im.size
    data = im.tobytes()
    rows = [bytearray(data[y * w * 3:(y + 1) * w * 3]) for y in range(h)]
    return w, h, rows


# --------------------------------------------------------------------------
# геометрия: поворот/зеркало, масштаб, RGB565
# --------------------------------------------------------------------------
def transform(w, h, rows, rotate=0, flip_h=False, flip_v=False):
    if flip_h:
        rows = [bytearray(b"".join(bytes(r[x * 3:x * 3 + 3]) for x in reversed(range(w)))) for r in rows]
    if flip_v:
        rows = rows[::-1]
    for _ in range((rotate // 90) % 4):
        # поворот на 90° по часовой стрелке: (x, y) -> (h-1-y, x)
        new_rows = [bytearray(h * 3) for _ in range(w)]
        for ny in range(w):
            for nx in range(h):
                oy = h - 1 - nx
                new_rows[ny][nx * 3:nx * 3 + 3] = rows[oy][ny * 3:ny * 3 + 3]
        rows = new_rows
        w, h = h, w
    return w, h, rows


def sample(rows, w, h, fx, fy):
    """билинейный сэмпл в координатах (fx, fy), с ограничением по краям."""
    if fx < 0:
        fx = 0.0
    if fy < 0:
        fy = 0.0
    if fx > w - 1:
        fx = w - 1.0
    if fy > h - 1:
        fy = h - 1.0
    x0, y0 = int(fx), int(fy)
    x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
    dx, dy = fx - x0, fy - y0
    out = bytearray(3)
    for c in range(3):
        v00 = rows[y0][x0 * 3 + c]
        v10 = rows[y0][x1 * 3 + c]
        v01 = rows[y1][x0 * 3 + c]
        v11 = rows[y1][x1 * 3 + c]
        top = v00 + (v10 - v00) * dx
        bot = v01 + (v11 - v01) * dx
        out[c] = int(top + (bot - top) * dy + 0.5)
    return out


def fit(w, h, rows, tw, th, mode, bg=(0, 0, 0)):
    """mode: cover (заполнить с обрезкой) | stretch (растянуть) | contain (вписать с полями).

    dest = src * s + o  ->  src = (dest - o) / s
    """
    if mode == "stretch":
        sx, sy = tw / w, th / h
        ox = oy = 0.0
    else:
        s = max(tw / w, th / h) if mode == "cover" else min(tw / w, th / h)
        sx = sy = s
        ox = (tw - w * s) / 2.0
        oy = (th - h * s) / 2.0

    out = []
    for y in range(th):
        line = bytearray(tw * 3)
        fy = (y - oy) / sy
        for x in range(tw):
            fx = (x - ox) / sx
            if 0.0 <= fx <= w - 1 and 0.0 <= fy <= h - 1:
                line[x * 3:x * 3 + 3] = sample(rows, w, h, fx, fy)
            else:
                line[x * 3:x * 3 + 3] = bytes(bg)
        out.append(line)
    return out


def rgb_to_565(rows, w, h, bswap=False):
    buf = bytearray(w * h * 2)
    i = 0
    for y in range(h):
        r = rows[y]
        for x in range(w):
            rv, gv, bv = r[x * 3], r[x * 3 + 1], r[x * 3 + 2]
            v = ((rv & 0xF8) << 8) | ((gv & 0xFC) << 3) | (bv >> 3)
            if bswap:
                buf[i] = v & 0xFF
                buf[i + 1] = v >> 8
            else:
                buf[i] = v >> 8
                buf[i + 1] = v & 0xFF
            i += 2
    return bytes(buf)


def rgb565_to_rows(buf, w, h, bswap=False):
    rows = []
    for y in range(h):
        line = bytearray(w * 3)
        for x in range(w):
            i = (y * w + x) * 2
            v = (buf[i] | (buf[i + 1] << 8)) if bswap else ((buf[i] << 8) | buf[i + 1])
            r = (v >> 11) & 0x1F
            g = (v >> 5) & 0x3F
            b = v & 0x1F
            line[x * 3] = (r * 255) // 31
            line[x * 3 + 1] = (g * 255) // 63
            line[x * 3 + 2] = (b * 255) // 31
        rows.append(line)
    return rows


# --------------------------------------------------------------------------
# команды
# --------------------------------------------------------------------------
def check_firmware(data, path, force):
    if len(data) < FIRMWARE_MIN_SIZE:
        raise SystemExit("%s: file is shorter than 0x%X - not an HG-UV98 image" % (
            path, FIRMWARE_MIN_SIZE))
    if not force and not any(h in data for h in MAGIC_HINTS):
        raise SystemExit("%s: no HG-UV98 signature strings found; "
                         "use --force if you are sure" % path)


def _read_firmware(path):
    """Читает файл прошивки; при отсутствии или пустоте даёт осмысленную ошибку.

    Относительный путь пробуем как есть (относительно текущего каталога) и,
    если там файла нет, — относительно каталога самого скрипта. Это позволяет
    запускать скрипт из любого каталога, когда прошивка лежит рядом с ним.
    """
    if not path:
        raise ValueError("File is missing or empty")
    candidates = [path]
    if not os.path.isabs(path):
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), path))
    real = None
    for cand in candidates:
        if os.path.isfile(cand) and os.path.getsize(cand) > 0:
            real = cand
            break
        if os.path.isfile(cand) and os.path.getsize(cand) == 0:
            raise ValueError("File is missing or empty")
    if real is None:
        raise ValueError("File is missing or empty")
    return open(real, "rb").read()


def cmd_extract(args):
    data = _read_firmware(args.firmware)
    check_firmware(data, args.firmware, args.force)
    zone_len = args.width * args.height * 2
    if args.offset + zone_len > len(data):
        raise SystemExit("zone 0x%X..0x%X is beyond the end of the file (%d bytes)" % (
            args.offset, args.offset + zone_len, len(data)))
    zone = data[args.offset:args.offset + zone_len]
    rows = rgb565_to_rows(zone, args.width, args.height)
    write_png(args.output, args.width, args.height, rows)
    print("extract: %s -> %s (%dx%d, RGB565, %s)" % (
        args.firmware, args.output, args.width, args.height, "LE" if args.bswap else "BE"))


def cmd_replace(args):
    data = _read_firmware(args.firmware)
    check_firmware(data, args.firmware, args.force)
    zone_len = args.width * args.height * 2
    if args.offset + zone_len > len(data):
        raise SystemExit("zone 0x%X..0x%X is beyond the end of the file (%d bytes)" % (
            args.offset, args.offset + zone_len, len(data)))

    w, h, rows = load_image(args.image)
    print("input: %s (%dx%d)" % (args.image, w, h))
    w, h, rows = transform(w, h, rows, args.rotate, args.flip_h, args.flip_v)

    bg = tuple(int(args.bg[i:i + 2], 16) for i in (0, 2, 4))
    rows = fit(w, h, rows, args.width, args.height, args.fit, bg)
    blob = rgb_to_565(rows, args.width, args.height, args.bswap)
    assert len(blob) == zone_len

    out = bytearray(data)
    old = bytes(out[args.offset:args.offset + zone_len])
    out[args.offset:args.offset + zone_len] = blob

    target = args.firmware if args.in_place else args.out
    if target is None:
        raise SystemExit("specify --out or --in-place")
    if args.backup and args.in_place:
        bak = args.firmware + ".bak"
        if os.path.exists(bak):
            raise SystemExit("backup already exists: %s" % bak)
        open(bak, "wb").write(data)
        print("backup: %s" % bak)
    open(target, "wb").write(bytes(out))

    changed = sum(1 for a, b in zip(old, blob) if a != b)
    print("replace: %s -> %s" % (args.firmware, target))
    print("  zone 0x%X..0x%X, %d bytes, %d bytes changed (%.1f %%)" % (
        args.offset, args.offset + zone_len, zone_len, changed, 100.0 * changed / zone_len))
    print("  file size: %d -> %d" % (len(data), len(out)))
    if args.preview:
        write_png(args.preview, args.width, args.height,
                  rgb565_to_rows(blob, args.width, args.height, args.bswap))
        print("  preview: %s" % args.preview)


# --------------------------------------------------------------------------
# диалоговый режим: ASCII-меню, ничего не нужно передавать аргументами
# --------------------------------------------------------------------------
def _ask(prompt, default=""):
    try:
        ans = input(prompt).strip()
    except EOFError:
        raise KeyboardInterrupt
    if not ans:
        return default
    return ans.strip('"').strip("'")


def _ask_bool(prompt, default=False):
    hint = "Y/n" if default else "y/N"
    ans = _ask("%s [%s]: " % (prompt, hint)).lower()
    if not ans:
        return default
    return ans in ("y", "yes", "1")


def _ask_int(prompt, default, lo=None, hi=None):
    while True:
        ans = _ask("%s [%d]: " % (prompt, default))
        try:
            val = int(ans, 0)
        except ValueError:
            print("  a number is required")
            continue
        if (lo is not None and val < lo) or (hi is not None and val > hi):
            print("  allowed range: %s..%s" % (lo, hi))
            continue
        return val


def _ask_path(prompt, must_exist=True, default=None):
    while True:
        suffix = " [%s]" % default if default else ""
        ans = _ask("%s%s: " % (prompt, suffix), default or "")
        if not ans:
            return None
        if not must_exist or os.path.exists(ans):
            return ans
        print("  no such file: %s" % ans)


def _onoff(flag):
    return "yes" if flag else "no"


def _kb(path):
    return "%.1f KB" % (os.path.getsize(path) / 1024.0)


def _list_files(exts):
    """Файлы текущей папки с нужными расширениями (отсортированы)."""
    try:
        entries = sorted(os.listdir("."))
    except OSError:
        return []
    return [n for n in entries
            if os.path.isfile(n) and (not exts or n.lower().endswith(exts))]


def _file_version(path):
    """Версия прошивки в файле (None, если не определилась)."""
    try:
        fw_common, _ = _radio_modules()
        return fw_common.version_of_file(path)
    except Exception:
        return None


def _choose_file(prompt, exts, current=None, with_version=False):
    """Показать файлы текущей папки; выбор номером, 0 — ввести путь вручную."""
    names = _list_files(exts)
    print("  %s in %s:" % (prompt, os.getcwd()))
    shown = names[:30]
    for i, name in enumerate(shown, 1):
        line = "  [%2d] - %-46s %9s" % (i, name, _kb(name))
        if with_version:
            line += "  version: %s" % (_file_version(name) or "not detected")
        print("   " + line)
    if not shown:
        print("    (nothing suitable here)")
    elif len(names) > len(shown):
        print("    ... and %d more (0 to type a path)" % (len(names) - len(shown)))
    print("    [0] - enter path manually")
    if current in names:
        dflt = str(names.index(current) + 1)
    else:
        dflt = "1" if shown else "0"
    while True:
        ans = _ask("  choice [%s]: " % dflt, dflt)
        if ans == "0":
            return _ask_path("  path")
        if ans.isdigit():
            idx = int(ans)
            if 1 <= idx <= len(shown):
                return shown[idx - 1]
            print("  no file number %s" % ans)
            continue
        if os.path.exists(ans):
            return ans
        print("  no such file: %s" % ans)


def _radio_modules():
    """fw_common.py и ymodem.py лежат рядом с этим скриптом."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import fw_common
    import ymodem
    return fw_common, ymodem


def _need_serial():
    try:
        import serial
        return serial
    except ImportError:
        print("  pyserial is not installed:  python -m pip install pyserial")
        return None


def _serial_io(ser):
    def getc(n):
        data = ser.read(n)
        return data if data else None

    def putc(b):
        return ser.write(b)

    return getc, putc


def _close_port(ser):
    try:
        ser.close()
    except Exception:
        pass


BAR_WIDTH = 18
BAR_FULL = "\u2588"     # █ — заполненная часть
BAR_HALF = "\u2592"     # ▒ — неполный текущий сегмент
BAR_EMPTY = "\u2591"    # ░ — пустая часть


def _bar_text(fraction):
    """Полоса из █/▒/░ шириной BAR_WIDTH для доли 0..1."""
    exact = BAR_WIDTH * max(0.0, min(1.0, fraction))
    filled = int(exact)
    bar = BAR_FULL * filled
    if filled < BAR_WIDTH:
        if exact - filled > 0.0:
            bar += BAR_HALF + BAR_EMPTY * (BAR_WIDTH - filled - 1)
        else:
            bar += BAR_EMPTY * (BAR_WIDTH - filled)
    return bar


def _bar(done, total, label="packet"):
    total = total or 1
    pct = int(100.0 * done / total)
    sys.stdout.write("\r[%s] %3d%%  %s %d/%d" % (
        _bar_text(done / float(total)), pct, label, done, total))
    sys.stdout.flush()


def _bar_done():
    sys.stdout.write("\n")
    sys.stdout.flush()


def _print_banner(blob, title="radio banner"):
    text = blob.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return
    print("  --- %s ---" % title)
    for line in text.split("\n"):
        print("  " + line.rstrip())
    print("  --------------------")


def _drain(getc, seconds=1.5):
    """Собрать то, что успела напечатать рация за отведённое время."""
    buf = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        chunk = getc(64)
        if chunk:
            buf += chunk
            deadline = time.monotonic() + 0.4
    return bytes(buf)


def _firmware_info(path):
    """Сведения об образе прошивки: размер, версия, дата, SHA-256, признаки."""
    fw_common, _ = _radio_modules()
    data = _read_firmware(path)
    ver = fw_common.detect_version(data)
    info = {
        "path": path,
        "size": len(data),
        "version": ver,
        "date": None,
        "sha256": hashlib.sha256(data).hexdigest(),
        "hg": any(m in data for m in MAGIC_HINTS),
        "splash": len(data) >= SPLASH_OFF + SPLASH_LEN,
    }
    if ver:
        tail = ver.rsplit("_", 1)[-1]
        if len(tail) == 6 and tail.isdigit():
            info["date"] = "20%s-%s-%s" % (tail[:2], tail[2:4], tail[4:])
    return info


def _print_firmware_info(path, expected_size=None):
    """Показать блок сведений о прошивке перед прошивкой и после дампа."""
    try:
        info = _firmware_info(path)
    except OSError as e:
        print("  error: %s" % e)
        return None
    print("  --- firmware info ---")
    print("  file     : %s" % info["path"])
    print("  size     : %d bytes (%d x 1K)" % (
        info["size"], (info["size"] + 1023) // 1024))
    if expected_size:
        if info["size"] == expected_size:
            print("  expected : matches an HG-UV98 image (%d bytes)" % expected_size)
        else:
            print("  expected : differs from %d bytes" % expected_size)
    print("  version  : %s" % (info["version"] or "not detected"))
    print("  date     : %s" % (info["date"] or "not detected"))
    print("  sha256   : %s" % info["sha256"])
    print("  HG-UV98  : %s" % ("signature strings found" if info["hg"]
                               else "no signature strings"))
    print("  splash   : %s" % (("present at 0x%X (160x128)" % SPLASH_OFF)
                               if info["splash"] else "missing"))
    print("  ---------------------")
    return info


FIT_MODES = ("cover", "stretch", "contain")
FIT_NAMES = {
    "cover": "cover - fill, crop the edges",
    "stretch": "stretch - fit exactly",
    "contain": "contain - fit inside with borders",
}
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")


class Menu(object):
    """Dialog state: the selected files and the operation options."""

    def __init__(self):
        self.firmware = None
        self.image = None
        self.offset = SPLASH_OFF
        self.width = SPLASH_W
        self.height = SPLASH_H
        self.bswap = False
        self.force = False
        self.fit_mode = "cover"
        self.bg = "ffffff"
        self.rotate = 0
        self.flip_h = False
        self.flip_v = False
        self.preview_keep = True
        self.port = None
        self.baud = 115200
        self.dump_timeout = 120.0
        self.boot_wait = 60.0
        self._ver_key = None
        self._ver = None

    # ---------------------------------------------------------------- вывод
    def firmware_version(self):
        """Версия текущей прошивки (с кешем по пути/размеру/mtime)."""
        if not self.firmware:
            return None
        try:
            st = os.stat(self.firmware)
        except OSError:
            return None
        key = (os.path.abspath(self.firmware), st.st_size, int(st.st_mtime))
        if self._ver_key != key:
            self._ver = _file_version(self.firmware)
            self._ver_key = key
        return self._ver

    def state(self):
        print("-" * 70)
        if self.firmware:
            print("  firmware : %s  (version %s)" % (
                self.firmware, self.firmware_version() or "not detected"))
        else:
            print("  firmware : not selected")
        print("  port     : %s" % ("%s @ %d" % (self.port, self.baud)
                                    if self.port else "not selected"))
        print("  zone     : 0x%X, %d bytes, %dx%d, %s" % (
            self.offset, self.width * self.height * 2, self.width, self.height,
            "little-endian" if self.bswap else "big-endian"))
        print("  image    : %s" % (self.image or "not selected"))
        print("  replace  : %s, bg #%s, rotate %d, flips %s/%s" % (
            self.fit_mode, self.bg, self.rotate, _onoff(self.flip_h), _onoff(self.flip_v)))

    # ------------------------------------------------------------- действия
    def _run(self, func, ns):
        try:
            func(ns)
        except SystemExit as e:
            msg = e.code if isinstance(e.code, str) else ""
            if msg and "HG-UV98" in msg and not ns.force:
                if _ask_bool("  not recognised as an HG-UV98 image. Continue anyway?", False):
                    ns.force = True
                    return self._run(func, ns)
                print("  cancelled")
                return
            if msg:
                print("  error: %s" % msg)
            elif e.code not in (None, 0):
                print("  error (code %s)" % e.code)
        except (PngError, OSError, zlib.error) as e:
            print("  error: %s" % e)

    def pick_firmware(self):
        p = _choose_file("Firmware files (*.bin)", (".bin",), self.firmware,
                         with_version=True)
        if p:
            self.firmware = p
            self.force = False
            print("  selected: %s (%s, version %s)" % (
                p, _kb(p), _file_version(p) or "not detected"))

    def pick_image(self):
        p = _choose_file("Images", IMAGE_EXTS, self.image)
        if p:
            self.image = p
            print("  selected: %s (%s)" % (p, _kb(p)))

    def extract(self):
        if not self.firmware:
            self.pick_firmware()
            if not self.firmware:
                return
        base = os.path.splitext(self.firmware)[0]
        out = _ask_path("  save PNG", must_exist=False, default=base + "_splash.png")
        if not out:
            return
        ns = argparse.Namespace(firmware=self.firmware, offset=self.offset,
                                width=self.width, height=self.height,
                                bswap=self.bswap, force=self.force, output=out)
        self._run(cmd_extract, ns)

    def replace(self):
        if not self.firmware:
            self.pick_firmware()
            if not self.firmware:
                return
        if not self.image:
            self.pick_image()
            if not self.image:
                return
        base = os.path.splitext(self.firmware)[0]
        print("  where to write the result:")
        print("    [1] - new file (source untouched)")
        print("    [2] - overwrite source, keep .bak")
        print("    [3] - overwrite source, no backup")
        what = _ask("  choice [1]: ", "1")
        if what == "2":
            in_place, backup, target = True, True, self.firmware
        elif what == "3":
            in_place, backup, target = True, False, self.firmware
        else:
            target = _ask_path("  new file", must_exist=False, default=base + "_patched.bin")
            if not target:
                return
            in_place, backup = False, False
        preview = os.path.splitext(target)[0] + "_preview.png" if self.preview_keep else None
        ns = argparse.Namespace(firmware=self.firmware, offset=self.offset,
                                width=self.width, height=self.height,
                                bswap=self.bswap, force=self.force, image=self.image,
                                out=None if in_place else target, in_place=in_place,
                                backup=backup, fit=self.fit_mode, bg=self.bg,
                                rotate=self.rotate, flip_h=self.flip_h,
                                flip_v=self.flip_v, preview=preview)
        self._run(cmd_replace, ns)

    # ------------------------------------------------------------ COM / radio
    def pick_port(self):
        fw_common, _ = _radio_modules()
        ports = fw_common.list_ports()
        print("  COM ports on this computer:")
        for i, (dev, desc) in enumerate(ports, 1):
            print("   %s[%2d] - %-8s %s" % ("*" if dev == self.port else " ", i, dev, desc))
        if not ports:
            print("    (none found - is pyserial installed?)")
        print("    [0] - type port name manually")
        dflt = "1" if ports else "0"
        for i, (dev, _desc) in enumerate(ports, 1):
            if dev == self.port:
                dflt = str(i)
                break
        while True:
            ans = _ask("  choice [%s]: " % dflt, dflt)
            if ans == "0":
                name = _ask("  port name (e.g. COM5)", self.port or "")
                if name:
                    self.port = name.upper()
                    print("  port: %s" % self.port)
                return
            if ans.isdigit():
                idx = int(ans)
                if 1 <= idx <= len(ports):
                    self.port = ports[idx - 1][0]
                    print("  port: %s (%s)" % (self.port, ports[idx - 1][1]))
                    return
                print("  no port number %s" % ans)
                continue
            self.port = ans.upper()
            print("  port: %s" % self.port)
            return

    def port_menu(self):
        while True:
            print("  COM port: %s, baud %d, download timeout %ds" % (
                self.port or "not selected", self.baud, int(self.dump_timeout)))
            print("    [1] - list and select port")
            print("    [2] - type port name")
            print("    [3] - baud rate")
            print("    [4] - download timeout (seconds)")
            print("    [0] - back")
            c = _ask("  > ")
            if c in ("", "0"):
                return
            if c == "1":
                self.pick_port()
            elif c == "2":
                name = _ask("  port name (e.g. COM5)", self.port or "")
                if name:
                    self.port = name.upper()
                    print("  port: %s" % self.port)
            elif c == "3":
                self.baud = _ask_int("  baud rate", self.baud, 1200, 4000000)
            elif c == "4":
                self.dump_timeout = float(_ask_int("  timeout, seconds",
                                                   int(self.dump_timeout), 10, 3600))
            else:
                print("  no such item")

    def _open_port(self):
        serial = _need_serial()
        if serial is None:
            return None
        if not self.port:
            self.pick_port()
            if not self.port:
                print("  no port selected")
                return None
        try:
            ser = serial.Serial(port=self.port, baudrate=self.baud, bytesize=8,
                                parity="N", stopbits=1, timeout=0.5,
                                xonxoff=False, rtscts=False)
        except Exception as e:
            print("  cannot open %s: %s" % (self.port, e))
            return None
        print("  opened %s @ %d,8,N,1" % (self.port, self.baud))
        return ser

    def _menu_ready(self):
        """Спросить, видно ли меню загрузчика; вернуть время ожидания баннера."""
        if _ask_bool("  is the bootloader menu already on the radio screen?", False):
            return 0.5
        return self.boot_wait

    def _boot_loader(self, ser, key, ymodem, action, wait=None, label="DOWNLOAD"):
        """Дождаться меню загрузчика и отправить пункт '1' или '2'."""
        getc, putc = _serial_io(ser)
        if wait is None:
            wait = self.boot_wait
        if wait <= 1.0:
            print("  The menu is already on the radio; sending '%s' (%s)..."
                  % (key.decode(), action))
        else:
            print("  Turn the radio on with PTT held and wait for the bootloader menu.")
            print("  Waiting for the banner, then sending '%s' (%s)..." % (
                key.decode(), action))
        banner = []
        ok = ymodem.select_menu(getc, putc, key, wait=wait,
                                banner_cb=lambda b: banner.append(b))
        if banner:
            _print_banner(banner[0])
        if not ok:
            print("  no banner seen (menu already on screen?); key sent anyway")
        ym = ymodem.YModem(getc, putc)
        ym.log = lambda msg: None
        ym.progress = lambda percent, packet_no, total: _bar(packet_no, total, label)
        return ym

    def radio_download(self):
        fw_common, ymodem = _radio_modules()
        default = "fw_dump_%s.bin" % time.strftime("%Y%m%d%H%M%S")
        target = _ask("  save dump as [%s]: " % default, default)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        except OSError as e:
            print("  error: %s" % e)
            return
        if os.path.exists(target) and not _ask_bool(
                "  %s exists, overwrite it?" % target, False):
            print("  cancelled")
            return
        wait = self._menu_ready()
        ser = self._open_port()
        if ser is None:
            return
        ym = None
        name = size = None
        try:
            print("  wait, init file transfer ...")
            print("  DOWNLOAD  radio -> PC  (waiting for the start packet...)")
            for attempt in range(3):
                try:
                    if ym is None:
                        ym = self._boot_loader(ser, b"2", ymodem, "Upload Image", wait,
                                               label="DOWNLOAD")
                    else:
                        ym.putc(b"2")
                    name, size = ym.recv_file(".", max_wait=self.dump_timeout,
                                              allow_overwrite=True, out_path=target)
                    break
                except (RuntimeError, TimeoutError, FileExistsError, OSError) as e:
                    _bar_done()
                    print("  error: %s" % e)
                    if attempt == 2:
                        print("  check the radio: menu item '2' selected, "
                              "cable in the right port")
                        left = _drain(ym.getc, 0.3) if ym else b""
                        if left:
                            print("  last bytes from the radio: %s" % left[:60].hex())
                        return
                    print("  if the bootloader menu is on the radio, press '2' on it now")
                    if _ask("  Enter to retry, 'q' to cancel: ").lower() == "q":
                        return
        finally:
            _close_port(ser)
        _bar_done()
        print("  dumped: %s (%d bytes, %d packets)" % (target, size, ym.valid_packets))
        if name and name != os.path.basename(target):
            print("  radio name: %s" % name)
        _print_firmware_info(target, fw_common.WANT_FW_SIZE)
        self.firmware = target
        print("  current firmware: %s" % target)

    def radio_upload(self):
        fw_common, ymodem = _radio_modules()
        if not self.firmware:
            self.pick_firmware()
            if not self.firmware:
                return
        path = self.firmware
        size = os.path.getsize(path)
        info = _print_firmware_info(path, fw_common.WANT_FW_SIZE)
        ver = info["version"] if info else fw_common.version_of_file(path)
        if size != fw_common.WANT_FW_SIZE:
            print("  warning: %d bytes, expected %d (%d packets of 1K)" % (
                size, fw_common.WANT_FW_SIZE, fw_common.WANT_PACKETS))
            if not _ask_bool("  flash it anyway?", False):
                print("  cancelled")
                return
        elif not _ask_bool("  flash %s into the radio?" % (ver or os.path.basename(path)),
                           False):
            print("  cancelled")
            return
        wait = self._menu_ready()
        ser = self._open_port()
        if ser is None:
            return
        ym = None
        sent = None
        try:
            ym = self._boot_loader(ser, b"1", ymodem, "Download Image", wait,
                                   label="UPLOAD")
            print("  wait, init file transfer ...")
            print("  UPLOAD  PC -> radio  (%d bytes, %d packets)"
                  % (size, (size + 1023) // 1024))
            for attempt in range(3):
                try:
                    sent = ym.send_file(path, retry=10, wait_initial_c=True,
                                        initial_timeout=20.0)
                    break
                except RuntimeError as e:
                    _bar_done()
                    print("  error: %s" % e)
                    if attempt == 2:
                        print("  check the radio: bootloader menu on screen, "
                              "item '1' ready, cable in the right port; "
                              "then try point 8 again")
                        left = _drain(ym.getc, 0.3) if ym else b""
                        if left:
                            print("  last bytes from the radio: %s" % left[:60].hex())
                        return
                    print("  if the bootloader menu is on the radio, press '1' on it now")
                    if _ask("  Enter to retry, 'q' to cancel: ").lower() == "q":
                        return
                    ym.putc(b"1")
            _bar_done()
            print("  sent %d bytes (%d packets)" % (sent, ym.valid_packets))
            answer = _drain(ym.getc, 1.5)
            if answer:
                _print_banner(answer, "radio answer")
            if _ask_bool("  send '3' (Execute The New Program) now?", False):
                ym.putc(b"3")
                answer = _drain(ym.getc, 2.0)
                if answer:
                    _print_banner(answer, "radio answer")
                print("  sent '3' - the new firmware is starting")
            else:
                print("  press '3' (Execute The New Program) on the radio to start it")
        except (RuntimeError, OSError) as e:
            _bar_done()
            print("  error: %s" % e)
        finally:
            _close_port(ser)

    # ------------------------------------------------------------ PIN lock
    def _pin_mod(self):
        """pin_lock.py лежит рядом с этим скриптом."""
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import pin_lock
        return pin_lock

    def pin_state(self):
        """Состояние PIN-блокировки в выбранном образе (строка для меню)."""
        if not self.firmware:
            return "no firmware selected"
        pin_lock = self._pin_mod()
        try:
            data = _read_firmware(self.firmware)
        except (OSError, ValueError) as e:
            return "error: %s" % e
        kind = pin_lock.state(data)
        if kind == "patched":
            pin = pin_lock.pin_of(data)
            return ("ACTIVE (%d digits)" % len(pin)) if pin else \
                   "ACTIVE (PIN slot unreadable)"
        if kind == "original":
            return "not active (stock boot scene)"
        return "unknown image: V1.1 dump required (hook %s)" % \
               pin_lock.hook_bytes(data).hex()

    def _pin_output(self, suffix):
        """Куда писать результат: новый файл или поверх исходного (с .bak)."""
        base = os.path.splitext(self.firmware)[0]
        print("  where to write the result:")
        print("    [1] - new file (source untouched)")
        print("    [2] - overwrite source, keep .bak")
        print("    [3] - overwrite source, no backup")
        what = _ask("  choice [1]: ", "1")
        if what == "2":
            return self.firmware, True
        if what == "3":
            return self.firmware, False
        target = _ask_path("  new file", must_exist=False, default=base + suffix)
        return target, False

    def _pin_write(self, data, target, backup):
        """Записать готовый образ (при необходимости с резервной копией)."""
        if backup:
            bak = self.firmware + ".bak"
            if os.path.exists(bak):
                print("  error: backup already exists: %s" % bak)
                return False
            try:
                open(bak, "wb").write(_read_firmware(self.firmware))
            except (OSError, ValueError) as e:
                print("  error: %s" % e)
                return False
            print("  backup: %s" % bak)
        try:
            open(target, "wb").write(bytes(data))
        except OSError as e:
            print("  error: %s" % e)
            return False
        print("  written: %s (%d bytes)" % (target, len(data)))
        return True

    def pin_set(self):
        """Включить PIN-блокировку (или заменить уже записанный PIN)."""
        pin_lock = self._pin_mod()
        if not self.firmware:
            self.pick_firmware()
            if not self.firmware:
                return
        try:
            data = _read_firmware(self.firmware)
        except (OSError, ValueError) as e:
            print("  error: %s" % e)
            return
        kind = pin_lock.state(data)
        if kind == "unknown":
            print("  error: unsupported image - hook bytes at 0x%X are %s" % (
                pin_lock.HOOK_OFF, pin_lock.hook_bytes(data).hex()))
            print("  the PIN patch is built for the V1.1 dump (507904 bytes) only")
            return
        if kind == "patched":
            print("  this image already has a PIN lock")
            if not _ask_bool("  replace the existing PIN?", False):
                print("  cancelled")
                return
        pin = ""
        while not pin:
            ans = _ask("  new PIN (4-6 digits): ")
            if not ans:
                print("  cancelled")
                return
            if pin_lock.valid_pin(ans):
                pin = ans
            else:
                print("  exactly 4, 5 or 6 digits are required")
        target, backup = self._pin_output("_locked.bin")
        if not target:
            return
        try:
            out = pin_lock.apply_pin(data, pin)
        except (ValueError, RuntimeError) as e:
            print("  error: %s" % e)
            return
        if not self._pin_write(out, target, backup):
            return
        print("  PIN lock: ACTIVE, %d digits (stored in the image, plaintext)" % len(pin))
        print("  payload: 0x%08X, %d bytes; hook 0x%08X -> %s" % (
            pin_lock.PAYLOAD_ADDR, len(pin_lock.PAYLOAD),
            pin_lock.HOOK_ADDR, pin_lock.hook_bytes(out).hex()))
        self.firmware = target
        self.force = False
        print("  current firmware: %s" % target)
        print("  flash it with item 8 (upload firmware to the radio)")

    def pin_remove(self):
        """Снять PIN-блокировку: исходная загрузочная сцена, область пуста."""
        pin_lock = self._pin_mod()
        if not self.firmware:
            self.pick_firmware()
            if not self.firmware:
                return
        try:
            data = _read_firmware(self.firmware)
        except (OSError, ValueError) as e:
            print("  error: %s" % e)
            return
        if pin_lock.state(data) != "patched":
            print("  no PIN lock in this image - nothing to remove")
            return
        if not _ask_bool("  remove the PIN lock and restore the stock boot scene?",
                         False):
            print("  cancelled")
            return
        target, backup = self._pin_output("_unlocked.bin")
        if not target:
            return
        try:
            out = pin_lock.remove_pin(data)
        except (ValueError, RuntimeError) as e:
            print("  error: %s" % e)
            return
        if not self._pin_write(out, target, backup):
            return
        print("  PIN lock: removed (hook restored, payload area blanked)")
        self.firmware = target
        self.force = False
        print("  current firmware: %s" % target)
        print("  flash it with item 8 (upload firmware to the radio)")

    def pin_menu(self):
        while True:
            print()
            print("  PIN lock (the radio asks for a code at power on):")
            print("    image: %s" % (self.firmware or "not selected"))
            print("    state: %s" % self.pin_state())
            print("    [1] - select firmware file")
            print("    [2] - set PIN")
            print("    [3] - remove PIN")
            print("    [0] - back")
            c = _ask("  > ")
            if c in ("", "0"):
                return
            if c == "1":
                self.pick_firmware()
            elif c == "2":
                self.pin_set()
            elif c == "3":
                self.pin_remove()
            else:
                print("  no such item")

    # -------------------------------------------------------------- подменю
    def zone_menu(self):
        while True:
            print()
            print("  zone settings:")
            print("    [1] - offset: 0x%X" % self.offset)
            print("    [2] - size: %dx%d %s" % (self.width, self.height,
                                            "(LE)" if self.bswap else "(BE)"))
            print("    [3] - pixel byte order: %s" % ("little-endian" if self.bswap else "big-endian"))
            print("    [4] - reset to defaults (0x%X, %dx%d, BE)" % (
                SPLASH_OFF, SPLASH_W, SPLASH_H))
            print("    [0] - back")
            c = _ask("  > ")
            if c in ("", "0"):
                return
            if c == "1":
                self.offset = _ask_int("  offset (hex or dec)", self.offset, 0)
            elif c == "2":
                self.width = _ask_int("  width", self.width, 1, 0x4000)
                self.height = _ask_int("  height", self.height, 1, 0x4000)
            elif c == "3":
                self.bswap = not self.bswap
                print("  now %s" % ("little-endian" if self.bswap else "big-endian"))
            elif c == "4":
                self.offset, self.width, self.height = SPLASH_OFF, SPLASH_W, SPLASH_H
                self.bswap = False
                print("  reset")
            else:
                print("  no such item")

    def options_menu(self):
        while True:
            print()
            print("  replacement options:")
            print("    [1] - image: %s" % (self.image or "not selected"))
            print("    [2] - fit: %s" % FIT_NAMES[self.fit_mode])
            print("    [3] - background color: #%s" % self.bg)
            print("    [4] - rotate: %d" % self.rotate)
            print("    [5] - flip horizontally: %s" % _onoff(self.flip_h))
            print("    [6] - flip vertically: %s" % _onoff(self.flip_v))
            print("    [7] - save preview: %s" % _onoff(self.preview_keep))
            print("    [0] - back")
            c = _ask("  > ")
            if c in ("", "0"):
                return
            if c == "1":
                self.pick_image()
            elif c == "2":
                i = FIT_MODES.index(self.fit_mode)
                self.fit_mode = FIT_MODES[(i + 1) % len(FIT_MODES)]
                print("  now: %s" % FIT_NAMES[self.fit_mode])
            elif c == "3":
                while True:
                    s = _ask("  background RRGGBB [%s]: " % self.bg, self.bg).lstrip("#").lower()
                    try:
                        int(s, 16)
                        if len(s) == 6:
                            self.bg = s
                            break
                    except ValueError:
                        pass
                    print("  need 6 hex digits (e.g. ffffff)")
            elif c == "4":
                while True:
                    v = _ask_int("  rotation (0/90/180/270)", self.rotate)
                    if v in (0, 90, 180, 270):
                        self.rotate = v
                        break
                    print("  allowed: 0, 90, 180 or 270")
            elif c == "5":
                self.flip_h = not self.flip_h
            elif c == "6":
                self.flip_v = not self.flip_v
            elif c == "7":
                self.preview_keep = not self.preview_keep
            else:
                print("  no such item")


def run_menu():
    m = Menu()
    print()
    print("=" * 70)
    print("  HG-UV98 - boot splash image (160x128 RGB565) by dkxce")
    print("  Everything is done from this menu; no arguments needed.")
    print("=" * 70)
    while True:
        print()
        m.state()
        print()
        print("  [1] - select firmware file")
        print("  [2] - extract current splash to PNG")
        print("  [3] - replace splash with an image")
        print("  [4] - zone settings (offset, size, byte order)")
        print("  [5] - replacement options (image, fit, rotate, flips)")
        print("  [6] - select COM port")
        print("  [7] - download firmware from the radio")
        print("  [8] - upload firmware to the radio")
        print("  [9] - PIN lock (set / remove)")
        print("  [0] - exit")
        c = _ask("  > ")
        if c in ("0", "q", "exit"):
            print("  done")
            return 0
        if c == "1":
            m.pick_firmware()
        elif c == "2":
            m.extract()
        elif c == "3":
            m.replace()
        elif c == "4":
            m.zone_menu()
        elif c == "5":
            m.options_menu()
        elif c == "6":
            m.port_menu()
        elif c == "7":
            m.radio_download()
        elif c == "8":
            m.radio_upload()
        elif c == "9":
            m.pin_menu()
        else:
            print("  no such item - enter 0..9")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        try:
            return run_menu()
        except (KeyboardInterrupt, EOFError):
            print("\nbye")
            return 0
    p = argparse.ArgumentParser(
        description="Replace the boot splash (160x128 RGB565) in an HG-UV98 firmware image.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, with_offset=True):
        sp.add_argument("firmware", help="firmware .bin file")
        if with_offset:
            sp.add_argument("--offset", type=lambda s: int(s, 0), default=SPLASH_OFF,
                            help="splash zone offset in the file (default 0x130)")
            sp.add_argument("--width", type=int, default=SPLASH_W)
            sp.add_argument("--height", type=int, default=SPLASH_H)
            sp.add_argument("--bswap", action="store_true",
                            help="little-endian pixel byte order")
        sp.add_argument("--force", action="store_true", help="skip the HG-UV98 image check")

    e = sub.add_parser("extract", help="extract the current splash to PNG")
    common(e)
    e.add_argument("output", help="where to save the PNG")
    e.set_defaults(func=cmd_extract)

    r = sub.add_parser("replace", help="replace the splash with an image")
    common(r)
    r.add_argument("image", help="input image (PNG; any format with Pillow)")
    r.add_argument("--out", help="write the patched image to a new file")
    r.add_argument("--in-place", action="store_true", help="overwrite the source file")
    r.add_argument("--backup", action="store_true", help="with --in-place: keep a .bak")
    r.add_argument("--fit", choices=("cover", "stretch", "contain"), default="cover",
                   help="cover - fill and crop (default), stretch - fit exactly, "
                        "contain - fit inside with --bg borders")
    r.add_argument("--bg", default="ffffff", help="border color for --fit contain (RRGGBB)")
    r.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0,
                   help="rotate the image clockwise (if it shows sideways)")
    r.add_argument("--flip-h", action="store_true", help="mirror horizontally")
    r.add_argument("--flip-v", action="store_true", help="mirror vertically")
    r.add_argument("--preview", help="save a PNG preview of what was written")
    r.set_defaults(func=cmd_replace)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except ValueError as e:
        raise SystemExit("%s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
