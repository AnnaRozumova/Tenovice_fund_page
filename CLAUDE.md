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
API Gateway (HTTP API)  ─►  Lambda (Python 3.11)  ─►  DynamoDB (one table)
   ▲
AWS CDK (Python) describes & deploys all of the above.
```

- **Frontend** `web/` — plain HTML/CSS/JS, **no build step** (no npm, no bundler). `<html lang="cs">`.
  Bilingual (CZ default + EN, DE-ready) via `web/i18n.js` — see "Internationalization" below.
- **Backend** `services/pledges_api/src/` — framework-agnostic Python (NOT a web framework). Handlers are
  plain Lambda `handler(event, context)` functions; domain logic kept framework-free on purpose.
- **Infra** `cdk/` — one stack (`FundraisingCalculatorStack`) = DynamoDB + Lambdas + HTTP API + S3 site.
  One `cdk deploy` provisions the whole app.

### CDK constructs (`cdk/src/`)
- `app.py` — CDK app entry point (`python -m src.app`, set in `cdk.json`).
- `stack.py` — `FundraisingCalculatorStack`; wires the constructs, outputs `HttpApiUrl`.
- `constructs/config.py` — `AppConfig`, reads context from `cdk.json` (`stage`, `project_name`,
  `api_name`, `pledges_table_name`).
- `constructs/dynamodb.py` — Pledges table (PK `pledgeID`) + `EmailIndex` GSI on `email` (projection ALL).
- `constructs/lambdas.py` — the 7 Lambda functions (Python 3.11), code from `../services/pledges_api/src`.
- `constructs/apigw.py` — HTTP API + CORS (`GET`/`POST`/`OPTIONS`, origins `*`) + the 7 routes.
- `constructs/s3_website.py` — public S3 static-website bucket; deploys `../web` and outputs the URL.

## API — 7 endpoints

| Method | Path | Handler (`services/pledges_api/src/handlers/`) | Notes |
|--------|------|-----------------------------------------------|-------|
| GET | `/stats` | `get_stats.handler` | reads the `STATS` row (running totals) |
| GET | `/pledges` | `list_pledges.handler` | `scan`; returns anonymous fields only |
| POST | `/pledges` | `create_pledge.handler` | upsert by email; adjusts `STATS` |
| GET | `/pledges/by-email` | `get_pledge_by_email.handler` | query `EmailIndex` (case-insensitive); returns **only the caller's own pledge, projected to an allowlist** (no `pledgeID`/timestamps) |
| GET | `/config` | `get_config.handler` | reads the `CONFIG` row (editable balance / goal / breakdown); documented defaults if the row is absent (C1) |
| POST | `/config` | `update_config.handler` | **admin-only** write of the `CONFIG` row; shared-secret bearer token, constant-time compare, fails closed (C2) |
| POST | `/calculate` | `calculate.handler` | **read-only** what-if simulator (D2a); computes impact + projection vs goal from the shared pledge math; reads `STATS`/`CONFIG`, writes nothing, no auth |

**Live dev API:** `https://tbaulwfk46.execute-api.eu-central-1.amazonaws.com` (region `eu-central-1`).
It is **deployed and holds test data** — `GET /stats` →
`{"pledged_total": 228150.0, "contributors_count": 19.0, "monthly_total": 12200.0}`.

### Email-based upsert
Email is the identity key. The first `POST /pledges` with an email creates a pledge; a later POST with the
same email updates it (the delta is applied to `STATS`). No tokens / auth — knowing the email is the only
ownership proof.

## Data model (DynamoDB, one table)

Primary key `pledgeID` (String). GSI `EmailIndex` on `email` (projection ALL) for upsert-by-email.

**Pledge row** (`domain/models.py` → `Pledge`):
- `pledgeID` — UUID
- `email` — lowercased (the only identity field; never displayed, never on public endpoints)
- `amount` — pledge amount in EUR (one-time amount, or per-month amount if monthly); 1–100,000
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
- `current_balance`, `fundraising_goal` — EUR
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
(`handlers/create_pledge.py`) and the read-only simulator (`handlers/calculate.py`, `POST /calculate`) so
the two can never drift (decision D8/D15). Moved out of `create_pledge.py` in D2a.
- **One-time:** campaign impact = `amount`; monthly effect = 0.
- **Monthly** (now until `end_month/end_year` inclusive):
  `remaining_months = (end_year - cur_year)*12 + (end_month - cur_month) + 1` (floored at 0);
  campaign impact = `amount * remaining_months`; monthly effect = `amount`.
