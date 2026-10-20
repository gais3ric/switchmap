# Тесты SwitchMap

Каждый набор запускается во временной папке со своей тестовой базой (её создаёт `helpers/seed.py`).
Рабочая база `switches.db` и ключи `switchmap.secret` не используются и не изменяются.

```
python tests/run_all.py              # быстрые тесты, ~1 минута
python tests/run_all.py --live       # + опрос по настоящему SNMP, поиск в сети и NetBox
python tests/run_all.py --browser    # + проверки в браузере
python tests/run_all.py --all        # всё, ~8 минут
python tests/run_all.py -k notify    # только наборы с «notify» в названии
python tests/run_all.py -k e2e_ui --browser --live -v   # один браузерный набор с подробным выводом
```

Запускайте из папки проекта Python-ом из `venv` (`.\venv\Scripts\python.exe tests\run_all.py`).
Код выхода 0 — всё прошло.

## Что проверяется

| Набор | Что внутри |
|---|---|
| `stats-existing`, `stats-fresh` | окно статистики на существующей и новой базе |
| `rates` | скорость трафика, переполнение счётчиков |
| `data` | хранение истории, периоды графиков, резервные копии, журнал, откат, экспорт |
| `security` | вход, роли, CSRF, сессии, шифрование паролей SNMPv3, заголовки |
| `notify` | Telegram и почта (поддельные серверы), фильтры, повторы, «мигание» портов |
| `live`* | полный опрос коммутаторов по SNMP v2c/v3 |
| `import`* | SNMPv3 в форме добавления, поиск в сети, импорт из NetBox (поддельный NetBox) |
| `e2e…`** | интерфейс в Chrome: страницы, формы, графики, вход, уведомления, импорт |
| `e2e_csp`** | защита от внедрения кода: ни одного нарушения CSP, внедрённые `onclick`/`<script>` не выполняются |

\* нужен snmpsim, \** нужны Node.js и Google Chrome.

## Подготовка (один раз)

**SNMP-симулятор** для `--live` — ставится в отдельное окружение, чтобы не смешивать с приложением:

```
python -m venv tests\.snmpsim
tests\.snmpsim\Scripts\pip install snmpsim pysmi cryptography
```

Он слушает `127.0.0.1:161` с данными из `snmpsim/data` (community `public` — «Cisco», `edge2` — «D-Link»;
SNMPv3: `simuser` / `authpass123` SHA / `privpass123` AES, контекст `public`). Другой путь к нему — переменная `SNMPSIM_BIN`.

**Браузерные тесты:**

```
cd tests\browser
npm install
```

Chrome ищется в `C:\Program Files\Google\Chrome\Application\chrome.exe`; другой путь — переменная `CHROME_PATH`.

Проверка настоящего `api.telegram.org` (нужен интернет) включается переменной `SWITCHMAP_TEST_INTERNET=1`.

## Устройство

- `test_*.py` — серверные тесты (Flask test client), аргумент — рабочая папка;
- `helpers/` — тестовая база, поддельные SNMP / Telegram / SMTP / NetBox, тестовые серверы для браузерных тестов;
- `browser/` — сценарии puppeteer; при падении скриншоты лежат в рабочей папке набора (её путь печатается).
