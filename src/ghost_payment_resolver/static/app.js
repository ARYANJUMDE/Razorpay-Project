// Ghost Payment Resolver — Frontend Dashboard Engine

let currentCases = [];
let activeFilter = 'all';
let currentCaseId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadMetricsAndBatch();
  loadAudits();
});

function initEventListeners() {
  // Batch Run Button
  document.getElementById('btn-run-batch').addEventListener('click', () => {
    const forceApiDown = document.getElementById('toggle-circuit-breaker').checked;
    const dailyCap = parseInt(document.getElementById('input-daily-cap').value, 10) || 50000000;
    runBatch(forceApiDown, dailyCap);
  });

  // Circuit Breaker Toggle
  const breakerToggle = document.getElementById('toggle-circuit-breaker');
  breakerToggle.addEventListener('change', () => {
    const isDown = breakerToggle.checked;
    const statusText = document.getElementById('system-status-text');
    const indicator = document.getElementById('system-status-indicator');

    if (isDown) {
      statusText.textContent = 'Gateway API Degraded (Simulated)';
      indicator.classList.add('down');
    } else {
      statusText.textContent = 'Payment Rails Active';
      indicator.classList.remove('down');
    }
  });

  // Filter Pills
  const filterPills = document.querySelectorAll('.filter-pill');
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      activeFilter = pill.dataset.filter;
      renderCasesTable();
    });
  });

  // CSV Export Button
  document.getElementById('btn-export-csv').addEventListener('click', () => {
    window.location.href = '/audits/export';
  });

  // Refresh Audits Button
  document.getElementById('btn-refresh-audits').addEventListener('click', loadAudits);

  // Modal Close buttons
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-dismiss-btn').addEventListener('click', closeModal);
  document.getElementById('modal-resolve-btn').addEventListener('click', () => {
    if (currentCaseId) {
      const forceApiDown = document.getElementById('toggle-circuit-breaker').checked;
      resolveSingleCase(currentCaseId, forceApiDown);
    }
  });
}

// Load Batch Metrics & Initial Cases
async function loadMetricsAndBatch() {
  try {
    const forceApiDown = document.getElementById('toggle-circuit-breaker').checked;
    await runBatch(forceApiDown, 50000000);
  } catch (err) {
    console.error('Error loading batch:', err);
  }
}

