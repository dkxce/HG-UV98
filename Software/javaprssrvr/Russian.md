### javAPRSSrvr IGate

[original here](http://www.ae5pl.net/javAPRSSrvrIGate.aspx) | [русский](Russian.md) | [english](Readme.md)    

**javAPRSSrvr IGate** это <a href="https://play.google.com/store/apps/details?id=net.ae5pl.javaprssrvrigate">приложение под Android</a> предназначенное для запуска APRS IGate сервера на устройстве Android под управлением операционной системы Oreo (8.0) или более поздней версии.
    Приложения на смартфоне (например, APRSDroid) могут подключаться к javAPRSSrvr IGate как к локальному APRS-IS серверу, достаточно только изменить строку подключения.
        javAPRSSrvr описан <a href="http://www.aprs-is.net/javAPRSSrvr">здесь</a>.  Дополнительную информацию о APRS-IS можно найти <a href="http://www.aprs-is.net">тут</a>

<img src="javAPRSSrvrIGateBlock.png"/>
    <p>
        На картинке снизу расположен экран настроек, под ней расписана каждая настройка.
    </p>
    <img src="javAPRSSrvrIGate_Settings.jpg" alt="Settings" style="height: 492px; width: 268px" />
    <ul >
        <li style="margin-top:10px">*<strong>Callsign:</strong> Ваш радиолюбительский позывной.</li>
        <li style="margin-top:10px">*<strong>Passcode:</strong> Ваш пароль для позывного APRS-IS. Для javAPRSSrvr IGate требуется, чтобы вы были лицензированным радиолюбителем и имели соответствующий пароль для позывного. Пароль можно получить <a href="https://apps.magicbug.co.uk/passcode/">здесь</a>, <a href="http://n5dux.com/ham/aprs-passcode/">здесь</a>, <a href="https://aprs.do3sww.de/">здесь</a>, <a href="https://www.pb1sam.be/passcode/">здесь</a>, <a href="https://www.iz3mez.it/aprs-passcode/">здесь</a>, <a href="https://callpass.kf5jwc.us/">здесь</a>, <a href="https://www.george-smart.co.uk/aprs/aprs_callpass/">здесь</a>, а еще <a href="http://doppelklix.de/wordpress/wp-includes/APRS-Passcode/index.php">тут</a> или <a href="http://rk1at.ru/aprs/">тут</a>. Либо можете воспользоваться <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/dkxce/APRSCodeGen/main/APRSCodeGen.html">генаратором</a> из <a href="https://github.com/dkxce/APRSCodeGen">моей утилиты</a>.</li>
        <li style="margin-top:10px">*<strong>Server SSID:</strong> Цифробуквенное обозначение SSID из одного или двух симовлов для именования сервера. По умолчанию: IG, используется для идентификации сервера (приложения) в интернет APRS-сети. <strong>Значение должно быть уникально.</strong></li>
        <li style="margin-top:10px">*<strong>IGate SSID:</strong> Число от 1 до 15, либо 0 если отсутствует. По умолчанию: 10. Используется для идентификации IGate (приложения) для APRS радиостанций в радиоэфире. <strong>Значение должно быть уникально.</strong></li>
        <li style="margin-top:10px"><strong>Local Client SSID (0=noSSID):</strong> SSID локального APRS клиента для подключения к javAPRSSrvr IGate серверу. Если локальный клиент не имеет SSID, введите 0. По умолчанию пусто. <strong>Значение должно быть уникально.</strong></li>
        <li style="margin-top:10px">*<strong>IGate Path:</strong> Путь дигипитеров при передачи сообщений в радиоэфир. По умолчанию: WIDE1-1,WIDE2-1.</li>
        <li style="margin-top:10px"><strong>APRS-IS Server:</strong> Адрес и порт (строка подключения) для внешнего APRS-IS сервера. Допустимые форматы строки:
            <ul>
                <li><strong>WebSocket</strong> (не все серверы APRS-IS поддерживают этот режим): ws://server[:port]/ или wss://server[:port]/ (wss=secure)</li>
                <li><strong>TCP</strong>: server:port</li>
            </ul>
            По умолчанию: ws://srvr.aprs-is.net:8080/</li>
        <li style="margin-top:10px">
            <strong>Filter Command:</strong> Фильтр для внешнего APRS-IS сервера для фильтрации входящих пакетов.<br />
            Рекомендуется использовать `friend range` фильтр <b>f/IGATE-SSID/50</b>, где <b>IGATE-SSID</b> ваш позывной и IGate SSID для отображения всех станций в 50 км радиусе от вашего местоположения. <strong>Не</strong> используйте Server SSID т.к. сервер не отправляет пакеты координат от своего имени; только IGate передает координаты. <br /> Я предпочитаю для себя такой набор фильтров: <i>r/55.00/37.00/50 p/DKXCE b/DKXCE* g/DKXCE* f/DKXCE/50 f/DKXCE-8/50 me/50</i>, где <i>DKXCE-8</i> - ваш позывной и IGate SSID.<br />
            Подробнее о фильтрах можно ознакомиться <a href="http://www.aprs-is.net/javAPRSFilter.aspx">в мануале</a>.
        </li>
        <li style="margin-top:10px">*<strong>Bluetooth TNC:</strong> Наименование Bluetooth KISS TNC подключения (для HG-UV98). Устройство TNC должно быть подключено и находиться в режиме KISS перед запуском javAPRSSrvr IGate.</li>
    </ul>
    <p>
        * обязательно к заполнению.
    </p>
    <h2>Назначения кнопок</h2>
    <p>
        Всего в интерфейсе программы 2 кнопки.</p>
    <ul>
        <li><strong>Start</strong><br />Запускает IGate сервер (начинает обмен пакетами).</li>
        <li><strong>Shutdown</strong><br />Остан6авливает IGate сервер (заканчивает обмен пакетами).</li>
    </ul>
    <h2>Подключение Android-приложений к javAPRSSrvr IGate</h2>
    <p>
        javAPRSSrvr IGate предоставляет локальные TCP порты для сторонних подключений. Подключиться можно только локально (т.е. с другого устройства подключиться не получится!).
        javAPRSSrvr IGate предоставляет два порта. Порт 10152 - без фильтра пакетов и 14580 - с фильтром пакетов.
    Вы можете подключить любое Android приложение (например: <a href="https://aprsdroid.org/">APRSDroid</a> или <a href="https://www.oruxmaps.com/cs/en/">OruxMaps</a> на любой из этих портов. При подключении к порту 14580, изучите мануал по <a href="http://www.aprs-is.net/javAPRSFilter.aspx">фильтрам</a> чтобы выбрать требуемые и настроить их в приложении.</br></br>
    Строка подключений для Android приложений: <b>localhost:14580</b> или <b>localhost:10152</b>
    </p>
    <h3>javAPRSSrvr IGate is GA released at the <a href="https://play.google.com/store/apps/details?id=net.ae5pl.javaprssrvrigate">Google Play Store</a>.</h3>
