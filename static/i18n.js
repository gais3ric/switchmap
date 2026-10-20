// Переводы в браузере. Сервер кладёт в window.I18N язык страницы и переводы строк, которые
// встречаются в скриптах (ключ — русский текст, как в шаблонах):
//   t('Сохранено')                              → «Saved»
//   t('Коммутатор «{name}» удалён', { name })   → подстановка {name}
//   tn(5, '{n} порт', '{n} порта', '{n} портов') → «5 ports» (формы — по правилам языка)
// Нет перевода — русский текст.
(function () {
    const data = window.I18N || { lang: 'ru', messages: {} };
    const messages = data.messages || {};
    const LANG = data.lang || 'ru';

    function format(text, params) {
        if (!params) return text;
        return text.replace(/\{(\w+)\}/g, (m, key) => (key in params && params[key] !== undefined && params[key] !== null)
            ? String(params[key]) : m);
    }

    function pluralIndex(lang, n) {
        n = Math.abs(parseInt(n, 10) || 0);
        if (lang === 'ru') {
            if (n % 10 === 1 && n % 100 !== 11) return 0;
            if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return 1;
            return 2;
        }
        if (lang === 'zh') return 0;
        if (lang === 'fr') return n <= 1 ? 0 : 1;
        return n === 1 ? 0 : 1;
    }

    window.t = function (msg, params) {
        let value = messages[msg];
        if (Array.isArray(value)) value = value[0];
        return format(value || msg, params);
    };

    window.tn = function (n, one, few, many, params) {
        params = Object.assign({ n }, params || {});
        const value = messages[one];
        let forms = [one, few, many], lang = 'ru';
        if (value) { forms = Array.isArray(value) ? value : [value]; lang = LANG; }
        return format(forms[Math.min(pluralIndex(lang, n), forms.length - 1)], params);
    };

    // Язык для дат и чисел (toLocaleString)
    window.LOCALE = { ru: 'ru-RU', en: 'en-GB', zh: 'zh-CN', es: 'es-ES', de: 'de-DE', fr: 'fr-FR' }[LANG] || LANG;
    window.LANG = LANG;
})();
