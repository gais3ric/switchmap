// Браузерная проверка окна статистики. node e2e.js <baseUrl> <shotsDir>
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
    const browser = await puppeteer.launch({
        executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        headless: true,
        args: ['--no-first-run', '--no-default-browser-check', '--lang=ru-RU', '--accept-lang=ru-RU'],
    });
    const page = await browser.newPage();
    await page.goto(base + '/login', { waitUntil: 'domcontentloaded' }); await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('button[type=submit]')]);
    await page.setViewport({ width: 1400, height: 900 });

    const jsErrors = [], dialogs = [], badResponses = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error' && !m.location().url?.includes('favicon')) jsErrors.push('console: ' + m.text()); });
    page.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
    page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) badResponses.push(`${r.status()} ${r.url()}`); });

    const toastTexts = () => page.$$eval('.toast .toast-text', els => els.map(e => e.textContent));
    const visible = () => page.$eval('#statsModal', el => el.classList.contains('visible'));
    const text = sel => page.$eval(sel, el => el.textContent.trim());
    const hidden = sel => page.$eval(sel, el => el.hidden);
    const waitIdle = () => page.waitForFunction(() => !document.getElementById('refreshStatsBtn').disabled, { timeout: 15000 });

    // ── 1. Регрессия: главная, топология, страница коммутатора без ошибок JS
    for (const url of ['/', '/topology']) {
        const r = await page.goto(base + url, { waitUntil: 'load', timeout: 60000 });
        check(`страница ${url} открывается`, r.status() === 200, r.status());
    }
    await page.goto(base + '/switch/1', { waitUntil: 'load', timeout: 60000 });
    check('Chart.js загрузился', await page.evaluate(() => typeof Chart !== 'undefined'));
    check('окно скрыто при загрузке страницы', !(await visible()));

    // ── 2. Открытие окна до какого-либо опроса
    await page.click('button[data-click="openStatsModal"]');
    await sleep(800);
    check('окно открылось', await visible());
    check('надпись «ещё не опрашивался»', (await text('#statsLastPoll')).includes('ещё не опрашивался'), await text('#statsLastPoll'));
    check('пустая история: подсказка видна', !(await hidden('#healthEmpty')));
    check('подсказка в списке портов', (await text('#portSelectStats option')).includes('Обновить данные'), await text('#portSelectStats option'));
    check('открытие окна не запускает SNMP-опрос', !badResponses.length && !(await page.evaluate(() =>
        performance.getEntriesByType('resource').some(e => e.name.includes('/api/poll_snmp')))));
    check('таймер автообновления запущен', await page.evaluate(() => statsRefreshTimer !== null));
    await page.screenshot({ path: path.join(shots, '1_empty.png') });

    // ── 3. Кнопка «Обновить данные»
    await page.click('#refreshStatsBtn');
    await waitIdle();
    await sleep(500);
    check('CPU заполнен', /%$/.test(await text('#cpuValue')), await text('#cpuValue'));
    check('RAM заполнен', /%$/.test(await text('#ramValue')), await text('#ramValue'));
    check('температура заполнена', /°C$/.test(await text('#tempValue')), await text('#tempValue'));
    check('время последнего опроса', (await text('#statsLastPoll')).startsWith('Последний опрос'), await text('#statsLastPoll'));
    check('график здоровья построен', await page.evaluate(() => !!Chart.getChart('healthChart')));
    check('подсказка истории скрыта', await hidden('#healthEmpty'));
    const opts = await page.$$eval('#portSelectStats option', os => os.map(o => o.value));
    check('в списке 9 портов + заглушка', opts.length === 10, opts);
    const poe = await page.$$eval('#poeGrid .poe-port', cs => cs.map(c => c.innerText.replace(/\s+/g, ' ').trim()));
    check('PoE: 4 карточки', poe.length === 4, poe);
    check('PoE: порт 2 «Питание 6.5 W»', poe.some(p => p.includes('0/2') && p.includes('Питание') && p.includes('6.5 W')), poe);
    check('PoE: порт 4 «Выключен»', poe.some(p => p.includes('0/4') && p.includes('Выключен')), poe);
    check('PoE: неизвестная мощность как «— W»', poe.some(p => p.includes('0/1') && p.includes('— W')), poe);

    // ── 4. Выбор порта: скорость трафика
    await page.select('#portSelectStats', '5');  // у порта 5 пока один опрос
    await sleep(700);
    check('один опрос: подсказка «нужно минимум два опроса»', (await text('#trafficEmpty')).includes('минимум два опроса')
        && !(await hidden('#trafficEmpty')), await text('#trafficEmpty'));
    check('один опрос: графика нет', await page.evaluate(() => !Chart.getChart('trafficChart')));

    await page.select('#portSelectStats', '3');  // 12 засеянных опросов + 1 настоящий
    await sleep(700);
    check('график трафика построен', await page.evaluate(() => !!Chart.getChart('trafficChart')));
    check('подсказка трафика скрыта', await hidden('#trafficEmpty'));
    const tc = await page.evaluate(() => {
        const ch = Chart.getChart('trafficChart');
        return { n: ch.data.labels.length, inData: ch.data.datasets[0].data, errData: ch.data.datasets[2].data,
                 yTitle: ch.options.scales.y.title.text, label0: ch.data.datasets[0].label };
    });
    check('12 точек скорости (13 опросов)', tc.n === 12, tc.n);
    check('ось Y в Мбит/с', tc.yTitle === 'Скорость, Мбит/с', tc.yTitle);
    check('первый интервал: входящий 35 Мбит/с', tc.inData[0] === 35, tc.inData);
    check('перезагрузка — разрыв линии (одна пустая точка)', tc.inData.filter(v => v === null).length === 1 && tc.inData[6] === null, tc.inData);
    check('ошибки: 3 за интервал с ошибками', tc.errData.includes(3), tc.errData);
    const summary = await text('#trafficSummary');
    check('сводка за последний интервал', /Последний интервал \(\d+ (с|мин)\): ↓ [\d.]+ (Кбит|Мбит|Гбит)\/с · ↑ /.test(summary), summary);
    await page.screenshot({ path: path.join(shots, '2_filled.png') });
    await page.$eval('.stats-modal-content', el => el.scrollTop = el.scrollHeight);
    await sleep(200);
    await page.screenshot({ path: path.join(shots, '3_filled_bottom.png') });

    // ── 5. Повторное обновление и автообновление сохраняют выбранный порт
    await page.click('#refreshStatsBtn');
    await waitIdle();
    await sleep(500);
    check('после «Обновить» порт 3 остался выбран', await page.$eval('#portSelectStats', s => s.value) === '3');
    const pts = await page.evaluate(() => Chart.getChart('trafficChart').data.labels.length);
    check('после второго опроса точек не меньше 12', pts >= 12, pts);
    await page.evaluate(() => autoRefreshStats());
    await sleep(700);
    check('автообновление: порт 3 остался, график есть', await page.$eval('#portSelectStats', s => s.value) === '3'
        && await page.evaluate(() => !!Chart.getChart('trafficChart')));

    // ── 6. Закрытие: Esc, клик по фону, крестик
    await page.keyboard.press('Escape');
    await sleep(200);
    check('Esc закрывает окно', !(await visible()));
    check('после закрытия таймер остановлен', await page.evaluate(() => statsRefreshTimer === null));
    check('после закрытия графики уничтожены', await page.evaluate(() => !Chart.getChart('healthChart') && !Chart.getChart('trafficChart')));

    await page.click('button[data-click="openStatsModal"]');
    await sleep(800);
    check('повторное открытие: графики снова построены', await page.evaluate(() => !!Chart.getChart('healthChart') && !!Chart.getChart('trafficChart')));
    await page.mouse.click(5, 450); // фон окна
    await sleep(200);
    check('клик по фону закрывает окно', !(await visible()));

    await page.click('button[data-click="openStatsModal"]');
    await sleep(500);
    await page.mouse.click(700, 450); // внутри окна
    await sleep(200);
    check('клик внутри окна не закрывает его', await visible());
    await page.click('.stats-modal-close');
    await sleep(200);
    check('крестик закрывает окно', !(await visible()));

    // ── 7. Двойное открытие не плодит таймеры
    await page.evaluate(() => { openStatsModal(); openStatsModal(); });
    const t1 = await page.evaluate(() => statsRefreshTimer);
    await page.evaluate(() => closeStatsModal());
    check('двойной вызов openStatsModal даёт один таймер', t1 !== null && await page.evaluate(() => statsRefreshTimer === null));

    // ── 8. Коммутатор без IP: понятная ошибка вместо падения
    await page.goto(base + '/switch/2', { waitUntil: 'load', timeout: 60000 });
    await page.click('button[data-click="openStatsModal"]');
    await sleep(500);
    await page.click('#refreshStatsBtn');
    await waitIdle();
    const t = await toastTexts();
    check('без IP: показано уведомление об ошибке', t.some(x => x.includes('IP')), t);
    check('без IP: PoE-блок скрыт', await page.$eval('#poeContainer', el => getComputedStyle(el).display === 'none'));
    await page.keyboard.press('Escape');

    // ── 9. Узкий экран (телефон)
    await page.setViewport({ width: 400, height: 800 });
    await page.goto(base + '/switch/1', { waitUntil: 'load', timeout: 60000 });
    await page.click('button[data-click="openStatsModal"]').catch(() => page.evaluate(() => openStatsModal()));
    await sleep(800);
    const overflow = await page.$eval('.stats-modal-content', el => el.scrollWidth - el.clientWidth);
    check('на 400px окно без горизонтальной прокрутки', overflow <= 0, overflow);
    await page.screenshot({ path: path.join(shots, '4_mobile.png') });

    // ── Итог
    check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    const unexpected = badResponses.filter(r => !r.includes('/api/poll_snmp/2'));
    check('нет неожиданных HTTP-ошибок', unexpected.length === 0, unexpected);
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
})().catch(e => { console.error('СЦЕНАРИЙ УПАЛ:', e); process.exit(1); });


