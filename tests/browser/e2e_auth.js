// Вход, пользователи, роли в интерфейсе, CSP. node e2e_auth.js <baseUrl> <shotsDir>
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
    const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true, args: ['--lang=ru-RU', '--accept-lang=ru-RU'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    const jsErrors = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    const open = async url => { await page.goto(base + url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(900); };
    const toasts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));
    const navVia = async action => {
        await page.evaluate(() => { window.__oldPage = true; });
        await action();
        await page.waitForFunction(() => !window.__oldPage && document.readyState !== 'loading', { timeout: 30000, polling: 200 });
        await sleep(600);
    };
    const login = async (user, pw) => {
        await open('/login');
        await page.type('#username', user); await page.type('#password', pw);
        await navVia(() => page.click('button[type=submit]'));
    };
    const visible = sel => page.$eval(sel, el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)).catch(() => false);

    // ── Без входа — на страницу входа с возвратом
    await open('/switch/1?port=3');
    check('без входа — страница входа', page.url().includes('/login?next=/switch/1'), page.url());
    await page.screenshot({ path: path.join(shots, 'a_login.png') });
    await page.type('#username', 'admin'); await page.type('#password', 'wrong-password');
    await navVia(() => page.click('button[type=submit]'));
    check('неверный пароль — сообщение', (await page.$eval('.auth-error', el => el.textContent)).includes('Неверное имя'));
    check('имя пользователя сохраняется в форме', await page.$eval('#username', el => el.value) === 'admin');
    await page.type('#password', 'adminpass123');
    await navVia(() => page.click('button[type=submit]'));
    check('после входа — возврат на исходную страницу', page.url().endsWith('/switch/1?port=3'), page.url());

    // ── Меню пользователя и смена пароля
    await page.click('.rail-avatar'); await sleep(300);
    const menu = await page.$eval('.user-menu .dropdown', el => el.innerText);
    check('меню: имя, роль, пароль, пользователи, выход', menu.includes('admin') && menu.includes('Администратор')
        && menu.includes('Сменить пароль') && menu.includes('Пользователи') && menu.includes('Выйти'), menu);
    await page.screenshot({ path: path.join(shots, 'a_user_menu.png') });
    await page.click('.user-menu .dropdown button[data-click="openPasswordModal"]'); await sleep(300);
    await page.type('#pwCurrent', 'adminpass123'); await page.type('#pwNew', 'adminpass456'); await page.type('#pwNew2', 'adminpass000');
    await page.click('#passwordModal .btn-primary'); await sleep(400);
    check('несовпадающие новые пароли — ошибка', (await toasts()).includes('Новые пароли не совпадают'));
    await page.$eval('#pwNew2', el => { el.value = ''; }); await page.type('#pwNew2', 'adminpass456');
    await page.click('#passwordModal .btn-primary'); await sleep(800);
    check('пароль изменён', (await toasts()).includes('Пароль изменён'));
    await open('/');
    check('после смены пароля сессия продолжается', !page.url().includes('/login'));

    // ── Пользователи
    await open('/users');
    check('страница пользователей', (await page.$$eval('#usersBody tr', r => r.length)) === 1);
    await page.click('.page-actions .btn-primary'); await sleep(300);
    await page.type('#uName', 'ivan'); await page.type('#uPass', 'Ivanpass123');
    await page.click('#uSubmit'); await sleep(900);
    check('создан наблюдатель «ivan»', (await toasts()).some(t => t.includes('«ivan» создан'))
        && (await page.$eval('#usersBody', el => el.innerText)).includes('ivan'));
    await page.screenshot({ path: path.join(shots, 'a_users.png') });
    const meRow = await page.$eval('#usersBody tr', tr => ({ text: tr.innerText, roleDisabled: tr.querySelector('[data-role]').disabled }));
    check('свою роль изменить нельзя (select заблокирован)', meRow.roleDisabled && meRow.text.includes('это вы'));
    const ivanRow = '#usersBody tr:nth-child(2)';
    await page.click(`${ivanRow} [data-toggle]`); await sleep(400);
    await page.click('#confirmOk'); await sleep(900);
    check('блокировка', (await page.$eval(ivanRow, el => el.innerText)).includes('заблокирован'));
    await page.click(`${ivanRow} [data-toggle]`); await sleep(900);
    check('разблокировка', (await page.$eval(ivanRow, el => el.innerText)).includes('активен'));
    await page.click(`${ivanRow} [data-password]`); await sleep(300);
    check('окно «новый пароль» без имени и роли', await page.$eval('#fName', el => el.hidden) && (await page.$eval('#userModalTitle', el => el.textContent)).includes('ivan'));
    await page.type('#uPass', 'Ivanpass999'); await page.click('#uSubmit'); await sleep(800);
    check('пароль задан администратором', (await toasts()).includes('Пароль задан'));

    // ── Выход и вход наблюдателем
    await page.click('.rail-avatar'); await sleep(300);
    await navVia(() => page.click('#logoutBtn'));
    check('выход ведёт на страницу входа', page.url().includes('/login'));
    await open('/');
    check('после выхода страницы закрыты', page.url().includes('/login'));
    await login('ivan', 'Ivanpass999');
    check('вход наблюдателем', !page.url().includes('/login') && await page.$eval('body', b => b.classList.contains('role-viewer')));
    check('наблюдатель: нет «Добавить коммутатор», удаления, настроек',
        !(await visible('.page-actions .btn-primary.admin-only')) && !(await visible('.btn-delete'))
        && !(await visible('.rail-item[data-label="Настройки"]')));
    check('наблюдатель: в навигации нет «Пользователи»', !(await page.$eval('.user-menu .dropdown', el => el.innerText)).includes('Пользователи'));
    await open('/switch/1');
    check('наблюдатель: нет «Редактировать», есть «Опросить» и «Статистика»', !(await visible('#editBtn')) && await visible('#snmpBtn')
        && await visible('button[data-click="openStatsModal"]'));
    const forced = await page.evaluate(async () => { const r = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"poll_enabled":true}' }); return [r.status, (await r.json()).error]; });
    check('наблюдатель: прямой запрос на изменение → 403 с объяснением', forced[0] === 403 && forced[1].includes('администратор'), forced);
    await page.click('#snmpBtn');
    await page.waitForFunction(() => !document.getElementById('snmpBtn').disabled, { timeout: 60000 });
    check('наблюдатель может опросить по SNMP', (await page.$eval('#snmpContent', el => el.innerText)).includes('Найдено интерфейсов'));
    check('наблюдатель: кнопки «Привязать» скрыты', !(await visible('.assign-btn')));
    await open('/audit');
    check('наблюдатель: в журнале нет кнопок отката', (await page.$$eval('[data-revert]', bs => bs.filter(b => b.offsetWidth).length)) === 0);
    await open('/users');
    check('наблюдатель: /users → «Нет доступа»', (await page.$eval('body', b => b.innerText)).includes('Нет доступа'));
    await open('/maintenance');
    check('наблюдатель: на «Данные» нет действий с копиями', !(await visible('#createBackup')) && !(await visible('#saveRetention')));
    await page.screenshot({ path: path.join(shots, 'a_viewer_maintenance.png') });

    // ── Все страницы работают с CSP (Chart.js, d3, pdfmake с разрешённых CDN)
    await login('admin', 'adminpass456').catch(() => {});
    if (page.url().includes('/login')) { await login('admin', 'adminpass456'); }
    await open('/topology');
    await sleep(1500);
    check('топология (d3 с CDN) работает при CSP', (await page.$$eval('#nodes g', g => g.length)) > 0);

    const cspErrors = jsErrors.filter(e => /Content Security Policy|Refused to/.test(e));
    check('нет нарушений CSP', cspErrors.length === 0, cspErrors);
    const unexpected = jsErrors.filter(e => !/status of (401|403)/.test(e));  // 401/403 — намеренные проверки теста
    check('нет неожиданных ошибок JS', unexpected.length === 0, unexpected);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });
