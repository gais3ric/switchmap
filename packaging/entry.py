"""Точка входа собранной программы (PyInstaller): switchmap[.exe] [команда]."""
import sys

import app

if __name__ == "__main__":
    sys.exit(app.main(sys.argv[1:]))
