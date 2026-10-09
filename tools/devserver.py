#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local preview server: serves site/ and reverse-proxies /api/ to EasyUpdate,
exactly mirroring what the nginx container does in production."""
import functools
import http.server
import os
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config                                                     # noqa: E402

SITE = os.path.normpath(os.path.join(HERE, "..", "site"))
UPSTREAM = config.get("EU_BASE").rstrip("/")
PORT = config.get_int("DEV_PORT")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _proxy(self):
        url = UPSTREAM + self.path
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read()
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() in ("transfer-encoding", "connection",
                                     "content-length", "content-encoding"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type",
                             e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:                                # noqa: BLE001
            self.send_error(502, "proxy error: %s" % e)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_GET()

    def do_HEAD(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            super().do_HEAD()


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    srv = Server(("127.0.0.1", PORT), Handler)
    print("serving %s on http://127.0.0.1:%d/  (api -> %s)" % (SITE, PORT, UPSTREAM))
    srv.serve_forever()
