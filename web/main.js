// Main application logic

// Fetch and display pledges statistics
async function loadPledgesStats() {
  try {
    const response = await fetch(`${CONFIG.API_URL}${withCurrency('/stats')}`);

    if (!response.ok) {
      throw new Error('Failed to fetch stats');
    }

    const data = await response.json();

    // Update pledges stats
    document.getElementById('pledgesTotal').textContent = formatCurrency(data.pledged_total || 0);
    document.getElementById('pledgesCount').textContent = data.contributors_count || 0;
    document.getElementById('pledgesMonthly').textContent = formatCurrency(data.monthly_total || 0);

  } catch (error) {
    console.error('Error loading stats:', error);
    document.getElementById('pledgesTotal').textContent = t('common.na');
    document.getElementById('pledgesCount').textContent = t('common.na');
    document.getElementById('pledgesMonthly').textContent = t('common.na');
  }
}

// Render the balance, goal, and progress bar from CONFIG (live values from /config)
function updateProgressBar() {
  document.getElementById('currentBalance').textContent = formatCurrency(CONFIG.CURRENT_BALANCE);
  document.getElementById('fundraisingGoal').textContent = formatCurrency(CONFIG.FUNDRAISING_GOAL);

  const progress = calculateProgress(CONFIG.CURRENT_BALANCE, CONFIG.FUNDRAISING_GOAL);
  const progressBar = document.getElementById('progressBar');
  const progressPercent = document.getElementById('progressPercent');

  // Clamp the *bar width* to 0–100 % so it can't overflow its container once the
  // balance exceeds the goal (the pledge page clamps the same way). The percent
  // *text* keeps the true value, so a >100 % campaign still reads honestly.
  const barWidth = Math.max(0, Math.min(progress, 100));

  // Animate progress bar
  setTimeout(() => {
    progressBar.style.width = `${barWidth}%`;
    progressPercent.textContent = `${progress}%`;
  }, 100);
}

// CTA button: pledging now requires an account (AUTH2, D18). Signed-in visitors
// go straight to the pledge page; everyone else lands on the auth screens (which
// return them to the pledge page after login). The home page itself stays public.
function setupPledgeButton() {
  const pledgeButton = document.getElementById('pledgeButton');

  pledgeButton.addEventListener('click', async () => {
    const token = await Auth.getIdToken();
    window.location.href = token ? 'pledge.html' : 'auth.html';
  });
}

// Initialize app
async function init() {
  await loadConfig();
  updateProgressBar();
  await loadPledgesStats();
  setupPledgeButton();
  // Show "Signed in as … · Sign out" when a session exists; keep its label in sync
  // with the language toggle.
  await renderAuthStatus('homeAuth');
  // A language switch also switches the currency (D22): re-fetch the config + stats
  // so the amounts come back in the new currency, and re-render the chrome.
  document.addEventListener('i18n:changed', async () => {
    renderAuthStatus('homeAuth');
    await loadConfig();
    updateProgressBar();
    await loadPledgesStats();
  });
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
