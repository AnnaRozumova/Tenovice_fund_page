# Development history

Chronological log of notable changes to this repository. Newest first. Each entry: what changed, why,
and how it was verified. Companion to `CLAUDE.md` (developer quick-start) and `docs/architecture.md`.

---

## 2026-06-19 — B1: drop `name`; harden the email-based edit flow (no hashing)

**Why:** privacy. Names are never needed (contact happens off-site) and never displayed, so the safest
place for a name is "not in the database." Done now, while only test data exists. Email stays as-is (no
hashing — decision D3) purely to recognize a returning pledger.

**What changed:**
- **`name` dropped everywhere:** `domain/models.py` (`Pledge` field + both DynamoDB converters),
  `domain/validation.py` (no longer required/accepted — silently ignored), `handlers/create_pledge.py`
  (create + update; the `ExpressionAttributeNames` `#name` escape went away with it), and the frontend
  (`web/pledge.html` form field + existing-pledge summary row; `web/pledge.js` form values, validation,
  payload, populate). Fixtures `one_time.json` / `monthly_update.json` wiped.
- **`/pledges/by-email` hardened:** instead of returning the raw DynamoDB item, it now projects an explicit
  **field allowlist** (`email`, `contributors_count`, `amount`, `is_monthly`, `campaign_total`, `message`,
  `end_month`, `end_year`) — internal fields like `pledgeID`/`created_at`/`updated_at` never leave the API.
  The lookup also matches email **case-insensitively** (`.strip().lower()`), so a returning user finds their
  pledge regardless of typed casing (creates store lowercased).
- **Tests:** the three parked stale suites (`test_validation.py`, `test_models.py`,
  `test_create_pledge.py`) were rewritten to the new no-`name` contract and **un-skipped**; added
  `test_get_pledge_by_email.py` (allowlist projection, case-insensitive match, 404/400). E2E
  `tests/e2e/test_api_pledges.py` rewritten against the real 4-endpoint contract (the old version targeted
  non-existent `GET`/`PUT /pledges/{id}` routes and `pledgers_count`).

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   37 passed   (0 skipped — all suites un-parked)
Quality gate PASSED
```
`/code-review` of the diff: no findings. `grep` confirms no `name` field in source, frontend, or tests
(only HTML `name="…"` form attributes remain).

**Deferred to later B steps:** the frontend still reads `pledgers_count` (B2) and there are no upper bounds
on `amount`/`contributors_count` yet (B3). A client-side email-format check is parked → D2.

---

## 2026-06-19 — A3: frontend dev harness (run the site locally)

**What changed:**
- `serve.ps1` (new) — one-command local static server (`py -3.11 -m http.server` over `web/`, default
  port 8000, `-Port` to change). Windows-first; mirrors the `python -m http.server` fallback.
- `web/README.md` — "Testing Locally" now leads with `pwsh ./serve.ps1` and documents `CONFIG.API_URL`
  as the single API-base knob.

**Verification:** served locally — `GET /`, `/pledge.html`, `/config.js` → HTTP 200; page title
"Tenovice Fundraising". API base confirmed single-sourced (`CONFIG.API_URL`, used by `main.js`/`pledge.js`).
No app/behavior change (only `serve.ps1` + `web/README.md`).

This completes **Phase A** (A1 docs · A2 quality gate · A3 dev harness), pushed as the single branch
`A-takeover-and-truth`.

---

## 2026-06-18 — A2: local quality gate (ruff + pytest on Python 3.11)

**What changed:**
- `check.ps1` — Windows-first one-command gate: creates a Python 3.11 venv, installs deps, runs ruff +
  pytest, exits non-zero on failure. `make check` target added for CI/Unix parity.
- `services/pledges_api/requirements-dev.txt` (test deps + ruff); minimal `[tool.ruff]` (target py311) in
  the previously-empty `services/pledges_api/pyproject.toml`.
- `tests/conftest.py` now sets `AWS_DEFAULT_REGION` + dummy creds at import (fixes `NoRegionError`).
- `tests/unit/test_pledge_math.py` (new) covers the locked pledge math (decision D8) — durable across the
  upcoming Phase B rework.

**Stale test suite parked (not rewritten here):** the existing `test_validation.py`, `test_models.py`, and
`test_create_pledge.py` (26 tests) assume an older contract (tuple-returning validation, `name` length,
`pledgers_count`, no `contributors_count`). They are **skipped with an explicit reason** pointing at the
privacy/data-model phase that rewrites them (drop `name`, fix the stats field, add caps).

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   3 passed, 26 skipped
Quality gate PASSED   (exit 0)
```
No application/behavior code changed (only the empty `pyproject.toml` gained ruff config).

---

## 2026-06-18 — A1: takeover audit + corrected docs

**Context.** Project handover. The code was the source of truth; `CLAUDE.md` had drifted from it.

**What changed (docs only — no code/behavior change):**
- Rewrote `CLAUDE.md` to match the real codebase.
- Added `docs/architecture.md` (architecture reference: components, endpoint→handler map, data model,
  pledge math, privacy model, planned direction).
- Added this `dev_history.md`.

**Audit findings reconciled against the code:**
- **4 endpoints**, not 3: `GET /stats`, `GET /pledges`, `POST /pledges`, `GET /pledges/by-email`.
- Pledge model is richer than the old docs claimed: adds `contributors_count`, `campaign_total`,
  `end_month`/`end_year`.
- The `STATS` row uses **`contributors_count`**; the frontend reads `pledgers_count` → supporters
  headline shows 0 (a real bug, fix planned).
- `services/pledges_api/src/utils/response.py` is **empty** — no shared util; `get_stats`,
  `list_pledges`, `get_pledge_by_email` each define their own `DecimalEncoder`/`_response`, and
  `create_pledge` has none.
- `get_pledge_by_email` returns the **full record incl. `name`+`email`** (PII leak).
- No upper bound on `amount` / `contributors_count`.
- `web/config.js` hardcodes `CURRENT_BALANCE` and `FUNDRAISING_GOAL`.

**Verification:**
```
$ curl -s -w "\nHTTP %{http_code}\n" https://tbaulwfk46.execute-api.eu-central-1.amazonaws.com/stats
{"pledged_total": 228150.0, "contributors_count": 19.0, "monthly_total": 12200.0}
HTTP 200
```
The dev API is **deployed and live** with test data — confirms the `contributors_count` field name and
the `pledgers_count` mismatch.

---

## Planned next (privacy & data-model hardening — Phase B remaining)

The data model changes early, while only test data exists (cheap now, painful once real friends pledge).
Test data in the live table will be reset when this phase deploys.

1. ~~**Drop `name`**~~ — done (B1).
2. ~~**Harden `/pledges/by-email`**~~ — done (B1).
3. ~~Keep `email` as-is (no hashing)~~ — confirmed/kept (B1).
4. **Canonicalize stats on `contributors_count`** (remove frontend `pledgers_count` reads). *(B2)*
5. Add **one shared `response()`/`DecimalEncoder` util** for all handlers. *(B2)*
6. Add **upper bounds** on `amount` and `contributors_count`. *(B3)*

Followed by: a one-command local quality gate (ruff + pytest/moto), editable numbers via a `CONFIG` row +
admin endpoint, CZ/EN i18n, calculator UX, the post-pledge payment page, then AWS deploy + custom domain.
