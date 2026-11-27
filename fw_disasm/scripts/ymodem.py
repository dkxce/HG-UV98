#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""Чистая реализация YMODEM для STM32/GD32 IAP-загрузчика HG-UV98.

Протокол — стандартный YMODEM (YMODEM-1K), используемый ST X-CUBE-IAP-USART
и встроенным загрузчиком рации Lanchonlh HG-UV98 (это "In-Application
Programming Application 3.3.0" для STM32F10x). Совместим с
canique/stm32-flasher, но чисто реализует и приём (upload из МК) и передачу
(download в МК) и исправляет ошибки эталонного кода.

Базовая схема:
  - приёмник (PC) шлёт 'C' (запрос CRC) -> передатчик (МК) шлёт
    пакет 0 (имя+размер), затем блоки данных 0x800 (1024) байт,
    затем два EOT и финальный пустой пакет.
  - CRC: CRC-16/CCITT (0x1021), init 0, старший байт первым.

Это API-модуль; точками входа являются flash_dump.py (upload из МК)
и flash_upload.py (download в МК).
"""
from __future__ import annotations

import os
import time as _time

# служебные байты протокола
SOH = b"\x01"     # 128-байтный блок
STX = b"\x02"     # 1024-байтный блок
EOT = b"\x04"
ACK = b"\x06"
NAK = b"\x15"
CAN = b"\x18"
CRCCH = b"C"


def _ord(by):
    return by if isinstance(by, int) else ord(by)


def _b(v):
    return bytes((v,))


# ---------------------------------------------------------------------------
# CRC-16/CCITT (XMODEM): полином 0x1021, init 0
# ---------------------------------------------------------------------------
def _make_crctable():
    t = []
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) \
                else (crc << 1) & 0xFFFF
        t.append(crc & 0xFFFF)
    return t


CRCTABLE = _make_crctable()


def calc_crc(data, crc=0):
    """CRC-16/CCITT по последовательности байт."""
    for ch in bytearray(data):
        idx = ((crc >> 8) ^ ch) & 0xFF
        crc = ((crc << 8) ^ CRCTABLE[idx]) & 0xFFFF
    return crc & 0xFFFF


# ---------------------------------------------------------------------------
# Выбор пункта меню загрузчика IAP 3.3.0
# ---------------------------------------------------------------------------
def select_menu(getc, putc, key, wait=30.0, quiet=0.4, banner_cb=None):
    """Дождаться появления меню загрузчика и отправить выбранный пункт.

    Загрузчик рации при включении с зажатым PTT печатает в COM баннер и
    меню ("Download ... ----------- 1" и т.д.), после чего ждёт ввода
    пункта С КЛАВИАТУРЫ ТЕРМИНАЛА через тот же COM-порт ('1'/'2'/'3').
    Эта функция ждёт, пока от рации придёт хоть байт (признак, что меню
    отобразилось), затем отправляет key (b'1', b'2' или b'3').

    getc(n) / putc(b) — как в YModem.
    banner_cb(bytes) — если задан, вызывается с полученным текстом баннера.
    Возвращает True, если ключ отправлен; False по таймауту wait (сек).
    """
    deadline = _time.monotonic() + wait
    got_any = False
    banner = bytearray()
    last_seen = _time.monotonic()
    while _time.monotonic() < deadline:
        c = getc(1)
        if c:
            got_any = True
            banner += c
            last_seen = _time.monotonic()
        elif got_any and _time.monotonic() - last_seen > quiet:
            # баннер закончился — меню отобразилось, теперь можно слать ключ
            break
        else:
            pass  # тишина до появления рации
    if banner_cb and banner:
        banner_cb(bytes(banner))
    # ключ отправляем ВСЕГДА: меню могло быть напечатано до открытия порта,
    # тогда новых байт нет и ждать баннер бессмысленно
    putc(key)
    return got_any


# ---------------------------------------------------------------------------
# YMODEM
# ---------------------------------------------------------------------------
class YModem(object):
    def __init__(self, getc, putc, header_pad=b"\x00", data_pad=b"\x1a"):
        """
        getc(n)  -> прочитать до n байт с COM-порта (bytes/None по таймауту)
        putc(b)  -> записать байты в COM-порт
        """
        self.getc = getc
        self.putc = putc
        self.header_pad = header_pad  # чем добить блок 0 (имя/размер)
        self.data_pad = data_pad      # чем добить последний блок данных
        self.tx_name = ""
        self.tx_size = 0
        self.rx_name = ""
        self.rx_size = 0
        self.valid_packets = 0        # успешных блоков данных
        self.valid_bytes = 0          # реально отправлено/принято байт данных
        self.log = None               # callable(str) или None
        self.progress = None          # callable(percent, packet_no, total_packets) или None

    def _log(self, msg):
        if self.log:
            self.log(msg)
        else:
            print(msg)

    def _progress(self, packet_no, total, percent=None):
        if self.progress:
            self.progress(percent, packet_no, total)

    # --- заголовки и контрольная сумма ------------------------------------
    def _make_header(self, kind, seq):
        return bytes([_ord(kind), seq & 0xFF, (0xFF - seq) & 0xFF])

    def _packet_crc(self, payload):
        c = calc_crc(payload)
        return bytes((c >> 8, c & 0xFF))

    # --- примитивы ввода/вывода --------------------------------------------
    def _wait_for(self, want, timeout=15.0, accept=(CAN,)):
        """Ждать конкретный байт. Возвращает полученный байт или None по
        таймауту; при двух подряд CAN возвращает -2."""
        cancel = 0
        deadline = _time.monotonic() + timeout
        while True:
            c = self.getc(1)
            if not c:                       # таймаут чтения
                if _time.monotonic() > deadline:
                    self._log("таймаут ожидания %02X" % _ord(want))
                    return None
                continue
            if c == want:
                return c
            if c == CAN:
                cancel += 1
                if cancel >= 2:
                    return -2
                continue
            # иной байт — игнорируем (шум/прогресс "Downloading...")
            self._log("ожидали %02X, получили %02X (игнор)" % (_ord(want), _ord(c)))

    def _wait_any(self, wanted, timeout=10.0):
        """Ждать один из байтов wanted; вернуть байт, 'cancel' или None."""
        deadline = _time.monotonic() + timeout
        cancel = 0
        while True:
            c = self.getc(1)
            if not c:
                if _time.monotonic() > deadline:
                    return None
                continue
            c = c[:1]
            if c in wanted:
                return c
            if c == CAN:
                cancel += 1
                if cancel >= 2:
                    return "cancel"
                continue
            # баннер/эхо/шум — игнорируем

    def _read_packet(self, root_timeout=15.0):
        """Принять целый пакет: тип, seq, ~seq, data, crc.
        Возвращает (kind, payload_without_crc, crc_ok).
          kind == None  -> таймаут (нет данных в окне root_timeout)
          kind == 'CAN' -> передатчик отменил (двойной CAN)
          kind == False -> неполный пакет (обрыв)
        """
        deadline = _time.monotonic() + root_timeout
        while True:
            kind = self.getc(1)
            if not kind:
                if _time.monotonic() > deadline:
                    return None, None, False
                continue
            if kind == SOH:
                plen = 128
            elif kind == STX:
                plen = 1024
            elif kind == CAN:
                # ждём второй CAN как подтверждение отмены
                if self.getc(1) == CAN:
                    return "CAN", None, False
                continue
            elif kind == EOT:
                return "EOT", None, True
            else:
                self._log("ожидали SOH/STX, получили %02X (игнор)" % _ord(kind))
                continue
            # читаем номер пакета и дополнение
            seq = self.getc(1)
            seqoc = self.getc(1)
            if not seq or not seqoc:
                return False, None, False
            seq = _ord(seq)
            body = self.getc(plen + 2)     # данные + CRC(2)
            if body is None or len(body) < plen + 2:
                return False, None, False
            crc_h, crc_l = body[plen], body[plen + 1]
            calc = calc_crc(body[:plen])
            ok = (calc == ((crc_h << 8) | crc_l)) and \
                (_ord(seqoc) == ((0xFF - seq) & 0xFF))
            return kind, body[:plen], ok

    # --- передача: PC -> MCU (download прошивки в рацию) --------------------
    def send_file(self, file_path, retry=10, wait_initial_c=False, initial_timeout=30.0):
        """Отправить бинарный файл в МК по YMODEM (кнопка 1 "Download Image").
        Возвращает число реально отправленных байт данных.

        wait_initial_c=True: сначала ждать символ 'C' (запрос CRC YMODEM) от
        приёмника и только потом слать блок 0. Нужно для реального загрузчика
        HG-UV98: после выбора пункта '1' он сам печатает баннер
        "Waiting for the file to be sent..." и ждёт 'C'-запрос."""
        size = os.path.getsize(file_path)
        name = os.path.basename(file_path)
        self.tx_name, self.tx_size = name, size
        self.valid_packets = self.valid_bytes = 0

        if wait_initial_c:
            self._log("Ожидаю 'C' (запрос CRC YMODEM) от рации...")
            c = self._wait_for(CRCCH, timeout=initial_timeout)
            if c in (None, -2):
                self._abort()
                raise RuntimeError(
                    "no 'C' from the radio (ready for Download? menu 1 selected?)")
            self._log("<<< 'C' получен, начинаю передачу")

        # --- блок 0: имя + размер ---
        head = name.encode("utf-8") if isinstance(name, str) else name
        size_bytes = b"%d" % size
        # блок 0 фиксирован в 128 байт: длинное имя не должно вытеснить размер
        head = head[:max(1, 128 - len(size_bytes) - 2)]
        payload = head + self.header_pad + size_bytes + self.header_pad
        payload = payload.ljust(128, self.header_pad)[:128]
        self.putc(self._make_header(SOH, 0) + payload + self._packet_crc(payload))
        self._log("Packet 0 >>> %s (%d bytes)" % (name, size))

        ack = self._wait_for(ACK)
        if ack in (None, -2):
            self._abort()
            raise RuntimeError("no ACK on packet 0 (radio not ready to receive?)")
        if self._wait_for(CRCCH) in (None, -2):
            self._abort()
            raise RuntimeError("no 'C' after packet 0")

        # --- блоки данных ---
        seq = 1
        err = 0
        packets = (size + 1023) // 1024
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                use_stx = len(chunk) > 128
                pad_len = 1024 if use_stx else 128
                pkt = chunk.ljust(pad_len, self.data_pad)[:pad_len]
                kind = STX if use_stx else SOH
                packet = self._make_header(kind, seq) + pkt + self._packet_crc(pkt)
                while True:
                    self.putc(packet)
                    self._log("Data packet %d/%d >>>" % (self.valid_packets + 1, packets))
                    c = self.getc(1)
                    if c == ACK:
                        self.valid_packets += 1
                        self.valid_bytes += len(chunk)
                        err = 0
                        self._progress(self.valid_packets, packets)
                        break
                    err += 1
                    if err > retry:
                        self._abort()
                        raise RuntimeError("too many errors on packet %d" % seq)
                seq = (seq + 1) & 0xFF

        # --- завершение: EOT; NAK -> ещё EOT; ACK -> финальный пустой блок 0 ---
        acked = False
        for attempt in range(3):
            self.putc(EOT)
            self._log(">>> EOT (%d)" % (attempt + 1))
            r = self._wait_any((ACK, NAK), timeout=10.0)
            if r == ACK:
                acked = True
                break
            if r == "cancel":
                self._log("receiver cancelled")
                return self.valid_bytes
        if not acked:
            raise RuntimeError("EOT was not acknowledged by the radio")

        # --- финальный пустой пакет 0 ---
        payload = bytes(128)
        self.putc(self._make_header(SOH, 0) + payload + self._packet_crc(payload))
        self._log("Packet End >>> (пустой блок 0)")
        self._wait_for(ACK, timeout=5.0)

        return self.valid_bytes

    # --- приём: MCU -> PC (upload прошивки из рации) ------------------------
    def recv_file(self, root_path, max_wait=120, allow_overwrite=False, out_path=None):
        """Принять файл из МК по YMODEM (кнопка 2 "Upload Image").
        Имя из блока 0 кладётся в root_path; если задан out_path — пишем
        ровно туда. Возвращает (имя_файла, размер)."""
        self.valid_packets = self.valid_bytes = 0
        deadline = _time.monotonic() + max_wait

        # --- фаза 1: приглашение 'C' до получения блока 0 ---
        got_header = False
        while not got_header:
            self.putc(CRCCH)
            self._log("<<< 'C' (запрос передачи)")
            kind, payload, ok = self._read_packet(root_timeout=2.0)
            if kind == "EOT":
                continue
            if kind in (SOH, STX) and ok and payload:
                got_header = True
                block0 = payload
                break
            if kind is None:
                # в окне 2 с ответа нет: повторяем 'C', пока не истечёт max_wait
                if _time.monotonic() > deadline:
                    raise TimeoutError(
                        "no start packet from the radio - is it in Upload mode "
                        "(menu 2) and the COM port right?")
                continue
            if _time.monotonic() > deadline:
                raise TimeoutError(
                    "no start packet from the radio - is it in Upload mode "
                    "(menu 2) and the COM port right?")

        # --- блок 0: имя и размер ---
        try:
            sep = block0.index(b"\x00")
        except ValueError:
            sep = len(block0)
        name = block0[:sep].decode("utf-8", "replace")
        rest = block0[sep + 1:]
        try:
            size = int(rest.split(b"\x00")[0].decode("ascii", "replace"))
        except (ValueError, IndexError):
            size = 0
        self.rx_name, self.rx_size = name, size
        if not name:
            name = "firmware_%06d.bin" % int(_time.time())
        self._log("Пакет 0: файл '%s', %d байт" % (name, size))

        self.putc(ACK)
        self.putc(CRCCH)
        self._log("<<< ACK, 'C'")

        if out_path is None:
            out_path = os.path.join(root_path, name)
        if os.path.exists(out_path) and not allow_overwrite:
            raise FileExistsError(
                "file already exists: %s (use --overwrite)" % out_path)

        # --- блоки данных ---
        expected_packets = (size + 1023) // 1024 if size else None
        received_packets = 0
        f = open(out_path, "wb")
        try:
            while True:
                kind, payload, ok = self._read_packet(root_timeout=10.0)
                if kind == "EOT":
                    # первый EOT: приёмник просит передать остаток/подтверждает
                    self.putc(ACK if received_packets else NAK)
                    # дождаться второго EOT (или финального пустого блока)
                    self._finish_after_eot()
                    break
                if kind is None:
                    self._abort()
                    raise RuntimeError("sender cancelled the transfer (CAN)")
                if kind is False:
                    raise TimeoutError("timeout receiving data from the radio")
                if not ok:
                    self.putc(NAK)
                    self._log("CRC ошибка -> NAK")
                    continue
                # если все ожидаемые пакеты уже получены — этот пакет только
                # финальный пустой блок 0 (конец передачи)
                if expected_packets is not None and received_packets >= expected_packets:
                    self.putc(ACK)
                    self._log("Packet End >>> (пустой блок 0)")
                    break
                # данные
                if expected_packets and received_packets + 1 == expected_packets:
                    remain = size - self.valid_bytes
                    f.write(payload[:remain])
                    self.valid_bytes += remain
                    received_packets += 1
                else:
                    f.write(payload)
                    self.valid_bytes += len(payload)
                    received_packets += 1
                self.valid_packets = received_packets
                self._log("Data packet %d/%s <<< %d байт" % (
                    received_packets,
                    expected_packets if expected_packets else "?",
                    len(payload)))
                self._progress(
                    received_packets,
                    expected_packets if expected_packets else received_packets)
                self.putc(ACK)
        finally:
            f.close()

        self._log("Готово: %s, принято %d байт, %d пакетов"
                  % (name, self.valid_bytes, self.valid_packets))
        return name, self.valid_bytes

    def _finish_after_eot(self):
        """Завершение передачи в роли приёмника после получения EOT.

        По YMODEM после первого EOT передатчик шлёт второй EOT, затем (в
        варианте для ST IAP) пустой финальный блок 0. Принимаем любой из
        этих вариантов в течение короткого окна."""
        # короткое окно: ждём второй EOT или пустой блок 0
        deadline = _time.monotonic() + 5.0
        while _time.monotonic() < deadline:
            kind, payload, ok = self._read_packet(root_timeout=0.5)
            if kind == "EOT":
                self.putc(ACK)
                self._log("<<< ACK на второй EOT")
                # посмотрим, нет ли ещё финального пустого блока
                continue
            if kind is not None and kind is not False and ok and \
                    kind == SOH and (payload is None or not any(payload)):
                self.putc(ACK)
                self._log("<<< ACK на финальный пустой блок 0")
                return
            if kind is None or kind is False:
                # таймаут окна — считаем передачу завершённой
                return
            # что-то иное — игнорируем до конца окна
        # конец окна: завершаем
        self._log("Окно завершения истекло — считаю передачу завершённой")

    # --- служебное ---
    def _abort(self):
        self.putc(CAN)
        self.putc(CAN)


if __name__ == "__main__":
    # самопроверка CRC
    assert calc_crc(b"123456789") == 0x31C3, hex(calc_crc(b"123456789"))
    assert calc_crc(b"") == 0x0000
    print("CRC-16/CCITT self-check OK: calc_crc(b'123456789')=0x%04X"
          % calc_crc(b"123456789"))
    print("YMODEM module OK")