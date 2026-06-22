/**
 * state.js — Shared App State (appState singleton)
 * Single source of truth for all input fields across all panels.
 * Persists to localStorage; pre-fills every panel on open.
 */

const STORAGE_KEY = 'ipm_app_state_v1';

const DEFAULTS = {
  // IPR
  ipr_model:  'composite',
  Pr:         '',
  Pb:         '',
  Qo_test:    '',
  Pwf_test:   '',
  // PVT
  sg_gas:     0.65,
  sg_oil:     0.84,
  oil_api:    '',
  sg_water:   1.03,
  wc:         0.0,
  gor:        '',
  P_eval:     '',
  T:          '',
  // VLP
  vlp_model:  'hagedorn_brown',
  tubing_id:  '',
  tubing_od:  '',
  casing_id:  '',
  roughness:  0.00015,
  theta:      0,
  depth:      '',
  dz_step:    50,
  thp:        '',
  T_surface:  '',
  T_bh:       '',
  q_min:      50,
  q_max:      5000,
  q_step:     100,
  // Meta
  well_name:  'Untitled Well',
};

// Completion tracking — which keys are required per panel
const REQUIRED = {
  ipr: ['Pr', 'Qo_test', 'Pwf_test'],
  pvt: ['sg_gas', 'wc'],
  vlp: ['tubing_id', 'depth', 'thp', 'T_surface', 'T_bh'],
};

class AppState {
  constructor() {
    this._state   = { ...DEFAULTS };
    this._saved   = {};   // what's been "Apply"-ed per panel
    this._load();
  }

  _load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        this._state  = { ...DEFAULTS, ...parsed._state  };
        this._saved  = { ...parsed._saved  };
      }
    } catch (e) { /* ignore corrupt storage */ }
  }

  _persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        _state: this._state,
        _saved: this._saved,
      }));
    } catch (e) { /* ignore quota errors */ }
  }

  get(key) { return this._state[key] ?? ''; }

  set(key, value) {
    this._state[key] = value;
    this._persist();
  }

  setMany(obj) {
    Object.assign(this._state, obj);
    this._persist();
  }

  /** Commit all fields from a panel object (called on "Apply & Close") */
  commit(panelId, fields) {
    Object.assign(this._state, fields);
    this._saved[panelId] = { ...fields, _ts: Date.now() };
    this._persist();
  }

  isSaved(panelId) {
    return !!this._saved[panelId];
  }

  /** Returns a flat snapshot suitable for API calls */
  snapshot() {
    return { ...this._state };
  }

  /** Check if minimum required fields for a panel are present */
  isComplete(panelId) {
    const req = REQUIRED[panelId] || [];
    return req.every(k => {
      const v = this._state[k];
      return v !== '' && v !== null && v !== undefined;
    });
  }

  reset() {
    this._state = { ...DEFAULTS };
    this._saved = {};
    localStorage.removeItem(STORAGE_KEY);
  }
}

window.appState = new AppState();
