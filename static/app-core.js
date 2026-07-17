/**
 * StadiumIQ — app-core.js
 * Shared API utilities, payload builder, and localStorage helpers.
 * Imported by all role-specific JS files via <script> tag ordering.
 */
'use strict';

// ── Transport / alert icon maps ──────────────────────────────────────────────
const TRANSPORT_ICONS = {
  walk:      '🚶',
  shuttle:   '🚌',
  metro:     '🚇',
  rideshare: '🚗',
  car:       '🅿️',
};

const ALERT_ICONS = {
  info:     'ℹ️',
  warning:  '⚠️',
  critical: '🚨',
};

const CROWD_CLASSES = {
  low:      'low',
  moderate: 'moderate',
  high:     'high',
  critical: 'critical',
};

// ── Venue display names ──────────────────────────────────────────────────────
const VENUE_LABELS = {
  sofi_stadium:          'SoFi Stadium — Los Angeles',
  metlife_stadium:       'MetLife Stadium — New York/NJ',
  att_stadium:           'AT&T Stadium — Dallas',
  nrg_stadium:           'NRG Stadium — Houston',
  levis_stadium:         "Levi's Stadium — San Francisco",
  arrowhead_stadium:     'Arrowhead — Kansas City',
  lincoln_financial:     'Lincoln Financial — Philadelphia',
  gillette_stadium:      'Gillette Stadium — Boston',
  hard_rock_stadium:     'Hard Rock Stadium — Miami',
  mercedes_benz_stadium: 'Mercedes-Benz Stadium — Atlanta',
  lumen_field:           'Lumen Field — Seattle',
  estadio_azteca:        'Estadio Azteca — Mexico City',
  estadio_akron:         'Estadio AKRON — Guadalajara',
  estadio_bbva:          'Estadio BBVA — Monterrey',
  bmo_field:             'BMO Field — Toronto',
  bc_place:              'BC Place — Vancouver',
};

const PHASE_LABELS = {
  pre_match: '🌅 Pre-Match',
  arrival:   '🚶 Arrival',
  kickoff:   '⚽ Kick-off',
  halftime:  '⏸️ Half-time',
  post_match:'🏁 Post-Match',
};

// ── Payload builder ──────────────────────────────────────────────────────────
/**
 * Collect form values into the /api/assist request body.
 * @param {string} roleOverride - Force a specific role value ('fan'|'staff'|'volunteer')
 * @returns {Object} API payload
 */
function buildPayload(roleOverride) {
  const g = (id) => {
    const el = document.getElementById(id);
    return el || null;
  };
  const val = (id, fallback = '') => g(id) ? g(id).value : fallback;
  const checked = (id) => g(id) ? g(id).checked : false;

  return {
    profile: {
      name:               (val('profile-name') || 'Guest').trim() || 'Guest',
      role:               roleOverride,
      language:           val('profile-language', 'en'),
      mobility_aid:       val('mobility-aid', 'none'),
      visual_impairment:  checked('visual-impairment'),
      hearing_impairment: checked('hearing-impairment'),
      party_size:         parseInt(val('profile-party-size', '1'), 10) || 1,
    },
    venue: {
      venue:              val('venue-select', 'sofi_stadium'),
      section:            (val('section') || 'GA').trim() || 'GA',
      current_zone:       (val('current-zone') || 'Main Entrance').trim() || 'Main Entrance',
      match_phase:        val('match-phase', 'arrival'),
      crowd_density_pct:  parseFloat(val('crowd-density', '65')) || 65.0,
    },
    navigation: {
      destination:               val('destination', 'seat'),
      destination_detail:        val('destination-detail', '').trim(),
      requires_elevator:         checked('requires-elevator'),
      requires_accessible_route: checked('requires-accessible-route'),
    },
    transport: {
      transport_mode: val('transport-mode', 'shuttle'),
      direction:      val('direction', 'arriving'),
      distance_km:    parseFloat(val('distance-km', '3.5')) || 3.5,
    },
  };
}

// ── API call ─────────────────────────────────────────────────────────────────
/**
 * POST /api/assist and return parsed JSON.
 * @param {Object} payload
 * @returns {Promise<Object>}
 */
async function fetchAssist(payload) {
  const res = await fetch('/api/assist', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = Array.isArray(err.detail)
      ? err.detail.map((d) => d.msg).join(', ')
      : (err.detail || `HTTP ${res.status} — please check your inputs.`);
    throw new Error(msg);
  }

  return res.json();
}

