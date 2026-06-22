# Development history

Chronological log of notable changes to this repository. Newest first. Each entry: what changed, why,
and how it was verified. Companion to `CLAUDE.md` (developer quick-start) and `docs/architecture.md`.

---

## 2026-06-22 — D4: responsive pass (phone + desktop)

**Why:** make the whole flow mobile-first and verified at phone + desktop widths (decision D10). Frontend-only
— no Python/CDK change; CSS + one markup move.

**What changed (all under `web/`):**
- **`style.css`** —
  - **Sticky status bar (`.calc-topbar`) → `static` at ≤768 px.** On phone/tablet it wraps to several rows
    (~140 px); as `sticky` it permanently covered a large slice of the viewport during the (long) calculator
    flow. It stays `sticky` on desktop, where it fits in one compact row (~85 px). Small-phone (≤560 px)
    tightening of its padding / value font.
  - **Tap targets.** `.checkbox-label` row gets `min-height: 44px`.
  - **Language toggle restyled (Martin's review):** smaller and tighter (`font-size: 0.75rem`,
    `padding: 4px 5px`, `gap: 3px`) so it stays subtle.
  - **Hero intro justified:** `.description` → `text-align: justify` + `hyphens: auto` (with `-webkit-hyphens`
    for Safari) for a cleaner block on the home page.
  - **`.sim-card`** gets `position: relative` + extra top padding so its centered heading clears the new
    corner toggle (see below).
- **`pledge.html`** — the calc-flow **language toggle moved out of the sticky status bar into the top-right
  corner of the `.sim-card`** ("Spočítej svůj přínos"), where it reads better than floating in the status bar.

**What did NOT change:** no backend/CDK/JS logic; no i18n keys added (the moved toggle reuses the existing
`common.langLabel`). The earlier "known 375 px hero overflow" was already resolved by the D2/D3 rework, and the
stray `</img>` was already fixed in D1 — both re-verified, nothing to change.

**Verification:** gate green (`ruff` clean, **77 passed**), i18n parity holds (114=114). Measured in-browser via
`getBoundingClientRect` overflow scans + computed styles (the screenshot tool was unavailable in this
environment): **no horizontal overflow** at 320 / 375 / 700 / 1280 px on home, lookup, existing-pledge, calc
flow, and success; corner toggle clears the centered sim heading at 320/375/desktop; the relocated toggle still
switches CZ↔EN.

---

## 2026-06-22 — D3: discreet dw-connect link (one Tenovice — no 3-direction breakdown)

**Why:** the project is **one** direction ("ONE Tenovice"), not three (Ondra). So we do **not** present a
"3 main directions" breakdown; dw-connect already has the full story, so a single discreet link suffices.
(An earlier take on D3 that rendered a 3-card breakdown with cover photos was dropped before merge.)
Frontend-only — no Python/CDK change.

**What changed (all under `web/`):**
- **`index.html`** — a discreet dw-connect link under the hero intro text (a `text-link` + a small note that
  it needs a logged-in dw-connect membership). No breakdown section.
- **`i18n.js`** — 2 keys per language: `index.dwConnectLink` + `index.dwConnectNote` (CZ+EN). Parity held.
- **`style.css`** — small `.hero-dwlink` / `.hero-dwlink-note` styling.

**What did NOT change:** no backend/CDK; `CONFIG.BREAKDOWN` stays as the `/config` fallback (from C1) but is
not rendered — `main.js` no longer reads it.

**Verification:** gate green (`ruff` clean, **77 passed**), i18n parity holds, `node --check` on the JS.
Link points to the members-only `https://dw-connect.org/projects/tenovice-project`, opens in a new tab
(`target=_blank`, `rel="noopener noreferrer"`), CZ↔EN re-translates, no layout regression at desktop/375 px.

---

## 2026-06-19 — D2: calculator + preview (display-only) and a separate pledge-save flow

