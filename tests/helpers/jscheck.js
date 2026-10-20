// Проверка синтаксиса JavaScript: static/*.js и встроенные <script> шаблонов (вставки Jinja заменяются заглушками).
// node tests/helpers/jscheck.js <папка проекта>  → код 0, если ошибок нет
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = process.argv[2] || path.join(__dirname, '..', '..');
const errors = [];

function check(code, where) {
    try {
        new vm.Script(code, { filename: where });
    } catch (e) {
        const line = (e.stack.match(/:(\d+)\n/) || [])[1];
        errors.push(`${where}${line ? ':' + line : ''}: ${e.message}`);
    }
}

for (const name of fs.readdirSync(path.join(root, 'static')).filter(n => n.endsWith('.js'))) {
    check(fs.readFileSync(path.join(root, 'static', name), 'utf8'), `static/${name}`);
}
for (const name of fs.readdirSync(path.join(root, 'templates')).filter(n => n.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(root, 'templates', name), 'utf8');
    const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;
    let m;
    while ((m = re.exec(html))) {
        const startLine = html.slice(0, m.index).split('\n').length;
        // {{ … }} → null (внутри строк — просто текст), {% … %} → пусто; номера строк сохраняются
        const code = m[1].replace(/\{%[\s\S]*?%\}/g, s => s.replace(/[^\n]/g, ' '))
                         .replace(/\{\{[\s\S]*?\}\}/g, s => 'null' + s.slice(4).replace(/[^\n]/g, ' '));
        check('\n'.repeat(startLine - 1) + code, `templates/${name}`);
    }
}
errors.forEach(e => console.log('FAIL ' + e));
console.log(errors.length ? `ИТОГО: провалено ${errors.length}` : 'ИТОГО: все проверки пройдены');
process.exit(errors.length ? 1 : 0);
