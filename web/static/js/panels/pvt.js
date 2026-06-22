/**
 * panels/pvt.js — PVT Data Panel logic
 * Live PVT curve + phase diagnosis badge.
 */

(function () {
  let _debounceTimer = null;
  let _oilGravMode = 'sg';  // 'sg' | 'api'
  let _activeProps = ['Rs', 'Bo'];

  function _getFormValues() {
    const sgOil  = parseFloat(document.getElementById('pvt-sg-oil').value);
    const oilApi = parseFloat(document.getElementById('pvt-oil-api').value);

    return {
      sg_gas:   parseFloat(document.getElementById('pvt-sg-gas').value)   || 0.65,
      sg_oil:   (!isNaN(sgOil))  ? sgOil  : 0.84,
      oil_api:  (_oilGravMode === 'api' && !isNaN(oilApi)) ? oilApi : '',
      sg_water: parseFloat(document.getElementById('pvt-sg-water').value) || 1.03,
      wc:       parseFloat(document.getElementById('pvt-wc').value)       || 0.0,
      gor:      parseFloat(document.getElementById('pvt-gor').value)      || '',
      Pb:       parseFloat(document.getElementById('pvt-Pb').value)       || appState.get('Pb') || '',
      P_eval:   parseFloat(document.getElementById('pvt-P-eval').value)   || '',
      T:        parseFloat(document.getElementById('pvt-T').value)        || '',
      T_bh:     parseFloat(document.getElementById('pvt-T').value)        || '',
      P_min:    14.7,
      P_max:    parseFloat(document.getElementById('pvt-P-eval').value) * 1.5 || appState.get('Pr') || 5000,
    };
  }

  function _validate(vals) {
    const msgs = [];
    if (vals.wc < 0 || vals.wc >= 1) msgs.push('Watercut must be in [0, 1)');
    if (vals.sg_gas <= 0)            msgs.push('Gas SG must be > 0');
    return msgs;
  }

  function _updatePhaseBadge(phase) {
    const badge = document.getElementById('phase-badge');
    badge.textContent = phase || '—';
    badge.className = 'phase-badge' +
      (phase === 'Undersaturated' ? ' undersaturated' : phase === 'Two-Phase' ? ' two-phase' : '');
  }

  function _readActiveProps() {
    _activeProps = [];
    document.querySelectorAll('#pvt-prop-toggles input[type=checkbox]:checked').forEach(cb => {
      _activeProps.push(cb.value);
    });
  }

  async function _computeProps(vals) {
    if (!vals.T || !vals.P_eval) return;
    try {
      const data = await API.pvtProperties({ ...vals, P: vals.P_eval });
      _updatePhaseBadge(data.phase);

      document.getElementById('chip-api').textContent     = data.api    != null ? data.api.toFixed(1)  : '—';
      document.getElementById('chip-pb-calc').textContent = data.Pb_calc != null ? data.Pb_calc.toFixed(0) : '—';
      document.getElementById('chip-Bo').textContent      = data.Bo     != null ? data.Bo.toFixed(4)   : '—';
      document.getElementById('chip-muo').textContent     = data.mu_l   != null ? data.mu_l.toFixed(3) : '—';
      document.getElementById('pvt-eval-chips').style.display = 'flex';
    } catch (_) {}
  }

  async function _computeCurve(vals) {
    if (!vals.T) return;
    _readActiveProps();
    if (_activeProps.length === 0) return;

    const placeholder = document.getElementById('pvt-chart-placeholder');
    const canvas      = document.getElementById('chart-pvt');

    try {
      const Pr = parseFloat(appState.get('Pr')) || 5000;
      const data = await API.pvtCurve({ ...vals, P_max: Pr, points: 60 });
      placeholder.style.display = 'none';
      canvas.style.display = '';
      Charts.createPVTChart('chart-pvt', data, _activeProps);
    } catch (err) {
      placeholder.style.display = '';
      placeholder.textContent = `Error: ${err.message}`;
    }
  }

  function _scheduleCompute() {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(() => {
      const vals = _getFormValues();
      const errs = _validate(vals);
      document.getElementById('pvt-validation').textContent = errs.length ? errs[0] : '';
      if (errs.length) return;
      _computeProps(vals);
      _computeCurve(vals);
    }, 280);
  }

  function fillFromState() {
    const s = appState;
    document.getElementById('pvt-sg-gas').value   = s.get('sg_gas')   || 0.65;
    document.getElementById('pvt-sg-oil').value   = s.get('sg_oil')   || 0.84;
    document.getElementById('pvt-oil-api').value  = s.get('oil_api')  || '';
    document.getElementById('pvt-sg-water').value = s.get('sg_water') || 1.03;
    document.getElementById('pvt-wc').value       = s.get('wc')       || 0.0;
    document.getElementById('pvt-gor').value      = s.get('gor')      || '';
    // Pb is inherited from IPR panel
    document.getElementById('pvt-Pb').value       = s.get('Pb')       || '';
    document.getElementById('pvt-T').value        = s.get('T')        || s.get('T_bh') || '';
    document.getElementById('pvt-P-eval').value   = s.get('P_eval')   || s.get('Pr')   || '';

    _scheduleCompute();
  }

  function apply() {
    const vals = _getFormValues();
    const errs = _validate(vals);
    if (errs.length) { window.Toast.show(errs[0], 'error'); return false; }
    appState.commit('pvt', { ...vals, T_bh: vals.T });
    window.Toast.show('PVT data saved.', 'success');
    return true;
  }

  function init() {
    // Input listeners
    document.getElementById('form-pvt').querySelectorAll('input, select').forEach(el => {
      el.addEventListener('input', _scheduleCompute);
    });

    // Property checkbox toggles
    document.querySelectorAll('#pvt-prop-toggles input').forEach(cb => {
      cb.addEventListener('change', _scheduleCompute);
    });

    // Oil gravity toggle
    document.getElementById('toggle-sg').addEventListener('click', () => {
      _oilGravMode = 'sg';
      document.getElementById('toggle-sg').classList.add('active');
      document.getElementById('toggle-api').classList.remove('active');
      document.getElementById('wrap-sg-oil').style.display  = '';
      document.getElementById('wrap-api-oil').style.display = 'none';
      _scheduleCompute();
    });
    document.getElementById('toggle-api').addEventListener('click', () => {
      _oilGravMode = 'api';
      document.getElementById('toggle-api').classList.add('active');
      document.getElementById('toggle-sg').classList.remove('active');
      document.getElementById('wrap-sg-oil').style.display  = 'none';
      document.getElementById('wrap-api-oil').style.display = '';
      _scheduleCompute();
    });

    document.getElementById('btn-pvt-apply').addEventListener('click', () => {
      if (apply()) window.Panels.close('pvt');
    });
  }

  window.PVTPanel = { init, fillFromState, apply };
})();
