// Main application logic

// Fetch and display pledges statistics
async function loadPledgesStats() {
  try {
    const response = await fetch(`${CONFIG.API_URL}/stats`);

    if (!response.ok) {
      throw new Error('Failed to fetch stats');
    }

    const data = await response.json();

    // Update pledges stats
    document.getElementById('pledgesTotal').textContent = formatCurrency(data.pledged_total || 0);
    document.getElementById('pledgesCount').textContent = data.pledgers_count || 0;
    document.getElementById('pledgesMonthly').textContent = formatCurrency(data.monthly_total || 0);

  } catch (error) {
    console.error('Error loading stats:', error);
    document.getElementById('pledgesTotal').textContent = 'N/A';
    document.getElementById('pledgesCount').textContent = 'N/A';
    document.getElementById('pledgesMonthly').textContent = 'N/A';
  }
}

// Update progress bar
function updateProgressBar() {
  const progress = calculateProgress(CONFIG.CURRENT_BALANCE, CONFIG.FUNDRAISING_GOAL);
  const progressBar = document.getElementById('progressBar');
  const progressPercent = document.getElementById('progressPercent');

  // Animate progress bar
  setTimeout(() => {
    progressBar.style.width = `${progress}%`;
    progressPercent.textContent = `${progress}%`;
  }, 100);
}

// Handle pledge button click
function setupPledgeButton() {
  const pledgeButton = document.getElementById('pledgeButton');

  pledgeButton.addEventListener('click', () => {
    window.location.href = 'pledge.html';
  });
}

// Initialize app
async function init() {
  updateProgressBar();
  await loadPledgesStats();
  setupPledgeButton();
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
