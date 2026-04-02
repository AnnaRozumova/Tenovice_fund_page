let currentStats = {
  pledged_total: 0,
  monthly_total: 0,
  pledgers_count: 0,
};

let existingPledge = null;
let isEditMode = false;

function $(id) {
  return document.getElementById(id);
}

function parsePositiveNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function isMonthlySelected() {
  return $('is_monthly').checked;
}

function getRemainingMonths(endMonth, endYear) {
  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();

  if (!endMonth || !endYear) {
    return 0;
  }

  const monthDiff = (endYear - currentYear) * 12 + (endMonth - currentMonth) + 1;
  return Math.max(0, monthDiff);
}

function getFormValues() {
  return {
    name: $('name').value.trim(),
    email: $('email').value.trim(),
    contributors_count: parsePositiveNumber($('contributors_count').value),
    amount: parsePositiveNumber($('amount').value),
    is_monthly: isMonthlySelected(),
    end_month: parsePositiveNumber($('end_month').value),
    end_year: parsePositiveNumber($('end_year').value),
    message: $('message').value.trim(),
  };
}

function getPledgeImpact(pledge) {
  if (!pledge) {
    return 0;
  }

  if (Number.isFinite(Number(pledge.campaign_total))) {
    return Number(pledge.campaign_total);
  }

  if (pledge.is_monthly) {
    return Number(pledge.amount || 0) * getRemainingMonths(
      Number(pledge.end_month || 0),
      Number(pledge.end_year || 0)
    );
  }

  return Number(pledge.amount || 0);
}

function getMonthlyEffect(pledge) {
  if (!pledge) {
    return 0;
  }
  return pledge.is_monthly ? Number(pledge.amount || 0) : 0;
}

function getContributorsCount(pledge) {
  if (!pledge) {
    return 0;
  }
  return Number(pledge.contributors_count || 0);
}

function toggleMonthlyFields() {
  const monthlyFields = $('monthlyFields');
  if (isMonthlySelected()) {
    monthlyFields.classList.remove('hidden');
    monthlyFields.setAttribute('aria-hidden', 'false');
  } else {
    monthlyFields.classList.add('hidden');
    monthlyFields.setAttribute('aria-hidden', 'true');
  }
}

