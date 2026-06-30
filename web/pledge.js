// Pledge page (D2 + AUTH2). The page is gated: a signed-out visitor is bounced to
// auth.html (only the home page is public, D18). Identity is the signed-in Cognito
// account, so the old email-lookup step is gone — the user's email comes from the
// session, and any existing pledge is loaded automatically. Two flows on the page:
//   1. The what-if SIMULATOR (zones 1+2): inputs -> "Calculate" button -> POST
//      /calculate -> render the returned result. No math in JS (single source of
//      truth is the backend, D8/D15); the call fires on the button, never on every
//      keystroke (Ondra: one request per keystroke would be wasteful).
//   2. The user's own one-person pledge (zone 3): POST /pledges. No "how many
//      people" field (that's the simulator) and no email field (known from the
//      session). 1 pledge = 1 supporter (B4).
// Every API call goes through Auth.apiFetch, which attaches the bearer id-token
// (the authorizer that requires it lands in AUTH3 — until then the API is open).

// Mirror of the backend caps so junk is rejected before any request. The amount cap
// is in the page currency: the backend cap is 2,500,000 CZK (~€100k) and an EUR amount
// is normalized to CZK before it applies, so the EUR-side cap is ~€100k (D22).
const MAX_AMOUNT_CZK = 2500000;
const MAX_AMOUNT_EUR = 100000;
const MAX_MESSAGE_LENGTH = 500;

function maxAmount() {
  return currentCurrency() === 'eur' ? MAX_AMOUNT_EUR : MAX_AMOUNT_CZK;
}

let currentStats = {
  pledged_total: 0,
  monthly_total: 0,
  contributors_count: 0,
};

let pledgeEmail = '';
let existingPledge = null;
let isEditMode = false;
let simIsMonthly = false;
let lastCalc = null; // last /calculate result, kept so a language switch can re-render it

function $(id) {
  return document.getElementById(id);
}

function showError(elementId, message) {
  const element = $(elementId);
  element.textContent = message;
  element.classList.remove('hidden');
}

function hideError(elementId) {
  const element = $(elementId);
  element.textContent = '';
  element.classList.add('hidden');
}

// (end_year, end_month) strictly before (now.year, now.month) — mirrors the
// backend reject_past check. Used only for input validation, not for any impact
// math (that lives on the backend).
function isEndDateInPast(month, year) {
  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();
  return year < currentYear || (year === currentYear && month < currentMonth);
}

// ============ Stats / config-driven chrome ============

async function loadStats() {
  try {
    const response = await Auth.apiFetch(withCurrency('/stats'));
    if (!response.ok) {
      throw new Error('Failed to fetch stats');
    }
    const data = await response.json();
    currentStats = {
      pledged_total: Number(data.pledged_total || 0),
      monthly_total: Number(data.monthly_total || 0),
      contributors_count: Number(data.contributors_count || 0),
    };
  } catch (error) {
    console.error('Error loading stats:', error);
  }
}

// Sticky top bar: real money raised vs goal (same metric as the home page).
function renderTopbar() {
  $('barBalance').textContent = formatCurrency(CONFIG.CURRENT_BALANCE);
  $('barGoal').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
  const pct = calculateProgress(CONFIG.CURRENT_BALANCE, CONFIG.FUNDRAISING_GOAL);
  $('barProgress').style.width = `${Math.max(0, Math.min(pct, 100))}%`;
  $('barProgressPct').textContent = `${pct}%`;
}

// Social-proof strip: "X friends already pledged €Y" (innerHTML for the <strong>
// emphasis; values come from the t() params, so they are escaped numbers/currency).
function renderSupporters() {
  $('supportersStripText').innerHTML = t('index.supportersStrip', {
    count: currentStats.contributors_count,
    amount: formatCurrency(currentStats.pledged_total),
  });
}

// ============ Simulator (zones 1 + 2) ============

function setSimType(monthly) {
  simIsMonthly = monthly;
  $('simTypeOneTime').classList.toggle('active', !monthly);
  $('simTypeMonthly').classList.toggle('active', monthly);
  $('simTypeOneTime').setAttribute('aria-pressed', String(!monthly));
  $('simTypeMonthly').setAttribute('aria-pressed', String(monthly));

  const monthlyFields = $('simMonthlyFields');
  monthlyFields.classList.toggle('hidden', !monthly);
  monthlyFields.setAttribute('aria-hidden', String(!monthly));
}

