// Auth screens (AUTH2). One page, several views toggled in JS: login, register,
// confirm-code (email verification), forgot-password, reset-password. All talk to
// the Cognito user pool via the vendored amazon-cognito-identity-js (SRP for
// login). The API stays open until AUTH3 — these screens only manage identity.
//
// Email is the username (the pool uses usernameAttributes=['email'], AUTH1), so
// every call passes the email as the Username.

const { CognitoUser, AuthenticationDetails, CognitoUserAttribute } = AmazonCognitoIdentity;

// Mirror of the backend EMAIL_RE and the Cognito password policy (10+ chars with an
// uppercase, a lowercase and a digit, AUTH1) so junk is caught before a network round-trip.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PASSWORD_MIN = 10;

// The view to land on (?view=login|register|...) and where to go after login.
const params = new URLSearchParams(window.location.search);
const nextTarget = sanitizeNext(params.get('next'));

// State carried across views (e.g. the email typed at register flows to confirm).
let pendingEmail = '';

function $(id) {
  return document.getElementById(id);
}

// Reuse the single pool accessor from auth-common.js (no duplicate config).
function cognitoUser(email) {
  return new CognitoUser({ Username: email, Pool: Auth.userPool() });
}

// Only allow same-site relative targets after login (no protocol/host), so a
// crafted ?next= can't turn the login into an open redirect. Backslashes are
// normalized first: browsers treat "\" as "/", so "\\evil.com" would otherwise
// slip through as the protocol-relative "//evil.com".
function sanitizeNext(value) {
  if (!value) {
    return 'pledge.html';
  }
  const normalized = value.replace(/\\/g, '/');
  if (/^[a-z][\w.+-]*:/i.test(normalized) || normalized.startsWith('/')) {
    return 'pledge.html';
  }
  return value;
}

// ============ view switching ============

const VIEWS = ['login', 'register', 'confirm', 'forgot', 'reset'];

function showView(name) {
  VIEWS.forEach((v) => {
    $(`view-${v}`).classList.toggle('hidden', v !== name);
  });
  clearFeedback();
}

// ============ feedback (errors / notices) ============

function clearFeedback() {
  const box = $('authMessage');
  box.textContent = '';
  box.className = 'form-message hidden';
}

function showError(message) {
  const box = $('authMessage');
  box.textContent = message;
  box.className = 'form-message form-message-error';
}

function showNotice(message) {
  const box = $('authMessage');
  box.textContent = message;
  box.className = 'form-message form-message-success';
}

// Map a Cognito error to a friendly, localized message. The pool has
// prevent_user_existence_errors on, so sign-in / forgot give uniform errors by
// design; we keep messages generic and fall back to a catch-all.
function authErrorMessage(err) {
  const code = (err && (err.code || err.name)) || '';
  switch (code) {
    case 'NotAuthorizedException':
      return t('auth.errIncorrect');
    case 'UserNotConfirmedException':
      return t('auth.errNotConfirmed');
    case 'UsernameExistsException':
      return t('auth.errExists');
    case 'CodeMismatchException':
    case 'ExpiredCodeException':
      return t('auth.errCode');
    case 'InvalidPasswordException':
      return t('auth.errPasswordPolicy');
    case 'LimitExceededException':
    case 'TooManyRequestsException':
      return t('auth.errLimit');
    default:
      return t('auth.errGeneric');
  }
}

// ============ validation ============

function passwordPolicyError(pw) {
  if (
    pw.length < PASSWORD_MIN ||
    !/[a-z]/.test(pw) ||
    !/[A-Z]/.test(pw) ||
    !/[0-9]/.test(pw)
  ) {
    return t('auth.errPasswordPolicy');
  }
  return '';
}