// Run Batch Resolution via API
async function runBatch(forceApiDown = false, dailyCap = 50000000) {
  const btn = document.getElementById('btn-run-batch');
  btn.disabled = true;
  btn.textContent = 'Resolving Batch...';

  try {
    const res = await fetch(`/batch/run?force_api_down=${forceApiDown}&daily_cap_paise=${dailyCap}`, {
      method: 'POST'
    });
    const data = await res.json();
    updateKpis(data.metrics);
    await loadCases();
    await loadAudits();
  } catch (err) {
    console.error('Failed to run batch:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Run Batch Evaluation (100 Cases)`;
  }
}

// Update KPI Header Cards
function updateKpis(metrics) {
  const inr = (metrics.amount_recovered_paise / 100).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  document.getElementById('kpi-recovered-amount').textContent = `₹${inr}`;
  document.getElementById('kpi-recovered-paise').textContent = `${metrics.amount_recovered_paise.toLocaleString('en-IN')} paise protected`;
  document.getElementById('kpi-recovery-rate').textContent = `${(metrics.recovery_rate * 100).toFixed(1)}%`;
  document.getElementById('kpi-recoverable-count').textContent = `${metrics.correctly_recovered} / ${metrics.recoverable_cases} recoverable cases`;
  document.getElementById('kpi-false-action-rate').textContent = `${(metrics.false_action_rate * 100).toFixed(2)}%`;
  document.getElementById('kpi-escalation-precision').textContent = `${(metrics.escalation_precision * 100).toFixed(1)}%`;
  document.getElementById('kpi-escalation-count').textContent = `${metrics.escalations} escalations processed`;
}

// Fetch All 100 Cases
async function loadCases() {
  try {
    const res = await fetch('/cases?limit=200');
    currentCases = await res.json();
    renderCasesTable();
  } catch (err) {
    console.error('Error fetching cases:', err);
  }
}

// Filter and Render Cases Table
function renderCasesTable() {
  const tbody = document.getElementById('cases-tbody');
  tbody.innerHTML = '';

  let filtered = currentCases;
  if (activeFilter === 'aligned') {
    filtered = currentCases.filter(c => c.expected_state === 'ALIGNED');
  } else if (activeFilter === 'webhook') {
    filtered = currentCases.filter(c => c.scenario.toLowerCase().includes('webhook'));
  } else if (activeFilter === 'timeout') {
    filtered = currentCases.filter(c => c.scenario.toLowerCase().includes('timeout'));
  } else if (activeFilter === 'double') {
    filtered = currentCases.filter(c => c.scenario.toLowerCase().includes('double'));
  } else if (activeFilter === 'soft') {
    filtered = currentCases.filter(c => c.expected_state === 'SOFT_DECLINE');
  } else if (activeFilter === 'hard') {
    filtered = currentCases.filter(c => c.expected_state === 'HARD_FAIL');
  } else if (activeFilter === 'ambiguous') {
    filtered = currentCases.filter(c => c.expected_state === 'AMBIGUOUS');
  }

  document.getElementById('case-counter').textContent = `Showing ${filtered.length} of ${currentCases.length} cases`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No cases matching filter '${activeFilter}'.</td></tr>`;
    return;
  }

  filtered.forEach(c => {
    const tr = document.createElement('tr');

    const stateClass = getStateBadgeClass(c.expected_state);
    const amountInr = (c.expected_amount_recovered_paise / 100).toFixed(2);
    const orderAmt = c.order ? (c.order.amount_paise / 100).toFixed(2) : '0.00';
    const payStatus = c.payments.length > 0 ? c.payments[0].status : 'NONE';

    tr.innerHTML = `
      <td><strong>${c.case_id}</strong></td>
      <td>${c.scenario}</td>
      <td><code>${c.order ? c.order.order_id : 'N/A'}</code></td>
      <td class="amount-text">₹${orderAmt}</td>
      <td><code>${payStatus}</code></td>
      <td><span class="tag-state ${stateClass}">${c.expected_state}</span></td>
      <td><span class="tag-action">${c.expected_action}</span></td>
      <td class="amount-text ${amountInr > 0 ? 'amount-highlight' : ''}">₹${amountInr}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="openCaseModal('${c.case_id}')">Inspect & AI</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function getStateBadgeClass(state) {
  switch (state) {
    case 'GHOST_SUCCESS': return 'tag-ghost';
    case 'SOFT_DECLINE': return 'tag-soft';
    case 'HARD_FAIL': return 'tag-hard';
    case 'AMBIGUOUS': return 'tag-ambiguous';
    default: return 'tag-aligned';
  }
}

// Open Modal and Fetch AI Explanation
async function openCaseModal(caseId) {
  currentCaseId = caseId;
  const modal = document.getElementById('case-modal');
  modal.style.display = 'flex';

  const caseObj = currentCases.find(c => c.case_id === caseId);
  if (!caseObj) return;

  document.getElementById('modal-case-badge').textContent = caseObj.case_id;
  document.getElementById('modal-title').textContent = `${caseObj.scenario}`;
  document.getElementById('modal-observed-state').textContent = caseObj.expected_state;
  document.getElementById('modal-action-taken').textContent = caseObj.expected_action;
  document.getElementById('modal-recovered-val').textContent = `₹${(caseObj.expected_amount_recovered_paise / 100).toFixed(2)}`;

  document.getElementById('modal-order-json').textContent = JSON.stringify(caseObj.order, null, 2);
  document.getElementById('modal-payment-json').textContent = JSON.stringify(caseObj.payments, null, 2);

  // Set loading for AI fields
  document.getElementById('modal-ai-root-cause').textContent = 'Generating AI Root Cause Analysis...';
  document.getElementById('modal-ai-merchant-summary').textContent = 'Summarizing for merchant operations...';
  document.getElementById('modal-ai-customer-en').textContent = 'Drafting English notification...';
  document.getElementById('modal-ai-customer-hinglish').textContent = 'Drafting Hinglish notification...';

  try {
    const res = await fetch(`/cases/${caseId}/explain`, { method: 'POST' });
    const aiData = await res.json();

    document.getElementById('modal-ai-root-cause').textContent = aiData.root_cause_analysis;
    document.getElementById('modal-ai-merchant-summary').textContent = aiData.merchant_summary;
    document.getElementById('modal-ai-customer-en').textContent = aiData.customer_message_en;
    document.getElementById('modal-ai-customer-hinglish').textContent = aiData.customer_message_hinglish;
    document.getElementById('modal-ai-safety').textContent = `✓ ${aiData.action_safety_note}`;
    document.getElementById('modal-ai-source').textContent = aiData.source === 'llm' ? 'LLM Generated' : 'Engine Guardrailed';
  } catch (err) {
    console.error('Failed to get AI explanation:', err);
    document.getElementById('modal-ai-root-cause').textContent = 'Explanation available via engine diagnosis.';
  }
}

// Single Case Resolution
async function resolveSingleCase(caseId, forceApiDown = false) {
  try {
    const res = await fetch(`/resolve/${caseId}?force_api_down=${forceApiDown}`, { method: 'POST' });
    const audit = await res.json();
    alert(`Case ${caseId} Resolved!\nAction Taken: ${audit.action_taken}\nRecovered: ₹${(audit.amount_recovered_paise / 100).toFixed(2)}\nReason: ${audit.reason}`);
    closeModal();
    loadAudits();
  } catch (err) {
    alert(`Resolution failed: ${err}`);
  }
}

// Close Modal
function closeModal() {
  document.getElementById('case-modal').style.display = 'none';
}

// Load Persistent Audits from SQLite
async function loadAudits() {
  const container = document.getElementById('audit-log-list');
  try {
    const res = await fetch('/audits?limit=10');
    const audits = await res.json();

    if (!audits || audits.length === 0) {
      container.innerHTML = '<div class="audit-item"><span class="audit-reason">No audit logs recorded yet in SQLite.</span></div>';
      return;
    }

    container.innerHTML = '';
    audits.forEach(a => {
      const item = document.createElement('div');
      item.className = 'audit-item';
      const timeStr = new Date(a.timestamp).toLocaleTimeString();
      const inrAmt = (a.amount_recovered_paise / 100).toFixed(2);

      item.innerHTML = `
        <div class="audit-meta">
          <span class="audit-time">${timeStr}</span>
          <span class="audit-case-id">${a.case_id}</span>
          <span class="tag-state ${getStateBadgeClass(a.observed_state)}">${a.observed_state}</span>
          <span class="tag-action">${a.action_taken}</span>
        </div>
        <div class="audit-outcome">
          <span class="amount-text ${inrAmt > 0 ? 'amount-highlight' : ''}">₹${inrAmt}</span>
        </div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.error('Error fetching SQLite audits:', err);
  }
}

// Clipboard helper
function copyText(elementId) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text);
  alert('Copied message draft to clipboard!');
}
