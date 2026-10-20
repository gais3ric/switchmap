"""Поддельный NetBox REST API для тестов импорта."""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKENS = {"Token 0123456789abcdef", "Bearer nbt_abc.secretpart"}


def _dev(i, name, ip=None, site=("HQ", "hq"), role=("Access switch", "access"), model=("Cisco", "C9300-48P"),
         status="active", interfaces=56, tags=()):
    return {"id": i, "name": name, "display": name,
            "primary_ip4": {"address": f"{ip}/24"} if ip else None, "primary_ip": {"address": f"{ip}/24"} if ip else None,
            "site": {"name": site[0], "slug": site[1]}, "role": {"name": role[0], "slug": role[1]},
            "device_type": {"model": model[1], "manufacturer": {"name": model[0]}},
            "status": {"value": status, "label": status.capitalize()}, "interface_count": interfaces,
            "tags": [{"slug": t} for t in tags]}


class NB:
    devices = []
    physical = {}
    html_mode = False

    @classmethod
    def reset(cls):
        cls.devices = [
            _dev(1, "core-sw1", "10.1.0.1", tags=("monitor",)),
            _dev(2, "floor2-sw", "10.0.0.1", model=("HPE", "Aruba 2930F-24G"), interfaces=28),
            _dev(3, "СКЛАД", None, site=("Warehouse", "wh"), model=("D-Link", "DGS-1210-28")),
            _dev(4, "old-sw", "10.1.0.9", status="planned"),
            _dev(5, "branch-sw", None, site=("Branch", "branch")),
        ] + [_dev(100 + i, f"ap-{i}", f"10.9.{i // 200}.{i % 200 + 1}", role=("Access point", "ap"),
                  model=("Ubiquiti", "U6-Pro"), interfaces=1) for i in range(260)]
        cls.physical = {1: 52, 2: 28, 3: 28, 5: 10}
        cls.html_mode = False


NB.reset()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, data, ctype="application/json"):
        body = (json.dumps(data) if ctype == "application/json" else data).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def page(self, items, q):
        limit = int(q.get("limit", ["50"])[0]); offset = int(q.get("offset", ["0"])[0])
        return {"count": len(items), "next": None, "previous": None, "results": items[offset:offset + limit]}

    def do_GET(self):
        if NB.html_mode:
            return self.reply(200, "<html>login</html>", "text/html")
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if self.headers.get("Authorization") not in TOKENS:
            return self.reply(403, {"detail": "Invalid token"})
        path = u.path
        if path == "/api/status/":
            return self.reply(200, {"netbox-version": "4.2.3", "django-version": "5.1"})
        if path == "/api/dcim/devices/":
            items = NB.devices
            if "id" in q:
                ids = {int(x) for x in q["id"]}
                items = [d for d in items if d["id"] in ids]
            if "site" in q:
                items = [d for d in items if d["site"]["slug"] == q["site"][0]]
            if "role" in q:
                items = [d for d in items if d["role"]["slug"] == q["role"][0]]
            if "tag" in q:
                items = [d for d in items if q["tag"][0] in [t["slug"] for t in d["tags"]]]
            if "status" in q:
                items = [d for d in items if d["status"]["value"] == q["status"][0]]
            return self.reply(200, self.page(items, q))
        if path == "/api/dcim/interfaces/":
            dev = int(q["device_id"][0])
            assert q.get("kind") == ["physical"]
            n = NB.physical.get(dev, 0)
            return self.reply(200, {"count": n, "results": []})
        if path == "/api/dcim/sites/":
            return self.reply(200, self.page([{"slug": s, "name": n} for n, s in
                                              (("HQ", "hq"), ("Warehouse", "wh"), ("Branch", "branch"))], q))
        if path == "/api/dcim/device-roles/":
            return self.reply(200, self.page([{"slug": "access", "name": "Access switch"}, {"slug": "ap", "name": "Access point"}], q))
        if path == "/api/extras/tags/":
            return self.reply(200, self.page([{"slug": "monitor", "name": "Monitor"}], q))
        return self.reply(404, {"detail": "Not found."})


def start():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
