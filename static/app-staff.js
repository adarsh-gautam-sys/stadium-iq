/**
 * StadiumIQ — app-staff.js
 * Staff command center logic: KPI row, alert acknowledgements, transport table.
 * Depends on: app-core.js (loaded first).
 *
 * API response shape:
 *   data.crowd_status     — crowd object
 *   data.transport_options — array of transport objects
 *   data.navigation, data.alerts, data.insights, data.confidence_score
 */
'use strict';

const STAFF_DEFAULT_BTN_TEXT = 'Generate Briefing ⚽';

// ── KPI row render ────────────────────────────────────────────────────────────
function renderKpiRow(data) {
  const crowd    = data.crowd_status || {};
  const transArr = data.transport_options || [];
  const alerts   = data.alerts || [];
  const pct      = crowd.occupancy_pct || 0;

  // Build transport flat map; pick recommended = lowest estimated_wait_minutes
  const tmap = {};
  let recMode = 'shuttle';
  let minWait = Infinity;
  transArr.forEach((t) => {
    tmap[t.mode] = t;
    if ((t.estimated_wait_minutes || 0) < minWait) {
      minWait = t.estimated_wait_minutes;
      recMode = t.mode;
    }
  });
  const recT = tmap[recMode] || {};

  // KPI 1 — Crowd Density
  const crowdKpiEl = document.getElementById('kpi-crowd');
  if (crowdKpiEl) {
    const valEl = crowdKpiEl.querySelector('.kpi-value');
    const subEl = crowdKpiEl.querySelector('.kpi-sub');
    const losEl = crowdKpiEl.querySelector('.kpi-los-badge');
    const bar   = crowdKpiEl.querySelector('.kpi-mini-fill');
    if (valEl) valEl.textContent = pct + '%';
    if (subEl) subEl.textContent = 'Zone: ' + (crowd.zone || '—');
    if (losEl) losEl.textContent = crowd.level_of_service || '—';
    if (bar)   setTimeout(() => { bar.style.width = pct + '%'; }, 50);
  }

  // KPI 2 — Active Alerts
  const alertKpiEl = document.getElementById('kpi-alerts');
  if (alertKpiEl) {
    const total    = alerts.length;
    const critical = alerts.filter((a) => a.severity === 'critical').length;
    const warning  = alerts.filter((a) => a.severity === 'warning').length;
    const info     = alerts.filter((a) => a.severity === 'info').length;
    const valEl    = alertKpiEl.querySelector('.kpi-value');
    const subEl    = alertKpiEl.querySelector('.kpi-sub');
    const badge    = alertKpiEl.querySelector('.kpi-badge');
    if (valEl)  valEl.textContent = total;
    if (subEl)  subEl.textContent = `${critical} critical · ${warning} warning · ${info} info`;
    if (badge) {
      if (critical > 0)      { badge.textContent = '🔴 Critical Active'; badge.className = 'kpi-badge red'; }
      else if (warning > 0)  { badge.textContent = '⚠️ Warnings Active'; badge.className = 'kpi-badge amber'; }
      else                   { badge.textContent = '✅ All Clear';        badge.className = 'kpi-badge green'; }
    }
  }

  // KPI 3 — Transport
  const transKpiEl = document.getElementById('kpi-transport');
  if (transKpiEl) {
    const icon  = TRANSPORT_ICONS[recMode] || '🚌';
    const wait  = recT.estimated_wait_minutes;
    const valEl = transKpiEl.querySelector('.kpi-value');
    const subEl = transKpiEl.querySelector('.kpi-sub');
    const badge = transKpiEl.querySelector('.kpi-badge');
    if (valEl) valEl.innerHTML = `<span style="font-size:1.8rem">${icon}</span>`;
    if (subEl) subEl.textContent = wait !== undefined ? `${wait.toFixed(1)}m wait` : '—';
    if (badge) {
      const onSched = (wait !== undefined && wait < 15);
      badge.textContent = onSched ? '✅ On Schedule' : '⚠️ Delayed';
      badge.className   = onSched ? 'kpi-badge green' : 'kpi-badge amber';
    }
  }

  // KPI 4 — AI Confidence
  const aiKpiEl = document.getElementById('kpi-ai');
  if (aiKpiEl) {
    const pctConf = Math.round((data.confidence_score || 0) * 100);
    const valEl   = aiKpiEl.querySelector('.kpi-value');
    const bar     = aiKpiEl.querySelector('.kpi-mini-fill');
    // The KPI value element contains a nested <span id="kpi-ai-val">
    const innerSpan = document.getElementById('kpi-ai-val') || valEl;
    if (innerSpan) innerSpan.textContent = pctConf + '%';
    if (bar) setTimeout(() => { bar.style.width = pctConf + '%'; }, 100);
  }
}

