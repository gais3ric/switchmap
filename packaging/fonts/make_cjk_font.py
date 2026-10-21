"""Шрифт для PDF на китайском (static/vendor/fonts, см. README.txt там же).
python packaging/fonts/make_cjk_font.py NotoSansSC[wght].ttf <папка проекта> <куда сохранить>

Noto Sans SC → два статических начертания (400, 700), только нужные символы: GB2312 (6763 иероглифа),
латиница, кириллица, знаки препинания, плюс все символы китайского каталога переводов."""
import json, os, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

src, project, out_dir = sys.argv[1:4]
chars = set()
for b1 in range(0xA1, 0xF8):
    for b2 in range(0xA1, 0xFF):
        try:
            chars.add(bytes([b1, b2]).decode("gb2312"))
        except UnicodeDecodeError:
            pass
ranges = [(0x20, 0x7E), (0xA0, 0x17F), (0x400, 0x45F), (0x2010, 0x206F), (0x20A0, 0x20BF), (0x2100, 0x215F),
          (0x2190, 0x21FF), (0x2460, 0x24FF), (0x2500, 0x257F), (0x25A0, 0x25FF), (0x3000, 0x303F), (0xFF00, 0xFFEF)]
for a, b in ranges:
    chars.update(chr(c) for c in range(a, b + 1))
cat = json.load(open(os.path.join(project, "locales", "zh.json"), encoding="utf-8"))
for v in cat.values():
    chars.update("".join(v) if isinstance(v, list) else v)
chars.discard("\n")

vf = TTFont(src)
cmap = vf.getBestCmap()
print("Кириллица в шрифте:", all(ord(c) in cmap for c in "АБВабвЖжЯяЁё"))
missing = sorted(c for c in chars if ord(c) not in cmap and ord(c) > 0x2FF)
print("нет в шрифте (не страшно):", len(missing))
text = "".join(sorted(c for c in chars if ord(c) in cmap))
print("символов в наборе:", len(text))

for weight, name in ((400, "Regular"), (700, "Bold")):
    f = instancer.instantiateVariableFont(TTFont(src), {"wght": weight})
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.hinting = False
    opts.desubroutinize = True
    s = subset.Subsetter(opts)
    s.populate(text=text)
    s.subset(f)
    # Имена начертаний: после instancer у обоих осталось «Thin» — pdfmake счёл бы их одним шрифтом
    names = f["name"]
    for rec in list(names.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17):
            names.removeNames(nameID=rec.nameID)
    for nid, val in ((1, "Noto Sans SC"), (2, name), (3, f"NotoSansSC-{name}-SwitchMap-subset"),
                     (4, f"Noto Sans SC {name}"), (6, f"NotoSansSC-{name}")):
        names.setName(val, nid, 3, 1, 0x409)
        names.setName(val, nid, 1, 0, 0)
    f["OS/2"].fsSelection = (f["OS/2"].fsSelection & ~0b1100001) | (0b100000 if weight == 700 else 0b1000000)
    f["head"].macStyle = 1 if weight == 700 else 0
    path = os.path.join(out_dir, f"NotoSansSC-{name}.ttf")
    f.save(path)
    print(path, os.path.getsize(path))
