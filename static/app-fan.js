/**
 * StadiumIQ — app-fan.js
 * Fan dashboard logic: form, transport chips, results rendering.
 * Depends on: app-core.js (loaded first).
 */
'use strict';

const FAN_DEFAULT_BTN_TEXT = 'Get My Guidance ⚽';

// ── Collapsible form ──────────────────────────────────────────────────────────
/**
 * Initialise the collapsible profile form toggle button.
 * @returns {void}
 */
function initFormToggle() {
  const toggleBtn   = document.getElementById('form-toggle-btn');
  const formCollapse= document.getElementById('form-collapse');
  if (!toggleBtn || !formCollapse) return;

  toggleBtn.addEventListener('click', () => {
    const isOpen = formCollapse.classList.toggle('open');
    toggleBtn.classList.toggle('open', isOpen);
    toggleBtn.setAttribute('aria-expanded', String(isOpen));
  });
}

// ── Transport chips ───────────────────────────────────────────────────────────
const TRANSPORT_DETAIL = {
  shuttle:   { icon: '🚌', label: 'FIFA Shuttle',  waitKey: 'shuttle_wait',   journeyKey: 'shuttle_journey',   pointKey: 'shuttle_departure', noteKey: 'shuttle_note'  },
  metro:     { icon: '🚇', label: 'Metro / Rail',  waitKey: 'metro_wait',     journeyKey: 'metro_journey',     pointKey: 'metro_point',       noteKey: 'metro_note'    },
  rideshare: { icon: '🚗', label: 'Rideshare',     waitKey: 'rideshare_wait', journeyKey: 'rideshare_journey', pointKey: 'rideshare_point',   noteKey: 'rideshare_note'},
  walk:      { icon: '🚶', label: 'Walk',          waitKey: 'walk_wait',      journeyKey: 'walk_journey',      pointKey: 'walk_point',        noteKey: 'walk_note'     },
  car:       { icon: '🅿️', label: 'Parking / Car', waitKey: 'car_wait',      journeyKey: 'car_journey',       pointKey: 'car_point',         noteKey: 'car_note'      },
};

let _transportData = {};
let _activeMode    = 'shuttle';

/**
 * Attach click delegation listener to the transport chips container.
 * @returns {void}
 */
function initTransportChips() {
  const chipsContainer = document.getElementById('transport-chips');
  if (!chipsContainer) return;

  chipsContainer.addEventListener('click', (e) => {
    const chip = e.target.closest('.transport-chip');
    if (!chip) return;
    const mode = chip.dataset.mode;
    if (!mode) return;
    setActiveChip(mode);
    renderTransportDetail(mode);
  });
}

/**
 * Mark a single chip as active and clear all other active states.
 * @param {string} mode - Transport mode key ('shuttle'|'metro'|'rideshare'|'walk'|'car')
 * @returns {void}
 */
function setActiveChip(mode) {
  _activeMode = mode;
  document.querySelectorAll('.transport-chip').forEach((el) => {
    el.classList.toggle('active', el.dataset.mode === mode);
  });
}

function renderTransportChips(transport) {
  _transportData = transport;
  const modes    = ['shuttle', 'metro', 'rideshare', 'walk', 'car'];
  const chipsEl  = document.getElementById('transport-chips');
  if (!chipsEl) return;

  chipsEl.innerHTML = '';
  modes.forEach((mode) => {
    const info   = TRANSPORT_DETAIL[mode] || { icon: '🚌', label: mode };
    const waitMs = transport[mode + '_wait_minutes'];
    const jMin   = transport[mode + '_journey_minutes'];
    const waitTxt = waitMs !== undefined ? `${waitMs.toFixed(1)}m` : '—';
    const jTxt    = jMin   !== undefined ? `${jMin.toFixed(1)}min` : '—';

    const chip = document.createElement('button');
    chip.className   = 'transport-chip' + (mode === transport.recommended_mode ? ' active' : '');
    chip.dataset.mode = mode;
    chip.setAttribute('aria-label', `${info.label} — wait: ${waitTxt}, journey: ${jTxt}`);
    chip.innerHTML = `
      <span class="chip-icon" aria-hidden="true">${info.icon}</span>
      <span class="chip-mode">${info.label}</span>
      <span class="chip-time">${waitTxt} · ${jTxt}</span>`;
    chipsEl.appendChild(chip);
  });

  _activeMode = transport.recommended_mode || 'shuttle';
  setActiveChip(_activeMode);
  renderTransportDetail(_activeMode);
}

/**
 * Render detailed stats for a selected transport mode into the detail box.
 * @param {string} mode - Transport mode key
 * @returns {void}
 */
function renderTransportDetail(mode) {
  const box = document.getElementById('transport-detail');
  if (!box || !_transportData) return;

  const info = TRANSPORT_DETAIL[mode] || { icon: '🚌', label: mode };
  const wait = _transportData[mode + '_wait_minutes'];
  const jour = _transportData[mode + '_journey_minutes'];
  const dep  = _transportData[mode + '_departure_point'] || '';
  const note = _transportData[mode + '_note']            || '';

  box.innerHTML = `
    <div class="td-mode">${info.icon} ${info.label}</div>
    <div class="td-stats">
      <div>
        <div class="td-stat-label">Wait</div>
        <div class="td-stat-val">${wait !== undefined ? wait.toFixed(1) + ' min' : '—'}</div>
      </div>
      <div>
        <div class="td-stat-label">Journey</div>
        <div class="td-stat-val">${jour !== undefined ? jour.toFixed(1) + ' min' : '—'}</div>
      </div>
    </div>
    ${dep  ? `<div class="td-point">📍 ${dep}</div>` : ''}
    ${note ? `<div class="td-note">${note}</div>`    : ''}
  `;
  box.classList.add('visible');
}

