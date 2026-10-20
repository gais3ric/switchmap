// Снимки экрана справки, подсказок и меню языка (ручная проверка внешнего вида).
// node shots_help.js <baseUrl> <shotsDir> [lang]
const puppeteer = require('puppeteer-core');
const path = require('path');
const [base, shots, lang = 'ru-RU'] = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        headless: true, args: [`--lang=${lang}`, `--accept-lang=${lang}`] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    const errors = [];
    page.on('pageerror', e => errors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    const shot = async name => page.screenshot({ path: path.join(shots, name + '.png') });
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' });
    await shot('00-login');
    await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await page.goto(base + '/help', { waitUntil: 'networkidle2' }); await sleep(300);
    await shot('01-help');
    await page.goto(base + '/help/snmp-vendors', { waitUntil: 'networkidle2' }); await sleep(300);
    await shot('02-vendors');
    await page.type('#helpSearch', 'mikrotik'); await sleep(300);
    await shot('03-search');
    await page.goto(base + '/help/installation#https', { waitUntil: 'networkidle2' }); await sleep(400);
    await shot('04-https');
    await page.goto(base + '/', { waitUntil: 'networkidle2' });
    await page.click('.page-actions [data-click="openModal"]'); await sleep(500);
    await page.hover('#addSwitchModal .help-tip'); await sleep(400);
    await shot('05-tip');
    await page.keyboard.press('Escape'); await sleep(300);
    await page.click('.rail-avatar'); await sleep(300);
    await shot('06-usermenu');
    await page.goto(base + '/', { waitUntil: 'networkidle2' });
    await page.evaluate(() => openSettingsModal()); await sleep(600);
    await shot('07-settings');
    console.log(errors.length ? 'ОШИБКИ: ' + JSON.stringify(errors) : 'без ошибок JS');
    await browser.close();
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });
