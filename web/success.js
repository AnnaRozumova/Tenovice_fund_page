// Success page (E1). After a pledge is saved, pledge.js redirects here with
// ?type=one-time|monthly. We show the matching payment path:
//   one-time -> QR codes for a single gift (+ bank details as a fallback);
//   monthly  -> standing-order bank details (no QR — a recurring order can't be
//               a single QR payment).
// The bank-detail values are copyable. No API calls, no state — static page.

function $(id) {
  return document.getElementById(id);
}

// Robust copy: navigator.clipboard needs a secure context (https/localhost);
// fall back to a hidden textarea + execCommand otherwise so it still works.
function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      resolve();
    } catch (err) {
      reject(err);
    }
  });
}

function flashCopied(button) {
  const original = button.textContent;
  button.textContent = '✓';
  button.classList.add('copied');
  setTimeout(() => {
    button.textContent = original;
    button.classList.remove('copied');
  }, 1200);
}

// A copy button either carries the literal value (data-copy-target) or points at
// an element whose live text to copy (data-copy-el) — the latter for the message
// value, which is localized (i18n) so it must copy whatever is currently shown.
function copyValueFor(button) {
  const elId = button.getAttribute('data-copy-el');
  if (elId) {
    const el = document.getElementById(elId);
    return el ? el.textContent.trim() : '';
  }
  return button.getAttribute('data-copy-target');
}

function setupCopyButtons() {
  document.querySelectorAll('.copy-btn').forEach((button) => {
    button.addEventListener('click', () => {
      copyText(copyValueFor(button))
        .then(() => flashCopied(button))
        .catch((err) => console.error('Copy failed:', err));
    });
  });
}

function getPledgeType() {
  const params = new URLSearchParams(window.location.search);
  // Default to one-time if the param is missing or unexpected.
  return params.get('type') === 'monthly' ? 'monthly' : 'one-time';
}

// Swap the heading/intro keys and toggle the QR vs standing-order blocks. Kept in
// a function so a language switch re-applies the right copy (i18n:changed).
let pledgeType = 'one-time';

function applyPaymentType() {
  const isMonthly = pledgeType === 'monthly';

  $('paymentHeading').setAttribute(
    'data-i18n',
    isMonthly ? 'payment.monthlyHeading' : 'payment.oneTimeHeading'
  );
  $('paymentHeading').textContent = t(
    isMonthly ? 'payment.monthlyHeading' : 'payment.oneTimeHeading'
  );
  $('paymentIntro').setAttribute(
    'data-i18n',
    isMonthly ? 'payment.monthlyIntro' : 'payment.oneTimeIntro'
  );
  $('paymentIntro').textContent = t(
    isMonthly ? 'payment.monthlyIntro' : 'payment.oneTimeIntro'
  );

  // Monthly has no QR (a recurring order can't be a single QR payment): hide the
  // QR figures, leaving each account window in place.
  document.querySelectorAll('[data-qr]').forEach((el) => {
    el.classList.toggle('hidden', isMonthly);
  });
  $('monthlyNote').classList.toggle('hidden', !isMonthly);
}

function initSuccessPage() {
  pledgeType = getPledgeType();
  applyPaymentType();
  setupCopyButtons();
  // i18n.js sets the static data-i18n nodes; re-apply the type-dependent copy
  // whenever the language changes.
  document.addEventListener('i18n:changed', applyPaymentType);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSuccessPage);
} else {
  initSuccessPage();
}