- **Simulator** (`/calculate`) multiplies by the what-if group size: `total_impact = people * amount *
  (remaining_months if monthly else 1)`.

> The frontend holds **no copy** of this math (removed in D2). `web/pledge.js` calls `POST /calculate` on the
> "Spočítat" button and only *displays* the returned result; it does not recompute anything (single source of
> truth, D8/D15). The only date logic left in JS is an input check that a monthly end date isn't in the past.

## JSON encoding note

All handlers return JSON through the **shared** `services/pledges_api/src/utils/response.py`
(`response(status, body)` + `DecimalEncoder`). The encoder serializes DynamoDB `Decimal` as `int` when
whole, else `float` (EUR amounts and counts display as integers). Don't reintroduce per-handler encoders —
unified in B2.

## Privacy & data model (Phase B — complete)

**B1:** `name` is **dropped** everywhere — model, validation, handlers, frontend (form + summary +
payload), fixtures. `/pledges/by-email` is **hardened**: it returns only the caller's own pledge projected
to an explicit field allowlist (no `pledgeID`/timestamps) and matches email case-insensitively. `email` is
stored **as-is (no hashing)**, used only to recognize a returning pledger so they can edit their own pledge.

**B2:** stats canonicalized on `contributors_count` end-to-end (removed the frontend `pledgers_count`
reads); all four handlers route through the shared `utils/response.py` (no more per-handler encoders).

**B3 — input caps** (`domain/validation.py` constants): `amount` ≤ `MAX_AMOUNT` (100,000),
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

One command runs ruff + pytest (moto) on **Python 3.11** (the Lambda runtime):

```bash
bash ./check.sh      # Linux / macOS / CI (canonical) — bootstraps a 3.11 .venv, installs deps, runs the gate
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
card on each page. `admin.html` is internal tooling and stays English. **Parity gate:** every language
must define the same keys — `node tools/check-i18n-parity.js` (non-zero on drift). Added D1.

## Configuration

- **CDK context** (`cdk/cdk.json`): `stage` (default `dev`), `project_name` (`fundraising-calculator`),
  `api_name` (`fundraising-api`), `pledges_table_name` (`Pledges`). Table name =
  `{project_name}-{stage}-{pledges_table_name}`. Override with `--context key=value`.
- **dev stage** → DynamoDB + S3 use `RemovalPolicy.DESTROY` (and S3 `auto_delete_objects`); any other
  stage → `RETAIN`.
- **Admin secret** (`update_config`): the `ADMIN_SECRET` Lambda env var. CDK reads it from the deploy
  environment (`os.environ`), which the CI/CD pipeline (D13) sources from SSM / Secrets Manager — it is
  **never committed**. If unset, `update_config` fails closed (every `POST /config` → 401). Validated with a
  constant-time compare; never logged. Editing happens over **HTTPS only** via `web/admin.html`.
- **Frontend** (`web/config.js`): `API_URL`, plus `CURRENT_BALANCE` / `FUNDRAISING_GOAL` / `BREAKDOWN` as
  **fallback defaults** (EUR). `loadConfig()` fetches `GET /config` on page load and overrides them (C1);
  the hardcoded values are used only if that request fails. `web/admin.html` + `admin.js` (C2) edit the
  numbers: paste the secret, prefill from `GET /config`, save via `POST /config`.
  The home page shows a discreet link to the members-only dw-connect project page (D3); the project is
  presented as **one** Tenovice direction (Ondra), so there is no per-direction breakdown UI — `CONFIG.BREAKDOWN`
  remains as the `/config` fallback but is not rendered.

## Adding a new Lambda handler
1. Create the handler in `services/pledges_api/src/handlers/`.
2. Define the `_lambda.Function` in `LambdasConstruct` (`cdk/src/constructs/lambdas.py`) and add it to the
   `LambdaHandlers` dataclass (mark Optional if not always wired).
3. Grant DynamoDB access (`table.grant_read_data` / `grant_read_write_data`).
4. Add the route in `ApiConstruct` (`cdk/src/constructs/apigw.py`); update CORS methods if needed.

## Conventions
- Code, identifiers, comments, commit messages in **English**.
- One change = one branch off `main`, named `NN-step-name` (digits + hyphens, **no spaces**);
  branch name == PR name. One step = one branch = one PR.
