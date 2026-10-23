"""Проверка доступности по ping: ответ «узел недоступен» не должен считаться «онлайн».
argv: <рабочая папка с тестовой базой>"""
import os, subprocess, sys, types
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка проекта
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(sys.argv[1]); sys.path[:0] = [ROOT]

fails = []
def check(name, cond, info=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {info}" if info != "" else ""))
    if not cond:
        fails.append(name)

import platform
import app as m

# Вывод Windows ping (русский — в кодировке консоли cp866)
EN_OK = b"""
Pinging 192.168.1.10 with 32 bytes of data:
Reply from 192.168.1.10: bytes=32 time<1ms TTL=255

Ping statistics for 192.168.1.10:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 0ms, Maximum = 0ms, Average = 0ms
"""
EN_UNREACH = b"""
Pinging 192.168.1.10 with 32 bytes of data:
Reply from 192.168.1.5: Destination host unreachable.

Ping statistics for 192.168.1.10:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
"""
RU_OK = """
Обмен пакетами с 192.168.1.10 по с 32 байтами данных:
Ответ от 192.168.1.10: число байт=32 время=2мс TTL=255

Статистика Ping для 192.168.1.10:
    Пакетов: отправлено = 1, получено = 1, потеряно = 0
    (0% потерь)
Приблизительное время приема-передачи в мс:
    Минимальное = 2мсек, Максимальное = 2 мсек, Среднее = 2 мсек
""".encode("cp866")
RU_UNREACH = """
Обмен пакетами с 192.168.1.10 по с 32 байтами данных:
Ответ от 192.168.1.5: Заданный узел недоступен.

Статистика Ping для 192.168.1.10:
    Пакетов: отправлено = 1, получено = 1, потеряно = 0
    (0% потерь)
""".encode("cp866")
V6_OK = b"Pinging fe80::1 with 32 bytes of data:\r\nReply from fe80::1: time=3ms\r\n"
TTL_EXPIRED = b"Reply from 10.0.0.1: TTL expired in transit.\r\n\r\nPackets: Sent = 1, Received = 1, Lost = 0 (0% loss),\r\n"

for name, out, want in [("EN ответ", EN_OK, True), ("EN узел недоступен", EN_UNREACH, False),
                        ("RU ответ", RU_OK, True), ("RU узел недоступен", RU_UNREACH, False),
                        ("IPv6 ответ", V6_OK, True), ("TTL expired", TTL_EXPIRED, False), ("пусто", b"", False)]:
    check(f"разбор вывода: {name}", m.ping_output_has_reply(out) is want)

# ping_host целиком: код 0 + «узел недоступен» на Windows — недоступен
real_run, real_system = subprocess.run, platform.system
def fake(code, out, system):
    subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=code, stdout=out)
    platform.system = lambda: system
try:
    fake(0, RU_UNREACH, "Windows"); check("Windows: код 0, но узел недоступен -> офлайн", m.ping_host("192.168.1.10") is False)
    fake(0, EN_OK, "Windows"); check("Windows: настоящий ответ -> онлайн", m.ping_host("192.168.1.10") is True)
    fake(1, b"Request timed out.", "Windows"); check("Windows: таймаут -> офлайн", m.ping_host("192.168.1.10") is False)
    fake(0, b"", "Linux"); check("Linux: код 0 -> онлайн", m.ping_host("192.168.1.10") is True)
    fake(1, b"", "Linux"); check("Linux: код 1 -> офлайн", m.ping_host("192.168.1.10") is False)
finally:
    subprocess.run, platform.system = real_run, real_system

print(f"\nИТОГО: {'провалено ' + str(len(fails)) if fails else 'все проверки пройдены'}")
sys.exit(1 if fails else 0)
