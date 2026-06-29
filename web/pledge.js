// Pledge page (D2). Two distinct flows on one page:
//   1. The what-if SIMULATOR (zones 1+2): inputs -> "Calculate" button -> POST
//      /calculate -> render the returned result. No math in JS (single source of
//      truth is the backend, D8/D15); the call fires on the button, never on every
//      keystroke (Ondra: one request per keystroke would be wasteful).
//   2. The user's own one-person pledge (zone 3): POST /pledges. No "how many
//      people" field (that's the simulator) and no email field (known from the
//      lookup step). 1 pledge = 1 supporter (B4).

// Mirror of the backend EMAIL_RE / caps so junk is rejected before any request.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MAX_AMOUNT = 100000;
const MAX_MESSAGE_LENGTH = 500;

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

function isValidEmail(email) {
  return EMAIL_RE.test(email);
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
    const response = await fetch(`${CONFIG.API_URL}/stats`);
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
    const response = await fetch(`${CONFIG.API_URL}/calculate`, {
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
  if (values.amount > MAX_AMOUNT) {
    return t('pledge.errAmountMax', { max: formatCurrency(MAX_AMOUNT) });
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
    const response = await fetch(`${CONFIG.API_URL}/pledges`, {
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
  $('lookupHero').classList.add('hidden');
  $('lookupCard').classList.add('hidden');
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
  const response = await fetch(`${CONFIG.API_URL}/pledges/by-email?email=${encodeURIComponent(email)}`);
  const data = await response.json();
  return { response, data };
}

async function handleLookup() {
  hideError('lookupError');

  const button = $('lookupButton');
  const email = $('lookupEmail').value.trim();

  if (!email) {
    showError('lookupError', t('pledge.errEmailRequired'));
    return;
  }
  if (!isValidEmail(email)) {
    showError('lookupError', t('pledge.errEmailFormat'));
    return;
  }

  button.disabled = true;
  button.textContent = t('pledge.btnChecking');

  try {
    await loadStats();
    const { response, data } = await lookupPledgeByEmail(email);

    if (!response.ok && data.message !== 'not found') {
      throw new Error('Lookup failed');
    }

    if (data.message === 'not found') {
      enterCreateMode(email);
      return;
    }

    pledgeEmail = email;
    existingPledge = data;
    isEditMode = false;
    populateExistingSummary(data);
    $('existingPledgeCard').classList.remove('hidden');
  } catch (error) {
    console.error('Error looking up pledge:', error);
    showError('lookupError', t('pledge.errLookup'));
  } finally {
    button.disabled = false;
    button.textContent = t('pledge.continue');
  }
}

function setupLookup() {
  $('lookupButton').addEventListener('click', handleLookup);
  $('editExistingButton').addEventListener('click', enterEditMode);
}

// On a language switch, refresh the strings JS renders at runtime (data-i18n
// covers the static markup automatically).
function refreshDynamicI18n() {
  if (existingPledge && !$('existingPledgeCard').classList.contains('hidden')) {
    populateExistingSummary(existingPledge);
  }
  if (!$('pledgeFlowSection').classList.contains('hidden')) {
    renderSupporters();
    setFormModeText();
    if (lastCalc) {
      renderSimResult(lastCalc);
    } else {
      renderSimPlaceholder();
    }
  }
}

async function initPledgePage() {
  await loadConfig();
  setupLookup();
  setupSimulator();
  setupPledgeForm();
  document.addEventListener('i18n:changed', refreshDynamicI18n);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPledgePage);
} else {
  initPledgePage();
}
