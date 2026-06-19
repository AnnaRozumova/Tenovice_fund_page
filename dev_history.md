# Development history

Chronological log of notable changes to this repository. Newest first. Each entry: what changed, why,
and how it was verified. Companion to `CLAUDE.md` (developer quick-start) and `docs/architecture.md`.

---

## 2026-06-19 — D1: i18n scaffolding (CZ default + EN) + language toggle

**Why:** the site is for Czech friends of the Tenovice sangha but the content was hard-coded in English.
D1 makes the public pages bilingual (CZ default, EN), with the structure ready for a third language (DE).

**What changed:**
- **New i18n core** `web/i18n.js` — one flat-key dictionary `TRANSLATIONS{cs,en}` (100 keys each),
  `t(key, {params})` with `{n}`-style interpolation and fallback (default lang → key), `applyTranslations()`
  (handles `data-i18n`, `data-i18n-html`, and `placeholder`/`alt`/`aria-label`/`title` attributes), a
  `localStorage`-persisted language toggle, `<html lang>` following the choice, and an `i18n:changed` event.
  Node-exportable so the parity checker can import it.
- **New parity checker** `tools/check-i18n-parity.js` — fails (non-zero) if any language's key set differs
  from the default language's. Run with `node tools/check-i18n-parity.js`.
- **Pages** (`index.html`, `pledge.html`, `success.html`) — a subtle `CS · EN` toggle in the **top-right of
  the first white card**, `data-i18n*` on every user-facing string, and the `i18n.js` script. The broken
  `</img>` markup in the home-page header (a known D4 item) was fixed here while restructuring it.
- **JS** (`main.js`, `pledge.js`) — all runtime-generated strings now go through `t()`; `pledge.js`
  re-renders its dynamic strings (form title/intro, preview status, mode note, existing-pledge type) on the
  `i18n:changed` event.
- **CSS** (`style.css`) — `.lang-toggle` / `.lang-btn` subtle text switch.
- **Wording** — Czech copy reviewed for the community-fundraising tone (informal "ty"; "příslib" for a
  pledge; "přínos" over "dopad").
- **`admin.html` stays English** — it is an internal tool, not part of the public bilingual site.
- **Bundled lint tidy** (per request): `domain/validation.py` now re-raises with `... from exc` in its
  `int()`/`Decimal()` guards (Codeac `raise-missing-from`); behaviour unchanged.

**What did NOT change:** calculator logic/layout (D2), goal-breakdown display (D3), the responsive pass
(D4 — the home page still has horizontal overflow at ~375px from the hero grid/banner), backend, admin copy.

**Verification:**
```
$ pwsh ./check.ps1                  → ruff clean, 66 passed
$ node tools/check-i18n-parity.js   → ✓ en: 100 keys, in parity with 'cs'
$ node --check web/{i18n,main,pledge}.js → ok
```
Browser (preview, desktop + mobile 375px): default load is Czech; the toggle switches the full UI CZ↔EN
(static via `data-i18n`, dynamic via `t()` + re-render), `<html lang>` updates, and the choice persists
across navigation. `/code-review` of the diff: no findings.

---

## 2026-06-19 — C2: protected `POST /config` + admin page

**Why:** C1 made the campaign numbers readable from a `CONFIG` row but nothing could write them. C2 adds
the admin write path so Anna can edit the balance / goal / breakdown without a code change — guarded by a
single shared secret (decision D6; Cognito would be overkill for one trusted editor).

**What changed:**
- **New write handler** `handlers/update_config.py` — authorizes via a bearer token compared to the
  `ADMIN_SECRET` env var with a **constant-time** compare (`hmac.compare_digest`); **fails closed** (no
  secret configured → every request 401). On success validates the body and `put_item`s the `CONFIG` row.
  The secret is never logged.
- **Validation** (`domain/validation.py`): `validate_config_input` + `BREAKDOWN_KEYS` (the canonical
  direction keys) + helper `_require_non_negative_int`. Rules: `current_balance` ≥ 0, `fundraising_goal`
  ≥ 1, `breakdown` must list exactly the 3 known keys, each with a non-negative whole-EUR amount.
