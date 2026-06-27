// Admin page: load the current CONFIG (public GET /config) and write it back
// (protected POST /config with the shared secret as a bearer token).

const BREAKDOWN_INPUTS = ['new_gompa', 'sangha_house', 'basecamp_north'];

function $(id) {
  return document.getElementById(id);
}

function showStatus(message, ok) {
  const el = $('status');
  el.textContent = message;
  el.classList.remove('hidden', 'ok', 'err');
  el.classList.add(ok ? 'ok' : 'err');
}

// Prefill the form from the current config (defaults are returned if unset).
async function prefill() {
  try {
    const response = await fetch(`${CONFIG.API_URL}/config`);
    if (!response.ok) {
      throw new Error('Failed to load config');
    }

    const data = await response.json();
    $('currentBalance').value = data.current_balance ?? '';
    $('fundraisingGoal').value = data.fundraising_goal ?? '';

    const byKey = {};
    (data.breakdown || []).forEach((item) => {
      byKey[item.key] = item.amount;
    });
    BREAKDOWN_INPUTS.forEach((key) => {
      $(`amount_${key}`).value = byKey[key] ?? '';
    });
  } catch (error) {
    console.error('Error loading config:', error);
    showStatus('Could not load current config. You can still enter values and save.', false);
  }
}

function buildPayload() {
  return {
    current_balance: Number($('currentBalance').value),
    fundraising_goal: Number($('fundraisingGoal').value),
    breakdown: BREAKDOWN_INPUTS.map((key) => ({
      key,
      amount: Number($(`amount_${key}`).value),
    })),
  };
}

async function save(event) {
  event.preventDefault();

  const secret = $('secret').value.trim();
  if (!secret) {
    showStatus('Please paste the admin secret.', false);
    return;
  }

  const saveButton = $('saveButton');
  saveButton.disabled = true;
  saveButton.textContent = 'Saving...';

  try {
    const response = await fetch(`${CONFIG.API_URL}/config`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${secret}`,
      },
      body: JSON.stringify(buildPayload()),
    });

    if (response.status === 401) {
      showStatus('Wrong or missing secret.', false);
      return;
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      showStatus(data.error || 'Could not save config.', false);
      return;
    }

    showStatus('Saved. The site now shows these numbers.', true);
  } catch (error) {
    console.error('Error saving config:', error);
    showStatus('Could not reach the server. Please try again.', false);
  } finally {
    saveButton.disabled = false;
    saveButton.textContent = 'Save';
  }
}

async function init() {
  $('adminForm').addEventListener('submit', save);
  await prefill();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
