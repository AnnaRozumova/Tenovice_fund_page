// Pledge page (D2 + AUTH2). The page is gated: a signed-out visitor is bounced to
// auth.html (only the home page is public, D18). Identity is the signed-in Cognito
// account, so the old email-lookup step is gone — the user's email comes from the
// session, and any existing pledge is loaded automatically. Two flows on the page:
//   1. The what-if SIMULATOR (zones 1+2): inputs -> "Calculate" button -> POST
//      /calculate -> render the returned result. No math in JS (single source of
//      truth is the backend, D8/D15); the call fires on the button, never on every
//      keystroke (Ondra: one request per keystroke would be wasteful).
//   2. The account's pledges (zone 3): since Phase M (D23) one account may hold
//      several, shown as a list of rows — each edited (PUT /pledges/{id}) or deleted
//      (DELETE /pledges/{id}), plus "add another" (POST /pledges). No "how many
//      people" field (that's the simulator) and no email field (known from the
//      session). Supporters count distinct accounts, not pledges.
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
let pledges = []; // the account's pledges (Phase M/D23 — one account may have several)
let editingId = null; // pledge_id being edited, or null when the form is in create mode
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

// The monthly forms take a number of months ("I'd contribute for N months from
// now"), which is friendlier than picking an end month + year. The backend still
// owns the impact math and works in an absolute (end_month, end_year) — D8 — so we
// only convert N <-> (end_month, end_year) at the input boundary, here. The backend
// counts remaining months inclusively from the current month, so N months ends
// (N - 1) months after the current one. This is input prep, not impact math.
const MAX_MONTHS = 600;

function monthsToEndDate(months) {
  const now = new Date();
  const zeroBased = now.getMonth() + (months - 1); // 0-indexed current month + (N-1)
  return {
    end_month: (zeroBased % 12) + 1,
    end_year: now.getFullYear() + Math.floor(zeroBased / 12),
  };
}

// Reverse: how many months from the current month up to a stored end date (inclusive),
// used to pre-fill the edit form. Floored at 1 so a returning user never sees 0/blank.
function endDateToMonths(endMonth, endYear) {
  const now = new Date();
  const months = (endYear - now.getFullYear()) * 12 + (endMonth - (now.getMonth() + 1)) + 1;
  return months > 0 ? months : 1;
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
  $('barPledged').textContent = formatCurrency(currentStats.pledged_total);
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
  const months = parseInt($('simMonths').value, 10);
  return { people, amount, months };
}

