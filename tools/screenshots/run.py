"""Скриншоты для README на русском и английском → docs/screenshots/<язык>/.

    python tools/screenshots/run.py [ru en]

Нужны: snmpsim (как для тестов: tests/.snmpsim или SNMPSIM_BIN), Node.js и зависимости tests/browser
(npm install), Google Chrome. Порт 161 на 127.0.0.1 должен быть свободен.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run_all import find_snmpsim, find_node, free_port  # noqa: E402
import demo_network  # noqa: E402


def main(langs):
    tmp = tempfile.mkdtemp(prefix="switchmap-shots-")
    data = os.path.join(tmp, "snmprec")
    demo_network.main(data)
    sim_bin, node = find_snmpsim(), find_node()
    if not sim_bin or not node:
        sys.exit("Нужны snmpsim (tests/.snmpsim) и Node.js — см. tests/README.md")
    sim = subprocess.Popen([sim_bin, f"--data-dir={data}", "--agent-udpv4-endpoint=127.0.0.1:161",
                            f"--cache-dir={os.path.join(tmp, 'cache')}"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(8)
    try:
        for lang in langs:
            out = os.path.join(ROOT, "docs", "screenshots", lang)
            shutil.rmtree(out, ignore_errors=True)
            os.makedirs(out)
            port = free_port()
            env = dict(os.environ, SWITCHMAP_LANG=lang, SWITCHMAP_UPDATE_CHECK="0", PYTHONIOENCODING="utf-8")
            log = open(os.path.join(tmp, f"server-{lang}.log"), "w", encoding="utf-8")
            srv = subprocess.Popen([sys.executable, os.path.join(HERE, "demo_server.py"), os.path.join(tmp, f"work-{lang}"),
                                    str(port)], stdout=log, stderr=subprocess.STDOUT, env=env)
            try:
                for _ in range(120):
                    time.sleep(1)
                    if "READY" in open(log.name, encoding="utf-8", errors="replace").read():
                        break
                else:
                    sys.exit("демо-сервер не запустился: " + log.name)
                time.sleep(2)
                env_node = dict(os.environ, NODE_PATH=os.path.join(ROOT, "tests", "browser", "node_modules"))
                r = subprocess.run([node, os.path.join(HERE, "take.js"), f"http://127.0.0.1:{port}", out, lang],
                                   env=env_node, capture_output=True, text=True, encoding="utf-8")
                print(lang, (r.stdout + r.stderr).strip(), sorted(os.listdir(out)))
            finally:
                srv.terminate()
                srv.wait(10)
                log.close()
    finally:
        sim.terminate()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["en", "ru"])
