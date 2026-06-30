# Architecture

Architecture reference for the Tenovice fundraising pledge calculator. Companion to the repo-root
`CLAUDE.md` (developer quick-start) and `dev_history.md` (change log). This document describes the
**current** system and the **locked-in direction** for the privacy/data-model work that follows.

## What the app is

A static website where friends of the Tenovice project enter a pledge — a one-time gift, or a monthly
amount for a chosen number of months — and see live how it moves the campaign total toward the goal. Pledges
are stored **anonymously**; the running totals inspire the next visitor. No real money moves through the
site: after pledging, the visitor is shown bank details + QR codes and sends the money themselves.

Audience: < 1000 friends, infrequent visits → the design optimizes for **low cost, low ops, simplicity**,
and works on phone + desktop.

## System diagram

```
   friend's phone / PC
          │
          ▼
   ┌──────────────────────────┐   HTML/CSS/JS (no build step)
   │  S3 static website (web/) │   <html lang="cs">
   └────────────┬─────────────┘
                │  fetch() JSON over HTTPS
                ▼
   ┌──────────────────────────┐
   │  API Gateway (HTTP API)   │   ANY /{proxy+}; CORS GET/POST/OPTIONS, origins *
   └────────────┬─────────────┘
                │
                ▼
   ┌──────────────────────────┐
   │  one Lambda: FastAPI app  │   routes in api/ (stats, pledges, config,
   │  via Mangum (Python 3.14) │   calculate); shared db/ utils/ domain/
   └────────────┬─────────────┘
                ▼
                  ┌──────────────────────────┐
                  │  DynamoDB (one table)     │
                  │  • pledge rows (by email) │
                  │  • STATS row              │
                  └──────────────────────────┘

   All of the above described & deployed by AWS CDK (Python) — one stack, one `cdk deploy`.
```

## Components

| Layer | Path | What it is |
|-------|------|------------|
| Frontend | `web/` | Plain HTML/CSS/JS static site, no build tools. Deployed to S3. Bilingual CZ/EN via `web/i18n.js` (D1; see "Internationalization"). |
| Backend | `services/pledges_api/src/` | One **FastAPI** app (`app.py` + `api/` routers) run in a single Lambda via **Mangum** (R1/D19); `domain/` logic stays framework-agnostic. |
| Infra | `cdk/` | One CDK stack: DynamoDB + the API Lambda + HTTP API + S3 site. |

### CDK constructs (`cdk/src/`)
- `app.py` — CDK app entry (`python -m src.app`).
- `stack.py` — `FundraisingCalculatorStack`; composes the constructs, outputs `HttpApiUrl`.
- `constructs/config.py` — `AppConfig` from `cdk.json` context.
- `constructs/dynamodb.py` — Pledges table (PK `pledgeID`) + `EmailIndex` GSI on `email`.
- `constructs/lambdas.py` — the **single API Lambda** (Python 3.14, handler `app.handler`); its asset
  Docker-bundles FastAPI + Mangum (≥0.21, for 3.14 event-loop support) with the source.
- `constructs/apigw.py` — HTTP API, CORS, the `ANY /{proxy+}` route → the API Lambda. **AUTH3:** a Cognito
  JWT authorizer gates that proxy route; `GET /stats`, `ANY /config`, and `OPTIONS /{proxy+}` are declared as
  separate unauthenticated routes (they win by route specificity) so the public home page, the shared-secret
  admin write, and CORS preflight bypass the token check. The `$default` stage carries throttling (rate 20 /
  burst 40) on every env.
- `constructs/s3_website.py` — public static-website bucket; deploys `../web`.
- `constructs/cognito.py` — Cognito **user pool + public app client** for site login (AUTH1, D18). The pool +
  web client back the **AUTH3** JWT authorizer in `apigw.py`, so the API now requires a valid token (only the
  home-page reads, the admin write, and preflight are public).

## API surface — route map

One FastAPI app behind `ANY /{proxy+}`; every route lives in `services/pledges_api/src/api/`.

| Method | Path | Route (`src/api/`) | Reads / writes |
|--------|------|--------------------|----------------|
| GET | `/stats` | `stats.py` | read `STATS` row |
| GET | `/pledges` | `pledges.py:list_pledges` | `scan`, anonymous fields only |
| POST | `/pledges` | `pledges.py:create_or_update_pledge` | upsert by email + adjust `STATS` |
| GET | `/pledges/by-email` | `pledges.py:get_pledge_by_email` | query `EmailIndex`; returns only the caller's own pledge, projected to an allowlist (no `pledgeID`/timestamps; email not echoed — B1/H1) |
| GET | `/config` | `config.py:get_config` | read `CONFIG` row (editable balance / goal / breakdown); documented defaults if absent |
| POST | `/config` | `config.py:update_config` | **admin-only** write of `CONFIG`; shared-secret bearer token (constant-time compare, fails closed) |
| POST | `/calculate` | `calculate.py` | **read-only** what-if simulator (D2a): `{people, amount, is_monthly, end_month?, end_year?}` → impact + projection vs goal; reads `STATS`/`CONFIG`, writes nothing, no auth |

**Email-based upsert:** email is the identity key. First POST creates; a later POST with the same email
updates, applying the delta to `STATS`. No tokens/auth — knowing the email is the ownership proof.

**Live dev API:** `https://wcu3d2uaf2.execute-api.eu-central-1.amazonaws.com` (`eu-central-1`), deployed from
`main` (stack `FundraisingCalculatorStack`); the table is fresh →
`GET /stats` → `{"pledged_total": 0, "contributors_count": 0, "monthly_total": 0}`. (The older `tbaulwfk46…`
API was a previous stack.) Dev site:
`http://fundraising-calculator-dev-026268603137-website.s3-website.eu-central-1.amazonaws.com`.

## Data model

Single DynamoDB table. PK `pledgeID` (String); GSI `EmailIndex` on `email` (projection ALL).

**Pledge row** (`domain/models.py` → `Pledge`):

| Field | Type | Notes |
|-------|------|-------|
| `pledgeID` | String | UUID |
| `email` | String | lowercased; the only identity field (never displayed, never on public endpoints) |
| `amount` | Number | canonical **CZK**; one-time amount, or per-month amount if monthly (API converts to EUR by `?currency=`, D22) |
| `is_monthly` | Bool | |
| `campaign_total` | Number | the pledge's total campaign impact (see "Pledge math"); stored so it stays stable |
| `created_at` | String | ISO timestamp |
| `updated_at?` | String | present only after an update |
| `message?` | String | optional |
| `end_month?`, `end_year?` | Number | present only for monthly pledges |

A pledge represents **one person** (B4). Legacy (pre-B4) rows may still carry a `contributors_count`
attribute; it is ignored and never re-written (no destructive migration).

**`STATS` row** (`pledgeID="STATS"`): `pledged_total` (Σ `campaign_total`), `contributors_count`
(the supporters total — a **count of pledges**, `+1` per new pledge, `+0` on edit since B4),
`monthly_total` (Σ monthly `amount`), `updated_at`.

**`CONFIG` row** (`pledgeID="CONFIG"`, added C1): the editable campaign numbers — `current_balance`,
`fundraising_goal`, and `breakdown` (a list of `{key, amount}`, where `key` is a stable identifier such as
`new_gompa` — localized labels live in the frontend i18n dict, not the DB). Read by `GET /config`; the
handler falls back to documented defaults when the row is absent, so the site works before it is seeded.
The row is written by the admin-only `POST /config` (`update_config`, C2; see "Admin secret" below).

> The `STATS` `contributors_count` is the single canonical field for the supporters total, used end-to-end
> (`STATS` → `GET /stats` → `web/main.js`). The old `pledgers_count` reads were removed in B2; since B4 it
> is a **pledge count** (1 per supporter), not a sum of per-pledge group sizes.

## Pledge math (single source of truth — `domain/pledge_math.py`)

The formula lives **once**, in `services/pledges_api/src/domain/pledge_math.py`, and is imported by both the
save path (`create_pledge.py`) and the read-only simulator (`calculate.py` / `POST /calculate`), so they can
never drift (D8/D15; consolidated in D2a).

- **One-time:** campaign impact = `amount`; monthly effect = 0.
- **Monthly** (runs from now until `end_month/end_year` inclusive):
  `remaining_months = (end_year - cur_year)*12 + (end_month - cur_month) + 1`, floored at 0;
  campaign impact = `amount * remaining_months`; monthly effect = `amount`.
- **Simulator** (`/calculate`) multiplies by the what-if group size:
  `total_impact = people * amount * (remaining_months if monthly else 1)`, and returns the projection toward
  the goal (`STATS` total + `CONFIG` goal → `projected_total`, progress %).

`campaign_total` is stored per pledge so the value stays stable as months pass. Money is stored in **canonical
CZK** and converted to the requested currency (`?currency=czk|eur`) at the API boundary (D22), integer display.

> The frontend holds **no copy** of this math (removed in D2): `web/pledge.js` calls `POST /calculate` on the
> "Spočítat" button and only *displays* the returned result — single source of truth (D8/D15). The monthly
> form collects a **number of months**; `pledge.js` converts it to `end_month`/`end_year` at the input
> boundary (and back, to pre-fill the edit form) — input prep, not impact math.

## Privacy model

