## Lanchonlh HG-UV98 Bootscreen

[RU](replace_splash.md) | [EN](replace_splash.en.md)

The screensaver in the image lies on the file offset**`0x130`, exactly 40,960 bytes** (`0x130..0xA130`) format**RGB565, senior byte first, 160×128**. The code starts just behind the zone (`0xA130`), so the script always writes a fixed block - the file size and the rest of the image remain the same byte-byte.

Any image is scaled 160×128 (bilinear), encoded in RGB565 and written into a zone. There.`extract`- pull out the current screensaver in PNG (convenient as a template / for verification).

## Finished assembly (exe)

Next to the script lies[assembled](dist/replace_splash.exe) **`dist\replace_splash.exe`**It can be used without installing Python and dependencies:

```
"dist\replace_splash.exe"            # интерактивное ASCII-меню (все операции)

"dist\replace_splash.exe" extract fw.bin splash.png
"dist\replace_splash.exe" replace fw.bin logo.png --out fw_patched.bin --preview check.png
```

It completely repeats the possibilities.`replace_splash.py`:
-**picture**(screensaver 160×128) in firmware - command`replace`optionally`--fit`, `--bg`, `--rotate`, `--flip`, `--preview`etc., and`extract`current screensaver in PNG;
-**patch the radio through the COM port**Items 6-8 of the menu: port selection,`upload firmware to the radio`(YMODEM firmware filler) and`download firmware from the radio`(Dumping) For COM-mode in exe already built-in`pyserial`protocol`ymodem.py`.

Binary portable: works from any directory, without Python and`pip`. The application is distributed as a single file; if its properties are blocked by Windows after copying, unlock through Properties → Unblock.

## Use (script, .py)

Without arguments, the script opens an ASCII dialog menu where all operations are available:

```
cd fw
python replace_splash.py
```

Menu and messages - in English (in English)`1 - select firmware file`, `2 - extract current splash to PNG`. . . When choosing firmware and pictures, the script shows**numbered list of current folder files** (`*.bin`for firmware - each file shows the size and version of the firmware; PNG/JPEG/BMP/GIF/WebP for the picture: the number selects the file,`0`Manually enter the path, empty Enter is the default file. Menu items: firmware selection, retrieval, replacement (into a new file / on-site with)`.bak`/ no copy), zone settings (shift, size, order of bytes) and replacement parameters (`cover`/`stretch`/`contain`, background, turn, mirrors, preview. The script shows the current state and does not require to remember anything.

The same operations with arguments (for scripts):

```
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

Options:`--fit cover|stretch|contain`by default`cover`- to fill with central trimming,`--bg RRGGBB`, `--rotate 0|90|180|270`, `--flip-h/-v`, `--offset`, `--width/--height`, `--bswap`(If the panel is waiting for little-endian),`--force`(Please check that this is an image of HG-UV98)`--preview out.png`PNG of what is actually recorded.

Images: PNG is readable by its implementation (8/16 bits, gray / RGB / palette / alpha, filters 0-4). If you put Pillow - additionally JPEG/BMP/GIF/WebP. Transparency is composited into white.

## Radio (COM port)

Items 6-8 of the main menu work with the radio via the COM port (YMODEM, IAP loader 3.3.0);`pyserial` (`python -m pip install pyserial`) and the protocol`ymodem.py`.

* **6 - select COM port**: list of ports, selection by number (current marked)`*`), enter the name manually, speed (default 115200) and timeout waiting dump.
* **7 - download firmware from the radio**: waits for the loader banner, sends itself`2`(Upload Image), asks the file name for the dump (by default)`fw_dump_<YYYYmmddHHMMSS>.bin`in the current folder; you can specify the path with the subfolder, takes 496 packets into this file, then prints the block**firmware info**(size and number of 1K packets, match with HG-UV98 image, version, date, SHA-256, signature strings and screensaver) and makes the downloaded file the current firmware.
* **8 - upload firmware to the radio**: shows the same block**firmware info**and asks for confirmation of the firmware of this version, sends`1`(Download Image) with a progress bar, and after a successful recording offers to send immediately`3`(Execute The New Program)

Before the opening of the port, both items are asked`is the bootloader menu already on the radio screen?`: `y`- the point key goes away immediately,`n`The script is waiting for the inclusion banner (the radio is turned on with the pinched PTT) up to 60 seconds. If the exchange has not started, a repeat is suggested: press`1`/`2`on the radio and Enter (up to three attempts),`q`- output; in case of final failure, the last received bytes are printed in hex. Direction is printed above the scale (`UPLOAD PC -> radio`or`DOWNLOAD radio -> PC`), and it is in each row of the scale; the port closes only after the radio response and transmission.`3`.

## What's tested

* `extract`PNG: This is the image of "LANCHONLH / FM DUAL BANDER + APRS" 160×128.
* **Round-trip:**Extract it back to replace it.**0 different bytes**(The encoder/decoder match exactly).
* Replacement with test image: only bytes inside are changed`0x130..0xA130` (`outside zone: 0`size`0x7C000`Save, code with`0xA130`untouched.
* Options`--rotate 90 --flip-h --fit contain --bg 00ff00`, `--fit stretch`, `--in-place --backup`- worked out, previews are visually verified (quadrants and gradient in place, turn / mirror are applied as stated).

## Firmware

* Radio FW: PwrOn + PTT
* APRS FW: PwrOn + PF2

To connect to the radio, open hyperterminal and start a new serial session using 1152000.8 n . 1st  
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