// Put a button into a busy state (disabled + busy label) while a callback-style
// Cognito call runs. The call's onSuccess/onFailure/callback must invoke done() to
// restore it; the try/catch only covers a synchronous throw from fn itself.
function withBusy(button, busyKey, fn) {
  const label = button.textContent;
  button.disabled = true;
  button.textContent = t(busyKey);
  const done = () => {
    button.disabled = false;
    button.textContent = label;
  };
  try {
    fn(done);
  } catch (err) {
    done();
    showError(t('auth.errGeneric'));
  }
}

// ============ login ============

function handleLogin() {
  clearFeedback();
  const email = $('loginEmail').value.trim();
  const password = $('loginPassword').value;

  if (!EMAIL_RE.test(email)) {
    showError(t('auth.errEmailFormat'));
    return;
  }
  if (!password) {
    showError(t('auth.errPasswordRequired'));
    return;
  }

  withBusy($('loginButton'), 'auth.btnSigningIn', (done) => {
    cognitoUser(email).authenticateUser(
      new AuthenticationDetails({ Username: email, Password: password }),
      {
        onSuccess: () => {
          // Tokens are now stored by the library; head to the gated page.
          window.location.href = nextTarget;
        },
        onFailure: (err) => {
          done();
          if ((err.code || err.name) === 'UserNotConfirmedException') {
            // Unverified account: send them to the code screen to finish.
            pendingEmail = email;
            $('confirmEmail').value = email;
            showView('confirm');
            showNotice(t('auth.errNotConfirmed'));
            return;
          }
          showError(authErrorMessage(err));
        },
      }
    );
  });
}

// ============ register ============

function handleRegister() {
  clearFeedback();
  const email = $('registerEmail').value.trim();
  const password = $('registerPassword').value;
  const confirm = $('registerPasswordConfirm').value;

  if (!EMAIL_RE.test(email)) {
    showError(t('auth.errEmailFormat'));
    return;
  }
  const policyError = passwordPolicyError(password);
  if (policyError) {
    showError(policyError);
    return;
  }
  if (password !== confirm) {
    showError(t('auth.errPasswordMatch'));
    return;
  }

  withBusy($('registerButton'), 'auth.btnRegistering', (done) => {
    // Store the chosen language in the standard `locale` attribute so the Cognito
    // Custom Message trigger can send the verification / reset emails in CZ or EN.
    const locale = document.documentElement.lang === 'en' ? 'en' : 'cs';
    const attributes = [
      new CognitoUserAttribute({ Name: 'email', Value: email }),
      new CognitoUserAttribute({ Name: 'locale', Value: locale }),
    ];
    Auth.userPool().signUp(email, password, attributes, null, (err) => {
      done();
      if (err) {
        showError(authErrorMessage(err));
        return;
      }
      // Email verification is required → go to the confirm-code screen.
      pendingEmail = email;
      $('confirmEmail').value = email;
      showView('confirm');
      showNotice(t('auth.codeSent', { email }));
    });
  });
}

// ============ confirm code (email verification) ============

function handleConfirm() {
  clearFeedback();
  const email = $('confirmEmail').value.trim();
  const code = $('confirmCode').value.trim();

  if (!EMAIL_RE.test(email)) {
    showError(t('auth.errEmailFormat'));
    return;
  }
  if (!code) {
    showError(t('auth.errCodeRequired'));
    return;
  }

  withBusy($('confirmButton'), 'auth.btnConfirming', (done) => {
    cognitoUser(email).confirmRegistration(code, true, (err) => {
      done();
      if (err) {
        showError(authErrorMessage(err));
        return;
      }
      // Verified — back to login (we don't keep the password around to auto-login).
      $('loginEmail').value = email;
      showView('login');
      showNotice(t('auth.confirmedNowLogin'));
    });
  });
}