// ── Alerts render ─────────────────────────────────────────────────────────────
/**
 * Render fan-relevant alerts into the alerts list.
 * @param {Object[]} alerts - Array of OperationalAlert objects from /api/assist
 * @returns {void}
 */
function renderAlertsFan(alerts) {
  const listEl = document.getElementById('fan-alerts');
  if (!listEl) return;
  listEl.innerHTML = '';

  if (!alerts || alerts.length === 0) {
    listEl.innerHTML = `<div class="fan-alert-item info">${ALERT_ICONS.info} All systems nominal — no active alerts.</div>`;
    return;
  }

  alerts.forEach((alert) => {
    const div  = document.createElement('div');
    div.className = 'fan-alert-item ' + (alert.severity || 'info');
    const desc = alert.action_required || alert.description || '';
    div.innerHTML = `<strong>${ALERT_ICONS[alert.severity] || 'ℹ️'} ${alert.title}</strong>
      ${desc ? `<div style="margin-top:3px;font-size:0.78rem;opacity:.85">${desc}</div>` : ''}`;
    listEl.appendChild(div);
  });
}

// ── Transport chips — API returns transport_options as an array of objects ─────
/**
 * Build and render transport chips from the API transport_options array.
 * Selects the chip with the lowest estimated wait as the recommended mode.
 * @param {Object[]} transportArr - Array of TransportOption objects from /api/assist
 * @returns {void}
 */
function renderTransportChips(transportArr) {
  const chipsEl = document.getElementById('transport-chips');
  if (!chipsEl) return;

  // Build a flat lookup map from the array
  _transportData = {};
  let recMode = 'shuttle';
  let minWait = Infinity;
  (transportArr || []).forEach((t) => {
    const m = t.mode;
    _transportData[m + '_wait_minutes']     = t.estimated_wait_minutes;
    _transportData[m + '_journey_minutes']  = t.estimated_journey_minutes;
    _transportData[m + '_departure_point']  = t.departure_point;
    _transportData[m + '_note']             = t.notes;
    // pick recommended = lowest wait
    if (t.estimated_wait_minutes < minWait) { minWait = t.estimated_wait_minutes; recMode = m; }
  });
  _transportData.recommended_mode = recMode;

  chipsEl.innerHTML = '';
  const order = ['shuttle', 'metro', 'rideshare', 'walk', 'car'];
  order.forEach((mode) => {
    const info    = TRANSPORT_DETAIL[mode] || { icon: '🚌', label: mode };
    const waitMs  = _transportData[mode + '_wait_minutes'];
    const jMin    = _transportData[mode + '_journey_minutes'];
    const waitTxt = waitMs !== undefined ? `${waitMs.toFixed(1)}m` : '—';
    const jTxt    = jMin   !== undefined ? `${jMin.toFixed(1)}min` : '—';

    const chip = document.createElement('button');
    chip.className    = 'transport-chip' + (mode === recMode ? ' active' : '');
    chip.dataset.mode = mode;
    chip.setAttribute('aria-label', `${info.label} — wait: ${waitTxt}, journey: ${jTxt}`);
    chip.innerHTML = `
      <span class="chip-icon" aria-hidden="true">${info.icon}</span>
      <span class="chip-mode">${info.label}</span>
      <span class="chip-time">${waitTxt} · ${jTxt}</span>`;
    chipsEl.appendChild(chip);
  });

  _activeMode = recMode;
  setActiveChip(_activeMode);
  renderTransportDetail(_activeMode);
}

// ── Main render — maps API response keys correctly ────────────────────────────
/**
 * Orchestrate all fan dashboard renders from a complete /api/assist response.
 * @param {Object} data - Complete AssistResponse object
 * @returns {void}
 */
function renderFan(data) {
  renderNavigationBase(data.navigation);
  renderCrowdBase(data.crowd_status);    // API uses crowd_status
  renderTransportChips(data.transport_options); // API uses transport_options (array)
  renderAlertsFan(data.alerts);
  renderInsightsBase(data);
  showResults();
}


// ── Form submit ───────────────────────────────────────────────────────────────
/**
 * Handle fan form submission: build payload, call API, render results.
 * @param {SubmitEvent} e - The form submit event
 * @returns {Promise<void>}
 */
async function handleFanSubmit(e) {
  e.preventDefault();
  const btn    = document.getElementById('submit-btn');
  const status = document.getElementById('status-msg');
  clearStatus(status);

  setLoading(btn, true, FAN_DEFAULT_BTN_TEXT);
  try {
    const payload = buildPayload('fan');
    const data    = await fetchAssist(payload);
    renderFan(data);
  } catch (err) {
    setStatus(status, err.message || 'Unable to fetch guidance. Please try again.');
  } finally {
    setLoading(btn, false, FAN_DEFAULT_BTN_TEXT);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initFormToggle();
  initTransportChips();

  const form = document.getElementById('fan-form');
  if (form) form.addEventListener('submit', handleFanSubmit);

  // Switch Role link
  document.querySelectorAll('.switch-role-link').forEach((el) => {
    el.addEventListener('click', () => { clearRole(); });
  });

  // Auto-fill name from localStorage
  const savedName = localStorage.getItem('stadiumiq_name');
  const nameEl    = document.getElementById('profile-name');
  if (savedName && nameEl) nameEl.value = savedName;
  if (nameEl) {
    nameEl.addEventListener('change', () => {
      if (nameEl.value.trim()) localStorage.setItem('stadiumiq_name', nameEl.value.trim());
    });
  }
});
