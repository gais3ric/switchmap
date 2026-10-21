// Подсказки «?» везде: на страницах, в окнах и панелях — текст виден целиком, не обрезан и ничем не закрыт.
// node e2e_tips.js <baseUrl> <shotsDir>
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
        executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true,
        args: ['--lang=ru-RU', '--accept-lang=ru-RU'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 900 });
    const jsErrors = [];
    page.on('pageerror', e => jsErrors.push(String(e.message || e)));
    page.on('dialog', d => d.dismiss());
    const open = async url => { await page.goto(base + url, { waitUntil: 'load', timeout: 60000 }); await sleep(400); };

    // Раскрыть всё, где могут прятаться подсказки: секции, <details>, поля SNMPv3
    const expandAll = () => page.evaluate(() => {
        document.querySelectorAll('details').forEach(d => { d.open = true; });
        document.querySelectorAll('[data-click="toggleSection"]').forEach(h => {
            const id = (h.dataset.args || '').replace(/[^\w-]/g, '');
            const c = document.getElementById('content-' + id);
            if (c && getComputedStyle(c).display === 'none') h.click();
        });
        document.querySelectorAll('select').forEach(s => {
            const v3 = [...s.options].find(o => o.value === '3');
            if (v3 && /snmp/i.test(s.name || s.id)) { s.value = '3'; s.dispatchEvent(new Event('change', { bubbles: true })); }
        });
    });

    let tested = 0;
    const failures = [];
    // Все видимые «?» внутри области (страница, окно или панель): навести, проверить окошко подсказки
    async function checkTips(scenario, scope = 'body') {
        await expandAll(); await sleep(300);
        const handles = await page.$$(`${scope} .help-tip`);
        let n = 0;
        for (const h of handles) {
            const visible = await h.evaluate(el => {
                if (!el.offsetParent) return false;
                el.scrollIntoView({ block: 'center', inline: 'center' });
                const r = el.getBoundingClientRect();
                const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                return r.width > 0 && top && (top === el || el.contains(top));
            });
            if (!visible) continue;
            await sleep(120);
            await h.hover(); await sleep(250);
            const res = await page.evaluate(tip => {
                const pop = document.getElementById('helpPopover');
                const expected = tip.querySelector('.help-pop').textContent.trim();
                if (!pop || pop.hidden) return { ok: false, why: 'не открылась' };
                const r = pop.getBoundingClientRect();
                const inside = r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight;
                const hit = document.elementFromPoint(r.left + r.width / 2, r.top + Math.min(12, r.height / 2));
                const onTop = hit && (hit === pop || pop.contains(hit));
                const text = pop.textContent.trim();
                const sized = r.width >= 120 && r.height >= 24;
                return { ok: inside && onTop && text === expected && sized,
                         why: { inside, onTop, sameText: text === expected, sized, w: Math.round(r.width), h: Math.round(r.height) },
                         label: expected.slice(0, 50) };
            }, h);
            n++;
            if (!res.ok) {
                failures.push({ scenario, ...res });
                await page.screenshot({ path: path.join(shots, `tip_fail_${failures.length}.png`) });
            }
            await page.mouse.move(2, 2); await sleep(300);
        }
        tested += n;
        check(`${scenario}: подсказок проверено ${n}`, n > 0 && !failures.some(f => f.scenario === scenario),
              failures.filter(f => f.scenario === scenario).slice(0, 3));
    }

    try {
        await page.goto(base + '/login', { waitUntil: 'domcontentloaded' });
        await page.type('#username', 'admin'); await page.type('#password', 'adminpass123');
        await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), page.click('button[type=submit]')]);

        await open('/');
        await page.evaluate(() => openSettingsModal()); await sleep(500);
        await checkTips('окно «Настройки»', '#settingsModal');
        await page.keyboard.press('Escape'); await page.evaluate(() => closeSettingsModal()); await sleep(300);
        await page.click('.page-actions [data-click="openModal"]'); await sleep(500);
        await checkTips('окно «Добавить коммутатор»', '#addSwitchModal');

        await open('/switch/1'); await checkTips('страница коммутатора');
        await page.evaluate(() => document.getElementById('editBtn').click()); await sleep(500);
        await checkTips('панель «Параметры» (режим правки)', '.drawer');

        await open('/discover'); await checkTips('поиск в сети');
        await page.evaluate(() => { const b = [...document.querySelectorAll('[data-tab], .tab, [role=tab]')].find(x => /NetBox/.test(x.textContent)); if (b) b.click(); });
        await sleep(400); await checkTips('импорт из NetBox');
        await open('/notifications'); await checkTips('уведомления');
        await open('/maintenance'); await checkTips('данные и резервные копии');
        await open('/users');
        await page.click('[data-click="openUserModal"]'); await sleep(400);
        await checkTips('окно «Добавить пользователя»', '#userModal');

        // Узкий экран: подсказка не уходит за край
        await page.setViewport({ width: 390, height: 844 });
        await open('/notifications'); await checkTips('уведомления на телефоне');
        await open('/switch/1');
        await page.evaluate(() => document.getElementById('editBtn').click()); await sleep(500);
        await checkTips('панель «Параметры» на телефоне', '.drawer');
        await page.setViewport({ width: 1400, height: 900 });

        // Мышь с «?» на ссылку «Подробнее» — подсказка не закрывается, ссылка работает
        await open('/');
        await page.evaluate(() => openSettingsModal()); await sleep(500);
        const tip = await page.$('#settingsModal .help-tip:has(a)');
        const tipWithLink = tip || (await page.$$('#settingsModal .help-tip')).pop();
        await tipWithLink.hover(); await sleep(250);
        const link = await page.$('#helpPopover a');
        if (link) {
            await link.hover(); await sleep(400);
            check('подсказка не закрывается, пока мышь на ней', await page.$eval('#helpPopover', el => !el.hidden));
            const href = await link.evaluate(a => a.getAttribute('href'));
            check('ссылка «Подробнее» ведёт в справку', /^\/help\//.test(href), href);
        }
        await page.mouse.move(2, 2); await sleep(400);
        check('мышь ушла — подсказка закрылась', await page.$eval('#helpPopover', el => el.hidden));

        // Клавиатура и сенсорный экран
        await tipWithLink.focus(); await sleep(200);
        check('фокус (Tab) открывает подсказку', await page.$eval('#helpPopover', el => !el.hidden));
        await page.keyboard.press('Escape'); await sleep(200);
        check('Esc закрывает подсказку, окно «Настройки» остаётся', await page.$eval('#helpPopover', el => el.hidden)
            && await page.$eval('#settingsModal', el => el.classList.contains('active')));
        await page.mouse.move(2, 2);
        await tipWithLink.click(); await sleep(200);
        await page.mouse.move(2, 2); await sleep(400);
        check('нажатие закрепляет подсказку (сенсорный экран)', await page.$eval('#helpPopover', el => !el.hidden));
        await tipWithLink.click(); await sleep(200);
        check('повторное нажатие закрывает', await page.$eval('#helpPopover', el => el.hidden));

        // «?» в заголовке секции не сворачивает секцию
        await open('/switch/1');
        await page.evaluate(() => document.getElementById('editBtn').click()); await sleep(500);
        const headTip = await page.$('.drawer [data-click="toggleSection"] .help-tip');
        if (headTip) {
            const sectionState = () => page.evaluate(() => [...document.querySelectorAll('.drawer [id^="content-"]')].map(c => getComputedStyle(c).display).join());
            const before = await sectionState();
            await headTip.click(); await sleep(300);
            check('нажатие на «?» в заголовке секции не сворачивает её', await sectionState() === before);
        }

        // ── Другие всплывающие элементы: меню, контекстное меню порта, подсказка порта
        const fullyVisible = sel => page.evaluate(sel => {
            const el = [...document.querySelectorAll(sel)].find(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'
                && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().height > 0);
            if (!el) return { ok: false, why: 'не открылось' };
            const r = el.getBoundingClientRect();
            const inside = r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 0.5 && r.bottom <= innerHeight + 0.5;
            const pts = [[r.left + 6, r.top + 6], [r.right - 6, r.bottom - 6], [r.left + r.width / 2, r.top + r.height / 2]];
            const onTop = pts.every(([x, y]) => { const h = document.elementFromPoint(x, y); return h && (h === el || el.contains(h)); });
            return { ok: inside && onTop, why: { inside, onTop, r: [r.left, r.top, r.right, r.bottom].map(Math.round) } };
        }, sel);
        for (const [w, h] of [[1400, 900], [390, 844]]) {
            await page.setViewport({ width: w, height: h });
            const sfx = w < 500 ? ' (телефон)' : '';
            for (const url of ['/', '/switch/1']) {
                await open(url);
                const toggles = await page.$$('[data-menu-toggle]');
                for (const tg of toggles) {
                    if (!await tg.evaluate(e => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden')) continue;
                    const label = await tg.evaluate(e => (e.textContent || e.title || '').trim().slice(0, 20) || e.className);
                    await tg.evaluate(e => e.scrollIntoView({ block: 'center' }));
                    await tg.evaluate(e => e.click()); await sleep(300);
                    const res = await fullyVisible('.menu-wrap.open .dropdown, .dropdown.open, .menu-wrap .dropdown.show');
                    check(`меню «${label}» на ${url}${sfx}: целиком на экране`, res.ok, res.why);
                    await page.keyboard.press('Escape'); await page.mouse.click(2, 300); await sleep(200);
                }
            }
            // Правый клик по крайнему порту в режиме правки — меню не за краем окна
            await open('/switch/1');
            await page.evaluate(() => document.getElementById('editBtn').click()); await sleep(400);
            // на телефоне панель «Параметры» занимает весь экран — закрываем её, режим правки остаётся
            await page.evaluate(() => { const d = document.getElementById('sidebar'); if (d && d.classList.contains('open') && innerWidth < 700) d.querySelector('[data-click="toggleMenu"]').click(); });
            await sleep(400);
            const ports = await page.$$(".port[data-type='switch']");
            const last = ports[ports.length - 1];
            await last.evaluate(e => e.scrollIntoView({ block: 'center', inline: 'end' }));
            const box = await last.boundingBox();
            await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2, { button: 'right' }); await sleep(300);
            const res = await fullyVisible('#portTypeMenu');
            check(`контекстное меню крайнего порта${sfx}: целиком на экране`, res.ok, res.why);
            await page.mouse.click(2, 300); await sleep(200);
        }
        // Нижняя панель на телефоне: все кнопки, включая профиль, на экране
        for (const w of [390, 320]) {
            await page.setViewport({ width: w, height: 760 });
            await open('/');
            const off = await page.evaluate(() => [...document.querySelectorAll('.rail .rail-item, .rail .rail-avatar')]
                .filter(e => getComputedStyle(e).display !== 'none')
                .map(e => ({ label: e.getAttribute('aria-label') || e.textContent.trim(), r: e.getBoundingClientRect() }))
                .filter(x => x.r.left < 0 || x.r.right > innerWidth || x.r.width < 24)
                .map(x => `${x.label}: ${Math.round(x.r.left)}..${Math.round(x.r.right)}`));
            check(`нижняя панель на экране ${w}px: все кнопки видны`, off.length === 0, off);
        }
        await page.setViewport({ width: 1400, height: 900 });

        check(`всего проверено подсказок: ${tested}`, tested >= 30, tested);
        check('нет ошибок JS', jsErrors.length === 0, jsErrors);
    } catch (e) {
        console.log('СЦЕНАРИЙ УПАЛ: ' + (e.stack || e));
        results.push(false);
    }
    await browser.close();
    const failed = results.filter(r => !r).length;
    console.log(`\nИТОГО: ${failed ? 'провалено ' + failed : 'все проверки пройдены'} (${results.length} проверок)`);
    process.exit(failed ? 1 : 0);
})();