function clampWidth(value) {
  return Math.max(0, Math.min(value, 100));
}

function renderSimPlaceholder() {
  lastCalc = null;
  $('simBigAmount').textContent = '—';
  $('simBigSub').textContent = t('sim.placeholder');
  $('simDetail').classList.add('hidden');
}

function renderSimResult(result) {
  lastCalc = result;

  const people = Number(result.people);
  const amount = Number(result.amount);
  const monthly = Boolean(result.is_monthly);

  $('simBigAmount').textContent = formatCurrency(Number(result.total_impact));
  $('simBigSub').textContent = t(
    monthly ? 'sim.peopleAmountMonthly' : 'sim.peopleAmountOneTime',
    { people, amount: formatCurrency(amount) }
  );

  $('simTotalImpact').textContent = formatCurrency(Number(result.total_impact));

  if (monthly) {
    $('simMonthlyRow').classList.remove('hidden');
    $('simDurationRow').classList.remove('hidden');
    $('simMonthlyEffect').textContent = formatCurrency(Number(result.monthly_effect));
    $('simDuration').textContent = t('sim.durationMonths', { n: Number(result.remaining_months) });
  } else {
    $('simMonthlyRow').classList.add('hidden');
    $('simDurationRow').classList.add('hidden');
  }

  const baseline = Number(result.baseline_progress_pct);
  const scenario = Number(result.scenario_progress_pct);
  const projected = Number(result.projected_progress_pct);

  const baseWidth = clampWidth(baseline);
  const addWidth = clampWidth(scenario);
  $('simSegBase').style.width = `${baseWidth}%`;
  $('simSegAdd').style.width = `${clampWidth(baseWidth + addWidth) - baseWidth}%`;

  $('simProjectedPct').textContent = `${Math.round(projected)}%`;
  $('simLegendNow').textContent = t('sim.legendNow', { pct: Math.round(baseline) });
  $('simLegendScenario').textContent = t('sim.legendScenario', { pct: Math.round(scenario) });
  $('simProjectedTotal').textContent = formatCurrency(Number(result.projected_total));
  $('simGoalAmount').textContent = formatCurrency(Number(result.goal));

  $('simDetail').classList.remove('hidden');
}

function getSimInputs() {
  const people = parseInt($('simPeople').value, 10);
  const amount = Number($('simAmount').value);
  const endMonth = parseInt($('simEndMonth').value, 10);
  const endYear = parseInt($('simEndYear').value, 10);
  return { people, amount, endMonth, endYear };
}

function validateSimInputs(values) {
  if (!Number.isFinite(values.people) || values.people < 1) {
    return t('sim.errInputs');
  }
  if (!Number.isFinite(values.amount) || values.amount <= 0) {
    return t('sim.errInputs');
  }
  if (simIsMonthly) {
    if (!values.endMonth || values.endMonth < 1 || values.endMonth > 12 || !values.endYear) {
      return t('sim.errEndDate');
    }
  }
  return '';
}

