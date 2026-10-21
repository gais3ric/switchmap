"""Точка входа собранной программы (PyInstaller): switchmap[.exe] [команда]."""
import sys

if __name__ == "__main__":
    # --version не трогает папку данных: работает и без прав администратора
    if sys.argv[1:2] in (["--version"], ["-V"]):
        import config
        print(config.version())
        sys.exit(0)
    import app
    sys.exit(app.main(sys.argv[1:]))
