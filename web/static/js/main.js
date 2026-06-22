/**
 * main.js — Router, Panel Orchestration, Status Strip, Toast System
 * Entry point: initialises all panels and wires up the Home launchpad.
 */

// ── Toast ─────────────────────────────────────────────────────────────────
window.Toast = {
  show(msg, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => {
      el.classList.add('fade-out');
      setTimeout(() => el.remove(), 250);
    }, duration);
  }
};

// ── Router ────────────────────────────────────────────────────────────────
window.Router = {
  show(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const target = document.getElementById(`screen-${screenId}`);
    if (target) target.classList.add('active');
  }
};

// ── Panel System ──────────────────────────────────────────────────────────
window.Panels = {
  _current: null,

  open(panelId) {
    // Close any open panel first
    if (this._current && this._current !== panelId) {
      this._closePanel(this._current, false);
    }

    const panel    = document.getElementById(`panel-${panelId}`);
    const backdrop = document.getElementById('overlay-backdrop');
    if (!panel) return;

    // Fill from state
    const fillers = {
      ipr:         () => IPRPanel.fillFromState(),
      pvt:         () => PVTPanel.fillFromState(),
      vlp:         () => VLPPanel.fillFromState(),
      sensitivity: () => {},
    };
    if (fillers[panelId]) fillers[panelId]();

    panel.classList.add('active');
    backdrop.classList.add('active');
    this._current = panelId;
  },

  close(panelId) { this._closePanel(panelId, true); },

  _closePanel(panelId, updateStatus) {
    const panel    = document.getElementById(`panel-${panelId}`);
    const backdrop = document.getElementById('overlay-backdrop');
    if (panel)    panel.classList.remove('active');
    if (backdrop) backdrop.classList.remove('active');
    if (this._current === panelId) this._current = null;
    if (updateStatus) updateStatusStrip();
  }
};

// ── Status Strip & Readiness ──────────────────────────────────────────────
function updateStatusStrip() {
  const iprDone = appState.isComplete('ipr');
  const pvtDone = appState.isSaved('pvt');
  const vlpDone = appState.isComplete('vlp');

  // Status strip badges
  const ssIpr = document.getElementById('ss-ipr');
  const ssPvt = document.getElementById('ss-pvt');
  const ssVlp = document.getElementById('ss-vlp');
  const ssMsg = document.getElementById('ss-msg');

  function _badge(el, done, label) {
    const badge = el.querySelector('.ss-badge');
    if (done) {
      badge.textContent = '✓';
      badge.className = 'ss-badge ss-badge--done';
    } else {
      badge.textContent = '—';
      badge.className = 'ss-badge ss-badge--empty';
    }
  }
  _badge(ssIpr, iprDone);
  _badge(ssPvt, pvtDone);
  _badge(ssVlp, vlpDone);

  const missing = [];
  if (!iprDone) missing.push('IPR');
  if (!vlpDone) missing.push('VLP');
  ssMsg.textContent = missing.length
    ? `Complete ${missing.join(', ')} to unlock Nodal Analysis`
    : 'Ready for Nodal Analysis ✓';

  // Nav status pill
  const pill = document.getElementById('nav-status-pill');
  const dot  = pill.querySelector('.status-dot');
  const text = document.getElementById('nav-status-text');
  if (iprDone && vlpDone) {
    dot.className  = 'status-dot status-dot--green';
    text.textContent = 'Ready';
  } else if (iprDone || pvtDone || vlpDone) {
    dot.className  = 'status-dot status-dot--blue';
    text.textContent = 'In progress';
  } else {
    dot.className  = 'status-dot status-dot--gray';
    text.textContent = 'No data yet';
  }

  // Completion badges on cards
  _setCardBadge('badge-ipr', iprDone);
  _setCardBadge('badge-pvt', pvtDone);
  _setCardBadge('badge-vlp', vlpDone);

  // Nodal readiness pill
  const nodalReady = iprDone && vlpDone;
  const nodalPill  = document.getElementById('nodal-readiness-pill');
  if (nodalPill) {
    nodalPill.textContent = nodalReady ? 'Ready ✓' : 'Complete IPR + VLP first';
    nodalPill.className   = nodalReady ? 'pill pill--ready' : 'pill pill--white';
  }

  // Readiness bar
  const steps = [iprDone, pvtDone, vlpDone];
  const pct   = Math.round((steps.filter(Boolean).length / 3) * 100);
  const fill  = document.getElementById('readiness-fill');
  if (fill) fill.style.width = pct + '%';

  // Readiness labels
  ['ipr', 'pvt', 'vlp'].forEach((p, i) => {
    const el = document.getElementById(`rb-${p}`);
    if (el) el.classList.toggle('done', steps[i]);
  });
}

