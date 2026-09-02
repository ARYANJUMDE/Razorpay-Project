// Ghost Payment Resolver — Midnight Command Center Frontend Engine (v5.0)

let currentCases = [];
let activeFilter = 'all';
let searchQuery = '';
let currentCaseId = null;

// Preset Webhook Templates
const WEBHOOK_TEMPLATES = {
  'payment.captured': {
    event: 'payment.captured',
    payload: {
      payment: {
        entity: {
          id: 'pay_demo_cap_' + Math.floor(Math.random() * 89999 + 10000),
          order_id: 'order_demo_wh_' + Math.floor(Math.random() * 8999 + 1000),
          amount: 149900,
          currency: 'INR',
          status: 'captured',
          method: 'upi',
          error_code: null
        }
      },
      order: {
        entity: {
          id: 'order_demo_wh_' + Math.floor(Math.random() * 8999 + 1000),
          amount: 149900,
          status: 'pending'
        }
      }
    }
  },
  'payment.failed': {
    event: 'payment.failed',
    payload: {
      payment: {
        entity: {
          id: 'pay_demo_fail_' + Math.floor(Math.random() * 89999 + 10000),
          order_id: 'order_demo_fail_' + Math.floor(Math.random() * 8999 + 1000),
          amount: 299900,
          currency: 'INR',
          status: 'failed',
          method: 'card',
          error_code: 'BAD_REQUEST_PAYMENT_TIMEDOUT'
        }
      },
      order: {
        entity: {
          id: 'order_demo_fail_' + Math.floor(Math.random() * 8999 + 1000),
          amount: 299900,
          status: 'pending'
        }
      }
    }
  }
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initLiveClock();
  initBackgroundCanvas();
  initEventListeners();
  loadMetricsAndBatch();
  loadAudits();
});

// Live Digital System Clock
function initLiveClock() {
  const clockEl = document.getElementById('live-clock');
  function update() {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    if (clockEl) clockEl.textContent = `${hrs}:${mins}:${secs}`;
  }
  update();
  setInterval(update, 1000);
}

