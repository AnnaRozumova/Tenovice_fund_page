// Lightweight i18n for the static site (no build step). Default language is CZ
// (decision D7); CZ + EN now, the structure is DE-ready — add a third key under
// TRANSLATIONS and the parity checker keeps it honest.
//
// Usage in markup:
//   <h1 data-i18n="index.heroTitle"></h1>            -> sets textContent
//   <p  data-i18n-html="pledge.monthlyNote"></p>     -> sets innerHTML (for <strong> etc.)
//   <input data-i18n-placeholder="pledge.msgPlaceholder">
//   <img data-i18n-alt="common.logoAlt">
//   <div data-i18n-aria-label="common.langLabel">
// Usage in JS: t('pledge.btnSaving'), t('pledge.statusMonthly', { n: 6 }).

const TRANSLATIONS = {
  cs: {
    // Common
    'common.loading': 'Načítání…',
    'common.na': 'N/A',
    'common.cancel': 'Zrušit',
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
    'index.ctaHeading': 'Chceš být u zrodu toho všeho?',
    'index.ctaButton': 'Přidat příslib',

    // Pledge page — static
    'pledge.docTitle': 'Přidat příslib | Fundraising Těnovice',
    'pledge.eyebrow': 'Fundraising Těnovice',
    'pledge.title': 'Zadej svůj příslib',
    'pledge.description':
      'Nejprve zadej e-mail. Pokud jsi už příslib zadal/a, můžeš si ho zobrazit a rozhodnout se, jestli ho upravíš.',
    'pledge.lookupHeading': 'Začni svým e-mailem',
    'pledge.lookupIntro': 'Zkontrolujeme, jestli už máš příslib v systému.',
    'pledge.emailLabel': 'E-mail',
    'pledge.continue': 'Pokračovat',
    'pledge.existingHeading': 'Našli jsme tvůj příslib',
    'pledge.existingIntro':
      'Pro tento e-mail jsme našli příslib. Můžeš si ho zobrazit a rozhodnout, jestli ho upravíš.',
    'pledge.fieldAmount': 'Částka',
    'pledge.fieldAmountEur': 'Částka (EUR)',
    'pledge.fieldType': 'Typ',
    'pledge.fieldEndDate': 'Datum konce',
    'pledge.fieldCampaignTotal': 'Celkový přínos pro sbírku',
    'pledge.fieldMessage': 'Zpráva',
    'pledge.fieldMessageOptional': 'Zpráva (nepovinné)',
    'pledge.editExisting': 'Ano, upravit příslib',
    'pledge.monthlyCheckbox': 'Toto je měsíční příslib',
    'pledge.endMonth': 'Měsíc konce',
    'pledge.endYear': 'Rok konce',
    'pledge.selectMonth': 'Vyber měsíc',
    'pledge.msgPlaceholder': 'Nepovinná zpráva k tvému příslibu',
    'pledge.save': 'Uložit příslib',
    'pledge.previewHeading': 'Náhled',
    'pledge.previewImpact': 'Celkový přínos příslibu',
    'pledge.previewMonthlyEffect': 'Měsíční příslib',
    'pledge.previewPledgedTotal': 'Nově celkem přislíbeno',
    'pledge.previewMonthlyTotal': 'Nově měsíčně přislíbeno',
    'pledge.previewProgress': 'Postup k cíli',
    'pledge.previewOf': 'z',
    'pledge.monthlyNote':
      '<strong>Měsíční příslib:</strong> celkový přínos se vypočítá jako částka × počet zbývajících měsíců do zvoleného měsíce a roku ukončení.',

    // Months
    'month.1': 'Leden',
    'month.2': 'Únor',
    'month.3': 'Březen',
    'month.4': 'Duben',
    'month.5': 'Květen',
    'month.6': 'Červen',
    'month.7': 'Červenec',
    'month.8': 'Srpen',
    'month.9': 'Září',
    'month.10': 'Říjen',
    'month.11': 'Listopad',
    'month.12': 'Prosinec',

    // Pledge page — dynamic (JS)
    'pledge.formTitleCreate': 'Tvůj příslib',
    'pledge.formTitleEdit': 'Uprav svůj příslib',
    'pledge.formIntroCreate': 'Všechny hodnoty náhledu níže se aktualizují živě, než uložíš.',
    'pledge.formIntroEdit':
      'Upravuješ existující příslib. Hodnoty náhledu nahrazují tvůj současný příslib v součtech.',
    'pledge.typeMonthly': 'Měsíčně opakovaný',
    'pledge.typeOneTime': 'Jednorázový',
    'pledge.modeCreate':
      '<strong>Režim nového příslibu:</strong> náhled přičítá tento příslib k současným součtům.',
    'pledge.modeEdit':
      '<strong>Režim úprav:</strong> náhled nahrazuje tvůj existující příslib v současných součtech.',
    'pledge.btnChecking': 'Kontroluji…',
    'pledge.btnSaving': 'Ukládám…',
    'pledge.statusEnterEmail': 'Pro začátek zadej e-mail.',
    'pledge.statusMonthly': 'Celkový přínos se počítá z {n} zbývajících měsíců.',
    'pledge.statusSelectEnd': 'Vyber měsíc a rok konce pro výpočet celkového přínosu.',
    'pledge.statusEditOneTime': 'Upravuješ existující jednorázový příslib.',
    'pledge.statusCreateOneTime': 'Vytváříš nový jednorázový příslib.',
    'pledge.statusNoStats': 'Nepodařilo se načíst aktuální statistiky. Náhled nemusí být dostupný.',
    'pledge.errEmailRequired': 'Zadej prosím svůj e-mail.',
    'pledge.errAmount': 'Částka musí být větší než 0.',
    'pledge.errEndMonth': 'Měsíc konce musí být mezi 1 a 12.',
    'pledge.errEndYear': 'Zadej prosím platný rok konce.',
    'pledge.errEndPast': 'Datum konce měsíčního příslibu musí být v aktuálním nebo budoucím měsíci.',
    'pledge.errLookup': 'Nepodařilo se ověřit existující příslib. Zkus to prosím znovu.',
    'pledge.errSave': 'Příslib se nepodařilo uložit. Zkus to prosím znovu.',

    // Success page
    'success.docTitle': 'Příslib uložen | Fundraising Těnovice',
    'success.thankYou': 'Děkujeme',
    'success.heading': 'Tvůj příslib byl uložen',
    'success.description':
      'Děkujeme za podporu projektu Těnovice. Teď se můžeš vrátit na úvodní stránku a zobrazit aktualizovaný přehled sbírky.',
    'success.another': 'Zadat další příslib',
  },

  en: {
    // Common
    'common.loading': 'Loading…',
    'common.na': 'N/A',
    'common.cancel': 'Cancel',
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
    'index.ctaHeading': 'Do you want to be a heart of it?',
    'index.ctaButton': 'Make a Pledge',

    // Pledge page — static
    'pledge.docTitle': 'Make a Pledge | Tenovice Fundraising',
    'pledge.eyebrow': 'Tenovice Fundraising',
    'pledge.title': 'Make your pledge',
    'pledge.description':
      'First enter your email. If you already made a pledge, you can review it and decide whether to update it.',
    'pledge.lookupHeading': 'Start with your email',
    'pledge.lookupIntro': 'We will check whether you already have a pledge in the system.',
    'pledge.emailLabel': 'Email',
    'pledge.continue': 'Continue',
    'pledge.existingHeading': 'Existing pledge found',
    'pledge.existingIntro':
      'We found a pledge for this email. You can review it and choose whether to update it.',
    'pledge.fieldAmount': 'Amount',
    'pledge.fieldAmountEur': 'Amount (EUR)',
    'pledge.fieldType': 'Type',
    'pledge.fieldEndDate': 'End date',
    'pledge.fieldCampaignTotal': 'Campaign total',
    'pledge.fieldMessage': 'Message',
    'pledge.fieldMessageOptional': 'Message (optional)',
    'pledge.editExisting': 'Yes, edit pledge',
    'pledge.monthlyCheckbox': 'This is a monthly recurring pledge',
    'pledge.endMonth': 'End month',
    'pledge.endYear': 'End year',
    'pledge.selectMonth': 'Select month',
    'pledge.msgPlaceholder': 'Optional message to accompany the pledge',
    'pledge.save': 'Save pledge',
    'pledge.previewHeading': 'Live preview',
    'pledge.previewImpact': 'Pledge total impact',
    'pledge.previewMonthlyEffect': 'Monthly effect',
    'pledge.previewPledgedTotal': 'Updated pledged total',
    'pledge.previewMonthlyTotal': 'Updated monthly total',
    'pledge.previewProgress': 'Updated progress toward common goal',
    'pledge.previewOf': 'of',
    'pledge.monthlyNote':
      '<strong>Monthly pledge:</strong> total impact equals amount × remaining months until the selected end month and year.',

    // Months
    'month.1': 'January',
    'month.2': 'February',
    'month.3': 'March',
    'month.4': 'April',
    'month.5': 'May',
    'month.6': 'June',
    'month.7': 'July',
    'month.8': 'August',
    'month.9': 'September',
    'month.10': 'October',
    'month.11': 'November',
    'month.12': 'December',

    // Pledge page — dynamic (JS)
    'pledge.formTitleCreate': 'Your pledge',
    'pledge.formTitleEdit': 'Update your pledge',
    'pledge.formIntroCreate': 'All preview values below update live before you save.',
    'pledge.formIntroEdit':
      'You are editing an existing pledge. Preview values replace your current pledge in totals.',
    'pledge.typeMonthly': 'Monthly recurring',
    'pledge.typeOneTime': 'One-time',
    'pledge.modeCreate':
      '<strong>New pledge mode:</strong> preview adds this pledge on top of current totals.',
    'pledge.modeEdit':
      '<strong>Edit mode:</strong> preview replaces your existing pledge in current totals.',
    'pledge.btnChecking': 'Checking…',
    'pledge.btnSaving': 'Saving…',
    'pledge.statusEnterEmail': 'Enter your email to begin.',
    'pledge.statusMonthly': 'Monthly impact uses {n} remaining month(s).',
    'pledge.statusSelectEnd': 'Select end month and end year to calculate total impact.',
    'pledge.statusEditOneTime': 'Editing existing one-time pledge.',
    'pledge.statusCreateOneTime': 'Creating new one-time pledge.',
    'pledge.statusNoStats': 'Could not load current stats. Preview may be unavailable.',
    'pledge.errEmailRequired': 'Please enter your email.',
    'pledge.errAmount': 'Amount must be greater than 0.',
    'pledge.errEndMonth': 'End month must be between 1 and 12.',
    'pledge.errEndYear': 'Please enter a valid end year.',
    'pledge.errEndPast': 'Monthly pledge end date must be in the current or a future month.',
    'pledge.errLookup': 'Could not check existing pledge. Please try again.',
    'pledge.errSave': 'Could not save pledge. Please try again.',

    // Success page
    'success.docTitle': 'Pledge Saved | Tenovice Fundraising',
    'success.thankYou': 'Thank you',
    'success.heading': 'Your pledge was saved',
    'success.description':
      'Thank you for supporting the Tenovice Project. You can now return to the homepage and see the refreshed campaign view.',
    'success.another': 'Make another pledge',
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
