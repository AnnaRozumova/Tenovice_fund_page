# Development history

Chronological log of notable changes to this repository. Newest first. Each entry: what changed, why,
and how it was verified. Companion to `CLAUDE.md` (developer quick-start) and `docs/architecture.md`.

---

## 2026-06-29 — AUTH1: Cognito user pool + app client (identity store, no authorizer yet)

**Why:** start Phase AUTH (D18) — the whole API incl. the calculator moves behind a login; only the home
page stays public. First step is the **identity store** every later step builds on. Built so deploy is
safe: **no authorizer is attached to the API**, so the API and site keep working unchanged.

**What:** new `cdk/src/constructs/cognito.py` — a Cognito **user pool** + a **public (no-secret) app
client**, wired into `stack.py` (outputs `UserPoolId` / `UserPoolClientId`). Config:
- email is the username; **self sign-up** + **email verification**; **email-only** password recovery.
- **strong password policy**: min 12 chars, lower + upper + digit + symbol.
- app client: no secret, **SRP** auth flow (for custom on-site login screens via
  `amazon-cognito-identity-js` — the chosen UI approach; see below), `prevent_user_existence_errors` on
  (email is the identity, so don't leak whether an address is registered), tokens id/access 1 h, refresh 30 d.
- dev pool is disposable (`DESTROY`); **prod pool is `RETAIN` + deletion-protected** (a future immutable-prop
  change would otherwise REPLACE the pool and orphan every account).
- built-in Cognito email sender (~50/day cap — fine at our scale; SES is a later prod follow-up).

**UI approach decided = custom on-site screens (not Cognito Hosted UI).** Reasons: (1) Hosted UI callback
URLs must be HTTPS (only `http://localhost` is exempt) and the dev site is HTTP-only until the
CloudFront/HTTPS phase (G) — custom screens talk to Cognito directly from JS and work on HTTP now; (2) the
requested "your email is safe" note belongs *in the registration form*, which Hosted UI can't host cleanly.
Custom screens also reuse the site's own design.

**Verification:** `cdk/src` ruff clean; the construct synthesizes to valid CloudFormation for **both** dev
(disposable, `DeletionProtection INACTIVE`) and prod (`Retain` + `DeletionProtection ACTIVE`) via
`assertions.Template` (no Docker needed — only the Lambda asset bundles). Services gate unaffected: **90
passed**. Full `cdk synth`/deploy (Docker) is run at deploy time on the dev account.

**Open product decision (raised, not resolved) — pre-AUTH3:** self sign-up is **open to anyone**. Once
AUTH3 attaches the JWT authorizer, a stranger can still self-register and obtain a valid token, so the gate
keeps out only people unwilling to register, not "randoms". If friends-only is wanted, add a pre-sign-up
Lambda trigger (invite / email allowlist) before AUTH3. Pledges stay anonymous regardless (no names; by-email
returns only the caller's own row).

---

## 2026-06-29 — Docs: point CLAUDE.md / architecture.md at the current live dev API

`CLAUDE.md` and `docs/architecture.md` still named the old `tbaulwfk46…` dev API (with the old
`228150 / 19 / 12200` test stats). Updated both to the current deployed dev API
`https://wcu3d2uaf2.execute-api.eu-central-1.amazonaws.com` (fresh table → zeros) + the dev site URL, and
documented the CORS-preflight middleware (see the CORS fix below). Docs-only; no code/behaviour change.

---

## 2026-06-29 — Fix: CORS preflight (OPTIONS) returned 405 → browser blocked POSTs

**Why:** after the first dev deploy, the deployed site's **calculator and pledge save failed in the browser**
("Výpočet/Příslib se nepodařilo…"), even though direct `curl` worked. Cause = CORS: the browser sends a
preflight `OPTIONS` before each POST; that preflight is forwarded through the single `ANY /{proxy+}` route
into FastAPI, which has no OPTIONS handler and returned **405**. A non-2xx preflight makes the browser block
the actual POST. (API Gateway already adds the CORS headers — only the status was wrong.)

**Fix:** `services/pledges_api/src/app.py` — an HTTP middleware answers every `OPTIONS` with **204** before
routing. (Not a catch-all `@app.options("/{path}")` route — that registers every path and would turn
unknown-path GETs into 405 instead of 404; caught by the existing proxy test.) API Gateway attaches the CORS
headers in front of the 204.

**Verification:** gate green — ruff clean, **90 passed** (+1 proxy test: `OPTIONS /calculate` → 204;
unknown-path GET still 404). Browser POSTs (calculator/save) work after a redeploy.

**Not a bug:** the supporters count showing **0** (not the old 19) on the fresh dev table is expected — the
new stack has its own empty DynamoDB table; the 19 was test data on a previous API.

---

## 2026-06-29 — F1: first dev deploy of Phase R + point the web at the live dev API

**Why:** deploy the new architecture (Phase R — FastAPI/Mangum, Python 3.14) to the dev AWS account and verify
it on real infrastructure (the Docker-bundled Lambda asset had only ever been built locally).

**Deploy:** `cdk deploy -c stage=dev` to the dev account (eu-central-1), stack `FundraisingCalculatorStack`.
Outputs: API `https://wcu3d2uaf2.execute-api.eu-central-1.amazonaws.com`, S3 website
`fundraising-calculator-dev-026268603137-website`. WAF not deployed on dev (stage-conditional, D21) → €0.

**Live verification (real AWS):** `GET /stats` → 200 zeros; `GET /config` → 200 documented defaults;
`GET /pledges` → 200 `[]`; `POST /calculate` → 200 with correct monthly impact (3×100×19 = 5700 + projection
vs goal); `GET /pledges/by-email` (unknown) → 404; `POST /config` wrong secret → 401; unknown path → 404
(FastAPI). The whole FastAPI/Mangum proxy on Python 3.14 runs on the live Lambda — Phase R confirmed.

**What changed (this PR):**
- `web/config.js` — `API_URL` now points at the deployed dev API (`wcu3d2uaf2`), replacing the stale
  `tbaulwfk46` (a previous stack) so the deployed site's calculator hits the live API. Prod gets its own URL
  at the domain phase (or a same-origin path behind CloudFront).

**Follow-up:** redeploy so the S3 site serves the updated `config.js`.

---

## 2026-06-29 — Fix: exclude the CONFIG sentinel row from `GET /pledges`

**Why:** the public anonymous list (`list_pledges`) filtered out the `STATS` sentinel row but **not**
`CONFIG` (added later, in C1). So once a `CONFIG` row exists, the public list returned a phantom
zero-amount pledge (all-null fields) for it. Found during R3 local testing.

**What changed:**
- `services/pledges_api/src/api/pledges.py` — the list comprehension guard is now
  `if item.get("pledgeID") not in ("STATS", "CONFIG")` (was `!= "STATS"`); added a comment so the
  sentinel exclusion isn't dropped again.
- `services/pledges_api/tests/integration/test_list_pledges.py` (new) — seeds STATS + CONFIG and asserts
  `GET /pledges` returns an empty list (no phantom row), plus a real-pledge case proving the pledge is
  listed while the sentinels (and the email / pledgeID) are not.

**Verification:** quality gate green — ruff clean, **89 passed** (was 87; +2 new). **Not deployed.**

---

## 2026-06-29 — CI/CD: GitHub Actions pipeline (CI gate + stage-aware deploy, WAF prod-only)

**Why:** add a GitHub Actions pipeline (Ondra). CI runs the quality gate on every PR; CD deploys the CDK
stack per stage, with WAF prod-only (decision D21).

**What changed:**
- `.github/workflows/ci.yml` — on PR + push to `main`: ruff + pytest on **Python 3.14** (the same gate as
  `check.sh`) + the CZ/EN i18n parity check. No AWS.
- `.github/workflows/deploy.yml` — manual (`workflow_dispatch`) deploy with a `stage` input (dev/prod). AWS
  auth via **OIDC** (no static keys); `cdk deploy -c stage=<stage>` (Docker on the runner bundles the
  FastAPI/Mangum Lambda asset). **The stage drives WAF: `dev` = no WAF (€0), `prod` = WAF (D21).** Uses
  GitHub Environments (`dev`/`prod`) for per-account secrets (`AWS_DEPLOY_ROLE`, `ADMIN_SECRET`).

**Prerequisites before CD can run** (documented in `deploy.yml`): create the `dev`/`prod` GitHub Environments
with the OIDC role + admin secret; `cdk bootstrap` once per account/region (eu-central-1). The WAF *resource*
itself lands with the prod front end (**CloudFront** — AWS WAF cannot attach to an API Gateway HTTP API
directly), so the pipeline is stage-ready now and WAF switches on for prod once that construct exists.

**Verification:** both workflow files parse (jobs: ci=`gate`, deploy=`deploy`); i18n parity passes (136 keys);
the ruff + pytest gate is green on 3.14 (87 passed, from R2). CD not executed here (needs the OIDC secrets +
bootstrap). **Not deployed.**

---

## 2026-06-29 — R3: confirm the frontend is proxy-ready (no re-point needed)

**Why:** R1 put the whole API behind one `ANY /{proxy+}` route — check whether the frontend's API base or
any path needs to change to keep working.

**Finding — no frontend change needed.** The proxy preserves every route path (`/stats`, `/pledges`,
`/pledges/by-email`, `/config`, `/calculate`) and the `$default` API Gateway stage adds no base-path prefix,
so the single API-base knob — `CONFIG.API_URL` in `web/config.js` — and every `${CONFIG.API_URL}/<path>`
fetch in `main.js` / `pledge.js` / `admin.js` keep working unchanged. There is still exactly one API-base
config value; a grep confirms no other hardcoded API URL in `web/`. No `web/` code was changed.

**Verification:** exercised every endpoint the frontend calls against the FastAPI app behind the proxy —
`GET /stats` `/config` `/pledges` (200), `POST /calculate` (200, correct one-time/monthly impact +
projection), `POST /config` with a wrong/empty admin secret (401), `OPTIONS` preflight (204), and an unknown
path (404 from FastAPI). All respond as the site expects.

**Note (pre-existing, out of R3 scope):** `GET /pledges` excludes the `STATS` sentinel row but not `CONFIG`,
so once a `CONFIG` row exists (since C1) the public list includes a phantom zero-amount pledge. Tracked
separately as a follow-up; not changed here.

This completes Phase R — **R1** (FastAPI app behind the proxy) · **R2** (Python 3.14) · **R3** (frontend
confirmed proxy-ready). **Not deployed.**

---

## 2026-06-29 — R2: Python runtime bump 3.11 → 3.14 (+ Mangum 0.19 → 0.21)

**Why:** standardize on the newer, supported Lambda runtime (decision D20). Small change in principle —
swap `3.11` for `3.14` in the CDK runtime, the local gate/venv, the serve scripts, and the ruff target.

**What changed:**
- `cdk/src/constructs/lambdas.py` — `_lambda.Runtime.PYTHON_3_11` → `PYTHON_3_14` (both the function `runtime`
  and the bundling `image`).
- `check.ps1` / `check.sh` — bootstrap the local `.venv` with Python 3.14 (`py -3.14` / `python3.14`).
- `serve.ps1` / `serve.sh` — static server on 3.14.
- `services/pledges_api/pyproject.toml` — ruff `target-version = "py314"`.
- `cdk/pyproject.toml` — `requires-python = ">=3.14"`.
- `services/pledges_api/requirements.txt` + `requirements-test.txt` — **Mangum `>=0.18,<0.20` → `>=0.21,<0.22`**.
- `tests/conftest.py` — unchanged (it carries no Python-version reference, only the moto AWS region/creds).

**The catch — Mangum had to move with the runtime.** The prompt's "verify FastAPI + Mangum + moto + boto3 on
3.14 first" caught a real incompatibility: **Mangum 0.19 fails on Python 3.14**. Its HTTP protocol calls
`asyncio.get_event_loop()` with no running loop, which on 3.14 raises `RuntimeError` (3.14 removed the old
behavior of silently creating one). Three proxy-event tests failed, and the live Lambda would have failed
identically (Mangum is the entrypoint). Fix: **Mangum 0.21** (released 2026-02, declares 3.14 support; its
`adapter.py` adds `_setup_event_loop()` — on the `RuntimeError` it creates and sets a new loop). The narrow
`<0.20` pin had to be widened to allow it.

**Verification:** quality gate green on a freshly rebuilt **Python 3.14.3** `.venv` — `ruff` clean,
**87 passed** (the 3 `test_proxy_event.py` Mangum tests now pass on 3.14). CDK: `Runtime.PYTHON_3_14` and its
`bundling_image` resolve in the installed `aws-cdk-lib` (full `cdk synth` needs Docker — deferred to deploy,
same as R1). No `3.11` / `py311` / `PYTHON_3_11` references remain in tooling/code. **Not deployed.**

---

## 2026-06-28 — R1: backend re-architecture — 7 Lambdas → one FastAPI app (Mangum) behind a proxy route

**Why:** the backend was 7 per-endpoint Lambdas, each its own file re-creating a DynamoDB resource and
re-defining the response/encoder — duplicated boilerplate that had to be changed in every file. R1 collapses
them into **one Lambda running a FastAPI app via Mangum, behind a single API Gateway `ANY /{proxy+}` route**;
shared concerns are imported once. Adding/changing an endpoint becomes a code change in FastAPI, no
CDK/API-GW edit. **Behavior and the JSON contracts are unchanged** — this is a re-shape, not a rewrite (the
framework-agnostic domain/validation/pledge-math moved across untouched).

**What changed (`services/pledges_api/src/`):**
- **New `app.py`** — `FastAPI(redirect_slashes=False)` including four routers; `handler = Mangum(app, lifespan="off")`
  is the Lambda entrypoint.
- **New `api/` package** — routes grouped by resource: `stats.py` (`GET /stats`), `pledges.py`
  (`GET /pledges`, `POST /pledges`, `GET /pledges/by-email`), `config.py` (`GET`/`POST /config`),
  `calculate.py` (`POST /calculate`). Each route calls the shared domain logic and returns via a shared
  `json_response`.
- **New shared modules:** `db.py` (`get_table()` — one cached boto3 resource, replacing the per-file
  `boto3.resource(...)`), `utils/http.py` (`DecimalJSONResponse` / `json_response`, reusing the existing
  `DecimalEncoder`), `config_defaults.py` (the `DEFAULT_*` campaign numbers, moved out of the old
  `get_config` handler so the config + calculate routes share them).
- **Removed** the whole `handlers/` package (the 7 `handler(event, context)` modules). The old
  `utils/response.py` `response()` Lambda-proxy envelope is gone too (Mangum builds the envelope now);
  only `DecimalEncoder` remains there, reused by the FastAPI response.
- **Runtime deps:** new `requirements.txt` (fastapi, mangum — boto3 stays runtime-provided); `requirements-test.txt`
  adds fastapi/mangum/httpx (tests import the app and drive it via `TestClient`).

**CDK (`cdk/`):**
- `constructs/lambdas.py` — the 7 `_lambda.Function`s become **one** (`...-dev-api`, handler `app.handler`),
  whose asset is **Docker-bundled** (`pip install -r requirements.txt -t /asset-output && cp -r src/. /asset-output`)
  so FastAPI/Mangum ship with the code. One `grant_read_write_data` (the single function serves reads, the
  simulator, and the admin write). `LambdaHandlers` dataclass removed.
- `constructs/apigw.py` — the 7 routes become **one** `ANY /{proxy+}` → `HttpLambdaIntegration` to the function;
  CORS preflight kept at the gateway. `stack.py` passes `api_function=` instead of `handlers=`.

**Tests:** the 6 integration suites were rewritten from `handler(event, context)` calls to FastAPI's
**`TestClient(app)`** (real routing through the whole app). Added **`test_proxy_event.py`** — feeds a real
API Gateway HTTP API v2 proxy event through `app.handler` (Mangum), locking that the `ANY /{proxy+}` path is
reconstructed so the routes match (the one thing `TestClient` can't exercise). Unit tests unchanged except
`test_response.py` (trimmed to `DecimalEncoder`, since `response()` is gone).

**Verification:** quality gate green — `ruff` clean, **87 passed** (was 86: +3 proxy-event, −2 removed
envelope tests). CDK structure confirmed by `cdk synth`: **1 application Lambda** (`fundraising-calculator-dev-api`,
`app.handler`) + **1 route `ANY /{proxy+}`** (down from 7 + 7), env `PLEDGES_TABLE_NAME` + `ADMIN_SECRET`.
The Docker bundle/deploy runs at deploy time (Docker was off locally; structure verified with bundling skipped).
`/code-review` (high) findings folded in: cached the boto3 resource, wrapped `by-email` in ClientError→500,
unified the email-query style, `redirect_slashes=False` + `lifespan="off"`, removed the dead `response()`.
Net diff ≈ **−780 lines**. **Runtime stays Python 3.11** (the 3.14 bump is the next step, R2). **Not deployed.**

**Watch item (D9):** the single `Mangum(app)` has no `api_gateway_base_path`. Fine on the `$default` stage
(no path prefix); when the custom domain / CloudFront lands (G1/D9), confirm the base path is stripped so the
FastAPI routes still match.

---

## 2026-06-26 — S3 website bucket name is account-unique (multi-account dev/prod)

**Why:** S3 bucket names are **globally unique across all of AWS**. The name was
`{project_name}-{stage}-website` (e.g. `fundraising-calculator-dev-website`), so the moment the app is
deployed from a **second account** — a per-developer dev account alongside the shared one — the bucket name
clashes and `cdk deploy` fails (`...already exists`). Hit live on the first dev-account deploy; worked
around then with a one-off `-c project_name=…` override.

**Fix** (`cdk/src/constructs/s3_website.py`): bucket name is now
`{project_name}-{stage}-{Aws.ACCOUNT_ID}-website`. The account id guarantees cross-account uniqueness;
`stage` still separates environments within one account. The id is a CloudFormation token resolved at
deploy time (renders as `Fn::Join[…, {Ref: AWS::AccountId}, …]`).

**Verified:** `cdk synth` renders the account-id join; `cdk deploy` to the dev account (026268603137) with
the **default** `project_name` (no override) now succeeds → bucket `fundraising-calculator-dev-026268603137-website`.
Enables the dev (agent's account) / prod (Anna's account) split without name collisions.

---

## 2026-06-26 — P1: `get_stats` returns zeros on an empty table (no more 500)

**Why:** a follow-up tracked in H1. `GET /stats` crashed with a **500** whenever the `STATS` row was absent —
which is the normal state of a freshly deployed table, before the first pledge exists. Surfaced live during
the first dev-account deploy: `GET /stats` → 500 on the empty table, while every other endpoint answered.

**Fix** (`handlers/get_stats.py`): `resp.get("Item")` returns `None` when the row is missing, and the
following `stats.get(...)` then raised `AttributeError` on `None` — uncaught (the `except` only caught
`ClientError`) → 500. Changed to `stats = resp.get("Item") or {}`, so the totals fall back to the existing
`Decimal("0")` / `0` defaults and the handler answers **200** with zeros.

**Verified:** new `tests/integration/test_get_stats.py` — populated `STATS` returns the row; empty table
returns 200 with zeros (regression guard for P1). Quality gate green: ruff clean, **86 passed**.

---

## 2026-06-23 — H1: pre-deploy security & quality review pass (+ low-severity hardening)

**Why:** before deploy (Phase F) and real anonymous pledges, run one cross-cutting security + quality review
over the **whole A–E change set vs `main`** (53 files) — the check no single per-step review saw at once.
Scope (H1): privacy/PII, admin-secret handling, input bounds, CORS. No AWS (local).

**Review.** Multi-agent pass across six dimensions (privacy, admin-secret, input-validation, infra/CORS/IAM,
frontend-XSS, general correctness), each finding then independently verified. **Result: 0 critical / 0 high /
0 medium.** Verified clean: admin secret (D6 — `hmac.compare_digest`, fails closed, never in repo/logs),
frontend XSS (pledge `message` rendered via `textContent`, not `innerHTML`), privacy core (`name` gone,
by-email allowlist, email off public endpoints, no PII in logs).

**Fixed (low/info, in scope):**
- **L1 — non-finite numbers** (`domain/validation.py`): `NaN`/`Infinity` in `amount` passed validation, then
  raised an uncaught exception (a `NaN` comparison → `InvalidOperation`; `Infinity` on the uncapped
  `/calculate` path → crash in the JSON encoder) → **HTTP 500**. Added an `is_finite()` guard in
  `_require_positive_decimal`; the int helpers reject fractional floats (silent `int()` truncation) and catch
  `OverflowError`; `_validate_end_date` catches `OverflowError` too. All return a clean **400** now.
- **L2 — error-detail leak:** the six handler `500` responses returned the internal `str(e)`/boto text to the
  client (a `"detail"` field). Removed — generic message only.
- **I1 — by-email minimization:** dropped `email` from the `get_pledge_by_email` allowlist (the caller
  supplied it in the query; echoing it back disclosed nothing). Coordinated frontend change in `web/pledge.js`
  (the existing-pledge summary now shows the entered email).
- **I2 — config truncation:** integer CONFIG fields silently truncated non-integer numeric input — now
  rejected ("must be a whole number").

**Deferred (triaged):** wildcard CORS (`allow_origins=["*"]`) on the API that also hosts `POST /config` →
lock origins at **G1** (needs the real domain); pre-existing robustness — `get_stats` 500s when the STATS row
is absent, and `create_pledge`'s read-then-write STATS upsert isn't atomic (race → double-count; near-zero
risk at our scale) → follow-ups; backend accepts fractional EUR while the UI assumes whole EUR → follow-up;
the public list echoes the user's free-text `message` (self-deanonymization if they type their own identity)
→ a copy hint for Anna when the calculator copy is drafted.

**What changed:** `domain/validation.py`; handlers `calculate.py`, `list_pledges.py`, `create_pledge.py`,
`update_config.py`, `get_config.py`, `get_stats.py`, `get_pledge_by_email.py`; `web/pledge.js`; tests
`test_validation.py` (+7), `test_get_pledge_by_email.py` (email no longer echoed).

**Verification:** gate green — `ruff` clean, **84 passed** (was 77; +7 H1 tests: NaN/Infinity on `/pledges`
& `/calculate`, fractional/Infinity config, by-email email-not-echoed). No AWS; not deployed.

---

## 2026-06-23 — E1: success page shows payment details (QR / standing order)

**Why:** a pledge is only a public promise — no money moves through the site. After saving, the user must
send the gift themselves, so the success page now shows the right payment path for the pledge they made
(decision: Phase E). Frontend-only — no Python/CDK change.

**What changed (all under `web/`):**
- **`success.html`** (rewritten) — added a payment section below the thank-you card. The pledge **type**
  decides the path: **one-time → QR codes**, **monthly → standing-order bank details** (a recurring order
  can't be a single QR payment). Two **paired panels** (`.payment-col`): each pairs a QR (one-time only)
  **above its own account window** — Czech account (CZK) and International account (EUR) — so on mobile a QR
  sits directly above the window it belongs to. Every value (account number, variable symbol, IBAN, BIC,
  purpose, message) is **copyable** via a copy button. The language toggle moved out of the card corner into
  the header, right-aligned under the logo (`.header-row` wrapper).
- **`success.js`** (new) — reads `?type=one-time|monthly` from the URL, swaps the heading/intro `data-i18n`
  keys and toggles the QR figures (`[data-qr]`) vs the standing-order note, and wires the copy buttons.
  Copy reads a literal `data-copy-target` (e.g. the IBAN without spaces) **or** the live text of an element
  via `data-copy-el` (the localized message value). Clipboard uses `navigator.clipboard` with an
  `execCommand` fallback for non-secure contexts. Re-applies the type-dependent copy on `i18n:changed`.
- **`pledge.js`** — after a successful save, the redirect carries the type: `success.html?type=<one-time|monthly>`.
- **`i18n.js`** — added the `payment.*` keys (CZ + EN). The bank **message** value is localized
  (`payment.messageValue`: `Prijmeni/Dar/Tenovice` / `Surname/Gift/Tenovice`).
- **`style.css`** — payment-card (brand-red top accent), two-column panels collapsing to one on ≤640 px,
  bank-detail rows + copy buttons (top-aligned so the button stays beside a wrapped IBAN), header-row wrapper.
- **`pledge.html`** — dropped the `header-banner` class so the logo is its natural (home-page) size; the dead
  `.header-banner` CSS was removed (no page used it after this).
- **`web/images/qr_cz.jpg`, `qr_intl.jpg`** — the QR images from the dw-connect source materials.

**Payment details** (verified against the dw-connect source): CZ acct `19-2247060207/0100`, variable symbol
`YYMMDD0108`, message `Surname/Gift/Tenovice`; INTL `International Diamondway Buddhism Foundation`, GLS Bank,
IBAN `DE24 4306 0967 0046 9538 18`, BIC `GENODEM1GLS`, purpose `TENOVICE`.

**What did NOT change:** no backend/CDK/JS pledge logic. Bundled in were a few review-driven cosmetic tweaks
across pages (home hero: dropped `hyphens` so "directions" no longer breaks mid-word, centered the dw-connect
link; consistent natural-size logo on pledge/calc).

**Verification:** gate green (`ruff` clean, **77 passed**), i18n parity **136=136**, `/code-review` = no
findings (no orphaned selectors, IBAN strip correct, all `data-i18n` keys present in both languages). Measured
in-browser via `getBoundingClientRect` (screenshot tool unavailable): one-time shows QR + bank panels, monthly
hides QR and shows the standing-order note; each QR centered above its window (desktop) / stacked above it
(mobile, order QR-CZ → CZ window → QR-INTL → INTL window); copy buttons resolve the right value incl. the
localized message; CZ↔EN switch re-renders; no horizontal overflow at 375 / 1000 / 1280 px. The full
save→success flow was driven end-to-end against the local dev-API harness (real handlers over moto).

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
