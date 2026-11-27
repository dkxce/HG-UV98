## Lanchonlh HG-UV98 Bootscreen

[RU](replace_splash.md) | [EN](replace_splash.en.md)     

Заставка в образе лежит по файловому смещению **`0x130`, ровно 40 960 байт** (`0x130..0xA130`), формат **RGB565, старший байт первым, 160×128**. Сразу за зоной начинается код (`0xA130`), поэтому скрипт всегда пишет фиксированный блок — размер файла и весь остальной образ остаются байт-в-байт прежними.

Любая картинка масштабируется под 160×128 (билинейно), кодируется в RGB565 и записывается в зону. Есть `extract` — вытащить текущую заставку в PNG (удобно как шаблон/для проверки).

## Использование

Без аргументов скрипт открывает диалоговое ASCII-меню, где доступны все операции:

```bash
cd fw
python replace_splash.py
```

Меню и сообщения — на английском (`1 - select firmware file`, `2 - extract current splash to PNG`, …). При выборе прошивки и картинки скрипт показывает **пронумерованный список файлов текущей папки** (`*.bin` для прошивки — у каждого файла показываются размер и версия прошивки; PNG/JPEG/BMP/GIF/WebP для картинки): номер выбирает файл, `0` — ввод пути вручную, пустой Enter — файл по умолчанию. Пункты меню: выбор прошивки, извлечение, замена (в новый файл / на месте с `.bak` / без копии), настройки зоны (смещение, размер, порядок байт) и параметры замены (`cover`/`stretch`/`contain`, фон, поворот, зеркала, предпросмотр). Скрипт показывает текущее состояние и не требует ничего помнить.

Те же операции аргументами (для скриптов):

```bash
cd fw

# 1. вытащить текущую заставку как шаблон (160x128 PNG)
python replace_splash.py extract "Lanchonlh HG-UV98 Radio Firmware V1.2_211026.bin" splash.png

# 2. заменить (в новый файл; исходник не трогается)
python replace_splash.py replace fw.bin logo.png --out fw_patched.bin --preview check.png

# 3. заменить на месте с резервной копией
python replace_splash.py replace fw.bin logo.png --in-place --backup

# 4. если на экране картинка повёрнута/зеркальна
python replace_splash.py replace fw.bin logo.png --out out.bin --rotate 90 --flip-h

# 5. вписать целиком с полями (не обрезать)
python replace_splash.py replace fw.bin logo.png --out out.bin --fit contain --bg ffffff
```

Опции: `--fit cover|stretch|contain` (по умолчанию `cover` — заполнить с центральной обрезкой), `--bg RRGGBB`, `--rotate 0|90|180|270`, `--flip-h/-v`, `--offset`, `--width/--height`, `--bswap` (если панель ждёт little-endian), `--force` (пропустить проверку, что это образ HG-UV98), `--preview out.png` — PNG того, что реально записано.

Картинки: PNG читается своей реализацией (8/16 бит, серый/RGB/палитра/alpha, фильтры 0–4). Если поставить Pillow — дополнительно JPEG/BMP/GIF/WebP. Прозрачность композитится на белый.

## Радио (COM-порт)

Пункты 6–8 главного меню работают с рацией через COM-порт (YMODEM, загрузчик IAP 3.3.0); нужен `pyserial` (`python -m pip install pyserial`) и протокол из `ymodem.py`.

- **6 — select COM port**: список портов, выбор по номеру (текущий помечен `*`), ввод имени вручную, скорость (по умолчанию 115200) и таймаут ожидания дампа.
- **7 — download firmware from the radio**: ждёт баннер загрузчика, сам отправляет `2` (Upload Image), спрашивает имя файла для дампа (по умолчанию `fw_dump_<YYYYmmddHHMMSS>.bin` в текущей папке; можно указать путь с подпапкой), принимает 496 пакетов в этот файл, после чего печатает блок **firmware info** (размер и число 1K-пакетов, совпадение с образом HG-UV98, версия, дата, SHA-256, наличие сигнатурных строк и заставки) и делает скачанный файл текущей прошивкой.
- **8 — upload firmware to the radio**: показывает тот же блок **firmware info** и просит подтверждение прошивки именно этой версии, отправляет `1` (Download Image) с прогресс-баром, а после успешной записи предлагает сразу отправить `3` (Execute The New Program).

Перед открытием порта оба пункта спрашивают `is the bootloader menu already on the radio screen?`: `y` — клавиша пункта уходит сразу, `n` — скрипт ждёт баннер включения (рация включается с зажатым PTT) до 60 с. Если обмен не начался, предлагается повтор: нажмите `1`/`2` на самой рации и Enter (до трёх попыток), `q` — выход; при окончательной неудаче печатаются последние полученные байты в hex. Над шкалой печатается направление (`UPLOAD  PC -> radio` или `DOWNLOAD  radio -> PC`), и оно же стоит в каждой строке шкалы; порт закрывается только после ответа рации и передачи `3`.

## Что проверено

- `extract` исходной заставки → PNG: получается та самая картинка «LANCHONLH / FM DUAL BANDER+APRS» 160×128.
- **Round-trip:** extract → replace обратно даёт **0 отличающихся байт** (кодер/декодер совпадают точно).
- Замена тестовой картинкой: изменены только байты внутри `0x130..0xA130` (`outside zone: 0`), размер `0x7C000` сохранён, код с `0xA130` не тронут.
- Варианты `--rotate 90 --flip-h --fit contain --bg 00ff00`, `--fit stretch`, `--in-place --backup` — отработали, предпросмотры визуально сверил (квадранты и градиент на месте, поворот/зеркало применяются как заявлено).

## Прошивка

- Radio FW: PwrOn + PTT
- APRS  FW: PwrOn + PF2 

To connect to the radio, open hyperterminal and start a new serial session using 1152000,8,n,1      
Now hold the PTT button and turn on the radio.     
You will get the following screen:    
 
```
======================================================================
=              (C) COPYRIGHT 2018 STMicroelectronics                 =
=                                                                    =
=     In-Application Programming Application  (Version 3.3.0)        =
=                                                                    =
=                                                                    =
======================================================================


=================== Main Menu ============================

  Download Image To the STM32F10x Internal Flash ------- 1

  Upload Image From the STM32F10x Internal Flash ------- 2

  Execute The New Program ------------------------------ 3

==========================================================
```

To get the flash image from the processor, type 2 then click on Transfer, receive file and use YMODEM.
496 packets of 1kb will now be transferred to your destination folder.     

Using this approach I extracted two different firmware versions from my two radios (see attachments).     

Downloading the firmware to the radio should be possible by pressing 1.