async function runCalculate() {
  hideError('simError');

  const values = getSimInputs();
  const validationError = validateSimInputs(values);
  if (validationError) {
    showError('simError', validationError);
    return;
  }

  const payload = {
    people: values.people,
    amount: values.amount,
    is_monthly: simIsMonthly,
  };
  if (simIsMonthly) {
    payload.end_month = values.endMonth;
    payload.end_year = values.endYear;
  }

  const button = $('simCalcButton');
  button.disabled = true;
  button.textContent = t('sim.btnCalculating');

  try {
    const response = await Auth.apiFetch(withCurrency('/calculate'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error('Calculate failed');
    }
    const data = await response.json();
    renderSimResult(data);
  } catch (error) {
    console.error('Error running calculation:', error);
    showError('simError', t('sim.errCalc'));
  } finally {
    button.disabled = false;
    button.textContent = t('sim.calcButton');
  }
}

function setupSimulator() {
  $('simTypeOneTime').addEventListener('click', () => setSimType(false));
  $('simTypeMonthly').addEventListener('click', () => setSimType(true));
  $('simCalcButton').addEventListener('click', runCalculate);
}

// ============ Pledge form (zone 3) ============

function toggleMonthlyFields() {
  const monthlyFields = $('monthlyFields');
  const monthly = $('is_monthly').checked;
  monthlyFields.classList.toggle('hidden', !monthly);
  monthlyFields.setAttribute('aria-hidden', String(!monthly));
}

function getPledgeValues() {
  return {
    amount: Number($('amount').value),
    is_monthly: $('is_monthly').checked,
    end_month: parseInt($('end_month').value, 10),
    end_year: parseInt($('end_year').value, 10),
    message: $('message').value.trim(),
  };
}

function validatePledgeForm(values) {
  if (!Number.isFinite(values.amount) || values.amount <= 0) {
    return t('pledge.errAmount');
  }
  if (values.amount > maxAmount()) {
    return t('pledge.errAmountMax', { max: formatCurrency(maxAmount()) });
  }
  if (values.message.length > MAX_MESSAGE_LENGTH) {
    return t('pledge.errMessageMax', { max: MAX_MESSAGE_LENGTH });
  }
  if (values.is_monthly) {
    if (!values.end_month || values.end_month < 1 || values.end_month > 12) {
      return t('pledge.errEndMonth');
    }
    if (!values.end_year || values.end_year < new Date().getFullYear()) {
      return t('pledge.errEndYear');
    }
    if (isEndDateInPast(values.end_month, values.end_year)) {
      return t('pledge.errEndPast');
    }
  }
  return '';
}

function buildPayload(values) {
  const payload = {
    email: pledgeEmail,
    amount: values.amount,
    is_monthly: values.is_monthly,
  };
  if (values.message) {
    payload.message = values.message;
  }
  if (values.is_monthly) {
    payload.end_month = values.end_month;
    payload.end_year = values.end_year;
  }
  return payload;
}

async function submitPledge(event) {
  event.preventDefault();
  hideError('formError');

  const values = getPledgeValues();
  const validationError = validatePledgeForm(values);
  if (validationError) {
    showError('formError', validationError);
    return;
  }

  const button = $('savePledgeButton');
  button.disabled = true;
  button.textContent = t('pledge.btnSaving');

  try {
    const response = await Auth.apiFetch(withCurrency('/pledges'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildPayload(values)),
    });
    if (!response.ok) {
      throw new Error('Failed to save pledge');
    }
    // Tell the success page which payment path to show: one-time -> QR,
    // monthly -> standing-order bank details (E1).
    const type = values.is_monthly ? 'monthly' : 'one-time';
    window.location.href = `success.html?type=${type}`;
  } catch (error) {
    console.error('Error saving pledge:', error);
    showError('formError', t('pledge.errSave'));
    button.disabled = false;
    button.textContent = t('pledge.save');
  }
}

function setupPledgeForm() {
  $('is_monthly').addEventListener('change', toggleMonthlyFields);
  $('pledgeForm').addEventListener('submit', submitPledge);
}

// Zone-3 heading/intro depend on create vs edit, so they are set in JS and
// re-applied on a language switch (data-i18n covers the rest of the markup).
function setFormModeText() {
  $('pledgeFormTitle').textContent = isEditMode
    ? t('pledge.formTitleEdit')
    : t('pledge.zoneHeading');
  $('pledgeFormIntro').textContent = isEditMode
    ? t('pledge.formIntroEdit')
    : t('pledge.zoneIntro');
}

function fillPledgeForm(values) {
  $('amount').value = Number(values.amount || 0) || '';
  $('is_monthly').checked = Boolean(values.is_monthly);
  $('end_month').value = values.end_month ? String(values.end_month) : '';
  $('end_year').value = values.end_year ? String(values.end_year) : '';
  $('message').value = values.message || '';
  toggleMonthlyFields();
}

// ============ Step transitions ============

function showFlowSection() {
  $('authLoading').classList.add('hidden');
  $('existingPledgeCard').classList.add('hidden');
  $('pledgeFlowSection').classList.remove('hidden');

  renderTopbar();
  renderSupporters();
  $('simGoalAmount').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
  renderSimPlaceholder();
  setFormModeText();
}

function enterCreateMode(email) {
  pledgeEmail = email;
  existingPledge = null;
  isEditMode = false;
  showFlowSection();
  fillPledgeForm({ amount: '', is_monthly: false, end_month: '', end_year: '', message: '' });
}

