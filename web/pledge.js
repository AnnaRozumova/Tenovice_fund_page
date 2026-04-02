let currentStats = {
    pledged_total: 0,
    monthly_total: 0,
    pledgers_count: 0,
  };
  
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
  
  function toggleMonthlyFields() {
    const monthlyFields = $('monthlyFields');
    if (isMonthlySelected()) {
      monthlyFields.classList.remove('is-hidden');
    } else {
      monthlyFields.classList.add('is-hidden');
    }
  }
  
  function calculatePreview(values) {
    const remainingMonths = values.is_monthly
      ? getRemainingMonths(values.end_month, values.end_year)
      : 0;
  
    const pledgeImpact = values.is_monthly
      ? values.amount * remainingMonths
      : values.amount;
  
    const monthlyEffect = values.is_monthly ? values.amount : 0;
  
    const updatedPledgedTotal = currentStats.pledged_total + pledgeImpact;
    const updatedMonthlyTotal = currentStats.monthly_total + monthlyEffect;
    const updatedContributorsCount = currentStats.pledgers_count + values.contributors_count;
  
    const progressPercent = calculateProgress(
      CONFIG.CURRENT_BALANCE + updatedPledgedTotal,
      CONFIG.FUNDRAISING_GOAL
    );
  
    return {
      remainingMonths,
      pledgeImpact,
      monthlyEffect,
      updatedPledgedTotal,
      updatedMonthlyTotal,
      updatedContributorsCount,
      progressPercent,
    };
  }
  
  function renderPreview() {
    const values = getFormValues();
    const preview = calculatePreview(values);
  
    $('previewPledgeImpact').textContent = formatCurrency(preview.pledgeImpact);
    $('previewMonthlyEffect').textContent = formatCurrency(preview.monthlyEffect);
    $('previewUpdatedPledgedTotal').textContent = formatCurrency(preview.updatedPledgedTotal);
    $('previewUpdatedMonthlyTotal').textContent = formatCurrency(preview.updatedMonthlyTotal);
    $('previewUpdatedContributorsCount').textContent = preview.updatedContributorsCount;
    $('previewUpdatedProgress').textContent = `${preview.progressPercent}%`;
  
    if (values.is_monthly && values.end_month && values.end_year) {
      $('previewMonthlyNote').textContent = `Calculated as ${formatCurrency(values.amount)} × ${preview.remainingMonths} remaining month(s).`;
    } else if (values.is_monthly) {
      $('previewMonthlyNote').textContent = 'Select end month and end year to calculate total impact.';
    } else {
      $('previewMonthlyNote').textContent = 'One-time pledge equals full campaign impact.';
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
  
      renderPreview();
    } catch (error) {
      console.error('Error loading stats:', error);
      $('formStatus').textContent = 'Could not load current stats. Preview may be unavailable.';
      $('formStatus').className = 'form-status error';
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
  
    const values = getFormValues();
    const validationError = validateForm(values);
    const submitButton = $('savePledgeButton');
    const status = $('formStatus');
  
    if (validationError) {
      status.textContent = validationError;
      status.className = 'form-status error';
      return;
    }
  
    submitButton.disabled = true;
    submitButton.textContent = 'Saving...';
    status.textContent = '';
    status.className = 'form-status';
  
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
      status.textContent = 'Could not save pledge. Please try again.';
      status.className = 'form-status error';
      submitButton.disabled = false;
      submitButton.textContent = 'Save Pledge';
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
    toggleMonthlyFields();
    renderPreview();
  }
  
  async function initPledgePage() {
    setupForm();
    await loadStats();
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPledgePage);
  } else {
    initPledgePage();
  }