# Инструкция к софту

[ORIGINAL HERE](https://github.com/Mihara/x1c3tool/blob/163a2c89a89dfa66d6e813860f687fe8251821e6/manual/manual.md) |
[РУССКИЙ](Russian.md) | [ENGLISH](Readme.md)

![X1C3 setup tool](setup-marked.png)

### Подключение к устройству

Найдите раздел помеченный на картинке как **0** и переключите пользовательский интерфейс на английский язык. 
К сожалению, вам придется делать это каждый раз, когда вы запускаете программу.

Раздел **1** управляет подключением к устройству. `Serial` обновляет список COM-портов, позволяя вам выбрать нужный из списка. 
`Open/Close` открывает и закрывает порт, `Read` и `Write` соответственно считывают конфигурацию с устройства и записывают ее обратно. 
`Reset` выдает AT-команду, которая сбрасывает конфигурацию до заводских значений по умолчанию, изменения вступают в силу немедленно и перезаписывают 
конфигурацию в EEPROM.

Обратите внимание, что даже если последовательный порт *подключится*, но устройство не подключено или находится не в требуемом режиме, 
чтение конфигурации из него так же как и запись не получится.

### Beaconing

В разделе **2** задается позывной и SSID, с которым устройство идентифицирует себя в эфире. При использовании в режиме прослушивания эфира никакие изменения не требуются. Данные устройства задаются, чтобы устройство самостоятельно работало в режиме Beaconing.

Раздел **3** в первую очередь касается правил отправки данных для Beaconing:

* `GPS ON` включает и отключает встроенный GPS-приемник. Вы можете отключить этот флажок, переключиться в режим `SPORT`, и устройство не будет само подавать сигнал, потому что GPS выключен.
* `Site` — это раскрывающийся список с обманчивым названием, который выбирает, должно ли устройство двигаться или работает стационарно:
  * `FIXED` - стационарный режим. Координаты для отправки берутся из полей раздела **4**. Значения отправляются как есть, поэтому необходимо написать их так, как они описаны в спецификации протокола APRS с указанием N/E/S/W в отдельных полях.
  * 
    Установив `Site` на `FIXED`, отключив все флажки в разделе **3** и установив `Smart` в раскрывающемся списке `OFF`, вы получите чистый Bluetooth TNC режим, который не передает ничего.
    
  * `SPORT` - режим движения. В режиме `SPORT` для отправки координат маяка используются координаты с GPS-приемника. Режим отправки зависит от состояния других флажков и полей в Разделе **3**.

    В данно режиме никакие пакеты не будут отправляться, пока устройство не установит определит GPS координаты по спутникам.
    
  * Режим `WS` не задокументирован.
  
* Раскрывающийся список `Smart` либо отключен, либо включает [интеллектуальный режим](http://www.hamhud.net/hh2/smartbeacon.html) на основе шаблонов движения с использованием одного из предопределенных алгоритмов. Согласно руководству *для X1C5* это означает следующее:
  * `1` - Автомобиль. Интервал оправки координат - 20 сек.
  * `2` - Велосипед. Интервал оправки координат - 40 сек.
  * `3` - Пешеход. Интервал оправки координат - 60 сек.
  * `4` - Черепаха (скалолазание). Интервал оправки координат - 90 сек.
  * `5` - Околостационарный режим. Интервал оправки координат - 120 сек.

* `Manual` заставляет устройство отправлять пакет координат при *отжатии* кнопки PTT, то есть сразу после того, как вы закончите говорить. 
* `Time` устанавливает интервал между автоматической отправкой пакетов координат в радиоэфир. Если установить `Smart` режим и поставить `Time`, скажем, на 300 секунд — пакет координат будет отправляться один раз в заданное количество секунд.
* `Queue` довольно странная опция, потому что этот режим работает параллельно с любым другим. Если вы выберете этот режим, то устройство будет посылать пакеты координат каждую минуту в выбранную секунду из интервала (0..59) исходя из времени полученному по GPS. 

Настройки APRS пакетов для Beaconing также находятся в Разделе **3**:

* `Path1` and `Path2` describe the digipeater path applied to the packets the device generates. Which APRS digipeater path to use is [a more involved discussion than this manual can accommodate](http://www.wa8lmf.net/DigiPaths/index.htm), but the reasonable default is `WIDE1`, `1`, `WIDE2`, `1`, which will translate to `WIDE1-1,WIDE2-1` and means "ask the local area digipeaters to repeat it once, and ask the wide area digipeaters to repeat it once too." Depending on digipeater activity in your area, you might want something else. Setting a faux-SSID dropdown to 0 disables the corresponding path component. Unfortunately, this means you can't have a path component without a SSID at all, though you can, for example, have just `WIDE2-1` as your digipeater path.
* `Type` is the APRS data type identifier, described in the [protocol specification][APRS] on page 17. The factory default is `!`, i.e. that the beacon is a position without timestamp, which additionally indicates the device has no messaging capability. I don't know if anything seriously pays attention to the APRS data type in this day and age, but if you use the device as a tracker-plus-TNC, you might want to put `=` in that field. This will be ignored if you use `MIC-E`, as in that case, the data type identifier field is repurposed.
* `MIC-E` checkbox enables [MIC-E compression][MIC-E], which packages the positioning data into otherwise less-relevant fields in the packet data structure and shortens the packet considerably. The nearby dropdown allows you to select a MIC-E status. If you don't enable this, [APRSDroid](https://aprsdroid.org/) in particular will display course, speed and altitude as part of the message itself, *(with no space between the start of the text message and the end of the speed/course/altitude data, too)* but I think it's actually APRSDroid parsing them wrong here. On the other hand, MIC-E compression is reported to be responsible for [data corruption in certain parts of the APRS network using archaic software](https://owenduffy.net/blog/?p=2326), so depending on where you are, you might want this off.
* `Icon 1` and `Icon 2` allow you to select which APRS icon your beacon will be represented with. You can find the description of what they mean on page 90 of the [APRS protocol spec][APRS]. A more human-readable description can be found in [this APRS symbols list](https://www.aprsdirect.com/symbol/list) -- just remember that in the X1C3 software, the Code column of that table is on the right, and the Table ID column is on the left -- so `/`, `[` means an icon of a human.

  `Icon 1` pair of fields is the default beacon icon. The `Icon 2` pair, with an accompanying field of a number of seconds, will be sent if the device detects you were stationary for that number of seconds or longer -- defaulting to 180. By default, the second icon is a "parking" sign. If you don't want this feature, just set identical icons. Be aware that when using GPS power saving (described below) it's likely that positioning precision will suffer, and your device will be considered always moving, so you'll never see the second icon.

Other important settings in Section **3**:

* `GPS Save(Manual/time)` enables GPS power saving mode. The GPS is kept off until it's time to beacon, upon which it is turned on, the position is reacquired, and the beacon is sent out. Smart beaconing requires a constant GPS fix to function, so if you turn on smart beaconing as well, this checkbox will be ignored.
* `PTT delay` specifies a delay in microseconds between the start of transmission and the start of sound. As far as I can tell, this applies to all packets sent out by the device, including the ones coming in via KISS interface. Set something sensible depending on your radio.

Other *unimportant* settings in Section **3**:

* `CH`: Do not get confused by this dropdown. X1C3 shares much of its hardware and software with the APRS parts of **Lanchonlh HG-UV98** handheld radio, in which this dropdown controls which of the two VFOs beacon packets will go out on. Being an external device connecting over a microphone plug, X1C3 cannot select between VFOs, so this setting has no effect.

Section **5** contains the fields describing extra information that goes into the message part of the beacon, as well as some tangentially related functions.

* The unmarked text field starts the message and can contain more or less anything up to a limit of 60 bytes. Everything else gets tacked on at the end, separated by spaces.
* `Mileage` checkbox will add the distance traveled. `Mileage memory` checkbox will enable saving the mileage counter between reboots if checked. `Mileage clear` button will clear this counter explicitly. As far as I can tell, mileage counter is part of the configuration EEPROM, so saving and loading configuration will mess it up anyway.
* `Voltage` will add the battery voltage.
* `Satellite` will add the number of currently visible satellites.
* `Temp` is supposed to add the current temperature according to the sensor inside the device, which is higher than ambient. Ironically, ticking this checkbox off does nothing and the temperature gets added anyway in the 20201113 version of the firmware.
* `Pressure` adds the pressure according to the sensor inside the device. Not only it's in hectopascales, this checkbox is broken like the temperature one.
* `TX` button will force the device to beacon immediately. This can be used for testing and tuning your radio.

Everything you tack onto the beacon increases transmission time, so it's wise to turn off everything you don't actually need. Unfortunately, bugs prevent you from turning off temperature and pressure.

### Digipeating

Whether the device will digipeat is described by the checkboxes in Section **6**. Both checkboxes correspond to two digipeater aliases the device listens to -- by default, `WIDE1` and `WIDE2`, which makes for a rudimentary, but effective enough digipeating capability.

The `delay` field introduces a delay before digipeating a heard packet.

The six-digit code in Section **7** is related to enabling and disabling digipeating remotely. According to the official manual, the device listens for "a beacon" containing a message in the form of "\<code\>\<command\>" where "command" is one of `A0`,`B0`,`A1`,`B1` and `R0`.

* `A` commands control the alias marked `DIGI 1` while `B` commands control `DIGI 2`
* `1` turns the alias on, while `0` turns it off.
* `R0` command resets the state to the one stored in the EEPROM

Further experimentation is required to ascertain whether this remote control does, in fact, work. I have not managed to invoke it by sending messages into the device from the BT side, so it might only work over the air, if at all.

Which is a shame, because the ability to enable and disable digipeating in the field would be handy.

### Bluetooth settings

While I say "Bluetooth," it appears that internally, the device has only one input-output stream, which is shared between Bluetooth SPP and the USB serial port. It is shared so much, that if you connect to it over Bluetooth, you can use my `x1c3tool` program to save and load configuration this way, so an Android application to manipulate the settings in the field is not out of the realm of possibility -- it just would take more spare time to write than I currently have.

The device's Bluetooth module is always discoverable unless connected. The name is *supposed* to be set to `<callsign>-<ssid>` on power on, but sometimes isn't, because of the way the serial interface gets confused about linebreaks. The default pin code for pairing is `1234`.

The settings that control Bluetooth behavior are in Section **10**:

* The unnamed checkbox enables and disables the Bluetooth module, so you can just plug your device into USB and have an USB-Serial TNC without Bluetooth at all, if you like.
* `Out1` dropdown selects the primary stream behavior:
  * `OFF` just disables everything, which is probably not something you want even if you disable Bluetooth entirely.
  * `KISS Hex` presents a proper KISS TNC interface.
  * `UI` presents a more human-readable interface, where received and transmitted packet contents are printed one per line, and occasional informative messages appear. This is the setting you want while you're tuning your radio and otherwise fiddling with the device. What's very strange is that APRSDroid actually keeps working fine when the device is in this mode, and I'm not entirely clear why -- presumably, the device recognizes KISS traffic when it receives it, but why does APRSDroid accept the one-packet-per-line messages, when it's configured for a KISS TNC?
  * `GPWPL` replaces output of transmitted beacons with NMEA "Waypoint Location" sentences. Received beacons seem not to appear at all. Presumably, you can use this in conjunction with some kind of navigator device for rendering the map, but the specific use case eludes me, since incoming APRS packets aren't getting parsed into GPWPL sentences as far as I can tell.
  * `KISS Asc` prints -- and presumably, expects -- incoming packets as if they were KISS frames, but translates them into a hexadecimal ASCII representation. That is, instead of sending 0xC0, it sends `C0`, etc. The use case eludes me and nothing else seems to work with this format.
* `Out2` is the secondary stream behavior -- rather than present a separate stream as the manual wants to imply, (where would it even do that?) it appears to intermix extra data into the same one.
  * `GPS` dumps raw GPS NMEA output the way it is received from the GPS into the stream. The intention, presumably, is to have an option to take over the beaconing functions of the device from the PC side without having an extra GPS in the system, though it would require some creative fiddling with the serial port to do.
  * `Rotator` is the most obscure function of the device. According to the original manual, the device is capable of controlling a Yaesu antenna rotator through the GS-232B interface to point at the beacons as they are heard. It certainly *tries* to -- in the `UI` mode, you can occasionally see output pertaining to that function, describing calculations of the relative positions resulting in an antenna azimuth. However, it's entirely unclear to me how would the data get to the rotator itself, or why this is done for directly received packets but not digipeated packets. Current versions of the setup tool are missing a bunch of buttons related to this function, so this might be specific only to certain versions of the device.

### Radio adjustment

Section **8** contains dropdowns which control volume levels for RX and TX audio, as well as two buttons for transmitting test signals.

In my experience, the device had a really hard time decoding packets until I set the RX level at -9.0dB. You want to fiddle with your particular radio and these volume levels for best results.

`TX 1200` and `TX 2200` buttons will transmit a 1200Hz and a 2200Hz tone, respectively, to aid you in tuning. `TX OFF` button will stop the transmission.

### Other stuff

* The `No Rx Power OFF` dropdown in Section **9** will turn the device off after the specified time elapses since the last received and parsed packet.
* `UTC time zone` dropdown in Section **11** gets saved to EEPROM, but I have no idea whatsoever whether it's actually used anywhere.
* The function of `Rx Analytic` in Section **12** is a complete mystery, but it, too, is saved to the EEPROM.

### AT commands

While the original manual implies some AT commands over the serial interface would allow you to change configuration this way, hardly any of them work. Here are all the commands that I've been able to verify as working:

* `AT+VER=?` reports device version.
* `AT+DEMO=ON` results in factory reset.
* `AT+LC=CLEAN` clears mileage counter.
* `AT+SET=READ` dumps the EEPROM back into the stream, pre-pending a 5-byte header that reads `HELLO` for *some* reason.
* `AT+SET=WRITE<eeprom>` writes the EEPROM back. The EEPROM being saved and loaded is exactly 512 bytes.
* `AT+TX=ON` is equivalent to clicking the `TX` button and forces a beacon to be sent.
* `AT+TONE=1200`, `AT+TONE=2200` and `AT+TONE=OFF` are the way the `TX 1200`, `TX 2200` and `TX OFF` buttons control the device.

Commands, with the exception of `AT+SET=WRITE`, are expected to terminate with CRLF.

One particular command I've found only works when connected to the Bluetooth SPP interface: `AT+NAME<name>` sets the Bluetooth name of the device. This is handled by the Bluetooth module itself. Occasionally, the CPU tries to rewrite the Bluetooth name, with mangled results, since it forgets to CRLF-terminate the string. The Bluetooth module used in my particular device is [HC-02](http://www.hc01.com/products/8), and according to the manufacturer's datasheet, it should also support `AT+PIN<4-digit pin code>`, and a few other AT commands that appear less useful. I have not verified whether the device resets the PIN code in the Bluetooth module, however, like it does with the Bluetooth name.

Sometimes, you can see the device send `AT+KISS=OFF` and `AT+KISS=ON` into the serial port when restarting. When trying to send those, both actually respond with `OK`, but it's not clear whether anything actually happens as a result.

**P.S.** Oh, and if you're up to buying a cheap HT for use with this, I recommend a Quansheng UV-R50-2, rather than the ubiquitous Baofeng UV-5R: it's only a little more expensive, but has actual filters.

[APRS]: http://www.aprs.org/doc/APRS101.PDF
[MIC-E]: https://www.marcelpost.com/wiki/index.php/MIC-E

