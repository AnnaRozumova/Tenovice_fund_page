# Architecture

Architecture reference for the Tenovice fundraising pledge calculator. Companion to the repo-root
`CLAUDE.md` (developer quick-start) and `dev_history.md` (change log). This document describes the
**current** system and the **locked-in direction** for the privacy/data-model work that follows.

## What the app is

A static website where friends of the Tenovice project enter a pledge — a one-time gift, or a monthly
amount until a chosen month/year — and see live how it moves the campaign total toward the goal. Pledges
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
   │  API Gateway (HTTP API)   │   CORS: GET/POST/OPTIONS, origins *
   └────────────┬─────────────┘
        ┌────────┼─────────────┬─────────────────────┐
        ▼        ▼             ▼                     ▼
    get_stats  list_pledges  create_pledge   get_pledge_by_email
        └────────┴─────────────┬─────────────────────┘
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
| Frontend | `web/` | Plain HTML/CSS/JS static site, no build tools. Deployed to S3. |
| Backend | `services/pledges_api/src/` | Framework-agnostic Python; each handler is a Lambda `handler(event, context)`. |
| Infra | `cdk/` | One CDK stack: DynamoDB + Lambdas + HTTP API + S3 site. |

### CDK constructs (`cdk/src/`)
- `app.py` — CDK app entry (`python -m src.app`).
- `stack.py` — `FundraisingCalculatorStack`; composes the constructs, outputs `HttpApiUrl`.
- `constructs/config.py` — `AppConfig` from `cdk.json` context.
- `constructs/dynamodb.py` — Pledges table (PK `pledgeID`) + `EmailIndex` GSI on `email`.
- `constructs/lambdas.py` — 6 Lambda functions (Python 3.11) from `../services/pledges_api/src`.
- `constructs/apigw.py` — HTTP API, CORS, the 6 routes.
- `constructs/s3_website.py` — public static-website bucket; deploys `../web`.

## API surface — endpoint → handler map

| Method | Path | Handler | Reads / writes |
|--------|------|---------|----------------|
| GET | `/stats` | `get_stats.handler` | read `STATS` row |
| GET | `/pledges` | `list_pledges.handler` | `scan`, anonymous fields only |
| POST | `/pledges` | `create_pledge.handler` | upsert by email + adjust `STATS` |
| GET | `/pledges/by-email` | `get_pledge_by_email.handler` | query `EmailIndex` (**returns full record today — PII leak, see "Planned direction"**) |
| GET | `/config` | `get_config.handler` | read `CONFIG` row (editable balance / goal / breakdown); documented defaults if absent |
| POST | `/config` | `update_config.handler` | **admin-only** write of `CONFIG`; shared-secret bearer token (constant-time compare, fails closed) |

**Email-based upsert:** email is the identity key. First POST creates; a later POST with the same email
updates, applying the delta to `STATS`. No tokens/auth — knowing the email is the ownership proof.

**Live dev API:** `https://tbaulwfk46.execute-api.eu-central-1.amazonaws.com` (`eu-central-1`), deployed
with test data. `GET /stats` → `{"pledged_total": 228150.0, "contributors_count": 19.0, "monthly_total": 12200.0}`.

## Data model

Single DynamoDB table. PK `pledgeID` (String); GSI `EmailIndex` on `email` (projection ALL).

**Pledge row** (`domain/models.py` → `Pledge`):

| Field | Type | Notes |
|-------|------|-------|
| `pledgeID` | String | UUID |
| `email` | String | lowercased; the only identity field (never displayed, never on public endpoints) |
| `contributors_count` | Number | how many people one pledge represents (≥ 1) |
| `amount` | Number | EUR; one-time amount, or per-month amount if monthly |
| `is_monthly` | Bool | |
| `campaign_total` | Number | the pledge's total campaign impact (see "Pledge math"); stored so it stays stable |
| `created_at` | String | ISO timestamp |
| `updated_at?` | String | present only after an update |
| `message?` | String | optional |
| `end_month?`, `end_year?` | Number | present only for monthly pledges |

**`STATS` row** (`pledgeID="STATS"`): `pledged_total` (Σ `campaign_total`), `contributors_count`
(Σ pledges' `contributors_count`), `monthly_total` (Σ monthly `amount`), `updated_at`.

**`CONFIG` row** (`pledgeID="CONFIG"`, added C1): the editable campaign numbers — `current_balance`,
`fundraising_goal`, and `breakdown` (a list of `{key, amount}`, where `key` is a stable identifier such as
`new_gompa` — localized labels live in the frontend i18n dict, not the DB). Read by `GET /config`; the
handler falls back to documented defaults when the row is absent, so the site works before it is seeded.
The row is written by the admin-only `POST /config` (`update_config`, C2; see "Admin secret" below).

> `contributors_count` is the single canonical field for the supporters total, used end-to-end
> (`STATS` → `GET /stats` → `web/main.js` + `web/pledge.js`). The old `pledgers_count` reads were removed
> in B2.

## Pledge math (defined once per side, kept in lockstep)

The calculator preview (`web/pledge.js`) and the saved totals (`create_pledge.py`) **must use the same
formula** — change one, change both.

- **One-time:** campaign impact = `amount`; monthly effect = 0.
- **Monthly** (runs from now until `end_month/end_year` inclusive):
  `remaining_months = (end_year - cur_year)*12 + (end_month - cur_month) + 1`, floored at 0;
  campaign impact = `amount * remaining_months`; monthly effect = `amount`.

`campaign_total` is stored per pledge so the value stays stable as months pass. Money is EUR, integer display.

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
6. ~~**Add upper bounds** on `amount` and `contributors_count`~~ — **done (B3)**; also `message` length.
   Caps (`amount` ≤ 100,000, `contributors_count` ≤ 5, `message` ≤ 500) are provisional constants in
   `domain/validation.py`, server-side only; they move to the `CONFIG` row in Phase C.

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

## Testing

- `services/pledges_api/tests/unit/` — pure logic (models, validation), no AWS.
- `services/pledges_api/tests/integration/` — handlers against **moto**-mocked DynamoDB.
- `tests/e2e/` (repo root) — against a **deployed** API via the `API_URL` env var; not part of `make test`.

`tests/conftest.py` adds `src/` to the import path. Run: `cd services/pledges_api && python -m pytest tests/ -v`.
