#!/usr/bin/env bash
# Local quality gate for services/pledges_api: ruff + pytest on Python 3.14 (the
# Lambda runtime). One command, no AWS.  Usage:  bash ./check.sh
#
# POSIX/Linux canonical form (CI + Anna/Ondra run Linux). The Windows-local
# equivalent is ./check.ps1; both share the same .venv and dependencies.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
svc="$repo/services/pledges_api"
venv="$repo/.venv"

# Locate an executable inside the venv, tolerating Linux (bin/) vs Windows
# (Scripts/, .exe) layouts so the same .venv works whichever script created it.
venv_bin() {
  for d in bin Scripts; do
    for ext in "" ".exe"; do
      [ -f "$venv/$d/$1$ext" ] && { echo "$venv/$d/$1$ext"; return 0; }
    done
  done
  return 1
}

# 1. Ensure a Python 3.14 venv (pin to the Lambda runtime, not the machine default).
if ! py="$(venv_bin python)"; then
  echo "Creating .venv with Python 3.14..."
  python3.14 -m venv "$venv"
  py="$(venv_bin python)"
fi

# 2. Install / refresh the gate dependencies.
"$py" -m pip install -q --upgrade pip
"$py" -m pip install -q -r "$svc/requirements-dev.txt"

echo "Using $("$py" --version)"
ruff="$(venv_bin ruff)"

# 3. Lint.  (set -e aborts with a non-zero exit if ruff finds problems.)
echo "== ruff =="
"$ruff" check "$svc/src" "$svc/tests"

# 4. Tests (-rs lists skipped tests with their reason).
echo "== pytest =="
( cd "$svc" && "$py" -m pytest tests/ -q -rs )

echo "Quality gate PASSED"
