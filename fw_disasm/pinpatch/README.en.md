# HG-UV98 PIN Lock (V1.1 firmware patch)

[RU](README.md) | [EN](README.en.md)

When turned on, the radio shows the screen`RADIO LOCK`It does not start until the correct PIN is entered from the keyboard.
After the correct code, the bootscreen is drawn again and the download continues normally.

PIN (4-6 digits) is set when the script is started and sewn into the image.

## Keyboards

| Code. | keyboard | Action. |
| --- | --- | --- |
| 0-9 | figures | symbolization |
| 10 | Menou | confirm |
| 13 | AB/BACK | erase |
| 11, 12. | UP / DOWN | ignored |
| 14, 15. | `*`, `#` | ignored |

Verification under way**Menus only**There is no automatic length check.
If you press MENU with the digits entered, but the length does not match the PIN, this is
mistake. You can't get out of the lockdown.

Codes are taken from recovered tables: 10 = MENU, 11/12 = up/down, 13 = BACK, 14/15 =`*`/`#`.

## What changes in image

| What? | File. | Address | It was. | Stallo |
| --- | --- | --- | --- | --- |
| Hook in the boot scene | 0x177A8 | 0x0801B7A8 | `adds.w r7, r5, #0x142` | `b.w 0x0804A000` |
| Payload | 0x46000 | 0x0804A000 | 0xFF (erasing) | 2924 bytes |

No more bytes change - checked by byte diff
(range 0x177A8...0x46B6B, 2891 different bytes).

## How it works.

* Hook stands right after the screensaver is taken out.
* Stub executes the repressed instruction and returns to 0x0801B7AC.
* Drawing - directly into the panel:`display_set_window`0x0801B9B .`tft_write_cmd`0x0801BA52 .`tft_write_byte`0x0801BA74 - same
  consistency that the staff`display_fill_rect`, including PC2.
  No buffers on the stack: frame function ≤ 48 bytes (task stack ~1 KB).
  Your 8×16 (1520 bytes) font is sewn into payload.
* Input -`key_scan`0x0802819A (bypasses keyboard lock settings).
* If`ADC2.CR2.ADON = 0`, called the regular initialization of ADC
  0x080294F8 – otherwise, the wait for the EOC in the keyboard scan will not end.
* After the password:`display_blit_image(0, 0, 128, 160, 0x08004130, 0xA000)`-
  bootscreen.

## File structure

Patch is collected from the source, and the finished payload is sewn directly into`patch_password.py`So you don't need Tulchain for a patch.

| File. | What is it? | Responsible for |
| --- | --- | --- |
| `patch_password.py` | Patcher (main script) | Stitches the PIN into the image: inserts the payload into the 0x46000 area, puts the hook`b.w`In 0x0801B7A8, checks the built-in payload by MD5. It contains a ready-made payload (hex) + PIN slot. Python 3 is enough to work without Tulchain |
| `payload.c` | Source payload in C | Logic of locking: rendering the PIN screen, input from`key_scan`Check code, bootscreen after success. Works in the free domain 0x0804A000 |
| `pinblob.c` | PIN slot (separate unit) | Massive`pin_blob[16]`magic`PWN1`, length, numbers, XOR control. Taken to a separate file so that GCC does not fold the patched bytes into a constant and discard the code |
| `start.S` | Payload entry point | Stub: saves registers, calls`pin_gate()`, executes the repressed instruction and returns to 0x0801B7AC |
| `font.S` | Font connection | Includes`font8x16.bin`sectionally`.rodata`how`font8x16` |
| `font8x16.bin` | Font 8×16 (1520 bytes) | ASCII-glyphs for all inscriptions on the screen |
| `link.ld` | Link script | Distributes sections from 0x0804A000:`.text`, `.rodata`, `.pinblob`, `.data` |
| `payload.bin` | Collected payload (ready) | Result of assembly:`arm-none-eabi-gcc … && objcopy`; put in the form of a patcher |
| `dist\patch_password.exe` | Ready patcher (Windows) | Self-sufficient exe: built-in Python + payload, tolchain and Python**leave out**. Starts in the same place, or from any folder, if you specify the full path |
| `fw_v1.1_2DKXCE.bin` | Original V1 firmware dump. 1st | Input image for patch; does not change |
| `README.md` | Documentation. | This file |

Payload build scheme:

```
start.S + payload.c + pinblob.c + font.S + font8x16.bin
    +---------------------+----------------+
    v                                        |
 arm-none-eabi-gcc -O0 -T link.ld            |
    v                                        |
 payload.elf                                |
    | objcopy -O binary                     |
    v                                        |
 payload.bin -------------------------------+
    |
    +-> patch_password.py (встроен hex+MD5-сверка)
        |
        v
fw_v1.1_2DKXCE.bin  ->  patch_password.py --pin 1234 -o locked.bin
                        |
                        v
                   locked.bin (патченый образ)
```

## Examples of use (launch)

The script works on any Python 3 without a toulchain – ready-made payload already
embedded`patch_password.py`.

Help:

