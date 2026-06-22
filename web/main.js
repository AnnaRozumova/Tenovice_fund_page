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

  // Animate progress bar
  setTimeout(() => {
    progressBar.style.width = `${progress}%`;
    progressPercent.textContent = `${progress}%`;
  }, 100);
}

// Render the 3-direction goal breakdown from CONFIG (live values from /config,
// fallback defaults otherwise). Labels are localized via data-i18n keys, so the
// language toggle re-translates them; the EUR amounts are language-independent.
function renderBreakdown() {
  const list = document.getElementById('breakdownList');
  if (!list || !Array.isArray(CONFIG.BREAKDOWN)) {
    return;
  }

  const links = CONFIG.BREAKDOWN_LINKS || {};
  const images = CONFIG.BREAKDOWN_IMAGES || {};

  list.innerHTML = '';
  CONFIG.BREAKDOWN.forEach((item) => {
    const nameKey = `breakdown.${item.key}`;
    const descKey = `breakdown.${item.key}Desc`;
    const url = links[item.key];
    const imageSrc = images[item.key];

    // When a direction has a dw-connect project page, the whole card is a link
    // (opens in a new tab); otherwise it renders as a plain block.
    const card = document.createElement(url ? 'a' : 'div');
    card.className = url ? 'breakdown-card breakdown-card-link' : 'breakdown-card';
    if (url) {
      card.href = url;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
    }

    // Optional cover photo (zooms gently on hover via the wrapper's overflow).
    if (imageSrc) {
      const media = document.createElement('div');
      media.className = 'breakdown-media';
      const img = document.createElement('img');
      img.src = imageSrc;
      img.loading = 'lazy';
      img.alt = t(nameKey);
      img.setAttribute('data-i18n-alt', nameKey);
      media.appendChild(img);
      card.appendChild(media);
    }

    const name = document.createElement('h3');
    name.className = 'breakdown-name';
    name.setAttribute('data-i18n', nameKey);
    name.textContent = t(nameKey);

    const desc = document.createElement('p');
    desc.className = 'breakdown-desc';
    desc.setAttribute('data-i18n', descKey);
    desc.textContent = t(descKey);

    const amount = document.createElement('div');
    amount.className = 'breakdown-amount';
    amount.textContent = formatCurrency(item.amount);

    card.append(name, desc, amount);
    list.appendChild(card);
  });
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
  await loadConfig();
  updateProgressBar();
  renderBreakdown();
  await loadPledgesStats();
  setupPledgeButton();
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