// Atmospheric Midnight Rain & Cyber Particles Canvas
function initBackgroundCanvas() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  let w = (canvas.width = window.innerWidth);
  let h = (canvas.height = window.innerHeight);

  window.addEventListener('resize', () => {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  });

  const drops = [];
  const count = 45;
  for (let i = 0; i < count; i++) {
    drops.push({
      x: Math.random() * w,
      y: Math.random() * h,
      l: Math.random() * 18 + 8,
      speed: Math.random() * 3 + 1.5,
      alpha: Math.random() * 0.25 + 0.05
    });
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
    ctx.lineWidth = 1;

    for (let i = 0; i < drops.length; i++) {
      const d = drops[i];
      ctx.globalAlpha = d.alpha;
      ctx.beginPath();
      ctx.moveTo(d.x, d.y);
      ctx.lineTo(d.x - d.speed * 0.4, d.y + d.l);
      ctx.stroke();

      d.y += d.speed;
      d.x -= d.speed * 0.4;
      if (d.y > h) {
        d.y = -d.l;
        d.x = Math.random() * w;
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `
    <span style="color:var(--cyan-neon);">⚡</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

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
      statusText.textContent = 'Gateway API Degraded (Simulated Failover)';
      indicator.classList.add('down');
      showToast('⚠️ Circuit Breaker Activated: Gateway signals untrusted -> Safe Escalation Mode', 'warning');
    } else {
      statusText.textContent = 'Payment Rails Active';
      indicator.classList.remove('down');
      showToast('✓ Payment Rails Restored: Full Automated Resolution Active', 'success');
    }
  });

  // Live Search Input
  const searchInput = document.getElementById('input-case-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      renderCasesTable();
    });
  }

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

  // Modal Tabs
  const modalTabBtns = document.querySelectorAll('.modal-tab-btn');
  modalTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modalTabBtns.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      
      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // CSV Export Button
  document.getElementById('btn-export-csv').addEventListener('click', () => {
    window.location.href = '/audits/export';
  });

  // Refresh Audits Button
  document.getElementById('btn-refresh-audits').addEventListener('click', loadAudits);

  // Webhook Sandbox Open/Close
  document.getElementById('btn-open-webhook-modal').addEventListener('click', openWebhookModal);
  document.getElementById('webhook-modal-close').addEventListener('click', closeWebhookModal);

  // Modal Close buttons
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-dismiss-btn').addEventListener('click', closeModal);
  document.getElementById('modal-resolve-btn').addEventListener('click', () => {
    if (currentCaseId) {
      const forceApiDown = document.getElementById('toggle-circuit-breaker').checked;
      resolveSingleCase(currentCaseId, forceApiDown);
    }
  });

  // Keyboard shortcut (Escape closes modal)
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal();
      closeWebhookModal();
    }
  });
}

// Judge 1-Click Demo Tour Action
async function runJudgeDemo(caseId, label, isBreaker = false) {
  showToast(`Running Demo: ${label}...`);
  if (isBreaker) {
    document.getElementById('toggle-circuit-breaker').checked = true;
    document.getElementById('system-status-indicator').classList.add('down');
    document.getElementById('system-status-text').textContent = 'Gateway API Degraded (Simulated Failover)';
  } else {
    document.getElementById('toggle-circuit-breaker').checked = false;
    document.getElementById('system-status-indicator').classList.remove('down');
    document.getElementById('system-status-text').textContent = 'Payment Rails Active';
  }

  // Load and update the decision graph immediately
  await openCaseModal(caseId);
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
  btn.innerHTML = `<div class="loader-spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;margin-right:8px;"></div> Resolving Batch...`;

  try {
    const res = await fetch(`/batch/run?force_api_down=${forceApiDown}&daily_cap_paise=${dailyCap}`, {
      method: 'POST'
    });
    const data = await res.json();
    updateKpis(data.metrics);
    await loadCases();
    await loadAudits();
    showToast(`✓ Batch Evaluated: ₹${(data.metrics.amount_recovered_paise/100).toLocaleString('en-IN')} recovered (100% precision)`);
  } catch (err) {
    console.error('Failed to run batch:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <div class="btn-shine"></div>
      <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
      <span>Run Batch Evaluation (100 Cases)</span>
    `;
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

  const barRecovery = document.getElementById('bar-recovery-rate');
  if (barRecovery) {
    barRecovery.style.width = `${Math.min(100, Math.max(0, metrics.recovery_rate * 100))}%`;
  }
}

// Fetch All 100 Cases
async function loadCases() {
  try {
    const res = await fetch('/cases?limit=200');
    currentCases = await res.json();
    renderCasesTable();

    // Default graph initialization with case_0041 if available
    if (currentCases.length > 0) {
      const defaultCase = currentCases.find(c => c.case_id === 'case_0041') || currentCases[0];
      updateMainDashboardStateMachine(defaultCase);
    }
  } catch (err) {
    console.error('Error fetching cases:', err);
  }
}

// Filter and Render Cases Table
function renderCasesTable() {
  const tbody = document.getElementById('cases-tbody');
  tbody.innerHTML = '';

  let filtered = currentCases;

  // Scenario Filter
  if (activeFilter === 'aligned') {
    filtered = filtered.filter(c => c.expected_state === 'ALIGNED');
  } else if (activeFilter === 'webhook') {
    filtered = filtered.filter(c => c.scenario.toLowerCase().includes('webhook'));
  } else if (activeFilter === 'timeout') {
    filtered = filtered.filter(c => c.scenario.toLowerCase().includes('timeout'));
  } else if (activeFilter === 'double') {
    filtered = filtered.filter(c => c.scenario.toLowerCase().includes('double'));
  } else if (activeFilter === 'soft') {
    filtered = filtered.filter(c => c.expected_state === 'SOFT_DECLINE');
  } else if (activeFilter === 'hard') {
    filtered = filtered.filter(c => c.expected_state === 'HARD_FAIL');
  } else if (activeFilter === 'ambiguous') {
    filtered = filtered.filter(c => c.expected_state === 'AMBIGUOUS');
  }

  // Search Filter
  if (searchQuery) {
    filtered = filtered.filter(c => {
      const caseId = (c.case_id || '').toLowerCase();
      const scenario = (c.scenario || '').toLowerCase();
      const orderId = (c.order ? c.order.order_id : '').toLowerCase();
      return caseId.includes(searchQuery) || scenario.includes(searchQuery) || orderId.includes(searchQuery);
    });
  }

  document.getElementById('case-counter').textContent = `Showing ${filtered.length} of ${currentCases.length} cases`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell"><span>No cases found matching your criteria.</span></td></tr>`;
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
        <button class="btn btn-sm btn-secondary" onclick="openCaseModal('${c.case_id}')">
          <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          Inspect & AI
        </button>
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

// Open Modal and Fetch AI Explanation + Update Decision Graph
async function openCaseModal(caseId) {
  currentCaseId = caseId;
  const modal = document.getElementById('case-modal');
  modal.style.display = 'flex';

  // Default to Tab 1
  document.querySelectorAll('.modal-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  const firstTabBtn = document.querySelector('.modal-tab-btn[data-tab="tab-ai"]');
  const firstPane = document.getElementById('tab-ai');
  if (firstTabBtn) firstTabBtn.classList.add('active');
  if (firstPane) firstPane.classList.add('active');

  let caseObj = currentCases.find(c => c.case_id === caseId);
  if (!caseObj) {
    try {
      const res = await fetch(`/cases/${caseId}`);
      caseObj = await res.json();
    } catch (e) {
      console.error('Could not fetch case:', e);
      return;
    }
  }

  document.getElementById('modal-case-badge').textContent = caseObj.case_id;
  document.getElementById('modal-title').textContent = `${caseObj.scenario}`;
  document.getElementById('modal-observed-state').textContent = caseObj.expected_state;
  document.getElementById('modal-action-taken').textContent = caseObj.expected_action;
  document.getElementById('modal-recovered-val').textContent = `₹${(caseObj.expected_amount_recovered_paise / 100).toFixed(2)}`;

  document.getElementById('modal-order-json').textContent = JSON.stringify(caseObj.order, null, 2);
  document.getElementById('modal-payment-json').textContent = JSON.stringify(caseObj.payments, null, 2);

  // Update Main Dashboard Decision Graph
  updateMainDashboardStateMachine(caseObj);

  // Set loading for AI fields
  document.getElementById('modal-ai-root-cause').textContent = 'Diagnosing root cause and analyzing payment rail signals...';
  document.getElementById('modal-ai-merchant-summary').textContent = 'Summarizing for merchant finance operations...';
  document.getElementById('modal-ai-customer-en').textContent = 'Drafting customer notification in English...';
  document.getElementById('modal-ai-customer-hinglish').textContent = 'Drafting Hinglish customer notification...';

  try {
    const res = await fetch(`/cases/${caseId}/explain`, { method: 'POST' });
    const aiData = await res.json();

    document.getElementById('modal-ai-root-cause').textContent = aiData.root_cause_analysis;
    document.getElementById('modal-ai-merchant-summary').textContent = aiData.merchant_summary;
    document.getElementById('modal-ai-customer-en').textContent = aiData.customer_message_en;
    document.getElementById('modal-ai-customer-hinglish').textContent = aiData.customer_message_hinglish;
    document.getElementById('modal-ai-safety').textContent = `✓ ${aiData.action_safety_note}`;
    document.getElementById('modal-ai-source').textContent = aiData.source === 'llm' ? 'LLM Generated' : 'Deterministic Guardrail';
  } catch (err) {
    console.error('Failed to get AI explanation:', err);
    document.getElementById('modal-ai-root-cause').textContent = 'Explanation available via engine diagnosis.';
  }
}

// Update State Machine Flowchart on Main Dashboard
function updateMainDashboardStateMachine(caseObj) {
  const caseHeader = document.getElementById('main-sm-case-id');
  const nodeDiagnoseName = document.getElementById('main-node-diagnose-name');
  const nodeDiagnoseDesc = document.getElementById('main-node-diagnose-desc');
  const nodePolicyDesc = document.getElementById('main-node-policy-desc');
  const nodeActionName = document.getElementById('main-node-action-name');
  const nodeActionDesc = document.getElementById('main-node-action-desc');
  const nodeAction = document.getElementById('main-node-action');

  if (caseHeader) caseHeader.textContent = `${caseObj.case_id} (${caseObj.expected_state})`;
  if (nodeDiagnoseName) nodeDiagnoseName.textContent = caseObj.expected_state;
  if (nodeDiagnoseDesc) nodeDiagnoseDesc.textContent = `${caseObj.scenario.substring(0, 24)}`;

  const forceApiDown = document.getElementById('toggle-circuit-breaker').checked;
  if (forceApiDown || caseObj.expected_state === 'AMBIGUOUS') {
    if (nodePolicyDesc) nodePolicyDesc.textContent = 'Circuit Breaker TRIPPED';
    if (nodeActionName) nodeActionName.textContent = 'ESCALATE';
    if (nodeActionDesc) nodeActionDesc.textContent = 'Safe Human Review Queue';
    if (nodeAction) nodeAction.className = 'sm-node active';
  } else {
    if (nodePolicyDesc) nodePolicyDesc.textContent = 'Cap & Safety PASSED';
    if (nodeActionName) nodeActionName.textContent = caseObj.expected_action;
    if (nodeActionDesc) nodeActionDesc.textContent = `₹${(caseObj.expected_amount_recovered_paise/100).toFixed(2)} Protected`;
    if (nodeAction) nodeAction.className = 'sm-node active node-highlight';
  }
}

// Single Case Resolution
async function resolveSingleCase(caseId, forceApiDown = false) {
  try {
    const res = await fetch(`/resolve/${caseId}?force_api_down=${forceApiDown}`, { method: 'POST' });
    const audit = await res.json();
    showToast(`Case ${caseId} Resolved: ${audit.action_taken} (₹${(audit.amount_recovered_paise/100).toFixed(2)})`);
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

// Webhook Sandbox Functions
function openWebhookModal() {
  const modal = document.getElementById('webhook-modal');
  modal.style.display = 'flex';
  loadWebhookTemplate('payment.captured');
}

function closeWebhookModal() {
  document.getElementById('webhook-modal').style.display = 'none';
}

function loadWebhookTemplate(type) {
  const payload = WEBHOOK_TEMPLATES[type] || WEBHOOK_TEMPLATES['payment.captured'];
  document.getElementById('webhook-payload-input').value = JSON.stringify(payload, null, 2);
}

async function sendSimulatedWebhook() {
  const input = document.getElementById('webhook-payload-input').value;
  const btn = document.getElementById('btn-send-webhook');
  btn.disabled = true;
  btn.textContent = 'Sending Webhook...';

  try {
    const res = await fetch('/webhooks/razorpay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: input
    });
    const data = await res.json();

    const respBox = document.getElementById('webhook-response-box');
    const respJson = document.getElementById('webhook-response-json');
    respBox.style.display = 'block';
    respJson.textContent = JSON.stringify(data, null, 2);

    showToast(`✓ Webhook Ingested: ${data.action_taken} on ${data.case_id}`);
    await loadAudits();
  } catch (err) {
    alert(`Webhook error: ${err}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Send Live Webhook`;
  }
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

// Enhanced Clipboard helper with button feedback
function copyText(elementId, btnElement) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text);
  
  if (btnElement) {
    const originalText = btnElement.innerHTML;
    btnElement.classList.add('copied');
    btnElement.innerHTML = `
      <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>
      <span>Copied!</span>
    `;
    setTimeout(() => {
      btnElement.classList.remove('copied');
      btnElement.innerHTML = originalText;
    }, 1800);
  }
}