function enterEditMode() {
  if (!existingPledge) {
    return;
  }
  isEditMode = true;
  showFlowSection();
  fillPledgeForm(existingPledge);
}

function populateExistingSummary(data) {
  // The by-email response no longer echoes the email (H1); show the one the user
  // just entered for the lookup (already stored in pledgeEmail).
  $('existingEmail').textContent = pledgeEmail || '-';
  $('existingAmount').textContent = formatCurrency(Number(data.amount || 0));
  $('existingCampaignTotal').textContent = formatCurrency(Number(data.campaign_total || 0));
  $('existingMessage').textContent = data.message ? data.message : '-';

  if (data.is_monthly) {
    $('existingType').textContent = t('pledge.typeMonthly');
    $('existingEndDate').textContent = `${data.end_month}/${data.end_year}`;
    $('existingEndDateRow').classList.remove('hidden');
  } else {
    $('existingType').textContent = t('pledge.typeOneTime');
    $('existingEndDateRow').classList.add('hidden');
  }
}

async function lookupPledgeByEmail(email) {
  const response = await Auth.apiFetch(
    withCurrency(`/pledges/by-email?email=${encodeURIComponent(email)}`)
  );
  // Guard the parse: an error response may carry a non-JSON body (gateway HTML).
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  return { response, data };
}

// Show the lookup-failed state inside the gate card with a retry, instead of
// silently dropping a returning pledger into the empty create form.
function showLookupError() {
  $('authLoadingText').classList.add('hidden');
  $('authLoadingError').classList.remove('hidden');
}

// Load the signed-in user's stats + any existing pledge, then reveal the right
// state: the existing-pledge review card (returning user) or the create flow.
async function startPledgeFlow() {
  await loadStats();

  try {
    const { response, data } = await lookupPledgeByEmail(pledgeEmail);
    const notFound = response.status === 404 || (data && data.message === 'not found');

    if (response.ok && data && !notFound) {
      $('authLoading').classList.add('hidden');
      existingPledge = data;
      isEditMode = false;
      populateExistingSummary(data);
      $('existingPledgeCard').classList.remove('hidden');
      return;
    }
    if (notFound) {
      enterCreateMode(pledgeEmail); // hides authLoading via showFlowSection
      return;
    }
    throw new Error('Lookup failed');
  } catch (error) {
    // Don't guess — surface the failure so the user can retry rather than risk
    // overwriting an existing pledge from a blank form.
    console.error('Error loading existing pledge:', error);
    showLookupError();
  }
}

function setupExistingCard() {
  $('editExistingButton').addEventListener('click', enterEditMode);
  $('authRetryButton').addEventListener('click', () => window.location.reload());
}

// On a language switch the currency switches too (D22), so we re-fetch money in the
// new currency rather than just re-symboling stale numbers. data-i18n covers the
// static markup automatically; this refreshes the JS-rendered, currency-bearing parts.
async function refreshDynamicI18n() {
  renderAuthStatus('pledgeAuth');
  await loadConfig(); // CONFIG.* now in the new currency

  if (existingPledge && !$('existingPledgeCard').classList.contains('hidden')) {
    const { response, data } = await lookupPledgeByEmail(pledgeEmail);
    if (response.ok && data) {
      existingPledge = data;
    }
    populateExistingSummary(existingPledge);
  }

  if (!$('pledgeFlowSection').classList.contains('hidden')) {
    await loadStats();
    renderTopbar();
    renderSupporters();
    $('simGoalAmount').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
    setFormModeText();
    // The last result was computed in the old currency, and the amount input is now
    // read as the new currency — clear it so the user recalculates intentionally.
    renderSimPlaceholder();
  }
}

async function initPledgePage() {
  await loadConfig();
  setupExistingCard();
  setupSimulator();
  setupPledgeForm();
  document.addEventListener('i18n:changed', refreshDynamicI18n);

  // Gate the page (AUTH2): bounce a signed-out visitor to the auth screens.
  const session = await Auth.requireAuth();
  if (!session) {
    return; // redirecting to auth.html
  }

  pledgeEmail = await Auth.getEmail();
  await renderAuthStatus('pledgeAuth');
  await startPledgeFlow();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPledgePage);
} else {
  initPledgePage();
}