function setPreviewStatus(text) {
  $('previewStatus').textContent = text;
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

function showFormSection() {
  $('pledgeFlowSection').classList.remove('hidden');
}

function hideLookupCardsForForm() {
  $('lookupCard')?.classList.add('hidden');
  $('existingPledgeCard').classList.add('hidden');
}

function calculatePreview(values) {
  const remainingMonths = values.is_monthly
    ? getRemainingMonths(values.end_month, values.end_year)
    : 0;

  const pledgeImpact = values.is_monthly
    ? values.amount * remainingMonths
    : values.amount;

  const monthlyEffect = values.is_monthly ? values.amount : 0;

  let updatedPledgedTotal = currentStats.pledged_total + pledgeImpact;
  let updatedMonthlyTotal = currentStats.monthly_total + monthlyEffect;
  let updatedContributorsCount = currentStats.pledgers_count + values.contributors_count;

  if (isEditMode && existingPledge) {
    updatedPledgedTotal =
      currentStats.pledged_total - getPledgeImpact(existingPledge) + pledgeImpact;

    updatedMonthlyTotal =
      currentStats.monthly_total - getMonthlyEffect(existingPledge) + monthlyEffect;

    updatedContributorsCount =
      currentStats.pledgers_count - getContributorsCount(existingPledge) + values.contributors_count;
  }

  const updatedProgressAmount = CONFIG.CURRENT_BALANCE + updatedPledgedTotal;
  const progressPercent = calculateProgress(
    updatedProgressAmount,
    CONFIG.FUNDRAISING_GOAL
  );

  return {
    remainingMonths,
    pledgeImpact,
    monthlyEffect,
    updatedPledgedTotal,
    updatedMonthlyTotal,
    updatedContributorsCount,
    updatedProgressAmount,
    progressPercent,
  };
}

function renderPreview() {
  if ($('pledgeFlowSection').classList.contains('hidden')) {
    return;
  }

  const values = getFormValues();
  const preview = calculatePreview(values);

  $('previewImpact').textContent = formatCurrency(preview.pledgeImpact);
  $('previewMonthlyEffect').textContent = formatCurrency(preview.monthlyEffect);
  $('previewPledgedTotal').textContent = formatCurrency(preview.updatedPledgedTotal);
  $('previewMonthlyTotal').textContent = formatCurrency(preview.updatedMonthlyTotal);
  $('previewContributorsCount').textContent = preview.updatedContributorsCount;
  $('previewProgressPercent').textContent = `${preview.progressPercent}%`;
  $('previewProgressAmount').textContent = formatCurrency(preview.updatedProgressAmount);
  $('previewGoalAmount').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
  $('previewProgressBar').style.width = `${Math.max(0, Math.min(preview.progressPercent, 100))}%`;

  if (isEditMode) {
    $('previewModeNote').innerHTML = '<strong>Edit mode:</strong> preview replaces your existing pledge in current totals.';
  } else {
    $('previewModeNote').innerHTML = '<strong>New pledge mode:</strong> preview adds this pledge on top of current totals.';
  }

  if (values.is_monthly && values.end_month && values.end_year) {
    setPreviewStatus(`Monthly impact uses ${preview.remainingMonths} remaining month(s).`);
  } else if (values.is_monthly) {
    setPreviewStatus('Select end month and end year to calculate total impact.');
  } else {
    setPreviewStatus(isEditMode ? 'Editing existing one-time pledge.' : 'Creating new one-time pledge.');
  }
}

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
      pledgers_count: Number(data.pledgers_count || 0),
    };
  } catch (error) {
    console.error('Error loading stats:', error);
    setPreviewStatus('Could not load current stats. Preview may be unavailable.');
  }
}

function populateExistingSummary(data) {
  $('existingName').textContent = data.name || '-';
  $('existingEmail').textContent = data.email || '-';
  $('existingContributors').textContent = Number(data.contributors_count || 0);
  $('existingAmount').textContent = formatCurrency(Number(data.amount || 0));
  $('existingCampaignTotal').textContent = formatCurrency(Number(data.campaign_total || 0));
  $('existingMessage').textContent = data.message ? data.message : '-';

  if (data.is_monthly) {
    $('existingType').textContent = 'Monthly recurring';
    $('existingEndDate').textContent = `${data.end_month}/${data.end_year}`;
    $('existingEndDateRow').classList.remove('hidden');
  } else {
    $('existingType').textContent = 'One-time';
    $('existingEndDateRow').classList.add('hidden');
  }
}

function populateForm(values) {
  $('name').value = values.name || '';
  $('email').value = values.email || '';
  $('contributors_count').value = Number(values.contributors_count || 1);
  $('amount').value = Number(values.amount || 0) || '';
  $('is_monthly').checked = Boolean(values.is_monthly);
  $('end_month').value = values.end_month ? String(values.end_month) : '';
  $('end_year').value = values.end_year ? String(values.end_year) : '';
  $('message').value = values.message || '';

  toggleMonthlyFields();
  renderPreview();
}

function enterCreateMode(email) {
  existingPledge = null;
  isEditMode = false;

  hideLookupCardsForForm();
  showFormSection();

  $('pledgeFormTitle').textContent = 'Your pledge';
  $('pledgeFormIntro').textContent = 'All preview values below update live before you save.';
  $('email').readOnly = false;

  populateForm({
    name: '',
    email,
    contributors_count: 1,
    amount: '',
    is_monthly: false,
    end_month: '',
    end_year: '',
    message: '',
  });
}

