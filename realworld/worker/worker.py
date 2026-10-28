#!/usr/bin/env python3
"""Small CPU-bound HTTP worker representing one VM."""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VM_NAME = os.getenv("VM_NAME", "vm")
VM_TYPE = os.getenv("VM_TYPE", "V1")
PORT = int(os.getenv("PORT", "8000"))


def burn(iterations):
    value = 1
    for _ in range(max(1, iterations)):
        value = (value * 1103515245 + 12345) & 0x7FFFFFFF
    if value == -1:
        raise RuntimeError("unreachable")


class Handler(BaseHTTPRequestHandler):
    def reply(self, body, status=200):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/health":
            self.reply({"status": "ok", "vm": VM_NAME, "vm_type": VM_TYPE})
        else:
            self.reply({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/batch":
            self.reply({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for task in payload.get("tasks", []):
            started = time.monotonic()
            burn(int(task["iterations"]))
            self.wfile.write((json.dumps({
                "id": task["id"], "duration": time.monotonic() - started
            }) + "\n").encode())
            self.wfile.flush()

    def log_message(self, *_args):
        return


ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
