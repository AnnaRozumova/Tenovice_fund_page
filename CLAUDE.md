# CLAUDE.md

Guidance for Claude Code (claude.ai/code) and any developer working in this repository.
It describes what the codebase **actually is today**. For the running change log and what's planned
next, see `dev_history.md`; for a fuller architecture write-up, see `docs/architecture.md`.

## Project overview

A small public-facing **fundraising pledge calculator** for the Tenovice project. A visitor enters an
intended gift (one-time, or monthly until a chosen month/year) and sees live how it moves the campaign
total toward the goal. Pledges are stored **anonymously** so other visitors are inspired to add their
own. **No real money moves through the site** — a pledge is a public promise; bank/QR payment details
are shown afterwards so the person sends the money themselves.

Scale: < 1000 friends, infrequent visits → deliberately cheap, simple, low-ops. Works on phone + desktop.

## Architecture

```
Browser (static HTML/CSS/JS on S3)
   │  fetch() JSON over HTTPS
   ▼
API Gateway (HTTP API, ANY /{proxy+})  ─►  one Lambda: FastAPI via Mangum (Python 3.14)  ─►  DynamoDB (one table)
   ▲
AWS CDK (Python) describes & deploys all of the above.
```

- **Frontend** `web/` — plain HTML/CSS/JS, **no build step** (no npm, no bundler). `<html lang="cs">`.
  Bilingual (CZ default + EN, DE-ready) via `web/i18n.js` — see "Internationalization" below. **Auth (AUTH2):**
  `auth.html`/`auth.js` are the custom login/register/verify/reset screens (Cognito SRP via the vendored
  `web/vendor/amazon-cognito-identity.min.js`); `auth-common.js` holds the shared session/token helper `Auth`
  (`requireAuth` gate, `apiFetch` bearer-token wrapper). The pledge page is gated behind a signed-in account
  (no more email-lookup step); the home page stays public. As of **AUTH3** the API enforces the token: the
  whole API is behind a Cognito JWT authorizer except the home-page reads (`GET /stats`, `GET /config`), the
  admin write (`POST /config`, own shared secret), and CORS preflight.
- **Backend** `services/pledges_api/src/` — **one FastAPI app** run in a single Lambda via **Mangum**
  (R1, decision D19). `app.py` mounts the routers in `api/`; shared concerns are imported once — `db.py`
  (`get_table()`), `utils/http.py` (`json_response` / `DecimalJSONResponse`), `config_defaults.py`,
  `domain/` (models, validation, pledge math — framework-agnostic). The Lambda entrypoint is `app.handler`
  (the Mangum adapter).
- **Infra** `cdk/` — one stack (`FundraisingCalculatorStack`) = DynamoDB + the API Lambda + HTTP API + S3 site.
  One `cdk deploy` provisions the whole app.

### CDK constructs (`cdk/src/`)
- `app.py` — CDK app entry point (`python -m src.app`, set in `cdk.json`).
- `stack.py` — `FundraisingCalculatorStack`; wires the constructs, outputs `HttpApiUrl`.
- `constructs/config.py` — `AppConfig`, reads context from `cdk.json` (`stage`, `project_name`,
  `api_name`, `pledges_table_name`).
- `constructs/dynamodb.py` — Pledges table (PK `pledgeID`) + `EmailIndex` GSI on `email` (projection ALL).
- `constructs/lambdas.py` — **the single API Lambda** (Python 3.14, handler `app.handler`); the asset is
  Docker-bundled (`pip install -r requirements.txt -t /asset-output && cp -r src/. /asset-output`) so
  FastAPI + Mangum ship with the code. Read-write on the table.
