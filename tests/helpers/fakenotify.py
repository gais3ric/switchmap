"""Поддельные Telegram Bot API и SMTP-сервер для тестов уведомлений."""
import base64
import datetime
import email
import email.policy
import ipaddress
import json
import os
import socketserver
import ssl
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "123456:TESTTOKEN"


# ───────────── Telegram ─────────────
class TG:
    sent = []            # [{chat_id, text, parse_mode}]
    fail = False         # True — отвечать 502
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 111, "type": "private", "first_name": "Иван", "username": "ivan"}}},
        {"update_id": 2, "my_chat_member": {"chat": {"id": -1009, "type": "supergroup", "title": "Сетевики"}}},
        {"update_id": 3, "message": {"chat": {"id": 111, "type": "private", "first_name": "Иван", "username": "ivan"}}},
    ]
    migrate = {"-500": -1005000}   # старая группа → супергруппа
    missing = {"-404"}


class TGHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, payload):
        if TG.fail:
            self.send_response(502); self.end_headers(); return
        parts = self.path.split("?")[0].strip("/").split("/")
        token, method = parts[0][3:], parts[1]
        if token != TOKEN:
            return self._reply(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
        if method == "getMe":
            return self._reply(200, {"ok": True, "result": {"id": 1, "is_bot": True, "first_name": "Map", "username": "switchmap_test_bot"}})
        if method == "getUpdates":
            return self._reply(200, {"ok": True, "result": TG.updates})
        if method == "sendMessage":
            cid = str(payload.get("chat_id"))
            if cid in TG.migrate:
                return self._reply(400, {"ok": False, "error_code": 400,
                                         "description": "Bad Request: group chat was upgraded to a supergroup chat",
                                         "parameters": {"migrate_to_chat_id": TG.migrate[cid]}})
            if cid in TG.missing:
                return self._reply(400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"})
            TG.sent.append(payload)
            return self._reply(200, {"ok": True, "result": {"message_id": len(TG.sent)}})
        return self._reply(404, {"ok": False, "error_code": 404, "description": "Not Found"})

    def do_GET(self):
        self._handle({})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._handle(json.loads(self.rfile.read(n) or b"{}"))


def start_telegram():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), TGHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# ───────────── SMTP ─────────────
class Mailbox:
    messages = []   # [{from, to, msg}]


def make_cert():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                                                        x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .sign(key, hashes.SHA256()))
    d = tempfile.mkdtemp()
    cp, kp = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
    with open(cp, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(kp, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cp, kp)
    return ctx


def smtp_handler(mode, user, password, ctx):
    class H(socketserver.StreamRequestHandler):
        def send(self, line):
            self.wfile.write((line + "\r\n").encode())
            self.wfile.flush()

        def readline(self):
            return self.rfile.readline().decode(errors="replace").rstrip("\r\n")

        def handle(self):
            if mode == "ssl":
                self.connection = ctx.wrap_socket(self.request, server_side=True)
                self.rfile = self.connection.makefile("rb")
                self.wfile = self.connection.makefile("wb")
            tls = mode == "ssl"
            authed = not user
            mail_from, rcpts = None, []
            self.send("220 fake ESMTP")
            while True:
                line = self.readline()
                if not line:
                    return
                cmd = line.split(" ")[0].upper()
                if cmd in ("EHLO", "HELO"):
                    ext = ["250-fake"]
                    if mode == "starttls" and not tls:
                        ext.append("250-STARTTLS")
                    if user and (tls or mode == "none"):
                        ext.append("250-AUTH PLAIN LOGIN")
                    ext.append("250 8BITMIME")
                    for e in ext:
                        self.send(e)
                elif cmd == "STARTTLS":
                    self.send("220 go")
                    self.connection = ctx.wrap_socket(self.request, server_side=True)
                    self.rfile = self.connection.makefile("rb")
                    self.wfile = self.connection.makefile("wb")
                    tls = True
                elif cmd == "AUTH":
                    parts = line.split(" ")
                    if parts[1].upper() == "PLAIN":
                        raw = parts[2] if len(parts) > 2 else (self.send("334 ") or self.readline())
                        _, u, p = base64.b64decode(raw).decode().split("\0")
                    else:
                        if len(parts) > 2:
                            u = base64.b64decode(parts[2]).decode()
                        else:
                            self.send("334 VXNlcm5hbWU6"); u = base64.b64decode(self.readline()).decode()
                        self.send("334 UGFzc3dvcmQ6"); p = base64.b64decode(self.readline()).decode()
                    if (u, p) == (user, password):
                        authed = True
                        self.send("235 ok")
                    else:
                        self.send("535 5.7.8 Authentication failed")
                elif cmd == "MAIL":
                    if not authed:
                        self.send("530 auth required"); continue
                    mail_from = line[10:].split(">")[0].strip("<")
                    rcpts = []
                    self.send("250 ok")
                elif cmd == "RCPT":
                    addr = line[8:].split(">")[0].strip("<")
                    if addr.endswith("@bad.test"):
                        self.send("550 no such user"); continue
                    rcpts.append(addr)
                    self.send("250 ok")
                elif cmd == "DATA":
                    self.send("354 end with .")
                    lines = []
                    while True:
                        l = self.rfile.readline()
                        if l in (b".\r\n", b".\n", b""):
                            break
                        lines.append(l[1:] if l.startswith(b"..") else l)
                    msg = email.message_from_bytes(b"".join(lines), policy=email.policy.default)
                    Mailbox.messages.append({"from": mail_from, "to": rcpts, "msg": msg})
                    self.send("250 queued")
                elif cmd == "RSET" or cmd == "NOOP":
                    self.send("250 ok")
                elif cmd == "QUIT":
                    self.send("221 bye"); return
                else:
                    self.send("502 unknown")
    return H


def start_smtp(mode="none", user="", password="", ctx=None):
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), smtp_handler(mode, user, password, ctx))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]
