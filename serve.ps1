#!/usr/bin/env pwsh
# Serve the static site in web/ locally for UI iteration — no deploy, no build.
# One command, Windows-first.  Usage:  pwsh ./serve.ps1 [-Port 8000]
#
# The API base is a single config value: CONFIG.API_URL in web/config.js
# (defaults to the live dev API, so the calculator shows real data locally).
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"
$web = Join-Path $PSScriptRoot "web"

Write-Host "Serving $web" -ForegroundColor Green
Write-Host "  -> http://localhost:$Port   (Ctrl+C to stop)" -ForegroundColor Green
Write-Host "API base = CONFIG.API_URL in web/config.js" -ForegroundColor DarkGray

py -3.11 -m http.server $Port --directory $web