- `constructs/apigw.py` — HTTP API + CORS (`GET`/`POST`/`OPTIONS`, origins `*`) + the `ANY /{proxy+}`
  route → the API Lambda (FastAPI does the per-endpoint routing). **AUTH3:** a Cognito **JWT authorizer**
  (`HttpUserPoolAuthorizer` over the AUTH1 pool + web client) is attached to the proxy route, so every
  request needs a valid token, with three unauthenticated carve-out routes that win by route specificity —
  `GET /stats`, `ANY /config` (public read + admin shared-secret write), and `OPTIONS /{proxy+}` (CORS
  preflight carries no token). The `$default` stage gets **throttling** (rate 20 / burst 40, both envs).
- `constructs/s3_website.py` — public S3 static-website bucket; deploys `../web` and outputs the URL.
- `constructs/cognito.py` — Cognito **user pool + public (no-secret) app client** for site login (AUTH1,
  D18): email sign-in, self sign-up + email verification, email-only password recovery, 12-char strong
  password policy; SRP flow for custom on-site screens. Also wires a **Custom Message Lambda**
  (`services/cognito_custom_message/`, pure stdlib, no bundling) as the pool's `custom_message` trigger —
  it localizes the verification / reset emails to **CZ or EN** by the user's `locale` attribute (set at
  sign-up from the site language; default CZ), covering sign-up / resend / forgot-password (AUTH2).
  The pool + web client back the **AUTH3** JWT authorizer in `apigw.py` (the API now requires a token).
  Prod pool is retained + deletion-protected; dev is disposable. Outputs `UserPoolId` / `UserPoolClientId`.

## API — 7 routes (one FastAPI app behind `ANY /{proxy+}`)

Every route is a FastAPI path in `services/pledges_api/src/api/`; the contracts are unchanged from the old
per-endpoint Lambdas.

| Method | Path | Route (`services/pledges_api/src/api/`) | Notes |
|--------|------|------------------------------------------|-------|
| GET | `/stats` | `stats.py` | reads the `STATS` row (running totals) |
| GET | `/pledges` | `pledges.py:list_pledges` | `scan`; returns anonymous fields only |
| POST | `/pledges` | `pledges.py:create_or_update_pledge` | upsert keyed by the caller's identity; adjusts `STATS`. **AUTH3:** behind the authorizer the email is the verified JWT `email` claim — the body email is ignored (no impersonation) |
| GET | `/pledges/by-email` | `pledges.py:get_pledge_by_email` | query `EmailIndex` (case-insensitive); returns **only the caller's own pledge, projected to an allowlist** (no `pledgeID`/timestamps; the email isn't echoed back either — H1). **AUTH3:** behind the authorizer the identity is the verified JWT `email` claim; `?email=` is ignored (effectively "my pledge"). Both handlers **fail closed** (401) on an authenticated request whose token has no `email` claim (e.g. an access token); the client-supplied email is honoured only when the app runs without the authorizer (local dev / tests) |
| GET | `/config` | `config.py:get_config` | reads the `CONFIG` row (editable balance / goal / breakdown); documented defaults if the row is absent (C1) |
| POST | `/config` | `config.py:update_config` | **admin-only** write of the `CONFIG` row; shared-secret bearer token, constant-time compare, fails closed (C2) |
| POST | `/calculate` | `calculate.py` | **read-only** what-if simulator (D2a); computes impact + projection vs goal from the shared pledge math; reads `STATS`/`CONFIG`, writes nothing. **AUTH3:** gated (login required) like the rest of the calculator |

**Live dev API:** `https://wcu3d2uaf2.execute-api.eu-central-1.amazonaws.com` (region `eu-central-1`),
deployed from `main` (stack `FundraisingCalculatorStack`). The table is **fresh** — `GET /stats` →
`{"pledged_total": 0, "contributors_count": 0, "monthly_total": 0}`. (The older `tbaulwfk46…` API was a
previous stack.) **Dev site:**
`http://fundraising-calculator-dev-026268603137-website.s3-website.eu-central-1.amazonaws.com`.

**CORS:** the browser's preflight `OPTIONS` is forwarded through the single `ANY /{proxy+}` route into the
app; an HTTP middleware in `app.py` answers it with `204` (API Gateway adds the actual CORS headers). Without
it FastAPI would 405 the preflight and the browser would block every `POST`.