function handleResendCode() {
  clearFeedback();
  const email = $('confirmEmail').value.trim();
  if (!EMAIL_RE.test(email)) {
    showError(t('auth.errEmailFormat'));
    return;
  }
  // Guard against rapid double-clicks (each would burn a Cognito send → LimitExceeded).
  const link = $('resendCodeLink');
  if (link.dataset.busy === '1') {
    return;
  }
  link.dataset.busy = '1';
  cognitoUser(email).resendConfirmationCode((err) => {
    link.dataset.busy = '';
    if (err) {
      showError(authErrorMessage(err));
      return;
    }
    showNotice(t('auth.resentCode'));
  });
}

// ============ forgot / reset password ============

function handleForgot() {
  clearFeedback();
  const email = $('forgotEmail').value.trim();
  if (!EMAIL_RE.test(email)) {
    showError(t('auth.errEmailFormat'));
    return;
  }

  withBusy($('forgotButton'), 'auth.btnSending', (done) => {
    cognitoUser(email).forgotPassword({
      onSuccess: () => {
        // (Rarely fires before a code is entered; treated like the code path.)
        done();
        pendingEmail = email;
        $('resetEmail').value = email;
        showView('reset');
        showNotice(t('auth.resetCodeSent'));
      },
      inputVerificationCode: () => {
        done();
        pendingEmail = email;
        $('resetEmail').value = email;
        showView('reset');
        showNotice(t('auth.resetCodeSent'));
      },
      onFailure: (err) => {
        done();
        showError(authErrorMessage(err));
      },
    });
  });
}

function handleReset() {
  clearFeedback();
  const email = $('resetEmail').value.trim();
  const code = $('resetCode').value.trim();
  const password = $('resetPassword').value;
  const confirm = $('resetPasswordConfirm').value;

  if (!EMAIL_RE.test(email)) {
    showError(t('auth.errEmailFormat'));
    return;
  }
  if (!code) {
    showError(t('auth.errCodeRequired'));
    return;
  }
  const policyError = passwordPolicyError(password);
  if (policyError) {
    showError(policyError);
    return;
  }
  if (password !== confirm) {
    showError(t('auth.errPasswordMatch'));
    return;
  }

  withBusy($('resetButton'), 'auth.btnResetting', (done) => {
    cognitoUser(email).confirmPassword(code, password, {
      onSuccess: () => {
        done();
        $('loginEmail').value = email;
        showView('login');
        showNotice(t('auth.resetDone'));
      },
      onFailure: (err) => {
        done();
        showError(authErrorMessage(err));
      },
    });
  });
}

// ============ wiring ============

function setupLinks() {
  document.querySelectorAll('[data-goto-view]').forEach((el) => {
    el.addEventListener('click', (event) => {
      event.preventDefault();
      showView(el.getAttribute('data-goto-view'));
    });
  });
}

// Wire links + buttons and pick the starting view. Done synchronously so the
// screens are interactive immediately, before any network wait.
function setupAuthScreens() {
  setupLinks();
  $('loginButton').addEventListener('click', handleLogin);
  $('registerButton').addEventListener('click', handleRegister);
  $('confirmButton').addEventListener('click', handleConfirm);
  $('resendCodeLink').addEventListener('click', (e) => {
    e.preventDefault();
    handleResendCode();
  });
  $('forgotButton').addEventListener('click', handleForgot);
  $('resetButton').addEventListener('click', handleReset);

  // Land on the requested view (default login); show the "please sign in" note
  // only on the login view, so a deep-link like ?view=register&next=… doesn't
  // mislabel the register screen with a login prompt.
  const wanted = params.get('view');
  const view = VIEWS.indexOf(wanted) >= 0 ? wanted : 'login';
  showView(view);
  if (params.get('next') && view === 'login') {
    showNotice(t('auth.loginRequiredNote'));
  }
}

async function initAuthPage() {
  setupAuthScreens();
  // Already signed in? Skip the screens. (After wiring, so a fast click isn't lost.)
  const session = await Auth.getSession();
  if (session) {
    window.location.href = nextTarget;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAuthPage);
} else {
  initAuthPage();
}