**Why:** wire the locked three-zone page design to the backend. The "what-if" calculator must get its
numbers from `POST /calculate` (D2a) and only *display* them — the JS copy of the pledge math is removed so
there is a single source of truth (decision D8/D15). The calculator (a stateless simulator) is separated
from saving a pledge (one person's own commitment). Frontend-only — no Python/CDK change.

**What changed (all under `web/`):**
- **`pledge.html`** — rebuilt the post-lookup page into three zones: a sticky campaign-status bar (real money
  vs goal, from `/config`), the **simulator** (how-many-people / amount-per-person / one-time–monthly + end
  date → a **"Spočítat" button**), a **preview** that shows the *calculator's* result, a supporters strip
  (`/stats`), and below a divider the **pledge form** (one person — no "how many people", no email field;
  email comes from the lookup step). Lookup step centered; logo stretched to the banner width on this page
  (`header-banner`). Success page (`success.html`) buttons/spacing normalized.
- **`pledge.js`** — rewritten. The calculator calls `POST /calculate` **on the button press, not on input**
  (Ondra: a request per keystroke is wasteful) and renders the returned `total_impact / monthly_effect /
  remaining_months` + two-segment projection (baseline pledged % + scenario gain %). **No pledge math in JS.**
  The pledge form saves via `POST /pledges` (`{email, amount, is_monthly, message?, end_month?, end_year?}` —
  **no `contributors_count`**). **Client-side validation** mirrors the backend: email format (`EMAIL_RE`) at
  the lookup step, `amount` ≤ 100,000 and `message` ≤ 500 in the form — bad input is blocked before any request.
- **`i18n.js`** — added the `sim.*` + pledge-zone keys (CZ+EN, parity held at 112=112); removed the now-dead
  live-preview/status/mode keys.
- **`config.js`** — added a **localhost-only** `?api=<url>` override (remembered in localStorage) so the site
  can point at a local dev API before deploy. Gated to `localhost`/`127.0.0.1` so a crafted link can't
  repoint the deployed site.
- **`style.css`** — calc-page styles (sticky bar, simulator grid, two-segment progress, supporters strip,
  centered pledge card), centered/narrowed lookup step, success-page polish, logo overflow fix.

**What did NOT change:** no backend/CDK — `POST /calculate` already shipped in D2a. The pledge math lives only
in `domain/pledge_math.py` now (the JS copy is gone).

**Verification:** gate green (`ruff` clean, **77 passed**), i18n parity 112=112. Browser-driven against a local
dev API running the real handlers (moto): real `/calculate` (108 × €50 monthly → €297,000, projection 19.4 %),
`/stats`-driven supporters, `/config`-driven status bar, pledge create + edit, client email/amount rejection,
CZ↔EN re-render, and **no horizontal overflow at 375 px**. Full end-to-end against the deployed API waits on
Phase F (the dev API is unreachable from production).

---

## 2026-06-19 — T1: POSIX dev scripts (`check.sh` / `serve.sh`)

**Why:** the committed dev helpers were Windows-only (`check.ps1` / `serve.ps1`), but the deploy pipeline and
Anna/Ondra run **Linux**, where they don't execute (Ondra's ask; decision D16). Add bash equivalents and make
them the canonical form in the docs; keep the `.ps1` versions as a Windows-local convenience.

**What changed:**
- **`check.sh` (new)** — mirrors `check.ps1`: bootstraps a Python 3.11 `.venv`, installs `requirements-dev.txt`,
  runs `ruff check` then `pytest -q -rs`; `set -euo pipefail` makes any failing step exit non-zero. A small
  `venv_bin` helper locates interpreters under either `bin/` (Linux/macOS) or `Scripts/`(+`.exe`) (Windows),
  so the **same `.venv` works whichever script created it**.
- **`serve.sh` (new)** — mirrors `serve.ps1`: serves `web/` over `python -m http.server` (prefers
  `python3.11`, falls back to `python3`/`python`) with the same `Cache-Control: no-store` no-cache handler;
  optional port arg (default 8000).
- **Docs** — `web/README.md` "Testing Locally" and repo `CLAUDE.md` (Quality gate + Run-the-site sections)
  now **lead with the `.sh` commands**, noting the `.ps1` Windows equivalents. The `Makefile check` target
  already gives Unix/CI parity.

**What did NOT change:** no app/behavior, no infra, no `.ps1` removed (kept for Windows). Tooling-only.

**Verification:**
```
$ bash ./check.sh        → Using Python 3.11.9 · ruff: All checks passed! · 77 passed · Quality gate PASSED
$ bash ./serve.sh 8127   → GET / 200 · GET /pledge.html 200 · Cache-Control: no-store, must-revalidate
$ bash -n check.sh serve.sh → syntax OK
```
Run via Git Bash on Windows against the existing 3.11 venv (proves the script logic); the only Linux
difference — `bin/` vs `Scripts/` and `python3.11` for venv creation — is handled, so Ondra's Linux CI
confirms the rest.

---

## 2026-06-19 — D2a: backend `POST /calculate` (server-side simulator math)

**Why:** the calculator on the pledge page is a stateless *what-if simulator* (decision D15) — "if N friends
each give X (one-time or monthly until a date), where does the campaign total land?". The math must come from
**one place**: rather than a JS copy in the browser that can drift from the Python save path, the calculator
will call this endpoint and only **display** the result (D8). This step builds the endpoint; the frontend
wiring is D2.

**What changed:**
- **New shared math module** `domain/pledge_math.py` — `calculate_pledge_values()` and
  `calculate_remaining_months()` moved here out of `create_pledge.py`, so the save path **and** the simulator
  compute impact through the same code (single source of truth, D8). `calculate_remaining_months` now floors
  at 0 (matches the documented spec) so a past end date yields no impact — the save path never reaches the
  floor because it rejects past dates in validation.