### Email-based upsert
Email is the identity key. The first `POST /pledges` with an email creates a pledge; a later POST with the
same email updates it (the delta is applied to `STATS`). No tokens / auth — knowing the email is the only
ownership proof.

## Data model (DynamoDB, one table)

Primary key `pledgeID` (String). GSI `EmailIndex` on `email` (projection ALL) for upsert-by-email.

**Pledge row** (`domain/models.py` → `Pledge`):
- `pledgeID` — UUID
- `email` — lowercased (the only identity field; never displayed, never on public endpoints)
- `amount` — pledge amount in **canonical CZK** (one-time amount, or per-month amount if monthly); 1–2,500,000. The API converts to EUR at the boundary by `?currency=` (D22)
- `is_monthly` — bool
- `campaign_total` — the pledge's total campaign impact (see "Pledge math"); stored so it stays stable as months pass
- `created_at` — ISO timestamp
- `updated_at?` — ISO timestamp, present only after an update
- `message?` — optional free text
- `end_month?`, `end_year?` — present only for monthly pledges

> A pledge represents **one person** (B4). Legacy (pre-B4) rows may still carry a `contributors_count`
> attribute — it is ignored by the model and never re-written; no destructive migration is performed.

**`STATS` row** (`pledgeID="STATS"`) — running totals:
- `pledged_total` — sum of `campaign_total`
- `contributors_count` — the supporters total; **a count of pledges** (1 per supporter since B4), `+1` on
  each new pledge, `+0` on edit. (Name kept for the frontend; it no longer sums per-pledge group sizes.)
- `monthly_total` — sum of monthly `amount`
- `updated_at`

**`CONFIG` row** (`pledgeID="CONFIG"`, added C1) — the editable campaign numbers served by `GET /config`:
- `current_balance`, `fundraising_goal` — canonical **CZK**; `exchange_rate` — CZK per EUR (D22, admin-editable)
- `breakdown` — list of `{key, amount}`; `key` is a stable identifier (`new_gompa`, `sangha_house`,
  `basecamp_north`) — localized labels live in the frontend i18n dict, not the DB
- `get_config` falls back to documented defaults when the row is absent. The row is written by the
  admin-only `POST /config` (`update_config`, C2) — guarded by a shared-secret bearer token.

> **`contributors_count`** (on the `STATS` row) is the single canonical field for the supporters total,
> used end-to-end (DynamoDB `STATS` → `GET /stats` → `web/main.js`). The old frontend `pledgers_count`
> reads were removed in B2; since B4 the value is a **pledge count** (1 per supporter), not a sum of group sizes.

## Pledge math (single source of truth — `domain/pledge_math.py`)

The formula lives **once**, in `services/pledges_api/src/domain/pledge_math.py`
(`calculate_pledge_values`, `calculate_remaining_months`), and is imported by both the save path
(`api/pledges.py`) and the read-only simulator (`api/calculate.py`, `POST /calculate`) so the two can never
drift (decision D8/D15). Consolidated into `domain/pledge_math.py` in D2a.
- **One-time:** campaign impact = `amount`; monthly effect = 0.
- **Monthly** (now until `end_month/end_year` inclusive):
  `remaining_months = (end_year - cur_year)*12 + (end_month - cur_month) + 1` (floored at 0);
  campaign impact = `amount * remaining_months`; monthly effect = `amount`.
- **Simulator** (`/calculate`) multiplies by the what-if group size: `total_impact = people * amount *
  (remaining_months if monthly else 1)`.

> The frontend holds **no copy** of this math (removed in D2). `web/pledge.js` calls `POST /calculate` on the
> "Spočítat" button and only *displays* the returned result; it does not recompute anything (single source of
> truth, D8/D15). The only date logic left in JS is an input check that a monthly end date isn't in the past.

## Currency — CZK canonical, converted at the boundary (D22)