```
python patch_password.py --help
```

Patch the image by specifying the PIN in the command line:

```
python patch_password.py fw_v1.1_2DKXCE.bin --pin 1234 -o locked.bin
```

Example of conclusion:

```
Image: original, no PIN lock.

Done.
  image:      locked.bin
  size:       507904 bytes
  PIN:        4 digits (stored in the image, plaintext)
  payload:    0x0804A000, 2924 bytes
  hook:       0x0801B7A8 -> 2ef02abc
  input md5:  a5f4d0edf8991dc8e5c89891beab1872
  output md5: e3ee395d878851f3c147cd9caa5299a2

Flash via IAP 'Download Image', COM 115200 8N1, file locked.bin
```

If`--pin`not specified, the script will ask for the password interactively (entering does not
screened, it's just a line:

```
python patch_password.py fw_v1.1_2DKXCE.bin
```

```
Radio password (4-6 digits): 123456
```

If not.`-o`The output file is created next to the original file under the name`<имя_без_расширения>_locked.bin`.

Check the image (original, patched or alien):

```
python patch_password.py fw_v1.1_2DKXCE.bin --check
python patch_password.py locked.bin --check
```

```
Image: original, no PIN lock.
Image: PATCHED (PIN lock active).
```

Incorrect PIN (not 4-6 digits) is rejected on the input:

```
python patch_password.py fw_v1.1_2DKXCE.bin --pin 12a
```

```
Error: PIN must be 4-6 digits.
```

`--force`allows you to patch an image whose bytes of the hook do not match
Known (for example, after experiments) - use consciously:

```
python patch_password.py unknown_image.bin --pin 1234 --force
```

### Ready Exe (without Python)

In a file.`dist\`laid`patch_password.exe`- self-sufficient
Windows binary with built-in Python and payload. For him.**leave out**neither
Tulchain or Python installed: runs on any Windows x64.

From the file.`dist`: `--help`The flags and the output example are all like the script above.

```
cd dist
patch_password.exe ..\fw_v1.1_2DKXCE.bin --pin 1234 -o locked.bin
patch_password.exe ..\locked.bin --check
```

You can run from any folder, specifying the full path:

```
"C:\...\pinpatch\dist\patch_password.exe" fw_v1.1_2DKXCE.bin --pin 1234 -o locked.bin
```

Binary is an exact copy`patch_password.py`Behavior: the same built-in
payload, MD5 reconciliations, and output texts (see examples above).

## Build payload

```
arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -O0 -ffreestanding -fno-builtin ^
  -fno-common -nostdlib -nostartfiles -Wl,-T,link.ld -Wl,--gc-sections ^
  -o payload.elf start.S payload.c pinblob.c font.S
arm-none-eabi-objcopy -O binary payload.elf payload.bin
```

**Important:**only`-O0`. Nana`-O1`/`-Os`GCC considers functions called through
pointers to fixed addresses, "clean" and removes calls - payload
It shrinks to 84 bytes and becomes an empty cycle.`-fno-ipa-pure-const`It helps only partially (the lines are missing).`-O0`Gets it all right.

`pin_blob`separate`pinblob.c`so that the compiler does not fold
Patched bytes to constant.

`patch_password.py`contains a ready-made payload in hex with an MD5 reconciliation, so
Tulchain patch is not needed.

## Limitations

* Just a dump.**V1. 1st**(507,904 bytes). The script checks the hook bytes and
  They will refuse to work in any other way.
* UI and main MK keyboard are blocked. APRS-coprocessor STC8 lives
  separately - its transmission patch does not disable.
* PIN is stored openly (it is a lock from accidental inclusion, not crypto protection).
* The loader is not affected: rollback - fill the original dump.

## Checked.

* The image size does not change (507 904);
* Only 4 bytes of the hook and the payload area change.
* Payload in the image of a byte is equal to`payload.bin`(except the PIN slot);
* Call pointers - with Thumb-bit;
* `b.w`Decoded exactly in 0x0804A000;
* PIN Slot: Magic`PWN1`length, numbers, XOR control;
* Repeated patch of the already patched image works;
* PIN validated: 3 digits, 7 digits and letters rejected
* Built-in payload is checked by MD5 at each launch.
* It's on the radio.

## History of corrections

1. In the first build, the built-in payload diverged from the collected by one byte:
   pointer`key_scan`remained even`blx`In the ARM-state → HardFault
   At the first push. Corrected, added MD5 reconciliation.
2. The second version of the GCC`-Os`Deleted all drawing calls (see above)
   build-up`-O0`.
3. The third version drew through 256B buffers on the stack - stack overflow
   tasks, the board showed only the boot logo. Drawing translated
   Direct recording of pixels without buffers.
4. In the fourth version was confused polarity CS: Helper`0x08023770`write**BRRR**(dumping)`0x08023768`in**BSRR**(installation), that is,
   The standard code first resets PC1, and at the end installs. Because
   The panel ignored the entire stream: the screen remained on the
   The screensaver, although PIN input worked.

---

(c) dkxce https://github.com/dkxce