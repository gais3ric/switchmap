Noto Sans SC (SIL Open Font License 1.1, см. NotoSansSC.OFL.txt) — шрифт с иероглифами для экспорта в PDF
на китайском. Загружается браузером только при таком экспорте.

Источник: https://github.com/google/fonts/tree/main/ofl/notosanssc (NotoSansSC[wght].ttf).
Из переменного шрифта сделаны два начертания (400 и 700) и оставлены только нужные символы:
GB2312, латиница, кириллица, знаки препинания и все символы китайского каталога переводов.

Пересобрать (нужен fonttools):
    python packaging/fonts/make_cjk_font.py NotoSansSC[wght].ttf . static/vendor/fonts
