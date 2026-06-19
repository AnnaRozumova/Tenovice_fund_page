#!/usr/bin/env bash
# Serve the static site in web/ locally for UI iteration — no deploy, no build.
# One command.  Usage:  bash ./serve.sh [PORT]   (default 8000)
#
# POSIX/Linux canonical form; the Windows-local equivalent is ./serve.ps1.
# Sends "Cache-Control: no-store" so edits to JS/CSS/HTML show on a normal
# refresh. The API base is a single config value: CONFIG.API_URL in web/config.js.
set -euo pipefail

port="${1:-8000}"
web="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/web"

# Prefer python3.11 (the Lambda runtime) but fall back to any python3 / python.
py="$(command -v python3.11 || command -v python3 || command -v python)"

echo "Serving $web"
echo "  -> http://localhost:$port   (Ctrl+C to stop)"
echo "API base = CONFIG.API_URL in web/config.js  (responses sent no-cache)"

SERVE_PORT="$port" SERVE_DIR="$web" "$py" - <<'PY'
import functools
import http.server
import os
import socketserver

port = int(os.environ["SERVE_PORT"])
directory = os.environ["SERVE_DIR"]


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Expires", "0")
        super().end_headers()


socketserver.TCPServer.allow_reuse_address = True
handler = functools.partial(NoCacheHandler, directory=directory)
with socketserver.TCPServer(("", port), handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
PY
