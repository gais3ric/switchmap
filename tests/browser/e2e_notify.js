// Страница «Уведомления». node e2e_notify.js <baseUrl> <shotsDir>
const puppeteer = require('puppeteer-core');
const path = require('path');
const [base, shots] = process.argv.slice(2);
const results = [];
const check = (name, cond, info = '') => {
    results.push(!!cond);
    console.log((cond ? 'OK   ' : 'FAIL ') + name + (info !== '' ? `  -> ${JSON.stringify(info)}` : ''));
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    const jsErrors = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' });
    await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
    const open = async url => { await page.goto(base + url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(1000); };
    const toasts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));
    const lastToast = async () => (await toasts()).slice(-1)[0] || '';
    const api = (url, method = 'GET') => page.evaluate(async (u, m) => (await fetch(u, { method: m })).json(), url, method);
    const type = async (sel, text) => { await page.$eval(sel, el => { el.value = ''; }); await page.type(sel, String(text)); };
    const info = await (async () => { await open('/'); return api('/__test/info'); })();

    // ── Навигация
    const rail = await page.$$eval('.rail-nav .rail-item', els => els.map(e => e.dataset.label));
    check('в навигации есть «Уведомления»', rail.some(l => l.startsWith('Уведомления')), rail);
    await open('/notifications');
    check('пункт навигации активен', await page.$eval('.rail-item[href="/notifications"]', el => el.classList.contains('is-active')));
    check('оба канала выключены', (await page.$eval('#badge-telegram', el => el.textContent)) === 'выключено'
        && (await page.$eval('#badge-email', el => el.textContent)) === 'выключено');
    check('изначально нет несохранённых изменений', await page.$eval('#dirtyMark', el => el.hidden));
    await page.screenshot({ path: path.join(shots, 'n_empty.png'), fullPage: true });

    // ── Telegram: токен, поиск чатов
    await page.type('#tgToken', 'wrong-token');
    await page.click('#findChats'); await sleep(1200);
    check('неверный токен — сообщение об ошибке', (await lastToast()).includes('не принял токен'), await toasts());
    await type('#tgToken', info.token);
    check('ввод отмечает несохранённые изменения', !(await page.$eval('#dirtyMark', el => el.hidden)));
    await page.click('#findChats'); await sleep(1200);
    const found = await page.$eval('#foundChats', el => el.innerText);
    check('найдены бот и чаты', found.includes('@switchmap_test_bot') && found.includes('Иван (@ivan)') && found.includes('Сетевики'), found);
    await page.click('#foundChats [data-add-chat="0"]'); await sleep(200);
    check('чат добавлен в список', (await page.$eval('#chatList', el => el.innerText)).includes('Иван'));
    check('кнопка «Добавить» стала «добавлен»', (await page.$eval('#foundChats [data-add-chat="0"]', b => b.disabled && b.textContent)) === 'добавлен');
    await type('#chatManual', 'abc'); await page.click('#chatAdd'); await sleep(300);
    check('неверный номер чата — ошибка', (await lastToast()).includes('Номер чата'));
    await type('#chatManual', '-1001234'); await page.click('#chatAdd'); await sleep(200);
    check('чат вручную добавлен', (await page.$$eval('#chatList .chat-item', r => r.length)) === 2);
    await page.click('#chatList [data-remove-chat="1"]'); await sleep(200);
    check('чат удалён из списка', (await page.$$eval('#chatList .chat-item', r => r.length)) === 1);
    await page.click('[data-test="telegram"]'); await sleep(1500);
    check('тестовое сообщение в Telegram отправлено', (await lastToast()).includes('Отправлено'), await toasts());
    check('тестовое сообщение дошло до «Telegram»', (await api('/__test/info')).tg_sent.length === 1);

    // ── Почта: пресеты
    await page.click('[data-preset="gmail"]'); await sleep(200);
    check('пресет Gmail заполняет сервер и порт', (await page.$eval('#mHost', el => el.value)) === 'smtp.gmail.com'
        && (await page.$eval('#mPort', el => el.value)) === '465' && (await page.$eval('#presetHint', el => el.textContent)).includes('Пароли приложений'));
    await page.click('[data-preset="custom"]'); await sleep(200);
    check('«Свой сервер» очищает адрес пресета', (await page.$eval('#mHost', el => el.value)) === ''
        && await page.$eval('[data-preset="custom"]', el => el.classList.contains('is-active')));
    await type('#mHost', '127.0.0.1'); await type('#mPort', info.smtp_port);
    await page.select('#mSecurity', 'none');
    await type('#mUser', 'mon@test.ru'); await type('#mPass', 'wrongpass'); await type('#mRcpt', 'noc@test.ru');
    await page.click('[data-test="email"]'); await sleep(1500);
    check('неверный пароль — подсказка про пароль приложения', (await lastToast()).includes('пароль приложения'), await toasts());
    await type('#mPass', 'apppass');
    await page.click('[data-test="email"]'); await sleep(1500);
    check('тестовое письмо отправлено', (await lastToast()).includes('получателей: 1'), await toasts());

    // ── Сохранение
    await page.click('[data-field="telegram.enabled"]');
    check('включение отражается сразу', (await page.$eval('#badge-telegram', el => el.textContent)).includes('после сохранения'));
    await page.click('[data-field="email.enabled"]');
    await page.click('#useCurrentUrl');
    check('«Текущий» подставляет адрес', (await page.$eval('#baseUrl', el => el.value)) === base, await page.$eval('#baseUrl', el => el.value));
    await type('#flapLimit', 0);
    await page.click('#saveBtn'); await sleep(1200);
    check('сохранено', (await lastToast()).includes('сохранены'), await toasts());
    check('после сохранения: каналы работают', (await page.$eval('#badge-telegram', el => el.textContent)) === 'работает'
        && (await page.$eval('#badge-email', el => el.textContent)) === 'работает');
    check('несохранённых изменений нет', await page.$eval('#dirtyMark', el => el.hidden));
    check('поле токена очищено, подсказка «сохранён»', (await page.$eval('#tgToken', el => el.value)) === ''
        && (await page.$eval('#tgToken', el => el.placeholder)).includes('сохранён'));
    await page.reload({ waitUntil: 'domcontentloaded' }); await sleep(1000);
    check('после перезагрузки настройки на месте', await page.$eval('[data-field="telegram.enabled"]', el => el.checked)
        && (await page.$eval('#mHost', el => el.value)) === '127.0.0.1' && (await page.$eval('#chatList', el => el.innerText)).includes('Иван'));

    // ── Событие → рассылка → история
    await api('/__test/flip', 'POST');
    await api('/__test/down', 'POST');
    await api('/api/notify/retry', 'POST');
    const after = await api('/__test/info');
    check('порт и недоступность — в Telegram одним сообщением', after.tg_sent.length === 2
        && after.tg_sent[1].text.includes('порт 2') && after.tg_sent[1].text.includes('недоступен'), after.tg_sent.slice(-1));
    check('на почту — только недоступность (фильтр по умолчанию)', after.mail.some(s => s.includes('коммутатор недоступен'))
        && !after.mail.some(s => s.includes('порт 2')), after.mail);
    await page.click('#reloadLog'); await sleep(700);
    const log = await page.$eval('#logBody', el => el.innerText);
    check('история отправки показывает сообщения', log.includes('Telegram') && log.includes('Почта') && log.includes('доставлено'), log.slice(0, 300));

    // ── Ошибка доставки: статус и «Повторить сейчас»
    await api('/__test/tgfail/1', 'POST');
    await api('/__test/flip', 'POST');
    await api('/api/notify/retry', 'POST');
    await page.reload({ waitUntil: 'domcontentloaded' }); await sleep(1000);
    const st = await page.$eval('#status-telegram', el => el.innerText);
    check('ошибка Telegram видна на карточке', (await page.$eval('#badge-telegram', el => el.textContent)) === 'ошибка'
        && st.includes('временно недоступен') && st.includes('Следующая попытка'), st);
    await page.screenshot({ path: path.join(shots, 'n_error.png'), fullPage: true });
    await api('/__test/tgfail/0', 'POST');
    await page.click('#status-telegram [data-retry]'); await sleep(1500);
    check('«Повторить сейчас» — снова работает', (await page.$eval('#badge-telegram', el => el.textContent)) === 'работает');

    // ── Ошибка формы при сохранении
    await page.$eval('#chatList [data-remove-chat="0"]', b => b.click()); await sleep(200);
    await page.click('#saveBtn'); await sleep(800);
    check('включённый Telegram без чатов не сохраняется', (await lastToast()).includes('хотя бы один чат'), await toasts());
    let asked = false;
    page.on('dialog', d => { asked = d.type() === 'beforeunload'; d.accept(); });
    await page.reload({ waitUntil: 'domcontentloaded' }); await sleep(1000);
    check('уход с несохранёнными изменениями — браузер переспрашивает', asked);

    // Скриншоты: тёмная и светлая тема, узкий экран
    await page.screenshot({ path: path.join(shots, 'n_dark.png'), fullPage: true });
    await page.evaluate(() => toggleTheme()); await sleep(400);
    await page.screenshot({ path: path.join(shots, 'n_light.png'), fullPage: true });
    await page.evaluate(() => toggleTheme());
    await page.setViewport({ width: 420, height: 900 }); await sleep(400);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check('на узком экране нет горизонтальной прокрутки', overflow <= 1, overflow);
    await page.screenshot({ path: path.join(shots, 'n_mobile.png'), fullPage: true });

    // Колокольчик понимает новые события
    await page.setViewport({ width: 1440, height: 900 });
    await open('/');
    await page.click('.bell-btn'); await sleep(900);
    check('в колокольчике «Коммутатор недоступен»', (await page.$eval('#eventsList', el => el.innerText)).includes('Коммутатор недоступен'));

    const unexpected = jsErrors.filter(e => !/status of 400/.test(e));  // 400 — намеренная проверка формы
    check('нет неожиданных ошибок JS', unexpected.length === 0, unexpected);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });
