// Configuration
// Edit these values as needed

const CONFIG = {
  // API URL — the deployed API Gateway base. Currently the dev stack
  // (FundraisingCalculatorStack, eu-central-1). Prod gets its own URL at the
  // domain/HTTPS phase (or a same-origin path behind CloudFront).
  API_URL: 'https://wcu3d2uaf2.execute-api.eu-central-1.amazonaws.com',

  // Cognito user pool for site login (AUTH1/AUTH2, decision D18). These are the
  // dev stack's CDK outputs (UserPoolId / UserPoolClientId). The client is a
  // public no-secret browser client (SRP). Per-stage, like API_URL above — prod
  // gets its own pool/client. The region is implied by the pool id prefix.
  COGNITO: {
    REGION: 'eu-central-1',
    USER_POOL_ID: 'eu-central-1_VyVmN4qrS',
    CLIENT_ID: '7b2o4arvk4j5nfpaeh44plg5kc',
  },

  // Fallback defaults in **canonical CZK** (D22). The live values come from
  // GET /config (the editable CONFIG row) and are already converted to the page
  // currency by the API; these are used only if that request fails. The breakdown
  // stores stable keys — the localized labels live in the i18n dict.
  CURRENT_BALANCE: 7750400, // Real money in account (CZK; ≈ €320k)
  FUNDRAISING_GOAL: 70000000, // Target amount (CZK; ≈ €2.89M)
  BREAKDOWN: [
    { key: 'new_gompa', amount: 29064000 },
    { key: 'sangha_house', amount: 29064000 },
    { key: 'basecamp_north', amount: 7750400 },
  ],
};

// The display currency follows the page language (decision D22): Czech → CZK,
// English → EUR. The active language is read from <html lang>, which i18n.js keeps
// in sync. The API does the actual conversion server-side; the frontend only sends
// this code (?currency=) and formats the already-converted numbers with the symbol.
function currentCurrency() {
  return document.documentElement.lang === 'en' ? 'eur' : 'czk';
}

// Append the current ?currency= to an API path (handles an existing query string),
// so every money-bearing request tells the backend which currency to return/accept.
function withCurrency(path) {
  const sep = path.indexOf('?') === -1 ? '?' : '&';
  return `${path}${sep}currency=${currentCurrency()}`;
}

// Dev-only API override: point the site at a different API without editing this
// file — e.g. a local dev API while the real one isn't deployed yet. Pass
// `?api=http://localhost:8127` (remembered in localStorage), or `?api=` to clear.
// Only honored when the page itself is served from localhost, so a crafted
// `?api=…` link can never repoint the deployed site at another host. No effect in
// production: with no query param and no stored value, API_URL above is used unchanged.
(function () {
  const host = window.location.hostname;
  if (host !== 'localhost' && host !== '127.0.0.1') {
    return;
  }
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.has('api')) {
      const value = params.get('api');
      if (value) {
        localStorage.setItem('tenovice.apiOverride', value);
      } else {
        localStorage.removeItem('tenovice.apiOverride');
      }
    }
    const override = localStorage.getItem('tenovice.apiOverride');
    if (override) {
      CONFIG.API_URL = override;
    }
  } catch (error) {
    /* query/localStorage unavailable — keep the default API_URL */
  }
})();

// Fetch the editable campaign numbers from the API and override the fallbacks.
// On any failure we keep the hardcoded defaults so the site still renders.
async function loadConfig() {
  try {
    const response = await fetch(`${CONFIG.API_URL}${withCurrency('/config')}`);
    if (!response.ok) {
      throw new Error('Failed to fetch config');
    }

    const data = await response.json();
    if (typeof data.current_balance === 'number') {
      CONFIG.CURRENT_BALANCE = data.current_balance;
    }
    if (typeof data.fundraising_goal === 'number') {
      CONFIG.FUNDRAISING_GOAL = data.fundraising_goal;
    }
    if (Array.isArray(data.breakdown)) {
      CONFIG.BREAKDOWN = data.breakdown;
    }
  } catch (error) {
    console.error('Error loading config, using defaults:', error);
  }
}

// Helper functions
function calculateProgress(current, goal) {
  return Math.round((current / goal) * 100);
}

// Format a money value with the symbol of the current page currency (D22). The
// value is already in that currency (the API converted it), so this only picks the
// symbol/locale: CZK → "2 500 Kč" (cs-CZ), EUR → "€2,500" (en).
function formatCurrency(amount) {
  const eur = currentCurrency() === 'eur';
  return new Intl.NumberFormat(eur ? 'en' : 'cs-CZ', {
    style: 'currency',
    currency: eur ? 'EUR' : 'CZK',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}