// ── Navigation intel render (right col) ───────────────────────────────────────
function renderStaffNav(nav) {
  const timeEl  = document.getElementById('nav-time');
  const routeEl = document.getElementById('nav-route');
  const altEl   = document.getElementById('nav-alt');
  if (timeEl)  timeEl.textContent  = nav.estimated_minutes + ' min';
  if (routeEl) routeEl.textContent = nav.route_description;
  if (altEl)   altEl.textContent   = nav.alternative_route;
}

// ── Transport table — API returns transport_options as array ──────────────────
function renderTransportTable(transportArr) {
  const tbody = document.getElementById('transport-tbody');
  if (!tbody) return;

  const tmap = {};
  let recMode = 'shuttle';
  let minWait = Infinity;
  (transportArr || []).forEach((t) => {
    tmap[t.mode] = t;
    if ((t.estimated_wait_minutes || 0) < minWait) {
      minWait = t.estimated_wait_minutes;
      recMode = t.mode;
    }
  });

  const modes = ['shuttle', 'metro', 'rideshare', 'walk', 'car'];
  tbody.innerHTML = '';
  modes.forEach((mode) => {
    const t    = tmap[mode] || {};
    const icon = TRANSPORT_ICONS[mode] || '🚌';
    const wait = t.estimated_wait_minutes;
    const jour = t.estimated_journey_minutes;
    const dep  = t.departure_point || '—';
    const tr   = document.createElement('tr');
    if (mode === recMode) tr.classList.add('preferred');
    tr.innerHTML = `
      <td class="t-mode">${icon} ${mode.charAt(0).toUpperCase() + mode.slice(1)}
        ${mode === recMode ? '<span class="kpi-badge green" style="margin-left:6px;font-size:.62rem">Preferred</span>' : ''}
      </td>
      <td class="t-wait">${wait !== undefined ? wait.toFixed(1) + ' min' : '—'}</td>
      <td class="t-journey">${jour !== undefined ? jour.toFixed(1) + ' min' : '—'}</td>
      <td class="t-point">${dep}</td>`;
    tbody.appendChild(tr);
  });
}

// ── Staff alerts ──────────────────────────────────────────────────────────────
function renderAlertsStaff(alerts) {
  const panel = document.getElementById('staff-alerts-panel');
  if (!panel) return;
  panel.innerHTML = '';

  if (!alerts || alerts.length === 0) {
    panel.innerHTML = `<div class="alerts-all-clear">✅ All systems nominal — no active alerts.</div>`;
    return;
  }

  alerts.forEach((alert, i) => {
    const card  = document.createElement('div');
    card.className = 'staff-alert-card ' + (alert.severity || 'info');
    const ackId = `ack-btn-${i}`;
    // API uses action_required; fall back to staff_action or description
    const action = alert.action_required || alert.staff_action || alert.description || '';

    card.innerHTML = `
      <div class="staff-alert-top">
        <div>
          <div class="staff-alert-title-row">
            <span class="staff-alert-title">
              ${ALERT_ICONS[alert.severity] || 'ℹ️'} ${alert.title}
            </span>
            ${alert.zone ? `<span class="staff-alert-zone">${alert.zone}</span>` : ''}
          </div>
        </div>
        <button class="btn-acknowledge" id="${ackId}" aria-label="Acknowledge alert: ${alert.title}">
          Acknowledge
        </button>
      </div>
      <div class="staff-alert-action">${action}</div>`;

    const ackBtn = card.querySelector(`#${ackId}`);
    if (ackBtn) {
      ackBtn.addEventListener('click', () => {
        ackBtn.textContent = '✓ Acknowledged';
        ackBtn.classList.add('acknowledged');
        ackBtn.disabled = true;
      });
    }

    panel.appendChild(card);
  });
}

// ── Staff crowd block ─────────────────────────────────────────────────────────
function renderCrowdStaff(crowd) {
  const zoneEl  = document.getElementById('crowd-zone');
  const losEl   = document.getElementById('los-badge');
  const pctEl   = document.getElementById('crowd-pct-label');
  const recEl   = document.getElementById('crowd-recommendation');
  const fillEl  = document.getElementById('crowd-fill');

  if (zoneEl) zoneEl.textContent = crowd.zone || '—';
  if (losEl)  losEl.textContent  = crowd.level_of_service || '—';
  if (pctEl)  pctEl.textContent  = (crowd.occupancy_pct || 0) + '% — ' +
    ((crowd.occupancy_pct || 0) < 70 ? 'Safe' : (crowd.occupancy_pct || 0) < 85 ? 'Moderate' : 'High');
  if (recEl)  recEl.textContent  = crowd.recommendation || '—';

  if (fillEl) {
    const alertClass = (crowd.occupancy_pct || 0) < 70 ? 'green' : (crowd.occupancy_pct || 0) < 85 ? 'amber' : 'red';
    fillEl.className = 'crowd-bar-fill ' + alertClass;
    setTimeout(() => { fillEl.style.width = (crowd.occupancy_pct || 0) + '%'; }, 50);
  }

  // Sync los-circle
  const losCircle = document.getElementById('crowd-los-circle');
  if (losCircle) losCircle.textContent = crowd.level_of_service || '—';
}

// ── Staff insights (amber variant) ────────────────────────────────────────────
function renderInsightsStaff(data) {
  const listEl      = document.getElementById('insights-list');
  const confVal     = document.getElementById('confidence-value');
  const confFill    = document.getElementById('confidence-fill');
  const storagePill = document.getElementById('storage-pill');
  const metaEl      = document.getElementById('methodology-text');

  if (listEl) {
    listEl.innerHTML = '';
    (data.insights || []).forEach((text, i) => {
      const el = document.createElement('div');
      el.className = 'staff-insight-item';
      el.style.animationDelay = `${i * 0.1}s`;
      el.textContent = text;
      listEl.appendChild(el);
    });
  }

  const pct = Math.round((data.confidence_score || 0) * 100);
  if (confVal)  confVal.textContent = pct + '%';
  if (confFill) setTimeout(() => { confFill.style.width = pct + '%'; }, 100);
  if (storagePill) {
    storagePill.textContent = '💾 ' + (
      (data.storage_status || '').startsWith('saved_to_firestore') ? 'Saved to Firestore' : 'Saved locally'
    );
  }
  if (metaEl) metaEl.textContent = data.methodology || '';
}

// ── Main render ───────────────────────────────────────────────────────────────
function renderStaff(data) {
  renderKpiRow(data);
  renderAlertsStaff(data.alerts);
  renderCrowdStaff(data.crowd_status);           // API: crowd_status
  renderStaffNav(data.navigation);
  renderTransportTable(data.transport_options);  // API: transport_options (array)
  renderInsightsStaff(data);
  showResults();
}

// ── Form submit ───────────────────────────────────────────────────────────────
async function handleStaffSubmit(e) {
  e.preventDefault();
  const btn    = document.getElementById('submit-btn');
  const status = document.getElementById('status-msg');
  clearStatus(status);

  setLoading(btn, true, STAFF_DEFAULT_BTN_TEXT);
  try {
    const payload = buildPayload('staff');
    const data    = await fetchAssist(payload);
    renderStaff(data);
  } catch (err) {
    setStatus(status, err.message || 'Unable to generate briefing. Please check inputs.');
  } finally {
    setLoading(btn, false, STAFF_DEFAULT_BTN_TEXT);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('staff-form');
  if (form) form.addEventListener('submit', handleStaffSubmit);

  document.querySelectorAll('.switch-role-link').forEach((el) => {
    el.addEventListener('click', clearRole);
  });

  // Sync venue/phase from header dropdowns to form fields
  const headerVenue = document.getElementById('header-venue');
  const formVenue   = document.getElementById('venue-select');
  if (headerVenue && formVenue) {
    headerVenue.addEventListener('change', () => { formVenue.value = headerVenue.value; });
  }

  const headerPhase = document.getElementById('header-phase');
  const formPhase   = document.getElementById('match-phase');
  if (headerPhase && formPhase) {
    headerPhase.addEventListener('change', () => { formPhase.value = headerPhase.value; });
  }
});
