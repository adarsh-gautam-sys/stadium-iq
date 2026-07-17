/**
 * StadiumIQ — app.js
 * Async fetch + full error handling + result rendering
 * Follows the canonical pattern from the playbook exactly.
 */

'use strict';

// ── Transport mode icons ─────────────────────────────────────────────────────
const TRANSPORT_ICONS = {
  walk:      '🚶',
  shuttle:   '🚌',
  metro:     '🚇',
  rideshare: '🚗',
  car:       '🅿️',
};

// ── Crowd badge class mapping ─────────────────────────────────────────────────
const CROWD_CLASSES = {
  low:      'low',
  moderate: 'moderate',
  high:     'high',
  critical: 'critical',
};

// ── Alert severity icons ─────────────────────────────────────────────────────
const ALERT_ICONS = {
  info:     'ℹ️',
  warning:  '⚠️',
  critical: '🚨',
};

// ── Collect form values into the API payload ─────────────────────────────────
function buildPayload() {
  const g = (id) => document.getElementById(id);

  return {
    profile: {
      name:               g('profile-name').value.trim() || 'Guest',
      role:               g('profile-role').value,
      language:           g('profile-language').value,
      mobility_aid:       g('mobility-aid').value,
      visual_impairment:  g('visual-impairment').checked,
      hearing_impairment: g('hearing-impairment').checked,
      party_size:         parseInt(g('profile-party-size').value, 10) || 1,
    },
    venue: {
      venue:              g('venue-select').value,
      section:            g('section').value.trim() || 'GA',
      current_zone:       g('current-zone').value.trim() || 'Main Entrance',
      match_phase:        g('match-phase').value,
      crowd_density_pct:  parseFloat(g('crowd-density').value) || 65.0,
    },
    navigation: {
      destination:              g('destination').value,
      destination_detail:       g('destination-detail').value.trim(),
      requires_elevator:        g('requires-elevator').checked,
      requires_accessible_route: g('requires-accessible-route').checked,
    },
    transport: {
      transport_mode: g('transport-mode').value,
      direction:      g('direction').value,
      distance_km:    parseFloat(g('distance-km').value) || 3.5,
    },
  };
}

// ── Render navigation guidance ───────────────────────────────────────────────
function renderNavigation(nav) {
  document.getElementById('nav-time').textContent = nav.estimated_minutes;
  document.getElementById('nav-route').textContent = nav.route_description;
  document.getElementById('nav-alt').textContent = nav.alternative_route;

  const badge = document.getElementById('crowd-badge');
  badge.textContent = nav.crowd_level.charAt(0).toUpperCase() + nav.crowd_level.slice(1) + ' Crowd';
  badge.className = 'crowd-badge ' + (CROWD_CLASSES[nav.crowd_level] || 'low');

  const a11yEl = document.getElementById('a11y-note');
  if (nav.accessibility_notes && nav.accessibility_notes !== 'Standard route — no accessibility adjustments required.') {
    a11yEl.style.display = 'flex';
    document.getElementById('a11y-text').textContent = nav.accessibility_notes;
  } else {
    a11yEl.style.display = 'none';
  }
}

// ── Render crowd status ───────────────────────────────────────────────────────
function renderCrowd(crowd) {
  document.getElementById('crowd-zone').textContent = crowd.zone;
  document.getElementById('los-badge').textContent = crowd.level_of_service;
  document.getElementById('crowd-pct-label').textContent = crowd.occupancy_pct + '%';
  document.getElementById('crowd-recommendation').textContent = crowd.recommendation;

  const fill = document.getElementById('crowd-fill');
  fill.className = 'crowd-fill ' + crowd.alert;
  // Animate width
  setTimeout(() => { fill.style.width = crowd.occupancy_pct + '%'; }, 50);

  const meter = document.getElementById('crowd-meter-el');
  meter.setAttribute('aria-valuenow', crowd.occupancy_pct);
}

// ── Render transport options ───────────────────────────────────────────────────
function renderTransport(options, preferredMode) {
  const list = document.getElementById('transport-list');
  list.innerHTML = '';

  options.slice(0, 5).forEach((opt, idx) => {
    const isPreferred = opt.mode === preferredMode || idx === 0;
    const icon = TRANSPORT_ICONS[opt.mode] || '🚌';

    const el = document.createElement('div');
    el.className = 'transport-item' + (isPreferred ? ' preferred' : '');
    el.setAttribute('role', 'listitem');
    el.innerHTML = `
      <span class="transport-icon" aria-hidden="true">${icon}</span>
      <div>
        <div class="transport-mode">${opt.mode}</div>
        <div class="transport-note">${opt.departure_point.substring(0, 60)}…</div>
      </div>
      <div class="transport-time">
        <div class="time-wait">Wait: ${opt.estimated_wait_minutes}m</div>
        <div class="time-journey">${opt.estimated_journey_minutes} min</div>
      </div>
    `;
    list.appendChild(el);
  });
}

// ── Render operational alerts ─────────────────────────────────────────────────
function renderAlerts(alerts) {
  const list = document.getElementById('alert-list');
  list.innerHTML = '';

  alerts.forEach((alert) => {
    const icon = ALERT_ICONS[alert.severity] || 'ℹ️';
    const el = document.createElement('div');
    el.className = 'alert-item ' + alert.severity;
    el.innerHTML = `
      <span class="alert-icon" aria-hidden="true">${icon}</span>
      <div>
        <div class="alert-title">${alert.title}</div>
        <div class="alert-action">${alert.action_required}</div>
      </div>
    `;
    list.appendChild(el);
  });
}

// ── Render AI insights ────────────────────────────────────────────────────────
function renderInsights(insights) {
  const list = document.getElementById('insights-list');
  list.innerHTML = '';

  insights.forEach((text) => {
    const el = document.createElement('div');
    el.className = 'insight-item';
    el.textContent = text;
    list.appendChild(el);
  });
}

// ── Render full response ──────────────────────────────────────────────────────
function renderResults(data, preferredMode) {
  renderNavigation(data.navigation);
  renderCrowd(data.crowd_status);
  renderTransport(data.transport_options, preferredMode);
  renderAlerts(data.alerts);
  renderInsights(data.insights);

  // Confidence score
  const pct = Math.round(data.confidence_score * 100);
  document.getElementById('confidence-value').textContent = pct + '%';
  setTimeout(() => {
    document.getElementById('confidence-fill').style.width = pct + '%';
  }, 100);

  // Storage status
  const pill = document.getElementById('storage-pill');
  pill.textContent = '💾 ' + (data.storage_status.startsWith('saved_to_firestore')
    ? 'Saved to Firestore'
    : data.storage_status.startsWith('saved_locally')
    ? 'Saved locally'
    : data.storage_status);

  // Methodology
  document.getElementById('methodology-text').textContent = data.methodology;

  // Show results panel
  const resultsEl = document.getElementById('results');
  resultsEl.classList.add('visible');
  resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Form submit handler — canonical playbook pattern ──────────────────────────
async function submitForm(e) {
  e.preventDefault();

  const submitBtn = document.getElementById('submit-btn');
  const statusEl  = document.getElementById('status-msg');

  // Disable UI immediately — prevent double-submit
  submitBtn.disabled = true;
  submitBtn.classList.add('loading');
  submitBtn.textContent = 'Getting your guidance…';
  statusEl.textContent = '';
  statusEl.className = '';
  statusEl.style.display = 'none';

  const payload = buildPayload();
  const preferredMode = payload.transport.transport_mode;

  try {
    const res = await fetch('/api/assist', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      // Show first Pydantic validation message if present
      const msg = Array.isArray(err.detail)
        ? err.detail.map((d) => d.msg).join(', ')
        : (err.detail || `HTTP ${res.status} — please check your inputs.`);
      throw new Error(msg);
    }

    const data = await res.json();
    renderResults(data, preferredMode);

  } catch (err) {
    statusEl.textContent = '⚠️ ' + err.message;
    statusEl.className = 'error';
    statusEl.style.display = 'block';
  } finally {
    // Always re-enable in finally — runs even on error
    submitBtn.disabled = false;
    submitBtn.classList.remove('loading');
    submitBtn.textContent = '⚽ Get My Stadium Guidance';
  }
}

// ── Bind form ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('assist-form').addEventListener('submit', submitForm);

  // Mirror accessibility checkboxes to accessible route field
  document.getElementById('mobility-aid').addEventListener('change', (e) => {
    const hasAid = e.target.value !== 'none';
    if (hasAid) {
      document.getElementById('requires-accessible-route').checked = true;
    }
  });
});
