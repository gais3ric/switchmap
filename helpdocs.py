"""Справка: статьи help/<язык>/<имя>.md с заголовком из полей «ключ: значение» между строками ---.

    ---
    title: Первые шаги
    category: start
    order: 1
    summary: Одной строкой — о чём статья
    ---
    Текст в Markdown: # заголовки, списки, **жирный**, `код`, ```блоки```, таблицы, [ссылки](/help/snmp),
    > заметки (> **Совет:** …, > **Важно:** …).

Нет статьи на языке пользователя — показывается английская, затем русская (с пометкой).
Разметка Markdown разбирается здесь же (без сторонних библиотек), весь текст экранируется.
"""
import html
import os
import re

import config
from i18n import N_

CATEGORIES = (  # порядок разделов в справке; подписи переводятся при показе
    ("start", N_("Начало работы")),
    ("devices", N_("Коммутаторы и SNMP")),
    ("monitoring", N_("Мониторинг и оповещения")),
    ("data", N_("Данные и обслуживание")),
    ("admin", N_("Администрирование")),
    ("problems", N_("Решение проблем")),
)
FALLBACKS = ("en", "ru")
_cache = {}


def help_dir():
    return os.path.join(config.resource_dir(), "help")


def _parse_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().lstrip("﻿")
    meta, body = {}, text
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    return meta, body


def articles(lang):
    """[{slug, title, category, order, summary, lang, text}] — с подстановкой статей других языков."""
    key = lang
    if key in _cache:
        return _cache[key]
    found = {}
    for code in (lang,) + tuple(l for l in FALLBACKS if l != lang):
        folder = os.path.join(help_dir(), code)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".md"):
                continue
            slug = name[:-3]
            if slug in found:
                continue
            meta, body = _parse_file(os.path.join(folder, name))
            found[slug] = {
                "slug": slug, "lang": code, "title": meta.get("title", slug),
                "category": meta.get("category", "start"), "order": int(meta.get("order", 99) or 99),
                "summary": meta.get("summary", ""), "keywords": meta.get("keywords", ""), "body": body,
                "text": plain_text(body),
            }
    order = {c: i for i, (c, _title) in enumerate(CATEGORIES)}
    result = sorted(found.values(), key=lambda a: (order.get(a["category"], 99), a["order"], a["title"]))
    _cache[key] = result
    return result


def get(lang, slug):
    return next((a for a in articles(lang) if a["slug"] == slug), None)


def reload():
    _cache.clear()


# ─────────── Markdown → HTML ───────────

def slugify(text):
    s = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.U).strip()
    return re.sub(r"[\s_]+", "-", s)[:60] or "section"


def _inline(text):
    """Строчная разметка; text ещё не экранирован."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
        s = re.sub(r"\[\[(.+?)\]\]", r"<kbd>\1</kbd>", s)  # [[Ctrl]] — клавиша
        out.append(s)
    return "".join(out)


def _link(m):
    label, url = m.group(1), html.unescape(m.group(2))
    if url.startswith(("/", "#")):
        return f'<a href="{html.escape(url)}">{label}</a>'
    if url.startswith(("http://", "https://")):
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'
    return label  # javascript: и прочее — только текст


def render(body):
    """Markdown → (html, оглавление [(id, заголовок)])."""
    lines = body.replace("\r\n", "\n").split("\n")
    out, toc, i = [], [], 0
    para = []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(p.strip() for p in para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            lang = stripped[3:].strip()
            indent = len(line) - len(line.lstrip())  # блок внутри пункта списка — с отступом
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                raw = lines[i]
                code.append(raw[indent:] if raw[:indent].strip() == "" else raw)
                i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            out.append(f'<pre{cls}><code>{html.escape(chr(10).join(code))}</code></pre>')
            i += 1
            continue
        m = re.match(r"(#{1,4})\s+(.*)", stripped)
        if m:
            flush()
            level = len(m.group(1)) + 1  # # в статье → <h2> (h1 — заголовок статьи)
            title = m.group(2).strip()
            # «## Заголовок {#snmpv3}» — метка одинакова во всех языках, на неё ссылаются подсказки
            mid = re.search(r"\s*\{#([\w-]+)\}\s*$", title)
            anchor = mid.group(1) if mid else slugify(title)
            title = title[:mid.start()] if mid else title
            if level == 2:
                toc.append((anchor, title))
            out.append(f'<h{level} id="{anchor}">{_inline(title)}</h{level}>')
            i += 1
            continue
        if stripped.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            text = " ".join(quote)
            kind = "note"
            low = text.lower()
            if re.match(r"\*\*(важно|important|重要|注意|importante|wichtig|attention)", low):  # i18n: ignore
                kind = "warning"
            elif re.match(r"\*\*(совет|tip|提示|建议|consejo|tipp|astuce)", low):  # i18n: ignore
                kind = "tip"
            out.append(f'<div class="callout callout-{kind}">{_inline(text)}</div>')
            continue
        if re.match(r"\|.*\|\s*$", stripped):
            flush()
            rows = []
            while i < len(lines) and re.match(r"\|.*\|\s*$", lines[i].strip()):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, rest = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            t = ["<div class=\"table-wrap\"><table class=\"table\"><thead><tr>"]
            t += [f"<th>{_inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rest:
                t.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue
        m = re.match(r"([-*]|\d+[.)])\s+(.*)", stripped)
        if m:
            flush()
            ordered = m.group(1)[0].isdigit()
            start = int(re.match(r"\d+", m.group(1)).group(0)) if ordered else 1
            items = []
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    break  # блок кода внутри пункта — после списка; нумерация продолжится (start)
                mm = re.match(r"\s*([-*]|\d+[.)])\s+(.*)", lines[i])
                if mm and (mm.group(1)[0].isdigit()) == ordered:
                    items.append(mm.group(2))
                elif items and lines[i].startswith(("  ", "\t")) and lines[i].strip():
                    items[-1] += " " + lines[i].strip()   # продолжение пункта
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            attr = f' start="{start}"' if ordered and start != 1 else ""
            out.append(f"<{tag}{attr}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if not stripped:
            flush()
        else:
            para.append(line)
        i += 1
    flush()
    return "\n".join(out), toc


def plain_text(body):
    """Текст для поиска: без разметки."""
    text = re.sub(r"```.*?```", " ", body, flags=re.S)
    text = re.sub(r"[#>*`|\[\]()_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def search_index(lang):
    return [{"slug": a["slug"], "title": a["title"], "summary": a["summary"], "category": a["category"],
             "text": (a["title"] + " " + a["keywords"] + " " + a["summary"] + " " + a["text"]).lower()}
            for a in articles(lang)]