- **Infra:** `UpdateConfigFn` (Python 3.11, **read-write** grant) + `POST /config` route. `ADMIN_SECRET`
  is injected from the deploy environment (`os.environ`), which the CI/CD pipeline (D13) sources from SSM /
  Secrets Manager — never committed; defaults to empty (fail closed). CORS already allowed `POST` + `*`
  headers, so the `Authorization` header needs no change.
- **Frontend:** `web/admin.html` + `web/admin.js` — an internal admin tool (plain English; public-site
  i18n is D1). Paste the secret, prefill from `GET /config`, edit, save via `POST /config`; a `401` shows
  "Wrong or missing secret".
- **Tests:** `tests/integration/test_update_config.py` (401 on missing/empty/wrong secret, fail-closed when
  unset, 200 writes the row, 400 on bad body/JSON) + config-validation cases in `tests/unit/test_validation.py`.

**What did NOT change:** no breakdown *display* by direction (= D3), no i18n, no change to the B3 pledge
caps, no pledge-endpoint changes.

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   66 passed   (was 51 → +15: 7 handler auth/write + 8 config-validation)
Quality gate PASSED
```
CDK Python compiles; `admin.js` passes `node --check`; `/admin.html` + `/admin.js` serve locally (200).
`grep` confirms `ADMIN_SECRET` is only ever read from the environment — no secret value in the repo.
`/code-review` of the diff: no findings. **Not deployed** — `POST`/`GET /config` go live in Phase F; until
then the admin page's prefill falls back to defaults and the save has no endpoint to reach.

**This completes Phase C** (C1 read · C2 admin write).

---

## 2026-06-19 — C1: CONFIG row + `GET /config`; frontend reads it

**Why:** the campaign numbers shown to visitors — current balance, the goal, and the 3-direction
breakdown — were hardcoded in `web/config.js` (and the balance/goal duplicated as static text in
`index.html`). Changing them meant a code edit + redeploy. C1 moves them behind an API so they become
editable data; the admin write path follows in C2.

**What changed:**
- **New read handler** `services/pledges_api/src/handlers/get_config.py` — mirrors `get_stats`: reads the
  `CONFIG` row (`pledgeID="CONFIG"`) and returns `current_balance` / `fundraising_goal` / `breakdown`.
  If the row (or a field) is absent it returns **documented defaults**, so the endpoint and the site work
  before the row is ever seeded. The breakdown stores **stable keys** (`new_gompa`, `sangha_house`,
  `basecamp_north`) + amounts — localized labels stay in the frontend i18n dict (D3), not the data layer.
  Balance/goal/breakdown amounts are **provisional** pending Anna's confirmation.
- **Infra:** `GetConfigFn` (Python 3.11, read-only DynamoDB grant) + `GET /config` route, wired the same
  guarded way as the other handlers (`LambdaHandlers.get_config` Optional → route added only when present).
- **Frontend:** `loadConfig()` in `web/config.js` fetches `/config` and overrides the now-fallback
  `CURRENT_BALANCE` / `FUNDRAISING_GOAL` / `BREAKDOWN`; on any failure the hardcoded defaults stand so the
  page still renders. `main.js` and `pledge.js` `await loadConfig()` before reading those numbers. The
  homepage balance **and** goal are now rendered from `CONFIG` (goal gained `id="fundraisingGoal"`), so
  changing the row visibly changes the page — not just the progress bar.
- **Test:** `tests/integration/test_get_config.py` (defaults when no row · stored row returned · amounts
  serialize as `int`).

**What did NOT change:** no admin/write path (`POST /config` + `admin.html` = C2), no breakdown *display*
by direction (= D3), no i18n, no change to the B3 validation caps (they move into `CONFIG` later).

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   51 passed   (was 48 → +3 from test_get_config)
Quality gate PASSED
```
CDK Python compiles (`py_compile`); JS passes `node --check`; site serves locally (`/`, `/pledge.html`
→ 200). `/code-review` of the diff: no findings. Not deployed — the live dev API still lacks `/config`,
so `loadConfig()` falls back to defaults locally (expected; real end-to-end is Phase F).

