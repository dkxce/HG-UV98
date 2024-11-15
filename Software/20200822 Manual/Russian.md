# Инструкция к софту

[ORIGINAL HERE](https://github.com/Mihara/x1c3tool/blob/163a2c89a89dfa66d6e813860f687fe8251821e6/manual/manual.md) |
[РУССКИЙ](Russian.md) | [ENGLISH](Readme.md)

![APRS SOFT](APRS-SETUP-HOWTO.jpg)      
![X1C3 setup tool](setup-marked.png)

### Подключение к устройству

Включите радиостанцию с нажатой боковой клавишей PF1. Появится экран `APRS UpData...`. Теперь вы можете подключиться к радиостанции с помощью программного обеспечения APRS 51.

Найдите раздел помеченный на картинке как **0** и переключите пользовательский интерфейс на английский язык. 
К сожалению, вам придется делать это каждый раз, когда вы запускаете программу.

Раздел **1** управляет подключением к устройству. `Serial` обновляет список COM-портов, позволяя вам выбрать нужный из списка. 
`Open/Close` открывает и закрывает порт, `Read` и `Write` соответственно считывают конфигурацию с устройства и записывают ее обратно. 
`Reset` выдает AT-команду, которая сбрасывает конфигурацию до заводских значений по умолчанию, изменения вступают в силу немедленно и перезаписывают 
конфигурацию в EEPROM.

Обратите внимание, что даже если последовательный порт *подключится*, но устройство не подключено или находится не в требуемом режиме, 
чтение конфигурации из него так же как и запись не получится.

### Beaconing (Режим Маяка)

В разделе **2** задается позывной и SSID, с которым устройство идентифицирует себя в эфире (подробнее см. в описании APRS). При использовании в режиме прослушивания эфира никакие изменения не требуются. Данные устройства задаются, чтобы устройство самостоятельно работало в режиме Beaconing.

Раздел **3** в первую очередь касается правил отправки данных для режима Маяка:

* `GPS ON` включает и отключает встроенный GPS-приемник. Вы можете отключить этот флажок, переключиться в режим `SPORT`, и устройство не будет само подавать сигнал, потому что GPS выключен.
* `Site` — это раскрывающийся список с обманчивым названием, который выбирает, должно ли устройство двигаться или работает стационарно:
  * `FIXED` - стационарный режим. Координаты для отправки берутся из полей раздела **4**. Значения отправляются как есть, поэтому необходимо написать их так, как они описаны в спецификации протокола APRS с указанием N/E/S/W в отдельных полях.

    Установив `Site` на `FIXED`, отключив все флажки в разделе **3** и установив `Smart` в раскрывающемся списке `OFF`, вы получите чистый Bluetooth TNC режим, который не передает ничего.
    
  * `SPORT` - режим движения. В режиме `SPORT` для отправки координат маяка используются координаты с GPS-приемника. Режим отправки зависит от состояния других флажков и полей в Разделе **3**.

    В данно режиме никакие пакеты не будут отправляться, пока устройство не установит определит GPS координаты по спутникам.
    
  * Режим `WS` не задокументирован.
  
* Раскрывающийся список `Smart` либо отключает, либо включает [интеллектуальный режим](http://www.hamhud.net/hh2/smartbeacon.html) на основе шаблонов движения с использованием одного из предопределенных алгоритмов. Согласно руководству *для X1C5* это означает следующее:
  * `1` - Автомобиль. Интервал оправки координат - 20 сек.
  * `2` - Велосипед. Интервал оправки координат - 40 сек.
  * `3` - Пешеход. Интервал оправки координат - 60 сек.
  * `4` - Черепаха (скалолазание). Интервал оправки координат - 90 сек.
  * `5` - Околостационарный режим. Интервал оправки координат - 120 сек.

* `Manual` заставляет устройство отправлять пакет координат при *отпускании* кнопки PTT, то есть сразу после того, как вы закончите говорить. 
* `Time` устанавливает интервал между автоматической отправкой пакетов координат в радиоэфир. Если установить `Smart` режим и поставить `Time`, скажем, на 300 секунд — пакет координат будет отправляться один раз в заданное количество секунд.
* `Queue` довольно странная опция, потому что этот режим работает параллельно с любым другим. Если вы выберете этот режим, то устройство будет посылать пакеты координат каждую минуту в выбранную секунду из интервала (0..59) исходя из времени полученному по GPS. 

Настройки APRS пакетов для режима Маяка в Разделе **3**:

* `Path1` и «Path2» описывают путь дигипитера, применяемый к ретранслируемым пакетам, генерируемым устройством. Какой путь дигипитера APRS использовать [можно почитать здесь](http://www.wa8lmf.net/DigiPaths/index.htm), но разумным значением по умолчанию является `WIDE1`, `1`, ` WIDE2`, `1`, что будет переведено как `WIDE1-1,WIDE2-1` и означает «попросите локальные (домашние) цифровые репитеры повторить этот пакет один раз и глобальные (общественные) цифровые репитеры также повторить передаваемый пакет один раз». В зависимости от активности дигипитеров в вашем регионе вам может понадобиться что-то другое. Установка в раскрывающемся списке faux-SSID значения 0 отключает соответствующий компонент пути. К сожалению, это означает, что у вас вообще не может быть компонента пути без SSID, хотя вы можете, например, указать только `WIDE2-1` в качестве пути вашего дигипитера.
* `Type` — это идентификатор типа данных APRS, описанный в спецификации протокола APRS Заводское значение по умолчанию — `!`, т. е. маяк представляет собой позицию без отметки времени, что дополнительно указывает на то, что устройство не имеет возможность обмена сообщениями. Я не знаю, обращают ли что-нибудь серьезное внимание на тип данных APRS в наши дни, но если вы используете устройство в качестве трекера плюс TNC, вы можете поставить `=` в этом поле. 
* `MIC-E` включает сжатие MIC-E, которое упаковывает данные позиционирования в менее важные поля в структуре пакетных данных и значительно сокращает пакет. В раскрывающемся списке рядом можно выбрать статус MIC-E. Если вы не включите это, [APRSDroid](https://aprsdroid.org/), в частности, будет отображать курс, скорость и высоту как часть самого сообщения, *(без пробела между началом текстового сообщения и конец данных о скорости/курсе/высоте)*, но я думаю, что на самом деле APRSDroid неправильно их анализирует. С другой стороны, сжатие MIC-E, как сообщается, несет ответственность за [повреждение данных в определенных частях сети APRS с использованием архаичного программного обеспечения] (https://owenduffy.net/blog/?p=2326), поэтому в зависимости от того, где Вы, возможно, захотите отключить это.
* `Icon 1` и `Icon 2` позволяют вам выбрать, каким значком APRS будет отображено ваше устройство. Вы можете найти описание того, что они означают в спецификации протокола APRS. Более удобочитаемое описание можно найти в [этом списке символов APRS](https://www.aprsdirect.com/symbol/list) — просто помните, что в программе столбец `Code` этой таблицы находится на справа, а столбец `ID` таблицы находится слева, поэтому `/`, `[` означает значок человека.

 `Icon 1` является значком по умолчанию. `Icon 2` с дополнительным полем количества секунд будет установлен, если устройство неподвижно в течение этого времени или дольше (по умолчанию 180). По умолчанию второй значок —  `parking` «парковка». Если вам не нужна эта функция, просто установите одинаковые значки. Имейте в виду, что при использовании режима энергосбережения GPS (описанного ниже) точность позиционирования может пострадать, и ваше устройство будет считаться постоянно движущимся, поэтому второго значка вы никогда не увидите.

Другие *важные* настройки в Разделе **3**:

* `GPS Save(Manual/time)` включает режим энергосбережения GPS. В этом режиме GPS отключен до тех пор, пока не придет назначенное время или не наступит событие для отправки пакета координат. После чего GPS включается, определяется положение, и только потом пакет отправляется. Для работы `Smart beaconing`  требуется постоянное определение местоположения GPS, поэтому, если вы также включите `Smart beaconing`, этот флажок будет проигнорирован.
* `PTT delay` определяет задержку в микросекундах между началом передачи и началом трансляции голоса. Насколько я могу судить, это относится ко всем пакетам, отправляемым устройством, включая те, которые приходят через интерфейс KISS.

Другие *неважные* настройки в Разделе **3**:

* `CH`: Раскрывающийся список определяет, на каком канале `А` или `B` будут передаваться APRS пакеты. 

Раздел **5** содержит поля, описывающие дополнительную информацию, которая входит в часть сообщения с координатами, а также некоторые косвенно связанные функции.

* Неотмеченное текстовое поле начинает сообщение и может содержать что угодно, но не более 60 байт. Все остальное прикрепляется в конце, разделяя пробелами.
* `Mileage` добавит пройденное расстояние. `Memory Distance` позволит сохранять счетчик пробега между выключчениями устройства, если он установлен. Кнопка `Mileage clear` явно очищает этот счетчик. Насколько я могу судить, счетчик пробега является частью конфигурации EEPROM, поэтому сохранение и загрузка конфигурации все равно его испортит.
* `Voltage` добавит напряжение батареи.
* `Satellite` добавит количество видимых в данный момент спутников.
* `Temp` добавляет текущую температуру по датчику внутри устройства, которая выше температуры окружающей среды. По иронии судьбы снятие этого флажка ничего не дает, и температура все равно добавляется в версии прошивки 20201113.
* `Pressure` добавляет давление в соответствии с датчиком внутри устройства. Мало того, что это в гектопаскалях, вдобавок этот флажок сломан, как и температурный.
* `TX` заставит устройство немедленно отправить пакет. Это можно использовать для тестирования и настройки вашего радио.

Все, что вы прикрепляете к пакету координат, увеличивает время передачи, поэтому разумно отключить все, что вам на самом деле не нужно. К сожалению, баги мешают отключить температуру и давление.

### Digipeating (Режим дигипитера/репитера)

Чтобы устройство работало в режиме дигипитера, установите флажки в разделе **6**. Оба флажка соответствуют двум псевдонимам дигипитеров, которые прослушивает устройство — по умолчанию это `WIDE1` и `WIDE2`. При приеме пакета и обнаружении этих значений в пути, радиостанция передаст если того требует принятиый пакет обратно в радиоэфир.

Поле `Delay` вводит задержку перед обратной отправкой принятогно пакета.

### Настройки Bluetooth

Модуль Bluetooth устройства всегда доступен для обнаружения, если он не подключен. *Предполагается*, что имя должно быть установлено на `<позывной>-<ssid>` при включении питания, но иногда это не так, из-за того, что последовательный интерфейс путается из-за разрывов строк. Пин-код по умолчанию для сопряжения — «1234».

Настройки, управляющие поведением Bluetooth, находятся в разделе **10**:

* Безымянный флажок включает и отключает модуль Bluetooth, так что вы можете просто подключить свое устройство к USB и иметь USB-Serial TNC вообще без Bluetooth, если хотите.
* `Out1` выбирает поведение основного потока:
  * `OFF` просто отключает все, что, вероятно, не то, что вам нужно, даже если вы полностью отключите Bluetooth.
  * `KISS Hex` представляет собой правильный интерфейс KISS TNC.
  * `UI` представляет собой более понятный для человека интерфейс, в котором содержимое полученных и переданных пакетов печатается по одному в строке, а иногда появляются информационные сообщения. Это параметр, который вам нужен, когда вы настраиваете радио или иным образом возитесь с устройством. Что очень странно, так это то, что APRSDroid продолжает нормально работать, когда устройство находится в этом режиме, и мне не совсем понятно, почему — предположительно, устройство распознает KISS-трафик, когда получает его, но почему APRSDroid принимает однопакетный построчные сообщения, когда он настроен для KISS TNC?
  * `GPWPL` заменяет вывод передаваемых маяков предложениями NMEA «Waypoint Location». Полученные маяки, кажется, вообще не появляются. Предположительно, вы можете использовать это в сочетании с каким-либо навигатором для рендеринга карт.
  * `KISS Asc` передает и, предположительно, ожидает входящие пакеты, как если бы они были фреймами KISS, но переводит их в шестнадцатеричное представление ASCII. То есть вместо отправки 0xC0 он отправляет `C0` и т. д. 
* `Out2` - это поведение вторичного потока -- вместо того, чтобы представлять отдельный поток, как это подразумевается в руководстве. Как это работает не понятно!
  * `GPS` выгружает необработанный вывод GPS NMEA в том виде, в котором он получен от GPS, в поток. Радиостанция может быть использована как внешний GPS-приемник.
  * `Rotator` — самая малоизвестная функция устройства. Согласно оригинальному руководству, устройство способно управлять поворотным устройством антенны Yaesu через интерфейс GS-232B, чтобы наводить маяки по мере их слышимости. Он, безусловно, *пытается* -- в режиме `UI` вы можете иногда видеть вывод, относящийся к этой функции, описывающий расчеты относительных положений, приводящие к азимуту антенны. Однако мне совершенно неясно, как данные попадут на сам ротатор.

### Настройка радиостанции

Раздел **8** содержит раскрывающиеся списки, которые контролируют уровни громкости для аудио RX и TX, а также две кнопки для передачи сигналов.

По моему опыту, устройству было очень трудно декодировать пакеты, пока я не установил уровень RX на -9,0 дБ. Вы можете поиграть с вашим радио и этими уровнями громкости для достижения наилучших результатов.

### Другие настройки

* `No Rx Power OFF` в разделе **9** выключит устройство по истечении указанного времени с момента последнего полученного и проанализированного пакета.
* `UTC TimeZone` в разделе **11** сохраняется в EEPROM, но я понятия не имею, используется ли он вообще где-либо.

### AT команды

Хотя в оригинальном руководстве подразумевается, что некоторые AT-команды через последовательный интерфейс позволят вам изменить конфигурацию таким образом, вряд ли какие-либо из них работают. Вот все команды, которые я смог проверить как работающие:

* `AT+VER=?` сообщает версию устройства.
* `AT+DEMO=ON` приводит к сбросу настроек.
* `AT+LC=CLEAN` очищает счетчик пробега.
* `AT+SET=READ` выгружает EEPROM обратно в поток, предварительно ожидая 5-байтового заголовка, который читается как `HELLO` по *некоторой* причине.
* `AT+SET=WRITE<eeprom>` записывает EEPROM обратно. Сохраняемый и загружаемый EEPROM имеет размер ровно 512 байт.
* «AT+TX=ON» эквивалентно нажатию кнопки «TX» и вызывает отправку маяка.
* `AT+TONE=1200`, `AT+TONE=2200` и `AT+TONE=OFF` определяют, как кнопки `TX 1200`, `TX 2200` и `TX OFF` управляют устройством.

Ожидается, что команды, за исключением `AT+SET=WRITE`, завершатся с помощью CRLF.

дна конкретная команда, которую я нашел, работает только при подключении к интерфейсу Bluetooth SPP: `AT+NAME<name>` устанавливает имя Bluetooth устройства. Этим занимается сам модуль Bluetooth. Иногда ЦП пытается переписать имя Bluetooth с искаженными результатами, поскольку он забывает завершать строку CRLF. В моем конкретном устройстве используется модуль Bluetooth [HC-02] (http://www.hc01.com/products/8), и, согласно техническому описанию производителя, он также должен поддерживать `AT+PIN<4-значный PIN-код. code>` и несколько других AT-команд, которые кажутся менее полезными. Однако я не проверял, сбрасывает ли устройство PIN-код в модуле Bluetooth, как это происходит с именем Bluetooth.

Иногда вы можете увидеть, как устройство отправляет `AT+KISS=OFF` и `AT+KISS=ON` в последовательный порт при перезапуске. При попытке отправить их оба фактически отвечают «ОК», но неясно, происходит ли что-нибудь в результате.        

[APRS](http://www.aprs.org/doc/APRS101.PDF)         
[MIC-E](https://www.marcelpost.com/wiki/index.php/MIC-E)             