The core rule: **all pledges are public, but all identities are private.**
- Public endpoints (`/stats`, `/pledges`) expose **anonymous fields only** — never `email`.
- `email` is used **only** to recognize a returning pledger so they can edit their own pledge.
- `name` is **not stored** (dropped in B1). `/pledges/by-email` returns only the caller's own pledge,
  projected to an explicit field allowlist (no `pledgeID`/timestamps).

## Planned direction (privacy & data-model hardening)

Locked decisions for the phase (full rationale lives in the project's decision log):
1. ~~**Drop `name`** everywhere~~ — **done (B1)**; never stored, never displayed, contact happens off-site.
2. **Store `email` as-is — no hashing.** A hash of a known email is only pseudonymous, so it adds an
   irreversible migration for marginal gain; minimization comes from storing no names + keeping email off
   every public endpoint.
3. ~~**Harden `/pledges/by-email`**~~ — **done (B1)**; returns only the caller's own pledge fields.
4. ~~**Canonicalize stats on `contributors_count`**~~ — **done (B2)**; frontend `pledgers_count` reads removed.
5. ~~**One shared `response()`/`DecimalEncoder` util**~~ — **done (B2)**; all four handlers use `utils/response.py`.
6. ~~**Add upper bounds** on `amount`~~ — **done (B3)**; also `message` length. Caps (`amount` ≤ 2,500,000 CZK
   since D22 (~€100k), `message` ≤ 500) are provisional constants in `domain/validation.py`, server-side only; they move to the
   `CONFIG` row in Phase C.
7. ~~**Remove `contributors_count` from the pledge**~~ — **done (B4)**; a pledge is one person (the "how
   many people" what-if lives in the Phase-D calculator/simulator). No contributors cap; the field left the
   model/validation/handlers/frontend; legacy DB rows may keep it (no destructive migration). `STATS`
   supporter tally now counts pledges (1 per supporter).

Doing this early is cheap (only test data exists); it gets painful once real friends pledge. See
`dev_history.md` for sequencing.

## Configuration & environments

- **CDK context** (`cdk/cdk.json`): `stage` (default `dev`), `project_name` (`fundraising-calculator`),
  `api_name` (`fundraising-api`), `pledges_table_name` (`Pledges`). Table =
  `{project_name}-{stage}-{pledges_table_name}`.
- **dev** → DynamoDB + S3 `RemovalPolicy.DESTROY`; other stages → `RETAIN`.
- **Frontend** (`web/config.js`): `API_URL`, plus `CURRENT_BALANCE` / `FUNDRAISING_GOAL` / `BREAKDOWN` as
  **fallback defaults**. `loadConfig()` fetches `GET /config` on page load and overrides them; the hardcoded
  values are used only if that request fails. `web/admin.html` + `admin.js` (C2) write the `CONFIG` row via
  `POST /config` (paste the secret, prefill from `GET /config`, save).

**Admin secret** (C2, decision D6): `update_config` authorizes the caller by comparing a bearer token
against the `ADMIN_SECRET` Lambda env var with a **constant-time** compare (`hmac.compare_digest`). It
**fails closed** — if no secret is configured, every write is rejected. CDK injects `ADMIN_SECRET` from the
deploy environment, which the CI/CD pipeline (D13) sources from SSM / Secrets Manager; it is **never
committed and never logged**. A single shared secret over HTTPS is intentional — Cognito would be overkill
for one trusted editor.

## Internationalization (i18n, D1)

Public pages are bilingual — **CZ default + EN**, structure DE-ready (decision D7). One flat-key dictionary
`web/i18n.js` (`TRANSLATIONS.cs` / `.en`) holds every user-facing string. Markup is tagged with `data-i18n`
(text), `data-i18n-html` (innerHTML), and `data-i18n-placeholder`/`-alt`/`-aria-label`; runtime strings use
`t('key', {params})`. `applyTranslations(lang)` updates the DOM, sets `<html lang>`, and dispatches an
`i18n:changed` event so JS-rendered strings re-render. The language persists in `localStorage`; a subtle
`CS · EN` toggle sits top-right of the first card on each page. `admin.html` is internal and stays English.
A parity checker (`tools/check-i18n-parity.js`) fails if any language's key set diverges from the default.

## Testing

- `services/pledges_api/tests/unit/` — pure logic (models, validation, Decimal encoding), no AWS.
- `services/pledges_api/tests/integration/` — the FastAPI app driven via **`TestClient`** against
  **moto**-mocked DynamoDB, plus `test_proxy_event.py` which feeds a real API-GW HTTP API v2 event through
  `app.handler` (Mangum) to lock the `ANY /{proxy+}` path routing.
- `tests/e2e/` (repo root) — against a **deployed** API via the `API_URL` env var; not part of `make test`.

`tests/conftest.py` adds `src/` to the import path. Run: `cd services/pledges_api && python -m pytest tests/ -v`.