---

## 2026-06-19 — B3: validation hardening (input caps)

**Why:** before this, `amount` and `contributors_count` had only a lower bound (≥ 1) and `message` had no
length limit at all. A single fat-finger or abusive value (e.g. amount 5,000,000) would skew the public
`STATS` totals. Caps keep the running totals sane.

**What changed (`domain/validation.py`):**
- New constants `MAX_AMOUNT = 100000`, `MAX_CONTRIBUTORS_COUNT = 5`, `MAX_MESSAGE_LENGTH = 500`.
- `_require_positive_decimal` / `_require_positive_int` gained an optional `maximum`; `validate_pledge_input`
  passes the caps and rejects over-cap input with a clear message (`'amount' must not exceed 100,000`, etc.).
  `message` over 500 chars is rejected too. Min ≥ 1 unchanged.
- Caps are **provisional** — the contributors cap especially, pending a product decision on whether the
  "one pledge for several people" feature stays. They are plain constants now and move into the editable
  `CONFIG` row in Phase C. Enforced **server-side only**; mirroring them in the form is deferred to D2.

**What did NOT change:** no frontend, no infra. The form still has only `min="1"`, so an over-cap value
reaches the API and fails with the generic "Could not save pledge" until D2 adds the client-side mirror.

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   48 passed
Quality gate PASSED
```
Six new cap tests in `test_validation.py` (each cap: at-limit accepted, over-limit rejected). Also confirmed
by calling `validate_pledge_input` directly: 10 EUR / 1 contributor accepted; 200,000 / 6 / 600-char message
each rejected with the expected message.

**This completes Phase B** (B1 privacy · B2 stats+response util · B3 caps).

---

## 2026-06-19 — B2: canonicalize `contributors_count`; unify the response util

**Why:** the supporters headline always showed **0** — the backend stores/serves `contributors_count`
but the frontend read `pledgers_count` (a field that doesn't exist in the response). Separately, every
handler defined its own `DecimalEncoder`/`_response`, and `create_pledge` had none (bare `json.dumps`).

**What changed:**
- **Shared response util:** filled the empty `services/pledges_api/src/utils/response.py` with a single
  `response(status, body)` + `DecimalEncoder` (whole `Decimal` → `int`, else `float`; EUR/counts display as
  integers). All **four** handlers (`get_stats`, `list_pledges`, `get_pledge_by_email`, `create_pledge`) now
  import it; their local copies are gone. `create_pledge` now encodes Decimals correctly (it didn't before).
- **Frontend canonicalization:** `web/main.js` (supporters headline) and `web/pledge.js` (init
  `currentStats`, `loadStats`, both `calculatePreview` branches) now read `contributors_count`; no
  `pledgers_count` remains in the codebase.
- **Bug fixed in passing:** `list_pledges` had a local `response = table.scan()` that shadowed the new
  imported `response` function — `return response(...)` would have raised at runtime. Renamed to
  `scan_result`. (ruff caught it via the now-unused import.)
- **Test:** added `tests/unit/test_response.py` (Decimal int/float encoding, envelope shape).
- **Dev harness:** `serve.ps1` now sends `Cache-Control: no-store` so frontend edits show on a normal
  refresh (no hard-reload needed during local iteration).

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   42 passed
Quality gate PASSED
```
Confirmed in the running site: the supporters headline now shows the real count (19) instead of 0.

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

## Planned next (after Phase C)

**Phases B and C are complete.** B (B1 privacy · B2 stats + shared response util · B3 input caps) hardened
the data model early, while only test data exists. C (C1 read · C2 admin write) made the campaign numbers
editable data behind `GET`/`POST /config`. Test data in the live table will be reset when this deploys
(Phase F).

Next: CZ/EN i18n (D1), calculator UX (D2; the B3 caps' frontend mirror lands here), goal-breakdown display
+ dw-connect link (D3), responsive pass (D4), the post-pledge payment page (E1), then AWS deploy + seed the
real `CONFIG` (F) and custom domain (G).