function enterEditMode() {
  if (!existingPledge) {
    return;
  }

  isEditMode = true;
  hideLookupCardsForForm();
  showFormSection();

  $('pledgeFormTitle').textContent = 'Update your pledge';
  $('pledgeFormIntro').textContent = 'You are editing an existing pledge. Preview values replace your current pledge in totals.';
  $('email').readOnly = true;

  populateForm(existingPledge);
}

async function lookupPledgeByEmail(email) {
  const response = await fetch(`${CONFIG.API_URL}/pledges/by-email?email=${encodeURIComponent(email)}`);
  const data = await response.json();
  return { response, data };
}

async function handleLookup() {
  hideError('lookupError');

  const lookupButton = $('lookupButton');
  const email = $('lookupEmail').value.trim();

  if (!email) {
    showError('lookupError', 'Please enter your email.');
    return;
  }

  lookupButton.disabled = true;
  lookupButton.textContent = 'Checking...';

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

    existingPledge = data;
    isEditMode = false;
    populateExistingSummary(data);
    $('existingPledgeCard').classList.remove('hidden');
  } catch (error) {
    console.error('Error looking up pledge:', error);
    showError('lookupError', 'Could not check existing pledge. Please try again.');
  } finally {
    lookupButton.disabled = false;
    lookupButton.textContent = 'Continue';
  }
}

function validateForm(values) {
  if (!values.name) {
    return 'Please enter your name.';
  }

  if (!values.email) {
    return 'Please enter your email.';
  }

  if (values.contributors_count <= 0) {
    return 'Contributors count must be greater than 0.';
  }

  if (values.amount <= 0) {
    return 'Amount must be greater than 0.';
  }

  if (values.is_monthly) {
    if (!values.end_month || values.end_month < 1 || values.end_month > 12) {
      return 'End month must be between 1 and 12.';
    }

    if (!values.end_year || values.end_year < new Date().getFullYear()) {
      return 'Please enter a valid end year.';
    }

    if (getRemainingMonths(values.end_month, values.end_year) <= 0) {
      return 'Monthly pledge end date must be in the current or a future month.';
    }
  }

  return '';
}

function buildPayload(values) {
  const payload = {
    name: values.name,
    email: values.email,
    contributors_count: values.contributors_count,
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
  $('formSuccess').classList.add('hidden');
  $('formSuccess').textContent = '';

  const values = getFormValues();
  const validationError = validateForm(values);
  const submitButton = $('savePledgeButton');

  if (validationError) {
    showError('formError', validationError);
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = 'Saving...';

  try {
    const response = await fetch(`${CONFIG.API_URL}/pledges`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(buildPayload(values)),
    });

    if (!response.ok) {
      throw new Error('Failed to save pledge');
    }

    window.location.href = 'success.html';
  } catch (error) {
    console.error('Error saving pledge:', error);
    showError('formError', 'Could not save pledge. Please try again.');
    submitButton.disabled = false;
    submitButton.textContent = 'Save pledge';
  }
}

function setupForm() {
  const form = $('pledgeForm');
  const inputs = form.querySelectorAll('input, textarea, select');

  inputs.forEach((input) => {
    input.addEventListener('input', () => {
      toggleMonthlyFields();
      renderPreview();
    });

    input.addEventListener('change', () => {
      toggleMonthlyFields();
      renderPreview();
    });
  });

  form.addEventListener('submit', submitPledge);
}

function setupLookup() {
  $('lookupButton').addEventListener('click', handleLookup);
  $('editExistingButton').addEventListener('click', enterEditMode);
}

async function initPledgePage() {
  setupLookup();
  setupForm();
  $('previewGoalAmount').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);
  $('previewProgressAmount').textContent = formatCurrency(CONFIG.CURRENT_BALANCE);
  setPreviewStatus('Enter your email to begin.');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPledgePage);
} else {
  initPledgePage();
}