function _setCardBadge(badgeId, done) {
  const el = document.getElementById(badgeId);
  if (!el) return;
  const ring = el.querySelector('.completion-ring');
  if (!ring) return;
  ring.className = 'completion-ring ' + (done ? 'completion-ring--done' : 'completion-ring--empty');
}

// ── Wire Launchpad Cards ──────────────────────────────────────────────────
function _wireLaunchpad() {
  // Panel cards
  document.querySelectorAll('[data-panel]').forEach(card => {
    card.addEventListener('click', () => {
      const panel = card.dataset.panel;
      if (panel === 'nodal') {
        // Check readiness
        if (!appState.isComplete('ipr') || !appState.isComplete('vlp')) {
          if (!appState.isComplete('ipr')) {
            Toast.show('Complete IPR data first.', 'error');
            setTimeout(() => Panels.open('ipr'), 400);
          } else {
            Toast.show('Complete VLP data first.', 'error');
            setTimeout(() => Panels.open('vlp'), 400);
          }
          return;
        }
        Router.show('nodal');
        setTimeout(() => NodalScreen.run(), 100);
      } else {
        Panels.open(panel);
      }
    });
  });

  // "Coming soon" cards
  document.querySelectorAll('[data-soon]').forEach(card => {
    card.addEventListener('click', () => {
      const title = card.querySelector('.card-title--muted')?.textContent || 'This feature';
      Toast.show(`${title} is on our roadmap and coming soon! Stay tuned.`, 'info', 4000);
    });
  });
}

// ── Panel Close Buttons ───────────────────────────────────────────────────
function _wirePanelClose() {
  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      Panels.close(btn.dataset.close);
      updateStatusStrip();
    });
  });

  // Backdrop click closes panel
  document.getElementById('overlay-backdrop').addEventListener('click', () => {
    if (Panels._current) Panels.close(Panels._current);
    updateStatusStrip();
  });
}

// ── Nav Actions ───────────────────────────────────────────────────────────
function _wireNav() {
  // Well name
  document.getElementById('nav-well-name').textContent = appState.get('well_name') || 'Untitled Well';

  document.getElementById('btn-edit-well').addEventListener('click', () => {
    document.getElementById('well-name-input').value = appState.get('well_name') || '';
    document.getElementById('well-modal-backdrop').style.display = 'flex';
  });
  document.getElementById('btn-well-cancel').addEventListener('click', () => {
    document.getElementById('well-modal-backdrop').style.display = 'none';
  });
  document.getElementById('btn-well-save').addEventListener('click', () => {
    const name = document.getElementById('well-name-input').value.trim() || 'Untitled Well';
    appState.set('well_name', name);
    document.getElementById('nav-well-name').textContent = name;
    document.getElementById('well-modal-backdrop').style.display = 'none';
    Toast.show('Well name updated.', 'success');
  });

  // Reset all
  document.getElementById('btn-reset-all').addEventListener('click', () => {
    document.getElementById('reset-modal-backdrop').style.display = 'flex';
  });
  document.getElementById('btn-reset-cancel').addEventListener('click', () => {
    document.getElementById('reset-modal-backdrop').style.display = 'none';
  });
  document.getElementById('btn-reset-confirm').addEventListener('click', () => {
    appState.reset();
    document.getElementById('reset-modal-backdrop').style.display = 'none';
    updateStatusStrip();
    Toast.show('All inputs reset.', 'info');
    // Reset nav
    document.getElementById('nav-well-name').textContent = 'Untitled Well';
    // Return to home
    Router.show('home');
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Initialise panels
  IPRPanel.init();
  PVTPanel.init();
  VLPPanel.init();
  SensPanel.init();
  NodalScreen.init();

  // Wire up UI
  _wireLaunchpad();
  _wirePanelClose();
  _wireNav();

  // Initial status
  updateStatusStrip();

  // Start on home
  Router.show('home');

  console.log('IPM Nodal Analysis Suite loaded ✓');
});
