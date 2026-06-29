#!/usr/bin/env node
// i18n parity checker: every language in web/i18n.js must define exactly the same
// set of keys as the default language. Exits non-zero (with a report) on any
// missing or extra key, so a half-translated string can't ship.
//
// Run: node tools/check-i18n-parity.js

const path = require('path');

const { TRANSLATIONS, I18N_DEFAULT_LANG } = require(path.join(__dirname, '..', 'web', 'i18n.js'));

const baseLang = I18N_DEFAULT_LANG;
const baseKeys = new Set(Object.keys(TRANSLATIONS[baseLang]));
let ok = true;

for (const lang of Object.keys(TRANSLATIONS)) {
  if (lang === baseLang) continue;

  const keys = new Set(Object.keys(TRANSLATIONS[lang]));
  const missing = [...baseKeys].filter((k) => !keys.has(k));
  const extra = [...keys].filter((k) => !baseKeys.has(k));

  if (missing.length || extra.length) {
    ok = false;
    console.error(`✗ ${lang}: ${missing.length} missing, ${extra.length} extra vs '${baseLang}'`);
    missing.forEach((k) => console.error(`    missing: ${k}`));
    extra.forEach((k) => console.error(`    extra:   ${k}`));
  } else {
    console.log(`✓ ${lang}: ${keys.size} keys, in parity with '${baseLang}'`);
  }
}

if (!ok) {
  console.error('\ni18n parity check FAILED');
  process.exit(1);
}
console.log(`\ni18n parity check passed (${baseKeys.size} keys per language)`);
