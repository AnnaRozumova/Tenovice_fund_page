// Configuration
// Edit these values as needed

const CONFIG = {
  // API URL - replace with your deployed API Gateway URL
  API_URL: 'https://tbaulwfk46.execute-api.eu-central-1.amazonaws.com',

  // Fallback defaults (in EUR). The live values come from GET /config (the
  // editable CONFIG row); these are used only if that request fails. The
  // breakdown stores stable keys — the localized labels live in the i18n dict.
  CURRENT_BALANCE: 320000, // Real money in account
  FUNDRAISING_GOAL: 2700000, // Target amount
  BREAKDOWN: [
    { key: 'new_gompa', amount: 1200000 },
    { key: 'sangha_house', amount: 1200000 },
    { key: 'basecamp_north', amount: 320000 },
  ],
};

// Fetch the editable campaign numbers from the API and override the fallbacks.
// On any failure we keep the hardcoded defaults so the site still renders.
async function loadConfig() {
  try {
    const response = await fetch(`${CONFIG.API_URL}/config`);
    if (!response.ok) {
      throw new Error('Failed to fetch config');
    }

    const data = await response.json();
    if (typeof data.current_balance === 'number') {
      CONFIG.CURRENT_BALANCE = data.current_balance;
    }
    if (typeof data.fundraising_goal === 'number') {
      CONFIG.FUNDRAISING_GOAL = data.fundraising_goal;
    }
    if (Array.isArray(data.breakdown)) {
      CONFIG.BREAKDOWN = data.breakdown;
    }
  } catch (error) {
    console.error('Error loading config, using defaults:', error);
  }
}

// Helper functions
function calculateProgress(current, goal) {
  return Math.round((current / goal) * 100);
}

function formatCurrency(amount) {
  return new Intl.NumberFormat('cs-CZ', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}
