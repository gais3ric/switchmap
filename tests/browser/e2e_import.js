// SNMPv3 в окне добавления, поиск в сети, импорт из NetBox. node e2e_import.js <baseUrl> <shotsDir>
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
    const open = async url => { await page.goto(base + url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(900); };
    const toasts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));
    const lastToast = async () => (await toasts()).slice(-1)[0] || '';
    const visible = sel => page.$eval(sel, el => !!(el.offsetWidth || el.offsetHeight)).catch(() => false);
    const type = async (sel, text) => { await page.$eval(sel, el => { el.value = ''; }); await page.type(sel, String(text)); };

    // ── Окно добавления: SNMPv3
    await open('/');
    await page.click('.page-actions .btn-primary'); await sleep(400);
    const M = '#addSwitchModal';
    check('по умолчанию v2c: community видно, v3 скрыто', await visible(`${M} [name=snmp_community]`) && !(await visible(`${M} [name=snmp_v3_user]`)));
    await page.select(`${M} [name=snmp_version]`, '3'); await sleep(200);
    check('v3: поля пользователя и паролей появились, community скрыто', await visible(`${M} [name=snmp_v3_user]`)
        && await visible(`${M} [name=snmp_v3_auth_key]`) && !(await visible(`${M} [name=snmp_community]`)));
    await page.select(`${M} [name=snmp_v3_auth_proto]`, 'none'); await sleep(150);
    check('без аутентификации шифрование блокируется', await page.$eval(`${M} [name=snmp_v3_priv_proto]`, el => el.disabled && el.value === 'none')
        && await page.$eval(`${M} [name=snmp_v3_auth_key]`, el => el.disabled));
    await page.select(`${M} [name=snmp_v3_auth_proto]`, 'SHA');
    await page.select(`${M} [name=snmp_v3_priv_proto]`, 'AES128'); await sleep(150);
    await type(`${M} [name=ip_address]`, '127.0.0.1');
    await type(`${M} [name=snmp_v3_user]`, 'simuser');
    await type(`${M} [name=snmp_v3_auth_key]`, 'short');
    await page.click(`${M} .probe-row .btn`); await sleep(400);
    check('короткий пароль — ошибка без запроса', (await page.$eval(`${M} [data-probe-result]`, el => el.innerText)).includes('не короче 8'));
    await type(`${M} [name=snmp_v3_auth_key]`, 'authpass123');
    await type(`${M} [name=snmp_v3_priv_key]`, 'privpass123');
    await type(`${M} [name=snmp_v3_context]`, 'public');
    await page.click(`${M} .probe-row .btn`);
    await page.waitForFunction(m => !document.querySelector(`${m} .probe-row .btn`).classList.contains('is-loading'), { timeout: 30000 }, M);
    const probe = await page.$eval(`${M} [data-probe-result]`, el => ({ text: el.innerText, cls: el.className }));
    check('«Проверить и заполнить»: коммутатор отвечает по v3', probe.cls.includes('is-ok') && probe.text.includes('sim-cisco')
        && probe.text.includes('SNMPv3 authPriv') && probe.text.includes('Cisco'), probe);
    check('название и порты подставлены', (await page.$eval('#name', el => el.value)) === 'sim-cisco'
        && (await page.$eval('#ports', el => el.value)) === '10');
    await page.screenshot({ path: path.join(shots, 'i_add_v3.png') });
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click(`${M} .btn-submit`)]); await sleep(900);
    const rowText = await page.$eval('#switchTable', el => el.innerText).catch(() => '');
    check('коммутатор создан, на главной видны v3 и модель', rowText.includes('sim-cisco') && rowText.includes('v3') && rowText.includes('C2960X'), rowText.slice(0, 300));

    // ── Поиск в сети
    await open('/discover');
    check('страница поиска: пункт меню активен', await page.$eval('.rail-item[href="/discover"]', el => el.classList.contains('is-active')));
    await type('#ranges', '127.0.0.1-3');
    await type('#scan-snmp-community', 'wrong, public');
    await page.click('#scanStart');
    await sleep(500);
    check('идёт поиск: прогресс и кнопка «Остановить»', await visible('#scanProgressCard') && await visible('#scanStop'));
    await page.waitForFunction(() => document.getElementById('scanProgress').innerText.includes('завершён'), { timeout: 60000 });
    await sleep(500);
    const res = await page.$eval('#scanBody', el => el.innerText);
    check('найден sim-cisco, подписан как «уже есть»', res.includes('127.0.0.1') && res.includes('уже есть'), res);
    check('уже добавленный выбрать нельзя', await page.$eval('#scanBody tr [data-pick]', el => el.disabled));
    check('кнопка «Добавить» неактивна', await page.$eval('#scanAdd', el => el.disabled));
    // Удаляем добавленный коммутатор и повторяем — теперь новый
    await page.evaluate(async () => {
        const html = await (await fetch('/')).text();
        const id = html.match(/sw-row-(\d+)/)[1];
        const f = new FormData(); f.append('csrf_token', document.querySelector('meta[name=csrf-token]').content);
        await fetch(`/delete/${id}`, { method: 'POST', body: f });
    });
    await page.click('#scanStart');
    await page.waitForFunction(() => document.getElementById('scanProgress').innerText.includes('Идёт'), { timeout: 10000 });
    await page.waitForFunction(() => document.getElementById('scanProgress').innerText.includes('завершён'), { timeout: 60000 });
    await sleep(500);
    check('теперь — «новый» и выбран', (await page.$eval('#scanBody', el => el.innerText)).includes('новый')
        && await page.$eval('#scanBody tr [data-pick]', el => el.checked));
    await type('#scanBody tr [data-name]', 'Ядро из поиска');
    check('кнопка «Добавить выбранные (1)»', (await page.$eval('#scanAdd', el => el.textContent)).includes('(1)'));
    console.log('INFO под кнопкой:', await page.$eval('#scanAdd', b => { b.scrollIntoView(); const r = b.getBoundingClientRect(); const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return el && (el.id || el.className); }));
    await page.$eval('#scanAdd', b => b.click());
    await page.waitForFunction(() => document.getElementById('scanBody').innerText.includes('добавлен'), { timeout: 15000 }).catch(() => {});
    check('добавлено — уведомление и отметка в строке', (await lastToast()).includes('Добавлено 1')
        && (await page.$eval('#scanBody', el => el.innerText)).includes('добавлен'), await toasts());
    await page.screenshot({ path: path.join(shots, 'i_scan.png'), fullPage: true });
    await page.reload({ waitUntil: 'domcontentloaded' }); await sleep(1200);
    check('после перезагрузки результаты поиска на месте', (await page.$eval('#scanBody', el => el.innerText)).includes('127.0.0.1')
        && (await page.$eval('#ranges', el => el.value)) === '127.0.0.1-3');
    await page.click('[data-filter="all"]'); await sleep(200);
    check('фильтр «Все устройства» переключается', await page.$eval('[data-filter="all"]', el => el.classList.contains('is-active')));

    // ── NetBox
    const nbUrl = await page.evaluate(async () => (await (await fetch('/__test/nb')).json()).url);
    await page.click('[data-tab="netbox"]'); await sleep(500);
    check('вкладка NetBox, адрес в строке (#netbox)', await visible('#nbForm') && page.url().endsWith('#netbox'));
    check('изначально «не настроено»', (await page.$eval('#nbStatus', el => el.innerText)).includes('не настроено'));
    await type('#nbUrl', nbUrl); await type('#nbToken', 'wrong');
    await page.click('#nbTest'); await sleep(1200);
    check('неверный токен — ошибка', (await lastToast()).includes('токен'));
    await type('#nbToken', '0123456789abcdef');
    await page.click('#nbTest'); await sleep(1500);
    check('подключено: версия и число устройств', (await page.$eval('#nbStatus', el => el.innerText)).includes('NetBox 4.2.3'));
    check('справочники загружены', (await page.$$eval('#nbRole option', o => o.length)) === 3 && (await page.$$eval('#nbSite option', o => o.length)) === 4);
    await page.select('#nbRole', 'access');
    await page.click('#nbLoad'); await sleep(1500);
    const nbRows = await page.$$eval('#nbBody tr', rs => rs.map(r => r.innerText));
    check('4 устройства роли access', nbRows.length === 4, nbRows.length);
    check('«Этаж 2» совпал по IP с предложением переименовать', nbRows.some(t => t.includes('floor2-sw') && t.includes('совпал по IP') && t.includes('Этаж 2 → floor2-sw')));
    check('по умолчанию выбраны новые с IP (1)', (await page.$eval('#nbImport', el => el.textContent)).includes('(1)'));
    await page.click('#nbAll'); await sleep(200);
    check('«выбрать все» — 4', (await page.$eval('#nbImport', el => el.textContent)).includes('(4)'));
    await page.screenshot({ path: path.join(shots, 'i_netbox.png') });
    await page.click('#nbImport'); await sleep(2500);
    check('импорт: уведомление', (await lastToast()).includes('Импорт из NetBox'), await toasts());
    const after = await page.$$eval('#nbBody tr', rs => rs.map(r => r.innerText));
    check('после импорта все связаны', after.length === 4 && after.every(t => t.includes('связан')), after);
    check('блок «Связанные коммутаторы»: 4', (await page.$eval('#nbLinked', el => el.innerText)).includes('4'));
    await page.click('#nbSync'); await sleep(1500);
    check('синхронизация', (await lastToast()).includes('Проверено 4'));
    await page.click('#nbAuto'); await sleep(800);
    check('автосинхронизация включена', (await lastToast()).includes('включена'));

    // Ссылка на NetBox на странице коммутатора
    await open('/');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
        page.evaluate(() => [...document.querySelectorAll('.sw-name a')].find(a => a.textContent === 'core-sw1').click())]);
    await sleep(800);
    check('страница коммутатора: модель и ссылка NetBox', (await page.$eval('#netboxLink', a => a.href)).endsWith('/dcim/devices/1/')
        && (await page.$eval('#switchModel', el => el.textContent)).includes('C9300-48P'));

    // Узкий экран
    await open('/discover');
    await page.setViewport({ width: 420, height: 900 }); await sleep(400);
    check('поиск на узком экране без горизонтальной прокрутки', (await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 1);
    await page.screenshot({ path: path.join(shots, 'i_mobile.png'), fullPage: true });
    await page.setViewport({ width: 1440, height: 900 });
    await page.evaluate(() => toggleTheme()); await sleep(300);
    await page.screenshot({ path: path.join(shots, 'i_scan_light.png') });
    await page.evaluate(() => toggleTheme());

    const unexpected = jsErrors.filter(e => !/status of (400|409)/.test(e));
    check('нет ошибок JS', unexpected.length === 0, unexpected);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });
