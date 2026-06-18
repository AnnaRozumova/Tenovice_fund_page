#!/usr/bin/env pwsh
# Serve the static site in web/ locally for UI iteration — no deploy, no build.
# One command, Windows-first.  Usage:  pwsh ./serve.ps1 [-Port 8000]
#
# Sends "Cache-Control: no-store" so edits to JS/CSS/HTML show on a normal
# refresh — no hard-reload needed while iterating on the frontend.
#
# The API base is a single config value: CONFIG.API_URL in web/config.js
# (defaults to the live dev API, so the calculator shows real data locally).
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"
$web = Join-Path $PSScriptRoot "web"

Write-Host "Serving $web" -ForegroundColor Green
Write-Host "  -> http://localhost:$Port   (Ctrl+C to stop)" -ForegroundColor Green
Write-Host "API base = CONFIG.API_URL in web/config.js  (responses sent no-cache)" -ForegroundColor DarkGray

$env:SERVE_PORT = $Port
$env:SERVE_DIR = $web

$server = @'
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
'@

py -3.11 -c $server
