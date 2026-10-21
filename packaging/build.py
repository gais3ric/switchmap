"""Сборка SwitchMap: программа (PyInstaller) и установщики.

    python packaging/build.py                    только программа → dist/switchmap/
    python packaging/build.py --installer        + установщик: Windows — .exe (Inno Setup), Linux — .deb и .rpm (nfpm)
    python packaging/build.py --version 1.2.0    версия (по умолчанию — из git-метки vX.Y.Z или 0.0.0)

Запускать Python-ом, в котором стоят requirements.txt и pyinstaller (см. packaging/README.md).
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "packaging")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
WINDOWS = os.name == "nt"

# Обёртка службы Windows (https://github.com/winsw/winsw, MIT) — точная версия и контрольная сумма
WINSW_URL = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"
# SHA-256 официального файла релиза v2.12.0 (18 243 033 байт; авторы его не подписывают)
WINSW_SHA256 = "05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da"


def run(cmd, **kw):
    print("+", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def detect_version(explicit):
    v = explicit or os.environ.get("SWITCHMAP_VERSION")
    if not v:
        try:
            v = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            v = "0.0.0"
    v = v.lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        sys.exit(f"Версия должна быть вида 1.2.3 (метка v1.2.3), получено: {v!r}")
    return v


def build_program(version):
    os.makedirs(BUILD, exist_ok=True)
    version_file = os.path.join(BUILD, "VERSION")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(version)
    sep = ";" if WINDOWS else ":"
    data = [(os.path.join(ROOT, "templates"), "templates"), (os.path.join(ROOT, "static"), "static"),
            (os.path.join(ROOT, "help"), "help"), (version_file, ".")]
    # переводы — только каталоги, без инструмента разработчика
    data += [(os.path.join(ROOT, "locales", n), "locales") for n in os.listdir(os.path.join(ROOT, "locales"))
             if n.endswith(".json")]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
           "--name", "switchmap", "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyinstaller"),
           "--specpath", BUILD, "--paths", ROOT,
           # pysnmp загружает MIB-модули по путям, APScheduler ищет триггеры через метаданные пакета
           "--collect-all", "pysnmp", "--collect-submodules", "apscheduler", "--copy-metadata", "apscheduler",
           "--exclude-module", "tkinter"]
    for src, dst in data:
        cmd += ["--add-data", f"{src}{sep}{dst}"]
    if WINDOWS:
        cmd += ["--icon", os.path.join(PKG, "windows", "switchmap.ico")]
    cmd.append(os.path.join(PKG, "entry.py"))
    run(cmd, cwd=ROOT)
    out = os.path.join(DIST, "switchmap")
    exe = os.path.join(out, "switchmap.exe" if WINDOWS else "switchmap")
    r = subprocess.run([exe, "--version"], capture_output=True, text=True)
    if r.stdout.strip() != version:
        sys.exit(f"Собранная программа сообщает версию {r.stdout.strip()!r} вместо {version}: {r.stderr}")
    shutil.copyfile(os.path.join(ROOT, "LICENSE"), os.path.join(out, "LICENSE.txt"))
    print(f"Программа: {out} (версия {version})")
    return out


def fetch_winsw():
    path = os.path.join(BUILD, "WinSW-x64-2.12.0.exe")
    if not os.path.isfile(path):
        os.makedirs(BUILD, exist_ok=True)
        print("Скачивание", WINSW_URL)
        with urllib.request.urlopen(WINSW_URL, timeout=60) as resp, open(path + ".part", "wb") as f:
            shutil.copyfileobj(resp, f)
        os.replace(path + ".part", path)
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != WINSW_SHA256:
        os.remove(path)
        sys.exit(f"Контрольная сумма WinSW не совпала: {digest}")
    return path


def find_iscc():
    candidates = [shutil.which("iscc"), os.environ.get("ISCC"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
                  r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe"]
    found = next((c for c in candidates if c and os.path.isfile(c)), None)
    if not found:
        sys.exit("Inno Setup не найден: winget install JRSoftware.InnoSetup (или переменная ISCC)")
    return found


def windows_installer(program, version):
    shutil.copy(fetch_winsw(), os.path.join(program, "switchmap-service.exe"))
    shutil.copy(os.path.join(PKG, "windows", "switchmap-service.xml"), program)
    shutil.copy(os.path.join(PKG, "switchmap.conf.example"), program)
    run([find_iscc(), f"/DAppVersion={version}", f"/DSourceDir={program}", f"/DOutputDir={DIST}",
         os.path.join(PKG, "windows", "switchmap.iss")])
    out = os.path.join(DIST, f"SwitchMap-Setup-{version}.exe")
    print("Установщик:", out)
    return [out]


def linux_packages(program, version):
    nfpm = os.environ.get("NFPM") or shutil.which("nfpm") or sys.exit("nfpm не найден: https://nfpm.goreleaser.com/install/")
    # nfpm подставляет переменные окружения не во все поля (в пути к файлам — нет), поэтому подставляем сами
    with open(os.path.join(PKG, "linux", "nfpm.yaml"), encoding="utf-8") as f:
        text = f.read().replace("${SWITCHMAP_VERSION}", version).replace("${SWITCHMAP_PROGRAM}", program.replace("\\", "/"))
    conf = os.path.join(BUILD, "nfpm.yaml")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(text)
    outs = []
    for packager in ("deb", "rpm"):
        run([nfpm, "package", "--config", conf, "--packager", packager, "--target", DIST], cwd=ROOT)
    for name in os.listdir(DIST):
        if name.endswith((".deb", ".rpm")) and version.replace("-", "~") in name:
            outs.append(os.path.join(DIST, name))
    print("Пакеты:", *outs, sep="\n  ")
    return outs


def main():
    ap = argparse.ArgumentParser(description="Сборка SwitchMap")
    ap.add_argument("--version")
    ap.add_argument("--installer", action="store_true", help="собрать установщик для этой системы")
    a = ap.parse_args()
    version = detect_version(a.version)
    program = build_program(version)
    if a.installer:
        (windows_installer if WINDOWS else linux_packages)(program, version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