function validateSimInputs(values) {
  if (!Number.isFinite(values.people) || values.people < 1) {
    return t('sim.errInputs');
  }
  if (!Number.isFinite(values.amount) || values.amount <= 0) {
    return t('sim.errInputs');
  }
  if (simIsMonthly) {
    if (!Number.isFinite(values.months) || values.months < 1 || values.months > MAX_MONTHS) {
      return t('pledge.errMonths');
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
    const end = monthsToEndDate(values.months);
    payload.end_month = end.end_month;
    payload.end_year = end.end_year;
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
    months: parseInt($('months').value, 10),
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
    if (!Number.isFinite(values.months) || values.months < 1 || values.months > MAX_MONTHS) {
      return t('pledge.errMonths');
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
    const end = monthsToEndDate(values.months);
    payload.end_month = end.end_month;
    payload.end_year = end.end_year;
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

  // Editing an existing pledge → PUT /pledges/{id}; a new one → POST /pledges.
  const editing = Boolean(editingId);
  const path = editing ? `/pledges/${encodeURIComponent(editingId)}` : '/pledges';

  let response = null;
  let threw = false;
  try {
    response = await Auth.apiFetch(withCurrency(path), {
      method: editing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildPayload(values)),
    });
  } catch (error) {
    response = null;
    threw = true;
  }

  if (!response || !response.ok) {
    console.error('Error saving pledge');
    // A thrown fetch (network blip) on a CREATE is ambiguous — the POST may have
    // reached the server and stored the pledge even though we never saw the reply.
    // There is no upsert (D23: POST always creates), so a blind retry would make a
    // duplicate. Tell the user to refresh and check first. A definitive server
    // rejection (a response with !ok) or an edit (PUT is idempotent by id) is safe
    // to retry with the normal message.
    const ambiguousCreate = threw && !editing;
    showError('formError', t(ambiguousCreate ? 'pledge.errSaveUnconfirmed' : 'pledge.errSave'));
    button.disabled = false;
    button.textContent = t('pledge.save');
    return;
  }

  // Saved. A new pledge → the payment path (one-time → QR, monthly → standing order, E1).
  if (!editing) {
    const type = values.is_monthly ? 'monthly' : 'one-time';
    window.location.href = `success.html?type=${type}`;
    return;
  }

  // Edit saved → back to the (refreshed) list. The pledge is already stored, so a reload
  // hiccup must NOT read as a save failure; fall back to rendering what we have.
  editingId = null;
  button.disabled = false;
  button.textContent = t('pledge.save');
  try {
    await reloadPledges();
  } catch (error) {
    console.error('Error refreshing after edit:', error);
    renderZone3();
  }
}

function setupPledgeForm() {
  $('is_monthly').addEventListener('change', toggleMonthlyFields);
  $('pledgeForm').addEventListener('submit', submitPledge);
  $('addPledgeButton').addEventListener('click', openCreateForm);
  $('cancelPledgeButton').addEventListener('click', cancelForm);
}

// Zone-3 form heading/intro depend on create vs edit, so they are set in JS and
// re-applied on a language switch (data-i18n covers the rest of the markup).
function setFormModeText() {
  $('pledgeFormTitle').textContent = editingId
    ? t('pledge.formTitleEdit')
    : t('pledge.zoneHeading');
  $('pledgeFormIntro').textContent = editingId
    ? t('pledge.formIntroEdit')
    : t('pledge.zoneIntro');
}

function fillPledgeForm(values) {
  $('amount').value = Number(values.amount || 0) || '';
  $('is_monthly').checked = Boolean(values.is_monthly);
  // The pledge is stored with an absolute end month/year; show it as the remaining
  // number of months (the input the form now uses).
  $('months').value =
    values.is_monthly && values.end_month && values.end_year
      ? String(endDateToMonths(values.end_month, values.end_year))
      : '';
  $('message').value = values.message || '';
  toggleMonthlyFields();
}

// ============ Step transitions ============

function showFlowSection() {
  $('authLoading').classList.add('hidden');
  $('pledgeFlowSection').classList.remove('hidden');

  renderTopbar();
  renderSupporters();
  $('simGoalAmount').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
  renderSimPlaceholder();
}

// ---- zone-3: list vs form visibility ----

function showList() {
  $('pledgeList').classList.remove('hidden');
  $('pledgeFormWrap').classList.add('hidden');
}

function showForm() {
  $('pledgeFormWrap').classList.remove('hidden');
  $('pledgeList').classList.add('hidden');
  // "Cancel" only makes sense when there's a list to return to.
  $('cancelPledgeButton').classList.toggle('hidden', pledges.length === 0);
}

// Human label for a pledge row's type ("one-time", or "monthly · N months").
function pledgeTypeLabel(pledge) {
  if (!pledge.is_monthly) {
    return t('pledge.rowOneTime');
  }
  if (pledge.end_month && pledge.end_year) {
    const months = endDateToMonths(pledge.end_month, pledge.end_year);
    return `${t('pledge.rowMonthly')} · ${t('sim.durationMonths', { n: months })}`;
  }
  return t('pledge.rowMonthly');
}

function renderPledgeRows() {
  const list = $('pledgeListItems');
  list.innerHTML = '';

  pledges.forEach((pledge) => {
    const row = document.createElement('li');
    row.className = 'pledge-row';

    const info = document.createElement('div');
    info.className = 'pledge-row-info';

    const head = document.createElement('div');
    head.className = 'pledge-row-head';
    const amount = document.createElement('span');
    amount.className = 'pledge-row-amount';
    amount.textContent = formatCurrency(Number(pledge.amount));
    const type = document.createElement('span');
    type.className = 'pledge-row-type';
    type.textContent = pledgeTypeLabel(pledge);
    head.appendChild(amount);
    head.appendChild(type);
    info.appendChild(head);

    const impact = document.createElement('div');
    impact.className = 'pledge-row-impact';
    impact.textContent = t('pledge.rowImpact', {
      amount: formatCurrency(Number(pledge.campaign_total)),
    });
    info.appendChild(impact);

    if (pledge.message) {
      const msg = document.createElement('div');
      msg.className = 'pledge-row-message';
      // textContent — the message is user-controlled; never inject it as HTML.
      msg.textContent = pledge.message;
      info.appendChild(msg);
    }

    const actions = document.createElement('div');
    actions.className = 'pledge-row-actions';
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'row-btn row-edit';
    editBtn.textContent = t('pledge.edit');
    editBtn.addEventListener('click', () => openEditForm(pledge.pledge_id));
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'row-btn row-delete';
    delBtn.textContent = t('pledge.delete');
    delBtn.addEventListener('click', () => deletePledgeRow(pledge.pledge_id));
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);

    row.appendChild(info);
    row.appendChild(actions);
    list.appendChild(row);
  });
}

// Render zone 3 from the current `pledges`: a non-empty account sees the list; an
// empty one drops straight into the create form (nothing to list yet).
function renderZone3() {
  if (pledges.length > 0) {
    renderPledgeRows();
    showList();
  } else {
    openCreateForm();
  }
}

function openCreateForm() {
  editingId = null;
  setFormModeText();
  fillPledgeForm({ amount: '', is_monthly: false, end_month: '', end_year: '', message: '' });
  hideError('formError');
  showForm();
}

function openEditForm(id) {
  const pledge = pledges.find((p) => p.pledge_id === id);
  if (!pledge) {
    return;
  }
  editingId = id;
  setFormModeText();
  fillPledgeForm(pledge);
  hideError('formError');
  showForm();
}

function cancelForm() {
  // Back to the list when there is one; on an empty account the create form is the
  // only view, so there is nothing to cancel to.
  if (pledges.length > 0) {
    renderPledgeRows();
    showList();
  }
}

// Fetch the account's pledges (a list since Phase M/D23). Throws on a failed request
// so the caller can show the retry state instead of dropping the user into a blank form.
async function loadPledges() {
  const response = await Auth.apiFetch(
    withCurrency(`/pledges/by-email?email=${encodeURIComponent(pledgeEmail)}`)
  );
  if (!response.ok) {
    throw new Error('Failed to load pledges');
  }
  const data = await response.json();
  pledges = Array.isArray(data.pledges) ? data.pledges : [];
}

// Re-fetch pledges + stats and re-render zone 3 (after an edit or delete).
async function reloadPledges() {
  await loadPledges();
  await loadStats();
  renderSupporters();
  renderZone3();
}

async function deletePledgeRow(id) {
  if (!window.confirm(t('pledge.deleteConfirm'))) {
    return;
  }
  try {
    const response = await Auth.apiFetch(
      `/pledges/${encodeURIComponent(id)}?email=${encodeURIComponent(pledgeEmail)}`,
      { method: 'DELETE' }
    );
    if (!response.ok) {
      throw new Error('Failed to delete pledge');
    }
    await reloadPledges();
  } catch (error) {
    console.error('Error deleting pledge:', error);
    window.alert(t('pledge.errDelete'));
  }
}

// Show the load-failed state inside the gate card with a retry, instead of silently
// dropping a returning pledger into an empty form.
function showLookupError() {
  $('authLoadingText').classList.add('hidden');
  $('authLoadingError').classList.remove('hidden');
}

// Load the signed-in user's stats + any existing pledge, then reveal the calc page in
// the right mode: a returning user lands straight in edit mode with their pledge
// pre-filled (no separate review card — this page already shows that pledge); a new
// user gets the empty create form.
async function startPledgeFlow() {
  await loadStats();
  try {
    await loadPledges();
    showFlowSection();
    renderZone3(); // list if the account has pledges, else the empty create form
  } catch (error) {
    // Don't guess — surface the failure so the user can retry rather than risk
    // adding a duplicate from a form shown over a failed load.
    console.error('Error loading pledges:', error);
    showLookupError();
  }
}

function setupRetry() {
  $('authRetryButton').addEventListener('click', () => window.location.reload());
}

// On a language switch the currency switches too (D22), so we re-fetch money in the
// new currency rather than just re-symboling stale numbers. data-i18n covers the
// static markup automatically; this refreshes the JS-rendered, currency-bearing parts.
async function refreshDynamicI18n() {
  renderAuthStatus('pledgeAuth');
  await loadConfig(); // CONFIG.* now in the new currency

  if ($('pledgeFlowSection').classList.contains('hidden')) {
    return;
  }

  await loadStats();
  renderTopbar();
  renderSupporters();
  $('simGoalAmount').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
  // The last sim result was computed in the old currency and the amount input is now
  // read as the new currency — clear it so the user recalculates intentionally.
  renderSimPlaceholder();

  // Re-fetch the pledges in the new currency (amounts are converted server-side, D22).
  const formOpen = !$('pledgeFormWrap').classList.contains('hidden');
  try {
    await loadPledges();
  } catch (error) {
    console.error('Error refreshing pledges:', error);
    return;
  }

  if (formOpen && editingId) {
    // An edit form is open: re-fill it from the refreshed pledge so its amount shows
    // the new currency (fall back to the list if that pledge just disappeared).
    const pledge = pledges.find((p) => p.pledge_id === editingId);
    if (pledge) {
      setFormModeText();
      fillPledgeForm(pledge);
    } else {
      renderZone3();
    }
  } else if (formOpen) {
    // A create form is open. Relabel its heading, and clear the amount: it was typed in
    // the old currency and would now be read as the new one on save (same reason the
    // simulator amount is cleared above). Message/months are currency-independent.
    setFormModeText();
    $('amount').value = '';
  } else {
    renderZone3();
  }
}

async function initPledgePage() {
  await loadConfig();
  setupRetry();
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
