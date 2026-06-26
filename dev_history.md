# Development history

Chronological log of notable changes to this repository. Newest first. Each entry: what changed, why,
and how it was verified. Companion to `CLAUDE.md` (developer quick-start) and `docs/architecture.md`.

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

## Planned next (privacy & data-model hardening)

The data model changes early, while only test data exists (cheap now, painful once real friends pledge).
Test data in the live table + the repo-root `*.json` fixtures will be reset as part of this work.

1. **Drop `name`** from the model, validation, handlers, and frontend (never stored, never displayed).
2. **Harden `/pledges/by-email`** to return only the caller's own pledge fields (no PII leak).
3. Keep `email` stored **as-is (no hashing)** — used only to recognize a returning pledger so they can
   edit their own pledge.
4. **Canonicalize stats on `contributors_count`** (remove frontend `pledgers_count` reads).
5. Add **one shared `response()`/`DecimalEncoder` util** for all handlers.
6. Add **upper bounds** on `amount` and `contributors_count`.

Followed by: a one-command local quality gate (ruff + pytest/moto), editable numbers via a `CONFIG` row +
admin endpoint, CZ/EN i18n, calculator UX, the post-pledge payment page, then AWS deploy + custom domain.
