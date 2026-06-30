// Lightweight i18n for the static site (no build step). Default language is CZ
// (decision D7); CZ + EN now, the structure is DE-ready — add a third key under
// TRANSLATIONS and the parity checker keeps it honest.
//
// Usage in markup:
//   <h1 data-i18n="index.heroTitle"></h1>            -> sets textContent
//   <p  data-i18n-html="some.htmlKey"></p>           -> sets innerHTML (for <strong> etc.)
//   <input data-i18n-placeholder="pledge.msgPlaceholder">
//   <img data-i18n-alt="common.logoAlt">
//   <div data-i18n-aria-label="common.langLabel">
// Usage in JS: t('pledge.btnSaving'), t('sim.durationMonths', { n: 6 }).

const TRANSLATIONS = {
  cs: {
    // Common
    'common.loading': 'Načítání…',
    'common.na': 'N/A',
    'common.backHome': 'Zpět na úvod',
    'common.backHomeArrow': '← Zpět na úvod',
    'common.langLabel': 'Jazyk',
    'common.logoAlt': 'Buddhismus Karma Kagjü',
    'footer.copyright': '© 2026 Projekt Těnovice. Všechna práva vyhrazena.',

    // Home page
    'index.docTitle': 'Fundraising Těnovice',
    'index.heroTitle': 'Projekt ONE Těnovice',
    'index.heroDesc':
      'Těnovice jsou velký projekt na mnoho generací. Aktuálně se soustředíme na tři hlavní směry: nová Gompa, Sangha House a nová část Basecampu – Sever.',
    'index.heroImageAlt': 'Pomoz vytvářet čistou zemi',
    'index.bannerAlt': 'Banner projektu',
    'index.progressHeading': 'Průběh sbírky',
    'index.currentBalanceLabel': 'Aktuální zůstatek',
    'index.currentBalanceSub': 'Reálné peníze na účtu',
    'index.goalLabel': 'Náš cíl',
    'index.goalSub': 'Cílová částka',
    'index.progressReached': 'z cíle dosaženo',
    'index.pledgesHeading': 'Přísliby sanghy',
    'index.totalPledgedLabel': 'Celkem přislíbeno',
    'index.supportersLabel': 'Podporovatelů',
    'index.monthlyLabel': 'Měsíční přísliby',
    'index.ctaHeading': 'Buď srdcem toho všeho',
    'index.ctaButton': 'Přidat příslib',

    // Home page — dw-connect link (hero)
    'index.dwConnectLink': 'Více o projektu Těnovice na dw-connect →',
    'index.dwConnectNote': 'Pro přihlášené členy dw-connect.',

    // Pledge page — static
    'pledge.docTitle': 'Přidat příslib | Fundraising Těnovice',
    'pledge.fieldAmountEur': 'Částka (Kč)',
    'pledge.fieldMessageOptional': 'Zpráva (nepovinné)',
    'pledge.monthlyCheckbox': 'Toto je měsíční příslib',
    'pledge.months': 'Počet měsíců',
    'pledge.monthsHint': 'Po kolik měsíců bys přispíval(a) (od teď).',
    'pledge.msgPlaceholder': 'Nepovinná zpráva k tvému příslibu',
    'pledge.save': 'Uložit příslib',
    'pledge.previewOf': 'z',

    // Calculator page — simulator (zones 1+2) + pledge zone (zone 3), D2
    'index.supportersStrip':
      'Už přislíbilo <strong>{count} přátel</strong> v celkové hodnotě <strong>{amount}</strong>. Přidej se k nim.',
    'sim.heading': 'Spočítej svůj přínos',
    'sim.sub':
      'Co kdyby přispělo víc přátel jako ty? Zadej hodnoty a klikni na Spočítat — hned uvidíš, jaký dopad na cíl byste měli společně. Nic se neukládá, je to jen orientační výpočet.',
    'sim.peopleLabel': 'Kolik lidí jako ty?',
    'sim.peopleHint': 'Kolik přátel by přispělo stejnou částkou (orientačně, bez omezení).',
    'sim.amountPerPerson': 'Částka na osobu (Kč)',
    'sim.typeLabel': 'Typ příspěvku',
    'sim.oneTime': 'Jednorázově',
    'sim.monthly': 'Měsíčně',
    'sim.calcButton': 'Spočítat',
    'sim.btnCalculating': 'Počítám…',
    'sim.resultEyebrow': 'Výsledek kalkulačky',
    'sim.totalImpact': 'Společný přínos pro sbírku',
    'sim.monthlyExtra': 'Měsíčně navíc',
    'sim.duration': 'Přispíváte po dobu',
    'sim.durationMonths': '{n} měsíců',
    'sim.projectedProgress': 'Postup k cíli po tomto scénáři',
    'sim.legendNow': 'teď {pct} %',
    'sim.legendScenario': 'tvůj scénář +{pct} %',
    'sim.placeholder': 'Zadej hodnoty a klikni na Spočítat.',
    'sim.peopleAmountOneTime': '{people} lidí × {amount} jednorázově',
    'sim.peopleAmountMonthly': '{people} lidí × {amount} měsíčně',
    'sim.errInputs': 'Zadej počet lidí a částku na osobu.',
    'sim.errCalc': 'Výpočet se nepodařilo načíst. Zkus to prosím znovu.',
    'pledge.zoneDivider': 'Teď přidej svůj vlastní příslib',
    'pledge.zoneHeading': 'Přidej svůj příslib',
    'pledge.zoneIntro':
      'Toto je tvůj osobní příslib za jednoho člověka. E-mail už máš zadaný z předchozího kroku — slouží jen k rozpoznání tvého příslibu a nikde se nezobrazuje.',
    'pledge.publicPromiseNote':
      'Příslib je veřejný slib — žádné peníze přes web neposíláš. Po uložení uvidíš bankovní údaje a QR kódy.',

    // Pledge page — dynamic (JS)
    'pledge.checkingSignIn': 'Ověřuji tvé přihlášení…',
    'pledge.formTitleEdit': 'Uprav svůj příslib',
    'pledge.formIntroEdit':
      'Upravuješ svůj existující příslib. Po uložení nahradí tvůj současný příslib.',
    'pledge.btnSaving': 'Ukládám…',
    'pledge.errAmount': 'Částka musí být větší než 0.',
    'pledge.errAmountMax': 'Částka nesmí přesáhnout {max}.',
    'pledge.errMessageMax': 'Zpráva nesmí přesáhnout {max} znaků.',
    'pledge.errMonths': 'Zadej počet měsíců (alespoň 1).',
    'pledge.errSave': 'Příslib se nepodařilo uložit. Zkus to prosím znovu.',
    'pledge.errLookup': 'Tvůj příslib se nepodařilo načíst. Zkus to prosím znovu.',
    'pledge.retry': 'Zkusit znovu',

    // Success page
    'success.docTitle': 'Příslib uložen | Fundraising Těnovice',
    'success.thankYou': 'Děkujeme',
    'success.heading': 'Tvůj příslib byl uložen',
    'success.description':
      'Děkujeme za podporu projektu Těnovice. Příslib je veřejný slib — peníze teď pošli sám/sama podle údajů níže.',
    'success.another': 'Zadat další příslib',

    // Success page — payment instructions (E1)
    'payment.oneTimeHeading': 'Pošli svůj jednorázový dar',
    'payment.oneTimeIntro':
      'Naskenuj QR kód v bankovní aplikaci, nebo použij bankovní údaje níže.',
    'payment.monthlyHeading': 'Nastav si trvalý příkaz',
    'payment.monthlyIntro':
      'Nastav si v bance měsíční trvalý příkaz podle údajů níže.',
    'payment.monthlyNote':
      'Měsíční trvalý příkaz si nastav ve své bance podle údajů níže. Pro opakované platby není QR kód.',
    'payment.qrCzAlt': 'QR kód pro platbu na český účet',
    'payment.qrCzCaption': 'Český účet (CZK)',
    'payment.qrIntlAlt': 'QR kód pro mezinárodní platbu',
    'payment.qrIntlCaption': 'Mezinárodní účet (EUR)',
    'payment.czHeading': 'Český účet (CZK)',
    'payment.intlHeading': 'Mezinárodní účet (EUR)',
    'payment.accountName': 'Majitel účtu',
    'payment.accountNumber': 'Číslo účtu',
    'payment.variableSymbol': 'Variabilní symbol',
    'payment.message': 'Zpráva pro příjemce',
    'payment.messageValue': 'Prijmeni/Dar/Tenovice',
    'payment.czHint':
      'Variabilní symbol je datum tvé platby (RRMMDD) následované 0108. „Prijmeni“ nahraď svým příjmením.',
    'payment.bank': 'Banka',
    'payment.iban': 'IBAN',
    'payment.bic': 'BIC',
    'payment.purpose': 'Účel platby',
    'payment.copy': 'Kopírovat',

    // Auth screens (AUTH2) — login / register / verify / password recovery
    'auth.docTitle': 'Přihlášení | Fundraising Těnovice',
    'auth.loginHeading': 'Přihlášení',
    'auth.loginIntro': 'Přihlas se, abys mohl/a používat kalkulačku a přidat svůj příslib.',
    'auth.registerHeading': 'Vytvoř si účet',
    'auth.registerIntro': 'Zaregistruj se e-mailem a heslem, abys mohl/a přidat příslib.',
    'auth.confirmHeading': 'Ověř svůj e-mail',
    'auth.confirmIntro': 'Zadej kód, který jsme ti poslali e-mailem, a ověř svůj účet.',
    'auth.forgotHeading': 'Obnova hesla',
    'auth.forgotIntro': 'Zadej svůj e-mail a pošleme ti kód pro obnovu hesla.',
    'auth.resetHeading': 'Zvol si nové heslo',
    'auth.resetIntro': 'Zadej kód z e-mailu a nové heslo.',
    'auth.emailLabel': 'E-mail',
    'auth.passwordLabel': 'Heslo',
    'auth.passwordConfirmLabel': 'Heslo znovu',
    'auth.newPasswordLabel': 'Nové heslo',
    'auth.codeLabel': 'Ověřovací kód',
    'auth.passwordHint': 'Alespoň 10 znaků, velké i malé písmeno a číslice.',
    'auth.emailSafetyNote':
      'Tvůj e-mail nikdy nesdílíme ani veřejně nezobrazujeme. Slouží jen k bezpečnému přihlášení, registraci a obnově hesla.',
    'auth.signInButton': 'Přihlásit se',
    'auth.registerButton': 'Vytvořit účet',
    'auth.confirmButton': 'Ověřit',
    'auth.sendResetButton': 'Poslat kód pro obnovu',
    'auth.resetButton': 'Změnit heslo',
    'auth.resendCode': 'Poslat kód znovu',
    'auth.forgotLink': 'Zapomněl/a jsi heslo?',
    'auth.haveCodeLink': 'Máš ověřovací kód?',
    'auth.noAccount': 'Ještě nemáš účet?',
    'auth.toRegister': 'Vytvoř si ho',
    'auth.haveAccount': 'Už máš účet?',
    'auth.toLogin': 'Přihlas se',
    'auth.loginRequiredNote': 'Pro použití kalkulačky a přidání příslibu se prosím přihlas.',
    'auth.signedInAs': 'Přihlášen/a jako {email}',
    'auth.signOut': 'Odhlásit se',
    'auth.btnSigningIn': 'Přihlašuji…',
    'auth.btnRegistering': 'Vytvářím účet…',
    'auth.btnConfirming': 'Ověřuji…',
    'auth.btnSending': 'Odesílám…',
    'auth.btnResetting': 'Měním heslo…',
    'auth.codeSent': 'Poslali jsme ověřovací kód na {email}.',
    'auth.confirmedNowLogin': 'Účet je ověřený. Teď se prosím přihlas.',
    'auth.resentCode': 'Posíláme ti nový kód.',
    'auth.resetCodeSent': 'Poslali jsme ti e-mailem kód pro obnovu hesla.',
    'auth.resetDone': 'Heslo bylo změněno. Teď se prosím přihlas.',
    'auth.errEmailFormat': 'Zadej prosím platný e-mail.',
    'auth.errPasswordRequired': 'Zadej prosím heslo.',
    'auth.errPasswordPolicy':
      'Heslo musí mít alespoň 10 znaků a obsahovat velké i malé písmeno a číslici.',
    'auth.errPasswordMatch': 'Hesla se neshodují.',
    'auth.errCodeRequired': 'Zadej prosím ověřovací kód.',
    'auth.errIncorrect': 'Nesprávný e-mail nebo heslo.',
    'auth.errNotConfirmed': 'Nejdřív prosím ověř svůj e-mail.',
    'auth.errExists': 'Účet s tímto e-mailem už možná existuje. Zkus se přihlásit.',
    'auth.errCode': 'Neplatný nebo expirovaný kód.',
    'auth.errLimit': 'Příliš mnoho pokusů. Zkus to prosím za chvíli.',
    'auth.errGeneric': 'Něco se pokazilo. Zkus to prosím znovu.',
  },

  en: {
    // Common
    'common.loading': 'Loading…',
    'common.na': 'N/A',
    'common.backHome': 'Back to homepage',
    'common.backHomeArrow': '← Back to homepage',
    'common.langLabel': 'Language',
    'common.logoAlt': 'Karma Kagyu buddhism',
    'footer.copyright': '© 2026 Tenovice Project. All rights reserved.',

    // Home page
    'index.docTitle': 'Tenovice Fundraising',
    'index.heroTitle': 'ONE Tenovice Project',
    'index.heroDesc':
      'Tenovice is a big project for many generations. At the moment we focus our development on 3 main directions: New Gompa, Sangha House and new land Basecamp North.',
    'index.heroImageAlt': 'Make your pure land',
    'index.bannerAlt': 'Project Banner',
    'index.progressHeading': 'Fundraising Progress',
    'index.currentBalanceLabel': 'Current Balance',
    'index.currentBalanceSub': 'Real money on account',
    'index.goalLabel': 'Our Goal',
    'index.goalSub': 'Target amount',
    'index.progressReached': 'of goal reached',
    'index.pledgesHeading': 'Sangha Pledges',
    'index.totalPledgedLabel': 'Total Pledged',
    'index.supportersLabel': 'Supporters',
    'index.monthlyLabel': 'Monthly Recurring',
    'index.ctaHeading': 'Be heart of it',
    'index.ctaButton': 'Make a Pledge',

    // Home page — dw-connect link (hero)
    'index.dwConnectLink': 'More about the Tenovice project on dw-connect →',
    'index.dwConnectNote': 'For logged-in dw-connect members.',

    // Pledge page — static
    'pledge.docTitle': 'Make a Pledge | Tenovice Fundraising',
    'pledge.fieldAmountEur': 'Amount (EUR)',
    'pledge.fieldMessageOptional': 'Message (optional)',
    'pledge.monthlyCheckbox': 'This is a monthly recurring pledge',
    'pledge.months': 'Number of months',
    'pledge.monthsHint': 'For how many months you would contribute (from now).',
    'pledge.msgPlaceholder': 'Optional message to accompany the pledge',
    'pledge.save': 'Save pledge',
    'pledge.previewOf': 'of',

    // Calculator page — simulator (zones 1+2) + pledge zone (zone 3), D2
    'index.supportersStrip':
      'Already <strong>{count} friends</strong> have pledged <strong>{amount}</strong>. Join them.',
    'sim.heading': 'Calculate your impact',
    'sim.sub':
      'What if more friends gave like you? Enter the values and press Calculate to see your combined impact on the goal. Nothing is saved — it is only an estimate.',
    'sim.peopleLabel': 'How many people like you?',
    'sim.peopleHint': 'How many friends would give the same amount (illustrative, no limit).',
    'sim.amountPerPerson': 'Amount per person (EUR)',
    'sim.typeLabel': 'Contribution type',
    'sim.oneTime': 'One-time',
    'sim.monthly': 'Monthly',
    'sim.calcButton': 'Calculate',
    'sim.btnCalculating': 'Calculating…',
    'sim.resultEyebrow': 'Calculator result',
    'sim.totalImpact': 'Combined impact on the campaign',
    'sim.monthlyExtra': 'Monthly addition',
    'sim.duration': 'Contributing for',
    'sim.durationMonths': '{n} months',
    'sim.projectedProgress': 'Progress to goal in this scenario',
    'sim.legendNow': 'now {pct}%',
    'sim.legendScenario': 'your scenario +{pct}%',
    'sim.placeholder': 'Enter values and press Calculate.',
    'sim.peopleAmountOneTime': '{people} people × {amount} one-time',
    'sim.peopleAmountMonthly': '{people} people × {amount} monthly',
    'sim.errInputs': 'Enter the number of people and the amount per person.',
    'sim.errCalc': 'Could not run the calculation. Please try again.',
    'pledge.zoneDivider': 'Now add your own pledge',
    'pledge.zoneHeading': 'Add your pledge',
    'pledge.zoneIntro':
      'This is your personal pledge for one person. Your email is already entered from the previous step — it is used only to recognize your pledge and is never shown.',
    'pledge.publicPromiseNote':
      'A pledge is a public promise — no money is sent through the site. After saving you will see the bank details and QR codes.',

    // Pledge page — dynamic (JS)
    'pledge.checkingSignIn': 'Checking your sign-in…',
    'pledge.formTitleEdit': 'Update your pledge',
    'pledge.formIntroEdit':
      'You are editing your existing pledge. Saving will replace your current pledge.',
    'pledge.btnSaving': 'Saving…',
    'pledge.errAmount': 'Amount must be greater than 0.',
    'pledge.errAmountMax': 'Amount must not exceed {max}.',
    'pledge.errMessageMax': 'Message must not exceed {max} characters.',
    'pledge.errMonths': 'Enter the number of months (at least 1).',
    'pledge.errSave': 'Could not save pledge. Please try again.',
    'pledge.errLookup': 'Could not load your pledge. Please try again.',
    'pledge.retry': 'Try again',

    // Success page
    'success.docTitle': 'Pledge Saved | Tenovice Fundraising',
    'success.thankYou': 'Thank you',
    'success.heading': 'Your pledge was saved',
    'success.description':
      'Thank you for supporting the Tenovice Project. A pledge is a public promise — now send the gift yourself using the details below.',
    'success.another': 'Make another pledge',

    // Success page — payment instructions (E1)
    'payment.oneTimeHeading': 'Send your one-time gift',
    'payment.oneTimeIntro':
      'Scan the QR code with your banking app, or use the bank details below.',
    'payment.monthlyHeading': 'Set up a standing order',
    'payment.monthlyIntro':
      'Set up a monthly standing order in your bank using the details below.',
    'payment.monthlyNote':
      'Set up a monthly standing order in your bank using the details below. There is no QR code for recurring payments.',
    'payment.qrCzAlt': 'Czech payment QR code',
    'payment.qrCzCaption': 'Czech bank account (CZK)',
    'payment.qrIntlAlt': 'International payment QR code',
    'payment.qrIntlCaption': 'International account (EUR)',
    'payment.czHeading': 'Czech account (CZK)',
    'payment.intlHeading': 'International account (EUR)',
    'payment.accountName': 'Account holder',
    'payment.accountNumber': 'Account number',
    'payment.variableSymbol': 'Variable symbol',
    'payment.message': 'Message for recipient',
    'payment.messageValue': 'Surname/Gift/Tenovice',
    'payment.czHint':
      'The variable symbol is the date of your payment (YYMMDD) followed by 0108. Replace “Surname” with your own.',
    'payment.bank': 'Bank',
    'payment.iban': 'IBAN',
    'payment.bic': 'BIC',
    'payment.purpose': 'Purpose',
    'payment.copy': 'Copy',

    // Auth screens (AUTH2) — login / register / verify / password recovery
    'auth.docTitle': 'Sign in | Tenovice Fundraising',
    'auth.loginHeading': 'Sign in',
    'auth.loginIntro': 'Sign in to use the calculator and add your pledge.',
    'auth.registerHeading': 'Create your account',
    'auth.registerIntro': 'Register with your email and a password to make a pledge.',
    'auth.confirmHeading': 'Verify your email',
    'auth.confirmIntro': 'Enter the code we sent to your email to verify your account.',
    'auth.forgotHeading': 'Reset your password',
    'auth.forgotIntro': 'Enter your email and we will send you a reset code.',
    'auth.resetHeading': 'Choose a new password',
    'auth.resetIntro': 'Enter the code from your email and a new password.',
    'auth.emailLabel': 'Email',
    'auth.passwordLabel': 'Password',
    'auth.passwordConfirmLabel': 'Confirm password',
    'auth.newPasswordLabel': 'New password',
    'auth.codeLabel': 'Verification code',
    'auth.passwordHint':
      'At least 10 characters, with an uppercase and a lowercase letter and a number.',
    'auth.emailSafetyNote':
      'Your email is never shared or shown publicly. It is used only for secure sign-in, registration and password recovery.',
    'auth.signInButton': 'Sign in',
    'auth.registerButton': 'Create account',
    'auth.confirmButton': 'Verify',
    'auth.sendResetButton': 'Send reset code',
    'auth.resetButton': 'Reset password',
    'auth.resendCode': 'Resend code',
    'auth.forgotLink': 'Forgot your password?',
    'auth.haveCodeLink': 'Have a verification code?',
    'auth.noAccount': 'No account yet?',
    'auth.toRegister': 'Create one',
    'auth.haveAccount': 'Already have an account?',
    'auth.toLogin': 'Sign in',
    'auth.loginRequiredNote': 'Please sign in to use the calculator and add your pledge.',
    'auth.signedInAs': 'Signed in as {email}',
    'auth.signOut': 'Sign out',
    'auth.btnSigningIn': 'Signing in…',
    'auth.btnRegistering': 'Creating account…',
    'auth.btnConfirming': 'Verifying…',
    'auth.btnSending': 'Sending…',
    'auth.btnResetting': 'Changing password…',
    'auth.codeSent': 'We sent a verification code to {email}.',
    'auth.confirmedNowLogin': 'Your account is verified. Please sign in.',
    'auth.resentCode': 'A new code is on the way.',
    'auth.resetCodeSent': 'We emailed you a password-reset code.',
    'auth.resetDone': 'Your password was changed. Please sign in.',
    'auth.errEmailFormat': 'Please enter a valid email address.',
    'auth.errPasswordRequired': 'Please enter your password.',
    'auth.errPasswordPolicy':
      'Password must be at least 10 characters and include an uppercase and a lowercase letter and a number.',
    'auth.errPasswordMatch': 'Passwords do not match.',
    'auth.errCodeRequired': 'Please enter the verification code.',
    'auth.errIncorrect': 'Incorrect email or password.',
    'auth.errNotConfirmed': 'Please verify your email first.',
    'auth.errExists': 'An account with this email may already exist. Try signing in.',
    'auth.errCode': 'Invalid or expired code.',
    'auth.errLimit': 'Too many attempts. Please try again shortly.',
    'auth.errGeneric': 'Something went wrong. Please try again.',
  },
};

