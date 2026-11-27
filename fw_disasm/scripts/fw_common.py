#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""Общие утилиты для flash_dump.py / flash_upload.py: список COM-портов,
определение версии прошивки в бинарнике и однострочный progress-bar."""
from __future__ import annotations

import os
import re
import sys


def list_ports():
    """Вернуть список [(device, description)] доступных COM-портов."""
    try:
        import serial.tools.list_ports as list_ports_mod
        return [(p.device, p.description or "") for p in list_ports_mod.comports()]
    except Exception:
        return []


def pick_port():
    """Если есть несколько портов — показать список и дать выбрать."""
    ports = list_ports()
    print("==== Доступные COM-порты ====")
    for i, (dev, desc) in enumerate(ports, 1):
        print("  [%d] %-6s %s" % (i, dev, desc))
    if not ports:
        print("  (порты не найдены)")
        return input("Введите COM-порт вручную (например COM9): ").strip()
    while True:
        s = input("\nВыберите номер порта [1-%d]: " % len(ports)).strip()
        try:
            idx = int(s)
            if 1 <= idx <= len(ports):
                return ports[idx - 1][0]
        except ValueError:
            pass
        # возможно, ввели имя напрямую
        if s.upper().startswith("COM"):
            return s.upper()


WANT_FW_SIZE = 507904
WANT_PACKETS = (WANT_FW_SIZE + 1023) // 1024  # 496


class ProgressBar:
    """Однострочный progress-bar, перезаписывает текущую строку через \\r."""

    WIDTH = 18

    def __init__(self, enabled=True):
        self.enabled = enabled

    def update(self, percent, packet_no, total):
        if not self.enabled or sys.stdout.isatty() is False and percent is None:
            pass
        percent = 0 if percent is None else int(percent)
        filled = int(self.WIDTH * percent / 100.0)
        bar = "\u2588" * filled + "\u2591" * (self.WIDTH - filled)
        sys.stdout.write(
            "\r[" + bar + "] %d%%  Пакет: %d/%d" %
            (percent, packet_no, total))
        sys.stdout.flush()

    def done(self):
        if self.enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()


# Паттерны версии в бинарнике прошивки HG-UV98.
# Порядок важен: сначала специализированные, потом общие.
VERSION_PATTERNS = [
    re.compile(rb"V(\d\.\d(?:\.\d)?)[-_ ]?(\d{6})"),   # V1.1_210517 / V1.2_211026
    re.compile(rb"(\d\.\d\.\d)[-_ ]?(\d{6})"),          # 1.0.1_190416
    re.compile(rb"V(\d\.\d)(?:_|-)(\d{6})"),
    re.compile(rb"(\d{6})[-_ ]?V(\d\.\d)"),
]


def detect_version(blob):
    """Искать версию и дату в бинарнике прошивки.

    Возвращает строку вида 'V1.2_211026' или None, если не найдено.
    blob — bytes прошивки."""
    if not blob:
        return None
    for pat in VERSION_PATTERNS:
        m = pat.search(blob)
        if m:
            groups = m.groups()
            ver = groups[0].decode("ascii", "replace")
            date = groups[1].decode("ascii", "replace") if len(groups) > 1 else ""
            # нормализуем: V1.2 -> V1.2, даты 6 цифр
            if not ver.startswith("V"):
                ver = "V" + ver
            return ver + ("_" + date if date else "")
    return None


def version_of_file(path):
    """Версия прошивки по файлу (только первые/последние 512 КБ хватает,
    но читаем весь — файлы 507904 байт)."""
    try:
        with open(path, "rb") as f:
            blob = f.read()
        return detect_version(blob)
    except Exception:
        return None