DynamoDB stores every amount in **canonical CZK** (the campaign's real bank account is in koruna). The
API converts to the currency the caller asks for via a `?currency=czk|eur` query param the frontend sends
per page language (CZ → `czk`, EN → `eur`). **Read** routes convert canonical CZK → the requested currency
and tag the response with `currency`; **write** routes (`POST /pledges`, `POST /calculate`) normalize the
incoming amount → canonical CZK first. No param / `czk` → koruna unchanged. The conversion lives once in
`domain/currency.py` (`parse_currency`, `to_display`, `to_canonical`, `convert_fields`, `normalize_amount`);
the rate is read once via `api/config.py` `read_exchange_rate` / `exchange_rate_of`, and flat responses go
through `localize()`. Amounts round to whole units; **percentages and `contributors_count` are never
converted** (currency-invariant). The save path rounds to whole CZK (a stored pledge is one canonical value,
kept whole/consistent in CZK); the read-only simulator (`/calculate`) keeps full precision internally and
rounds only the output fields, so per-person rounding isn't amplified by the people/months multiplier. The
exchange rate (CZK per EUR, default 24.22) lives in the `CONFIG` row next to `current_balance`; admin edits
it (for now via the AWS console, D22-storage).

**Frontend (`web/`):** the display currency follows the page language (CZ → CZK, EN → EUR). `config.js`
`currentCurrency()` reads it from `<html lang>` (kept in sync by `i18n.js`); `withCurrency(path)` appends
`?currency=` to every money-bearing request; `formatCurrency(amount)` renders the already-converted value
with the right symbol (`2 500 Kč` / `€2,500`). A **language switch re-fetches** the money data in the new
currency (it doesn't just re-symbol stale numbers) — `main.js` and `pledge.js` do this on `i18n:changed`; the
simulator result is cleared so the user recalculates (the amount input is now read as the new currency).
Currency-dependent static labels (e.g. the amount field's `(Kč)`/`(EUR)`) are baked per-language in the i18n
dict since currency ≡ language. `admin.html` is unaffected — it omits `?currency=` and edits canonical CZK.
**Deploy the backend + frontend currency changes together** (the backend defaults are CZK, so an un-updated
frontend would label koruna with a € symbol).

## JSON encoding note

Routes return JSON through the **shared** `json_response(status, body)` in
`services/pledges_api/src/utils/http.py` — a `DecimalJSONResponse` that reuses `DecimalEncoder` from
`utils/response.py`. The encoder serializes DynamoDB `Decimal` as `int` when whole, else `float` (CZK
amounts and counts display as integers). One shared place — don't reintroduce per-route encoders.
(Mangum builds the Lambda-proxy response envelope, so the old hand-rolled `response()` envelope was removed
in R1; `utils/response.py` now holds only `DecimalEncoder`.)

## Privacy & data model (Phase B — complete)

**B1:** `name` is **dropped** everywhere — model, validation, handlers, frontend (form + summary +
payload), fixtures. `/pledges/by-email` is **hardened**: it returns only the caller's own pledge projected
to an explicit field allowlist (no `pledgeID`/timestamps) and matches email case-insensitively. `email` is
stored **as-is (no hashing)**, used only to recognize a returning pledger so they can edit their own pledge.

**B2:** stats canonicalized on `contributors_count` end-to-end (removed the frontend `pledgers_count`
reads); all four handlers route through the shared `utils/response.py` (no more per-handler encoders).

**B3 — input caps** (`domain/validation.py` constants): `amount` ≤ `MAX_AMOUNT` (2,500,000 **CZK** since D22;
~€100k — an EUR amount is normalized to CZK before this cap applies),
`message` ≤ `MAX_MESSAGE_LENGTH` (500 chars); min ≥ 1. Over-cap input is rejected with a clear error. Caps
are **provisional** and move into the editable `CONFIG` row in Phase C. Caps are enforced **server-side
only** for now; mirroring them in the form is deferred to D2.

**B4 — `contributors_count` removed from the pledge.** A saved pledge represents **one person** (Anna+Ondra
decision): the "how many people" what-if lives in the calculator/simulator (Phase D), not the stored pledge.
`contributors_count` is gone from the model, validation (incl. the B3 cap), the create/update handlers, the
`by-email` allowlist, the public list, and the frontend form/payload. The DB column **may remain** on legacy
rows — no destructive migration. The `STATS` supporter tally (still stored under `contributors_count`) now
counts pledges: `+1` per new pledge, `+0` on edit.

> The test data in the live table will be reset when the privacy/data-model phase deploys (Phase F).

## Input & error hardening (H1 — pre-deploy review)

A cross-cutting security/quality review over the whole A–E change set (vs `main`) found **no
critical/high/medium** issues. Fixes applied:
- **Non-finite numbers** (`NaN`/`Infinity`) are rejected as a clean **400** in `domain/validation.py` — they
  previously passed validation and crashed a handler with an uncaught exception (→ 500). Integer CONFIG fields
  also reject fractional input instead of silently truncating it.
- **`500` responses no longer echo internal exception detail** (`str(e)`/boto text) to the client — generic
  message only.
- **`/pledges/by-email` no longer echoes the caller's own email** back in the body (they supplied it in the
  query; minimization). `web/pledge.js` shows the entered email in the existing-pledge summary instead.

Deferred (tracked): wildcard CORS lock → **G1** (needs the domain); atomic STATS update and integer-EUR
enforcement → follow-ups; a "messages are public" copy hint for Anna. (`get_stats` no-row default —
**done 2026-06-26, P1**: returns 200 with zeros on an empty table.)

## Development commands

From the repo root (`Makefile`):
```bash
make test              # all tests (services/pledges_api)
make test-unit         # unit tests
make test-integration  # integration tests (moto, mocked AWS)
make test-coverage     # tests + coverage report
make check             # quality gate: ruff lint + pytest (Unix/CI; Windows: pwsh ./check.ps1)

make infra-install     # install CDK deps
make infra-synth       # cdk synth
make infra-diff        # cdk diff vs deployed
make infra-deploy      # cdk deploy
make infra-destroy     # cdk destroy
make infra-bootstrap   # cdk bootstrap (first time per account/region)
```
From `cdk/` (`cdk/Makefile`): `make fmt` / `make lint` run **ruff** on `cdk/src`.

### Running the tests directly
```bash
cd services/pledges_api
pip install -r requirements-test.txt   # pytest, pytest-cov, moto, boto3
python -m pytest tests/ -v
```
`tests/conftest.py` puts `src/` on the import path. Layout:
- `tests/unit/` — pure logic (models, validation), no AWS.
- `tests/integration/` — handlers against moto-mocked DynamoDB.
- repo-root `tests/e2e/` — hits a **deployed** API (`API_URL` env var); not run by `make test`.

### Quality gate

One command runs ruff + pytest (moto) on **Python 3.14** (the Lambda runtime):

```bash
bash ./check.sh      # Linux / macOS / CI (canonical) — bootstraps a 3.14 .venv, installs deps, runs the gate
pwsh ./check.ps1     # Windows dev — same gate (the two share one .venv)
make check           # Unix / CI parity — assumes ruff + deps already installed
```

`check.sh` is the canonical POSIX form (CI + Anna/Ondra run Linux); `check.ps1` is the Windows-local
convenience (D16). `requirements-dev.txt` = test deps + ruff; `.venv/` is gitignored. The legacy tests are currently
**skipped with a reason** (they assume an older validation/model contract — tuple-returning validation,
`name` length, `pledgers_count`, no `contributors_count`) and get rewritten in the privacy/data-model
phase. The locked pledge math is covered now in `tests/unit/test_pledge_math.py`.

### Run the site locally

```bash
bash ./serve.sh      # serves web/ at http://localhost:8000 (canonical; pass a port arg to change)
pwsh ./serve.ps1     # Windows equivalent (-Port to change). No build, no deploy.
```

The API base is a single config value — `CONFIG.API_URL` in `web/config.js` (defaults to the live dev
API, so the calculator shows real data locally). See `web/README.md` for the plain `python -m http.server`
fallback.

## Internationalization (i18n)

Public pages are bilingual — **CZ (default) + EN**, structure DE-ready (decision D7). All user-facing
strings live in one flat-key dictionary `web/i18n.js` (`TRANSLATIONS.cs` / `.en`). Markup uses
`data-i18n` (text), `data-i18n-html` (innerHTML), `data-i18n-placeholder`/`-alt`/`-aria-label`; JS uses
`t('key', {params})`. The choice persists in `localStorage`, `<html lang>` follows, and an `i18n:changed`
event lets JS re-render its dynamic strings. A subtle `CS · EN` toggle sits in the top-right of the first
card on each page (on `success.html` it sits under the logo in the header instead). `admin.html` is internal
tooling and stays English. **Parity gate:** every language must define the same keys —
`node tools/check-i18n-parity.js` (non-zero on drift). Added D1.

## Configuration

- **CDK context** (`cdk/cdk.json`): `stage` (default `dev`), `project_name` (`fundraising-calculator`),
  `api_name` (`fundraising-api`), `pledges_table_name` (`Pledges`). Table name =
  `{project_name}-{stage}-{pledges_table_name}`. Override with `--context key=value`.
- **S3 website bucket name** = `{project_name}-{stage}-{AWS::AccountId}-website`. S3 names are **globally
  unique across all of AWS**, so the account id is included to keep the same app deployable from multiple
  accounts (dev / prod) without a name clash; `stage` separates environments within one account.
- **dev stage** → DynamoDB + S3 use `RemovalPolicy.DESTROY` (and S3 `auto_delete_objects`); any other
  stage → `RETAIN`.
- **Admin secret** (`update_config`): the `ADMIN_SECRET` Lambda env var. CDK reads it from the deploy
  environment (`os.environ`), which the CI/CD pipeline (D13) sources from SSM / Secrets Manager — it is
  **never committed**. If unset, `update_config` fails closed (every `POST /config` → 401). Validated with a
  constant-time compare; never logged. Editing happens over **HTTPS only** via `web/admin.html`.
- **Frontend** (`web/config.js`): `API_URL`, a `COGNITO` block (`USER_POOL_ID` / `CLIENT_ID` / `REGION` for
  the login screens, AUTH2 — per-stage like `API_URL`), plus `CURRENT_BALANCE` / `FUNDRAISING_GOAL` /
  `BREAKDOWN` as **fallback defaults** (canonical CZK, D22). `loadConfig()` fetches `GET /config` on page load and overrides them (C1);
  the hardcoded values are used only if that request fails. `web/admin.html` + `admin.js` (C2) edit the
  numbers: paste the secret, prefill from `GET /config`, save via `POST /config`.
  The home page shows a discreet link to the members-only dw-connect project page (D3); the project is
  presented as **one** Tenovice direction (Ondra), so there is no per-direction breakdown UI — `CONFIG.BREAKDOWN`
  remains as the `/config` fallback but is not rendered.

## Adding a new endpoint
1. Add a FastAPI route to the right module in `services/pledges_api/src/api/` (or a new module whose
   `router` is included in `app.py`). Return via `json_response(status, body)`; reach DynamoDB through
   `db.get_table()`; reuse `domain/` for validation + math.
2. **No CDK / API-Gateway change** — the single `ANY /{proxy+}` route already forwards every path to the app
   (that's the point of D19).
3. Add tests in `services/pledges_api/tests/integration/` driving the app via FastAPI's `TestClient`.

## Conventions
- Code, identifiers, comments, commit messages in **English**.
- One change = one branch off `main`, named `NN-step-name` (digits + hyphens, **no spaces**);
  branch name == PR name. One step = one branch = one PR.
