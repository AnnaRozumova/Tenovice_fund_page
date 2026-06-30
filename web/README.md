# Tenovice Fundraising Frontend

Simple, static landing page for the Tenovice fundraising campaign.

## Quick Start

Just open `index.html` in your browser! No installation needed.

## Configuration

Edit `config.js` to update:

```javascript
const CONFIG = {
  // Your API URL
  API_URL: 'https://your-api-id.execute-api.region.amazonaws.com',

  // Hardcoded values
  CURRENT_BALANCE: 12500,  // Update this manually
  FUNDRAISING_GOAL: 50000, // Update this manually
};
```

## Customization

### Add Logo
1. Place your logo file (e.g., `logo.png`) in the `web/` folder
2. Edit `index.html`, replace:
   ```html
   <div class="logo-placeholder">LOGO</div>
   ```
   with:
   ```html
   <img src="logo.png" alt="Tenovice Logo" style="max-height: 80px;">
   ```

### Add Images
1. Place images in `web/images/` folder
2. Edit `index.html`, replace image placeholders:
   ```html
   <div class="image-placeholder">Image 1</div>
   ```
   with:
   ```html
   <img src="images/your-image.jpg" alt="Description">
   ```

### Edit Text
Simply edit the HTML in `index.html`:
- Title: `<h1 class="title">`
- Description: `<p class="description">`

## Deploy to S3

### Option 1: AWS CLI
```bash
# Configure AWS CLI first
aws configure

# Sync to S3 bucket
aws s3 sync . s3://your-bucket-name --exclude ".git/*" --exclude "README.md"

# Make bucket public for website hosting
aws s3 website s3://your-bucket-name --index-document index.html
```

### Option 2: AWS Console
1. Open S3 console
2. Create/select your bucket
3. Upload all files: `index.html`, `style.css`, `config.js`, `main.js`, and any images
4. Go to bucket Properties → Static website hosting → Enable
5. Set index document: `index.html`
6. Go to Permissions → Edit bucket policy (make public)

### Example Bucket Policy for Public Access
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

## Files

```
web/
├── index.html      # Home page (progress + stats); CTA routes to auth/pledge
├── auth.html       # Login / register / verify / reset screens (Cognito, AUTH2)
├── pledge.html     # Pledge calculator (gated behind login; create/edit, simulator)
├── success.html    # Post-pledge confirmation
├── admin.html      # Internal admin: edit balance/goal/breakdown (English only)
├── style.css       # Styling
├── config.js       # API URL + COGNITO (pool/client ids) + fallback defaults; loads GET /config
├── i18n.js         # CZ/EN dictionary + toggle (see "Languages")
├── main.js         # Home-page logic
├── auth.js         # Auth-screens logic (Cognito SRP)
├── auth-common.js  # Shared session/token helper `Auth` (requireAuth, apiFetch bearer token)
├── pledge.js       # Pledge-page logic
├── admin.js        # Admin-page logic
├── vendor/         # amazon-cognito-identity.min.js (vendored, no build step)
└── README.md       # This file
```
(Parity checker lives outside `web/` at `tools/check-i18n-parity.js`.)

## Authentication (AUTH2)

Login required for the pledge flow (the home page stays public). Users sign in / register / verify their
email / reset their password through the on-site `auth.html` screens, which talk to a **Cognito user pool**
via the vendored `amazon-cognito-identity-js` (SRP — no build step). Set the pool in `config.js`:

```javascript
COGNITO: {
  REGION: 'eu-central-1',
  USER_POOL_ID: 'eu-central-1_xxxxxxxxx', // CDK output UserPoolId
  CLIENT_ID: 'xxxxxxxxxxxxxxxxxxxxxxxxxx', // CDK output UserPoolClientId
},
```

It's **per-stage like `API_URL`** (prod gets its own pool/client). The screens talk to Cognito directly, so
you can test register→verify→login locally against a deployed dev pool. The API itself is still open until
the AUTH3 authorizer; `auth-common.js` already attaches the id-token as a bearer header on every API call.

## Features

- ✅ No build tools needed
- ✅ Works directly in browser
- ✅ Fully responsive design
- ✅ Live pledge statistics from API
- ✅ Animated progress bar
- ✅ Ready for S3 static hosting

## Testing Locally

Serve the site over HTTP — don't open `index.html` from `file://`, API calls get blocked by CORS.

**One command, from the repo root:**
```bash
bash ./serve.sh          # serves web/ at http://localhost:8000 (Linux/macOS/CI)
bash ./serve.sh 8080     # custom port
```
On Windows the equivalent is `pwsh ./serve.ps1` (`-Port 8080` for a custom port). Both serve `web/` on
Python 3.14 and send `Cache-Control: no-store` so edits show on a normal refresh.

The **API base is a single config value** — `CONFIG.API_URL` in `config.js`. It defaults to the live
dev API, so the calculator shows real data locally; point it at another API if you need to.

**Plain Python (any OS):**
```bash
cd web
python -m http.server 8000    # open http://localhost:8000 (no no-cache header)
```

## Languages (i18n)

The public pages are bilingual — **Czech (default) and English** — with a subtle `CS · EN` toggle in the
top-right of each page. All user-facing strings live in **one dictionary**, `web/i18n.js`
(`TRANSLATIONS.cs` / `TRANSLATIONS.en`, flat keys like `index.heroTitle`).

- **Markup** is tagged with `data-i18n="key"` (text), `data-i18n-html="key"` (HTML, e.g. `<strong>`),
  or `data-i18n-placeholder` / `data-i18n-alt` / `data-i18n-aria-label`.
- **JS-rendered** strings use `t('key')` (with `{param}` interpolation, e.g. `t('sim.durationMonths', { n: 6 })`).
- The chosen language is stored in `localStorage` and `<html lang>` follows it. Adding a third language
  (the structure is DE-ready) = add a `de` block with the same keys.
- `admin.html` is an internal tool and stays English (not part of the public i18n).

**Parity check** — every language must define exactly the same keys. Run from the repo root:
```bash
node tools/check-i18n-parity.js
```
It exits non-zero and lists any missing/extra key, so a half-translated string can't ship.