// ── Button loading state ─────────────────────────────────────────────────────
function setLoading(btn, isLoading, defaultText) {
  btn.disabled = isLoading;
  if (isLoading) {
    btn.classList.add('loading');
    btn.textContent = 'Loading…';
  } else {
    btn.classList.remove('loading');
    btn.textContent = defaultText;
  }
}

// ── Status message ────────────────────────────────────────────────────────────
function setStatus(el, msg, type = 'error') {
  if (!el) return;
  el.textContent = '⚠️ ' + msg;
  el.className = 'status-msg ' + type;
  el.style.display = 'block';
}
function clearStatus(el) {
  if (!el) return;
  el.textContent = '';
  el.className = 'status-msg';
  el.style.display = 'none';
}

// ── Shared navigation render ──────────────────────────────────────────────────
function renderNavigationBase(nav) {
  const timeEl = document.getElementById('nav-time');
  const routeEl = document.getElementById('nav-route');
  const altEl   = document.getElementById('nav-alt');
  const badgeEl = document.getElementById('crowd-badge');
  const a11yEl  = document.getElementById('a11y-note');
  const a11yTxt = document.getElementById('a11y-text');

  if (timeEl)  timeEl.textContent = nav.estimated_minutes;
  if (routeEl) routeEl.textContent = nav.route_description;
  if (altEl)   altEl.textContent = nav.alternative_route;

  if (badgeEl) {
    badgeEl.textContent = nav.crowd_level.charAt(0).toUpperCase() + nav.crowd_level.slice(1) + ' Crowd';
    badgeEl.className   = 'crowd-badge ' + (CROWD_CLASSES[nav.crowd_level] || 'low');
  }

  if (a11yEl && a11yTxt) {
    if (nav.accessibility_notes &&
        nav.accessibility_notes !== 'Standard route — no accessibility adjustments required.') {
      a11yEl.classList.add('visible');
      a11yTxt.textContent = nav.accessibility_notes;
    } else {
      a11yEl.classList.remove('visible');
    }
  }
}

// ── Shared crowd render — uses 'crowd_status' key from API ───────────────────
function renderCrowdBase(crowd) {
  const zoneEl  = document.getElementById('crowd-zone');
  const losBadge= document.getElementById('los-badge');
  const pctEl   = document.getElementById('crowd-pct-label');
  const recEl   = document.getElementById('crowd-recommendation');
  const fillEl  = document.getElementById('crowd-fill');
  const meterEl = document.getElementById('crowd-meter-el');

  if (zoneEl)   zoneEl.textContent  = crowd.zone;
  if (losBadge) losBadge.textContent = crowd.level_of_service;
  if (pctEl)    pctEl.textContent   = crowd.occupancy_pct + '%';
  if (recEl)    recEl.textContent   = crowd.recommendation;

  const alertClass = crowd.occupancy_pct < 70 ? 'green' : crowd.occupancy_pct < 85 ? 'amber' : 'red';
  if (fillEl) {
    fillEl.className = 'crowd-fill ' + alertClass;
    setTimeout(() => { fillEl.style.width = crowd.occupancy_pct + '%'; }, 50);
  }
  if (meterEl) meterEl.setAttribute('aria-valuenow', crowd.occupancy_pct);
}


// ── Shared insights + meta render ─────────────────────────────────────────────
function renderInsightsBase(data) {
  const listEl   = document.getElementById('insights-list');
  const confVal  = document.getElementById('confidence-value');
  const confFill = document.getElementById('confidence-fill');
  const storagePill = document.getElementById('storage-pill');
  const metaEl   = document.getElementById('methodology-text');

  if (listEl) {
    listEl.innerHTML = '';
    (data.insights || []).forEach((text, i) => {
      const el = document.createElement('div');
      el.className = 'insight-item';
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
      data.storage_status.startsWith('saved_to_firestore') ? 'Saved to Firestore' :
      data.storage_status.startsWith('saved_locally')      ? 'Saved locally'       :
      data.storage_status
    );
  }

  if (metaEl) metaEl.textContent = data.methodology || '';
}

// ── Show results section ──────────────────────────────────────────────────────
function showResults() {
  const el = document.getElementById('results');
  if (!el) return;
  el.classList.add('visible');
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Role preference localStorage ──────────────────────────────────────────────
function saveRole(role) {
  try { localStorage.setItem('stadiumiq_role', role); } catch (_) {}
}
function getRole() {
  try { return localStorage.getItem('stadiumiq_role'); } catch (_) { return null; }
}
function clearRole() {
  try { localStorage.removeItem('stadiumiq_role'); } catch (_) {}
}
