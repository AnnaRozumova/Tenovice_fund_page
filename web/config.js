// Configuration
// Edit these values as needed

const CONFIG = {
  // API URL - replace with your deployed API Gateway URL
  API_URL: 'https://tbaulwfk46.execute-api.eu-central-1.amazonaws.com',

  // Hardcoded values (update manually)
  CURRENT_BALANCE: 12500, // Real money in account (in EUR)
  FUNDRAISING_GOAL: 50000, // Target amount (in EUR)
};

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