const I18N_DEFAULT_LANG = 'cs';
const I18N_STORAGE_KEY = 'tenovice.lang';
const I18N_ATTRS = ['placeholder', 'alt', 'aria-label', 'title'];

let _lang = I18N_DEFAULT_LANG;

// Translate a key for the current language, with {param} interpolation. Falls
// back to the default language, then to the key itself, so a missing string is
// visible rather than blank.
function t(key, params) {
  const dict = TRANSLATIONS[_lang] || TRANSLATIONS[I18N_DEFAULT_LANG];
  let str = dict[key];
  if (str === undefined) {
    str = TRANSLATIONS[I18N_DEFAULT_LANG][key];
  }
  if (str === undefined) {
    return key;
  }
  if (params) {
    Object.keys(params).forEach((p) => {
      str = str.split(`{${p}}`).join(String(params[p]));
    });
  }
  return str;
}

function getStoredLang() {
  try {
    const saved = localStorage.getItem(I18N_STORAGE_KEY);
    return TRANSLATIONS[saved] ? saved : I18N_DEFAULT_LANG;
  } catch (e) {
    return I18N_DEFAULT_LANG;
  }
}

// Apply translations to every tagged element and broadcast the change so that
// JS-rendered strings (preview, statuses) can refresh themselves.
function applyTranslations(lang) {
  _lang = TRANSLATIONS[lang] ? lang : I18N_DEFAULT_LANG;
  document.documentElement.lang = _lang;

  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    el.innerHTML = t(el.getAttribute('data-i18n-html'));
  });
  I18N_ATTRS.forEach((attr) => {
    document.querySelectorAll(`[data-i18n-${attr}]`).forEach((el) => {
      el.setAttribute(attr, t(el.getAttribute(`data-i18n-${attr}`)));
    });
  });

  document.querySelectorAll('[data-set-lang]').forEach((btn) => {
    const isActive = btn.getAttribute('data-set-lang') === _lang;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-pressed', String(isActive));
  });

  document.dispatchEvent(new CustomEvent('i18n:changed', { detail: { lang: _lang } }));
}

function setLang(lang) {
  try {
    localStorage.setItem(I18N_STORAGE_KEY, lang);
  } catch (e) {
    /* storage may be unavailable; still apply for this session */
  }
  applyTranslations(lang);
}

function setupI18n() {
  document.querySelectorAll('[data-set-lang]').forEach((btn) => {
    btn.addEventListener('click', () => setLang(btn.getAttribute('data-set-lang')));
  });
  applyTranslations(getStoredLang());
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupI18n);
  } else {
    setupI18n();
  }
}

// Exported for the parity checker (Node); ignored in the browser.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { TRANSLATIONS, I18N_DEFAULT_LANG };
}
