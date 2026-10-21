// Скриншоты для README. node take.js <адрес демо-сервера> <папка> <ru|en>
// puppeteer-core — из tests/browser/node_modules (NODE_PATH), Chrome — CHROME_PATH или стандартный путь.
const puppeteer = require('puppeteer-core');
const path = require('path');
const [base, out, lang] = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({
        executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        headless: true, args: [`--lang=${lang}`, `--accept-lang=${lang}`, '--hide-scrollbars'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', e => errors.push(String(e.message || e)));
    const shot = async (name, opts = {}) => { await sleep(400); await page.screenshot({ path: path.join(out, name + '.png'), ...opts }); };
    const open = async url => { await page.goto(base + url, { waitUntil: 'networkidle2' }); await sleep(700); };

    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' });
    await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await page.evaluate(l => fetch('/api/language', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: l }) }), lang);

    await open('/');
    await shot('01-dashboard');

    await open('/switch/1');
    await shot('02-switch');
    await page.evaluate(() => { const r = document.querySelector('#portsTableBody'); if (r) r.scrollIntoView({ block: 'start' }); });
    await page.evaluate(() => window.scrollBy(0, -80));
    await shot('03-ports-table');

    await open('/switch/1');
    await page.click('button[data-click="openStatsModal"]'); await sleep(2000);
    await page.evaluate(() => { const s = document.getElementById('portSelectStats'); const o = [...s.options].find(x => /^49\b|Te1\/1\/1/.test(x.textContent)) || s.options[1]; s.value = o.value; s.dispatchEvent(new Event('change', { bubbles: true })); });
    await sleep(2000);
    await page.evaluate(() => { const m = document.querySelector('#statsModal .modal-content') || document.querySelector('.modal.active .modal-content'); if (m) m.scrollTop = 0; });
    await page.setViewport({ width: 1440, height: 1300, deviceScaleFactor: 1 }); await sleep(800);
    await shot('04-statistics');
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });

    await open('/topology');
    await sleep(3500);
    await page.evaluate(() => { const b = [...document.querySelectorAll('button')].find(x => /fit|Вписать|Уместить|Ajust/i.test(x.dataset.click || '') || x.dataset.click === 'fitTopology'); if (b) b.click(); });
    await sleep(1200);
    await shot('05-topology');

    await open('/');
    await page.click('#netSearchInput');
    await page.type('#netSearchInput', '3c:52:82');
    await sleep(1500);
    await shot('06-search');

    await open('/discover');
    await shot('07-discovery');

    await open('/notifications');
    await shot('08-notifications');

    await open('/maintenance');
    await shot('09-backups');

    await open('/help/getting-started');
    await shot('10-help');

    await open('/switch/1');
    await page.evaluate(() => toggleTheme()); await sleep(600);
    await shot('11-light-theme');
    await page.evaluate(() => toggleTheme());

    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
    await open('/');
    await shot('12-mobile');

    console.log(errors.length ? 'JS errors: ' + JSON.stringify(errors) : 'ok');
    await browser.close();
})();
