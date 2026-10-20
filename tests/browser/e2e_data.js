// Журнал, «Данные», экспорт, период графиков. node e2e_data.js <baseUrl> <shotsDir>
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
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' }); await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
    await page.setViewport({ width: 1440, height: 900 });
    const jsErrors = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !String(m.location().url).includes('favicon')) jsErrors.push('console: ' + m.text()); });
    page.on('dialog', d => d.accept(d.defaultValue()));
    const open = async url => { await page.goto(base + url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(1200); };
    // Надёжное ожидание перезагрузки: метка в window пропадает на новой странице
    const navVia = async action => {
        await page.evaluate(() => { window.__oldPage = true; });
        await action();
        await page.waitForFunction(() => !window.__oldPage && document.readyState !== 'loading', { timeout: 30000, polling: 200 });
        await sleep(500);
    };
    const toasts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));
    const fetchHead = url => page.evaluate(async u => { const r = await fetch(u); const b = await r.arrayBuffer();
        return { status: r.status, type: r.headers.get('content-type'), disp: r.headers.get('content-disposition'), size: b.byteLength,
                 magic: String.fromCharCode(...new Uint8Array(b).slice(0, 2)) }; }, url);

    // ── Навигация
    await open('/');
    const rail = await page.$$eval('.rail-nav .rail-item', els => els.map(e => e.dataset.label));
    check('в навигации есть «Журнал» и «Данные»', rail.includes('Журнал изменений') && rail.includes('Данные и резервные копии'), rail);

    // ── Экспорт на главной
    await page.click('.page-actions [data-menu-toggle]'); await sleep(250);
    check('меню экспорта открывается', await page.$eval('.page-actions .menu-wrap', el => el.classList.contains('open')));
    const links = await page.$$eval('.page-actions .dropdown a', as => as.map(a => a.getAttribute('href')));
    check('главная: 5 вариантов экспорта', links.length === 5 && links[0] === '/export/inventory.xlsx', links);
    const inv = await fetchHead('/export/inventory.xlsx');
    check('инвентарь скачивается как xlsx', inv.status === 200 && inv.magic === 'PK' && inv.type.includes('spreadsheetml') && inv.disp.includes('attachment'), inv);
    await page.keyboard.press('Escape'); await sleep(200);
    check('Esc закрывает меню', !(await page.$eval('.page-actions .menu-wrap', el => el.classList.contains('open'))));

    // ── Экспорт и история на странице коммутатора
    await open('/switch/1');
    await page.click('.page-actions [data-menu-toggle]'); await sleep(250);
    const sw = await page.$$eval('.page-actions .dropdown a, .page-actions .dropdown button', els => els.map(e => e.getAttribute('href') || e.getAttribute('onclick')));
    check('коммутатор: Excel, PDF, 3 CSV, история', sw.includes('/export/switch/1.xlsx') && sw.includes('exportToPDF()')
        && sw.filter(h => h && h.endsWith('.csv')).length === 3 && sw.includes('/audit?switch=1'), sw);
    const x = await fetchHead('/export/switch/1.xlsx');
    check('Excel коммутатора скачивается', x.status === 200 && x.magic === 'PK' && x.size > 1000, x);
    const csv = await fetchHead('/export/switch/1/ports.csv');
    check('CSV портов скачивается', csv.status === 200 && csv.type.includes('text/csv'), csv);
    await page.click('#snmpBtn'); await page.keyboard.press('Escape');

    // ── Период графиков
    await page.waitForFunction(() => !document.getElementById('snmpBtn').disabled, { timeout: 60000 });
    await page.evaluate(() => document.getElementById('snmpPanel').classList.remove('visible'));
    await page.evaluate(() => localStorage.removeItem('switchmap.statsPeriod'));
    await open('/switch/1');
    await page.click('button[onclick="openStatsModal()"]'); await sleep(1300);
    check('по умолчанию период 24 ч', await page.$eval('#statsPeriod .is-active', b => b.dataset.period) === '24h');
    await page.select('#portSelectStats', '10109'); await sleep(1000);
    check('24 ч: сводка «Последний интервал»', (await page.$eval('#trafficSummary', el => el.textContent)).startsWith('Последний интервал'));
    await page.click('#statsPeriod button[data-period="7d"]'); await sleep(1300);
    const s7 = await page.evaluate(() => ({ active: document.querySelector('#statsPeriod .is-active').dataset.period,
        summary: document.getElementById('trafficSummary').textContent,
        ds: Chart.getChart('trafficChart')?.data.datasets.map(d => d.label), health: !!Chart.getChart('healthChart') }));
    check('7 д: кнопка активна, графики перестроены', s7.active === '7d' && s7.health && s7.ds, s7);
    check('7 д: средние, пики и сводка за период', s7.summary.startsWith('За 7 дней') && s7.ds.includes('Пик входящий')
        && s7.ds[0].includes('среднее'), s7);
    await page.screenshot({ path: path.join(shots, 'd_stats_7d.png') });
    await open('/switch/1');
    await page.click('button[onclick="openStatsModal()"]'); await sleep(1000);
    check('выбор периода запоминается', await page.$eval('#statsPeriod .is-active', b => b.dataset.period) === '7d');
    await page.click('#statsPeriod button[data-period="1y"]'); await sleep(800);
    await page.click('#statsPeriod button[data-period="24h"]'); await sleep(800);
    await page.keyboard.press('Escape'); await sleep(300);

    // ── Журнал: правка → запись → детали → откат
    const oldName = await page.$eval('#nameInput', el => el.value);
    await page.click('#editBtn'); await sleep(400);
    await page.$eval('#nameInput', el => { el.value = ''; });
    await page.type('#nameInput', 'Ядро (переименовано)');
    await navVia(() => page.click('#saveBtn'));
    await page.click('.page-actions [data-menu-toggle]'); await sleep(250);
    await navVia(() => page.click('.page-actions .dropdown a[href="/audit?switch=1"]'));
    await sleep(800);
    check('«История изменений» открывает журнал с фильтром', page.url().endsWith('/audit?switch=1')
        && await page.$eval('#filterSwitch', s => s.value) === '1');
    const first = await page.$eval('#auditBody .audit-row', r => ({ id: r.dataset.id, text: r.innerText }));
    check('верхняя запись — переименование', first.text.includes('Изменён коммутатор') && first.text.includes('Название'), first.text);
    await page.click('#auditBody .audit-row .audit-summary'); await sleep(300);
    const det = await page.$eval(`.audit-details[data-for="${first.id}"]`, el => ({ hidden: el.hidden, text: el.innerText }));
    check('клик раскрывает «было → стало»', !det.hidden && det.text.includes(oldName) && det.text.includes('Ядро (переименовано)'), det);
    await page.screenshot({ path: path.join(shots, 'd_audit.png') });
    await page.click(`[data-revert="${first.id}"]`); await sleep(400);
    check('откат спрашивает подтверждение', await page.$eval('#confirmModal', el => el.classList.contains('active')));
    await page.click('#confirmOk'); await sleep(1200);
    check('уведомление об откате', (await toasts()).includes('Изменение откачено'), await toasts());
    const after = await page.$$eval('#auditBody .audit-row', rows => rows.slice(0, 2).map(r => r.innerText));
    check('в журнале — запись «Откат», исходная отмечена', after[0].includes('Откат изменения') && after[1].includes('отменено'), after);
    await open('/switch/1');
    check('название вернулось', await page.$eval('#nameInput', el => el.value) === oldName);
    await open('/audit');
    await page.select('#filterAction', 'settings'); await sleep(600);
    check('фильтр по действию и URL', page.url().includes('action=settings')
        && (await page.$$eval('#auditBody .audit-row', rs => rs.every(r => r.innerText.includes('Настройки')))));

    // ── «Данные»: копии, сроки, обслуживание
    await open('/maintenance');
    const kpi = await page.evaluate(() => ['kpiSize', 'kpiRaw', 'kpiBackups'].map(id => document.getElementById(id).textContent));
    check('KPI заполнены', kpi.every(v => v && v !== '—'), kpi);
    const n0 = await page.$$eval('#backupsBody tr', r => r.length);
    await page.click('#createBackup'); await sleep(1200);
    const n1 = await page.$$eval('#backupsBody tr', r => r.length);
    check('«Создать копию» добавляет строку и уведомляет', n1 === n0 + 1 && (await toasts()).some(t => t.startsWith('Копия создана')), { n0, n1 });
    const dl = await page.$eval('#backupsBody a', a => a.getAttribute('href'));
    const dlr = await fetchHead(dl);
    check('копия скачивается', dlr.status === 200 && dlr.size > 1000, dlr);
    await page.screenshot({ path: path.join(shots, 'd_maintenance.png') });
    await page.$eval('#retRaw', el => { el.value = '5'; });
    await page.click('#saveRetention'); await sleep(800);
    check('сроки хранения сохраняются', (await toasts()).includes('Сроки хранения сохранены'));
    await page.click('#runMaintenance'); await sleep(1500);
    check('«Обслужить сейчас» — отчёт', (await toasts()).some(t => t.startsWith('Готово')), await toasts());
    await page.click('#backupsBody [data-restore]'); await sleep(400);
    check('восстановление спрашивает подтверждение', await page.$eval('#confirmModal', el => el.classList.contains('active')));
    await page.click('#confirmOk');
    await page.waitForNavigation({ waitUntil: 'load', timeout: 15000 }).catch(() => {});
    await sleep(800);
    check('после восстановления — копия «перед восстановлением»', (await page.$$eval('#backupsBody tr', rs => rs.map(r => r.innerText)))
        .some(t => t.includes('перед восстановлением')));
    const n2 = await page.$$eval('#backupsBody tr', r => r.length);
    await page.click('#backupsBody tr:last-child [data-delete]'); await sleep(400);
    await page.click('#confirmOk'); await sleep(1000);
    check('удаление копии', await page.$$eval('#backupsBody tr', r => r.length) === n2 - 1);
    await open('/audit');
    check('восстановление базы записано в журнал', (await page.$eval('#auditBody', el => el.innerText)).includes('База восстановлена из копии'));

    check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });




