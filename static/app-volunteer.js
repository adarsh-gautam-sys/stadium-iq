/**
 * StadiumIQ — app-volunteer.js
 * Volunteer dashboard logic: Radar, guidance script, warning-only alerts,
 * copy-to-clipboard briefing, collapsible refresh form.
 * Depends on: app-core.js (loaded first).
 */
'use strict';

const VOL_DEFAULT_BTN_TEXT = 'Refresh Briefing ⚽';

// ── Quick status pills ────────────────────────────────────────────────────────
/**
 * Update the three status pills (crowd LoS, zone, match phase) from crowd data.
 * @param {Object} crowd - CrowdStatus object from /api/assist
 * @returns {void}
 */
function updateStatusPills(crowd) {
  const crowdPill = document.getElementById('pill-crowd');
  const zonePill  = document.getElementById('pill-zone');
  const phasePill = document.getElementById('pill-phase');

  if (crowdPill) {
    crowdPill.textContent = `📊 Crowd: LoS ${crowd.level_of_service}`;
    crowdPill.className   = 'status-pill ' +
      (crowd.alert === 'green' ? 'crowd-green' : crowd.alert === 'red' ? 'crowd-red' : 'crowd-amber');
  }
  if (zonePill)  zonePill.textContent  = `📍 Zone: ${crowd.zone}`;
  if (phasePill) {
    const phaseVal = document.getElementById('match-phase');
    const phaseLabel = PHASE_LABELS[phaseVal?.value] || '🚶 Arrival';
    phasePill.textContent = phaseLabel;
  }
}

// ── Fan Assistance Radar render ───────────────────────────────────────────────
/**
 * Render the Fan Assistance Radar section: LoS badge, occupancy bar,
 * and auto-generated volunteer guidance script.
 * @param {Object} crowd - CrowdStatus object from /api/assist
 * @returns {void}
 */
function renderRadar(crowd) {
  const losEl   = document.getElementById('radar-los');
  const zoneEl  = document.getElementById('radar-zone');
  const fillEl  = document.getElementById('radar-fill');
  const occEl   = document.getElementById('radar-occ');
  const scriptEl= document.getElementById('guidance-script');
  const phaseEl = document.getElementById('radar-phase-note');

  if (losEl)  losEl.textContent  = crowd.level_of_service;
  if (zoneEl) zoneEl.textContent = crowd.zone;
  if (occEl)  occEl.textContent  = crowd.occupancy_pct + '% Occupancy';

  if (fillEl) {
    fillEl.className = 'radar-fill-inner ' + crowd.alert;
    setTimeout(() => { fillEl.style.width = crowd.occupancy_pct + '%'; }, 50);
  }

  if (scriptEl) {
    scriptEl.className = 'guidance-script-box' + (crowd.alert === 'red' ? ' critical' : '');
    // Build a volunteer-specific script from the crowd data
    const densityWord = crowd.occupancy_pct < 60 ? 'Low crowd' :
      crowd.occupancy_pct < 75 ? 'Moderate crowd' :
      crowd.occupancy_pct < 88 ? 'High congestion' : 'Critical congestion';
    const action = crowd.alert === 'red'
      ? 'Guide fans to emergency exit routes immediately. Summon additional staff.'
      : crowd.alert === 'amber'
      ? 'Guide fans to alternative concourse routes. Expect wait times. Encourage patience.'
      : 'Normal flow — guide fans to their sections. Monitor ingress rate.';
    scriptEl.textContent = `${densityWord}. ${action} ${crowd.volunteer_guidance || ''}`;
  }

  if (phaseEl) {
    const phaseEl2 = document.getElementById('match-phase');
    const phase = phaseEl2?.value || 'arrival';
    const mult  = { arrival: '0.75', kickoff: '1.2', halftime: '0.9', post_match: '1.1', pre_match: '0.6' };
    phaseEl.textContent = `Match Phase: ${phase.replace('_', '-')} × ${mult[phase] || '1.0'} multiplier applied`;
  }
}

// ── Personal navigation (compact) ─────────────────────────────────────────────
/**
 * Render volunteer personal navigation guidance (compact form of navigation card).
 * @param {Object} nav - NavigationGuidance object from /api/assist
 * @returns {void}
 */
function renderVolNav(nav) {
  const timeEl   = document.getElementById('nav-time');
  const routeEl  = document.getElementById('nav-route');
  const altEl    = document.getElementById('nav-alt');
  const badgeEl  = document.getElementById('crowd-badge');

  if (timeEl)  timeEl.textContent = nav.estimated_minutes;
  if (routeEl) routeEl.textContent = nav.route_description;
  if (altEl)   altEl.textContent   = nav.alternative_route;
  if (badgeEl) {
    badgeEl.textContent = nav.crowd_level.charAt(0).toUpperCase() + nav.crowd_level.slice(1) + ' Crowd';
    badgeEl.className   = 'crowd-badge ' + (CROWD_CLASSES[nav.crowd_level] || 'low');
  }
}

// ── Volunteer alerts (warning + critical only) ─────────────────────────────────
/**
 * Render volunteer alerts — only warning and critical severity shown.
 * Info alerts are suppressed to reduce noise for volunteers.
 * @param {Object[]} alerts - Array of OperationalAlert objects from /api/assist
 * @returns {void}
 */
function renderAlertsVol(alerts) {
  const listEl  = document.getElementById('vol-alerts');
  const clearEl = document.getElementById('vol-alerts-clear');
  if (!listEl) return;

  const relevant = (alerts || []).filter(
    (a) => a.severity === 'warning' || a.severity === 'critical'
  );

  listEl.innerHTML = '';
  if (relevant.length === 0) {
    if (clearEl) clearEl.style.display = 'block';
    return;
  }
  if (clearEl) clearEl.style.display = 'none';

  relevant.forEach((alert) => {
    const div = document.createElement('div');
    div.className = 'vol-alert-item ' + alert.severity;
    div.innerHTML = `
      <div>
        <div class="vol-alert-title">
          ${ALERT_ICONS[alert.severity] || '⚠️'} ${alert.title}
          ${alert.zone ? `<span class="alert-zone-pill">${alert.zone}</span>` : ''}
        </div>
        <div class="vol-alert-action">
          ${alert.volunteer_action || alert.staff_action || alert.description || ''}
        </div>
      </div>`;
    listEl.appendChild(div);
  });
}

// ── Volunteer briefing (teal insights) ────────────────────────────────────────
/**
 * Render volunteer AI briefing insights with teal styling.
 * @param {Object} data - Complete AssistResponse object
 * @returns {void}
 */
function renderInsightsVol(data) {
  const listEl   = document.getElementById('insights-list');
  const confVal  = document.getElementById('confidence-value');
  const confFill = document.getElementById('confidence-fill');
  const storagePill = document.getElementById('storage-pill');
  const metaEl   = document.getElementById('methodology-text');

  if (listEl) {
    listEl.innerHTML = '';
    (data.insights || []).forEach((text, i) => {
      const el = document.createElement('div');
      el.className = 'vol-insight-item';
      el.style.animationDelay = `${i * 0.1}s`;
      el.textContent = text;
      listEl.appendChild(el);
    });
  }

  const pct = Math.round((data.confidence_score || 0) * 100);
  if (confVal)  confVal.textContent = pct + '%';
  if (confFill) {
    setTimeout(() => { confFill.style.width = pct + '%'; }, 100);
    const confBar = document.getElementById('confidence-bar');
    if (confBar) confBar.setAttribute('aria-valuenow', String(pct));
  }
  if (storagePill) {
    storagePill.textContent = '💾 ' + (
      data.storage_status.startsWith('saved_to_firestore') ? 'Saved to Firestore' : 'Saved locally'
    );
  }
  if (metaEl) metaEl.textContent = data.methodology || '';
}

// ── Copy guidance to clipboard ─────────────────────────────────────────────────
/**
 * Initialise the "Copy Guidance" button with clipboard write logic.
 * Copies volunteer script + AI briefing as formatted plain text.
 * @returns {void}
 */
function initCopyGuidance() {
  const copyBtn = document.getElementById('copy-guidance-btn');
  if (!copyBtn) return;

  copyBtn.addEventListener('click', async () => {
    const insights = document.getElementById('insights-list');
    const script   = document.getElementById('guidance-script');
    const parts    = [];

    if (script)   parts.push('=== VOLUNTEER GUIDANCE ===\n' + script.textContent.trim());
    if (insights) parts.push('\n=== AI BRIEFING ===\n' + insights.textContent.trim());

    const text = parts.join('\n') || 'No guidance loaded yet.';
    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = '✓ Copied to Clipboard!';
      copyBtn.classList.add('copied');
      setTimeout(() => {
        copyBtn.textContent = '📋 Copy Guidance to Clipboard';
        copyBtn.classList.remove('copied');
      }, 2500);
    } catch (_) {
      copyBtn.textContent = 'Copy failed — try manually selecting text.';
    }
  });
}

// ── Collapsible form ──────────────────────────────────────────────────────────
/**
 * Initialise the collapsible refresh form toggle button.
 * @returns {void}
 */
function initVolFormToggle() {
  const toggleBtn    = document.getElementById('vol-form-toggle');
  const formCollapse = document.getElementById('vol-form-collapse');
  if (!toggleBtn || !formCollapse) return;

  toggleBtn.addEventListener('click', () => {
    const isOpen = formCollapse.classList.toggle('open');
    toggleBtn.classList.toggle('open', isOpen);
    toggleBtn.setAttribute('aria-expanded', String(isOpen));
  });
}

// ── Main render ───────────────────────────────────────────────────────────────────
/**
 * Orchestrate all volunteer dashboard renders from a complete /api/assist response.
 * @param {Object} data - Complete AssistResponse object
 * @returns {void}
 */
function renderVolunteer(data) {
  updateStatusPills(data.crowd_status);  // API: crowd_status
  renderRadar(data.crowd_status);
  renderVolNav(data.navigation);
  renderAlertsVol(data.alerts);
  renderInsightsVol(data);
  showResults();
}


// ── Form submit ───────────────────────────────────────────────────────────────
/**
 * Handle volunteer refresh form submission: build payload, call API, render.
 * @param {SubmitEvent} e - The form submit event
 * @returns {Promise<void>}
 */
async function handleVolSubmit(e) {
  e.preventDefault();
  const btn    = document.getElementById('submit-btn');
  const status = document.getElementById('status-msg');
  clearStatus(status);

  setLoading(btn, true, VOL_DEFAULT_BTN_TEXT);
  try {
    const payload = buildPayload('volunteer');
    const data    = await fetchAssist(payload);
    renderVolunteer(data);
  } catch (err) {
    setStatus(status, err.message || 'Unable to refresh briefing. Please check inputs.');
  } finally {
    setLoading(btn, false, VOL_DEFAULT_BTN_TEXT);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initVolFormToggle();
  initCopyGuidance();

  const form = document.getElementById('vol-form');
  if (form) form.addEventListener('submit', handleVolSubmit);

  document.querySelectorAll('.switch-role-link').forEach((el) => {
    el.addEventListener('click', clearRole);
  });
});