- **New read-only handler** `handlers/calculate.py` (`POST /calculate`) — input
  `{people, amount, is_monthly, end_month?, end_year?}`; output `total_impact = people * amount *
  (remaining_months if monthly else 1)`, plus `monthly_effect`, `remaining_months`, and the projection
  (`current_total` from `STATS`, `goal` from `CONFIG`, `projected_total`, and `baseline_/projected_/
  scenario_progress_pct` to one decimal). **Writes nothing** (read-only DynamoDB grant). The goal default
  reuses `get_config.DEFAULT_FUNDRAISING_GOAL`, so the simulator stays consistent with the rest of the site
  when the `CONFIG` row is absent.
- **Validation** (`domain/validation.py`): new `validate_calculate_input` — `people` is a positive int with
  **no upper cap** (D15) and `amount` is **uncapped** (the `MAX_AMOUNT` cap guards stored `STATS`; the
  calculator stores nothing, and a large-group what-if must stay expressible). A past monthly end date is
  **not** rejected here (the math floors months at 0). Extracted a shared `_validate_end_date(reject_past=…)`
  helper and refactored `validate_pledge_input` onto it (pledge save uses `reject_past=True`); re-added
  `_require_positive_int`.
- **Infra:** `CalculateFn` (Python 3.11, **read-only** grant) + `POST /calculate` route. CORS already allowed
  `POST` + `*`. Brings the API to **7 endpoints / 7 Lambdas**.
- **Tests:** `tests/integration/test_calculate.py` (one-time, monthly, zero-months/past date, no-DB-write,
  defaults when rows absent, integer serialization, validation errors); `tests/unit/test_pledge_math.py`
  re-pointed at `domain.pledge_math` + a zero-months floor case.

**What did NOT change:** no frontend (the calculator wiring is D2); the pledge save behavior is unchanged (the
floor is unreachable on that path); no deploy.

**Verification:**
```
$ pwsh ./check.ps1
== ruff ==     All checks passed!
== pytest ==   77 passed   (was 65 → +11 calculate + 1 zero-months math)
Quality gate PASSED
```
CDK Python compiles (`py_compile`). Real handler output (moto, 100 people × €50/mo until 12/2030):
`{remaining_months: 55, total_impact: 275000, monthly_effect: 5000, current_total: 228150, goal: 2700000,
projected_total: 503150, baseline_progress_pct: 8.4, projected_progress_pct: 18.6, scenario_progress_pct: 10.2}`.
`/code-review` (high): one low-severity note — `calculate_remaining_months` is computed twice for monthly
input; left as-is rather than duplicate the formula in the handler or change the shared signature (negligible
cost). **Not deployed** — `/calculate` goes live in Phase F.

---

## 2026-06-19 — B4: remove `contributors_count` from the pledge (1 pledge = 1 supporter)

**Why:** the project owner (Anna) and reviewer (Ondra) clarified that the "how many people" idea belongs to
a *what-if calculator/simulator* (Phase D), not to a saved pledge. A saved pledge represents **one person**;
the supporters headline is a count of pledges. There is **no contributors cap** (Anna: none wanted).

**What changed:**
- **Model** (`domain/models.py`) — `contributors_count` removed from the `Pledge` dataclass and from
  `to_dynamodb_item`; `from_dynamodb_item` now **ignores** a legacy `contributors_count` on older rows.
- **Validation** (`domain/validation.py`) — `contributors_count` no longer required/validated; the B3
  `MAX_CONTRIBUTORS_COUNT` cap and the now-unused `_require_positive_int` helper were removed.
- **Handlers** — `create_pledge` adjusts the `STATS` supporter tally by **+1 on create, +0 on edit** (the
  field is still stored under `contributors_count`, now a pledge count); the `_adjust_stats` param is
  `supporters_delta`. `get_pledge_by_email` dropped `contributors_count` from its allowlist; `list_pledges`
  dropped it from the public rows. `get_stats` unchanged (still serves the `STATS` supporter total).
- **Frontend** (`web/pledge.html`, `web/pledge.js`, `web/i18n.js`) — the contributors form field, the
  existing-pledge summary row, the live-preview row, the POST payload, and 3 i18n keys (`pledge.fieldContributors`,
  `pledge.previewContributors`, `pledge.errContributors`) were removed.
- **No destructive DB migration** — old rows may keep the attribute; the pledge path simply stops writing it.
- **Tests/fixtures** updated across the suite; new tests: contributors-in-payload is ignored, a legacy row
  with `contributors_count` is not surfaced, and two pledges count as two supporters.

**What did NOT change:** the pledge math, the email-based upsert flow, the `STATS` field name (kept for the
frontend), the calculator rework itself (Phase D2 reframes the page into a simulator + separate save).

**Verification:**
```
$ pwsh ./check.ps1                  → ruff clean, 65 passed
$ node tools/check-i18n-parity.js   → ✓ en: 97 keys, in parity with 'cs'
```
Browser-checked the pledge page: the contributors field is gone, the live preview renders, and the POST
payload is `{email, amount, is_monthly}`.

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
