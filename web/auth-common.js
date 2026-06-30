// Shared auth/session helpers (AUTH2, decision D18). Loaded on every page that
// needs to know who is signed in: the home page (CTA routing + sign-out), the
// pledge page (login gate + token on API calls), and the auth screens.
//
// Identity lives in AWS Cognito (the dev/prod user pool from AUTH1). We use the
// vendored `amazon-cognito-identity-js` (web/vendor/, no build step) which does
// the SRP login — the password is never sent to our code, only an SRP proof to
// Cognito — and stores the resulting tokens in localStorage, keyed by the app
// client id. `getSession()` transparently refreshes an expired id/access token
// from the 30-day refresh token, so callers just ask for a fresh token.
//
// NOTE (AUTH2 scope): the API itself is still open at this point — the Cognito
// JWT authorizer lands in AUTH3. We already attach `Authorization: Bearer <idToken>`
// to every API call here so nothing has to change on the frontend when the
// authorizer is switched on.

const Auth = (function () {
  // Cognito user-pool handle, built from the per-stage config (web/config.js).
  function userPool() {
    return new AmazonCognitoIdentity.CognitoUserPool({
      UserPoolId: CONFIG.COGNITO.USER_POOL_ID,
      ClientId: CONFIG.COGNITO.CLIENT_ID,
    });
  }

  // The most recently authenticated user, restored from localStorage (or null).
  function currentUser() {
    return userPool().getCurrentUser();
  }

  // Resolve to a valid CognitoUserSession, or null if signed out / unrecoverable.
  // getSession() refreshes the tokens with the refresh token when they expired.
  function getSession() {
    return new Promise((resolve) => {
      const user = currentUser();
      if (!user) {
        resolve(null);
        return;
      }
      user.getSession((err, session) => {
        if (err || !session || !session.isValid()) {
          resolve(null);
          return;
        }
        resolve(session);
      });
    });
  }

  // The id-token JWT for API calls (sent as the bearer token), or null.
  async function getIdToken() {
    const session = await getSession();
    return session ? session.getIdToken().getJwtToken() : null;
  }

  // The signed-in user's email, read from the verified id-token claims.
  async function getEmail() {
    const session = await getSession();
    if (!session) {
      return null;
    }
    const claims = session.getIdToken().decodePayload();
    return claims.email || claims['cognito:username'] || null;
  }

  function signOut() {
    const user = currentUser();
    if (user) {
      user.signOut();
    }
  }

  // Gate a page: if not signed in, bounce to the auth screens and remember where
  // to return. Resolves to the session (caller may proceed) or null (redirecting).
  async function requireAuth() {
    const session = await getSession();
    if (!session) {
      const here = window.location.pathname.split('/').pop() + window.location.search;
      window.location.href = `auth.html?next=${encodeURIComponent(here)}`;
      return null;
    }
    return session;
  }

  // fetch() against the API with the bearer token attached when signed in. The
  // path is appended to CONFIG.API_URL (e.g. apiFetch('/calculate', {...})).
  async function apiFetch(path, options) {
    const opts = options || {};
    const token = await getIdToken();
    const headers = Object.assign({}, opts.headers);
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return fetch(`${CONFIG.API_URL}${path}`, Object.assign({}, opts, { headers }));
  }

  return {
    userPool,
    currentUser,
    getSession,
    getIdToken,
    getEmail,
    signOut,
    requireAuth,
    apiFetch,
  };
})();

// Render a subtle "Signed in as <email> · Sign out" bar into a container, when a
// session exists. Used on the home + pledge pages. Re-runs on i18n:changed so the
// "Sign out" label follows the language. Returns the resolved email (or null).
async function renderAuthStatus(containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    return null;
  }
  const email = await Auth.getEmail();
  if (!email) {
    container.classList.add('hidden');
    container.innerHTML = '';
    return null;
  }

  container.classList.remove('hidden');
  container.innerHTML = '';

  const who = document.createElement('span');
  who.className = 'auth-status-who';
  // textContent (not innerHTML) — the email is user-controlled, never inject it.
  who.textContent = t('auth.signedInAs', { email });

  const sep = document.createElement('span');
  sep.className = 'auth-status-sep';
  sep.setAttribute('aria-hidden', 'true');
  sep.textContent = '·';

  const out = document.createElement('button');
  out.type = 'button';
  out.className = 'auth-status-signout';
  out.textContent = t('auth.signOut');
  out.addEventListener('click', () => {
    Auth.signOut();
    window.location.href = 'index.html';
  });

  container.appendChild(who);
  container.appendChild(sep);
  container.appendChild(out);
  return email;
}
