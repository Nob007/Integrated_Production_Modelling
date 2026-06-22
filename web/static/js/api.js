/**
 * api.js — Fetch wrappers for the Flask backend
 */

const API_BASE = '';  // same origin

async function _post(endpoint, data) {
  const resp = await fetch(API_BASE + endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    let err = `HTTP ${resp.status}`;
    try { const j = await resp.json(); err = j.error || err; } catch (_) {}
    throw new Error(err);
  }
  return resp.json();
}

const API = {
  iprCurve:        (data) => _post('/api/ipr/curve',        data),
  pvtProperties:   (data) => _post('/api/pvt/properties',   data),
  pvtCurve:        (data) => _post('/api/pvt/curve',        data),
  vlpCurve:        (data) => _post('/api/vlp/curve',        data),
  nodalSolve:      (data) => _post('/api/nodal/solve',      data),
  traverse:        (data) => _post('/api/traverse',         data),
  sensitivityRun:  (data) => _post('/api/sensitivity/run',  data),
  exportCsv:       (data) => fetch(API_BASE + '/api/export/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }),
};

window.API = API;
