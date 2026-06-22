/**
 * panels/vlp.js — VLP Data Panel logic
 * Heavy computation (pressure traverse per rate step) — triggered on "Run" button.
 * Inherited PVT chips displayed from appState.
 */

(function () {
  let _computing = false;
  let _debounceTimer = null;

  function _getFormValues() {
    return {
      vlp_model:  document.getElementById('vlp-model').value,
      tubing_id:  parseFloat(document.getElementById('vlp-tubing-id').value)  || '',
      tubing_od:  parseFloat(document.getElementById('vlp-tubing-od').value)  || '',
      casing_id:  parseFloat(document.getElementById('vlp-casing-id').value)  || '',
      roughness:  parseFloat(document.getElementById('vlp-roughness').value)  || 0.00015,
      theta:      parseFloat(document.getElementById('vlp-theta').value)      || 0,
      depth:      parseFloat(document.getElementById('vlp-depth').value)      || '',
      dz_step:    parseFloat(document.getElementById('vlp-dz-step').value)    || 50,
      thp:        parseFloat(document.getElementById('vlp-thp').value)        || '',
      T_surface:  parseFloat(document.getElementById('vlp-T-surface').value)  || '',
      T_bh:       parseFloat(document.getElementById('vlp-T-bh').value)       || '',
      q_min:      parseFloat(document.getElementById('vlp-q-min').value)      || 50,
      q_max:      parseFloat(document.getElementById('vlp-q-max').value)      || 5000,
      q_step:     parseFloat(document.getElementById('vlp-q-step').value)     || 100,
    };
  }

  function _validate(vals) {
    const msgs = [];
    if (!vals.tubing_id || vals.tubing_id <= 0)  msgs.push('Tubing ID required (> 0 ft)');
    if (!vals.depth || vals.depth <= 0)           msgs.push('Total depth required (> 0 ft)');
    if (!vals.thp)                                msgs.push('Wellhead pressure (THP) required');
    if (!vals.T_surface)                          msgs.push('Surface temperature required');
    if (!vals.T_bh)                               msgs.push('Bottomhole temperature required');
    if (vals.T_bh && vals.T_surface && vals.T_bh < vals.T_surface)
      msgs.push('BH temperature must be ≥ surface temperature');
    if (vals.tubing_id && vals.casing_id && vals.tubing_id >= vals.casing_id)
      msgs.push('Tubing ID must be less than Casing ID');
    return msgs;
  }

  function _renderInheritedChips() {
    const container = document.getElementById('vlp-inherited-chips');
    const s = appState;
    const chips = [];
    if (s.get('Pr'))     chips.push(['Pr', `${s.get('Pr')} psia`, 'IPR']);
    if (s.get('Pb'))     chips.push(['Pb', `${s.get('Pb')} psia`, 'IPR']);
    if (s.get('gor'))    chips.push(['GOR', `${s.get('gor')} scf/STB`, 'PVT']);
    if (s.get('wc'))     chips.push(['WC', s.get('wc'), 'PVT']);
    if (s.get('sg_gas')) chips.push(['sg_gas', s.get('sg_gas'), 'PVT']);

    container.innerHTML = chips.length
      ? chips.map(([k, v, src]) =>
          `<span class="inherited-chip"><strong>${k}</strong>: ${v} <span style="opacity:.6">← ${src}</span></span>`
        ).join('')
      : '';
  }

  async function _runVLP() {
    if (_computing) return;
    const vals = _getFormValues();
    const pvtVals = {
      sg_gas:   appState.get('sg_gas')   || 0.65,
      sg_oil:   appState.get('sg_oil')   || 0.84,
      oil_api:  appState.get('oil_api')  || '',
      sg_water: appState.get('sg_water') || 1.03,
      wc:       appState.get('wc')       || 0,
      gor:      appState.get('gor')      || 500,
      Pb:       appState.get('Pb')       || 0,
      Pr:       appState.get('Pr')       || 3000,
    };
    const merged = { ...pvtVals, ...vals };

    const errs = _validate(vals);
    document.getElementById('vlp-validation').textContent = errs.length ? errs[0] : '';
    if (errs.length) return;

    _computing = true;
    const loading  = document.getElementById('vlp-chart-loading');
    const canvas   = document.getElementById('chart-vlp');
    const placeholder = document.getElementById('vlp-chart-placeholder');
    placeholder.style.display = 'none';
    loading.style.display = '';

    try {
      const data = await API.vlpCurve(merged);
      canvas.style.display = '';
      loading.style.display = 'none';
      Charts.createVLPChart('chart-vlp', data);
      document.getElementById('vlp-chart-note').textContent =
        `VLP computed at ${data.q.length} rate points · ${appState.get('vlp_model') === 'beggs_brill' ? 'Beggs-Brill' : 'Hagedorn-Brown'}`;
    } catch (err) {
      loading.style.display = 'none';
      placeholder.style.display = '';
      placeholder.textContent = `Error: ${err.message}`;
    } finally {
      _computing = false;
    }
  }

  function _scheduleVLP() {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(_runVLP, 600);
  }

  function fillFromState() {
    const s = appState;
    document.getElementById('vlp-model').value      = s.get('vlp_model')  || 'hagedorn_brown';
    document.getElementById('vlp-tubing-id').value  = s.get('tubing_id')  || '';
    document.getElementById('vlp-tubing-od').value  = s.get('tubing_od')  || '';
    document.getElementById('vlp-casing-id').value  = s.get('casing_id')  || '';
    document.getElementById('vlp-roughness').value  = s.get('roughness')  || 0.00015;
    document.getElementById('vlp-theta').value      = s.get('theta')      || 0;
    document.getElementById('vlp-depth').value      = s.get('depth')      || '';
    document.getElementById('vlp-dz-step').value    = s.get('dz_step')    || 50;
    document.getElementById('vlp-thp').value        = s.get('thp')        || '';
    document.getElementById('vlp-T-surface').value  = s.get('T_surface')  || '';
    document.getElementById('vlp-T-bh').value       = s.get('T_bh')       || '';
    document.getElementById('vlp-q-min').value      = s.get('q_min')      || 50;
    document.getElementById('vlp-q-max').value      = s.get('q_max')      || 5000;
    document.getElementById('vlp-q-step').value     = s.get('q_step')     || 100;

    _renderInheritedChips();
    document.getElementById('vlp-validation').textContent = '';

    const vals = _getFormValues();
    if (_validate(vals).length === 0) _scheduleVLP();
  }

  function apply() {
    const vals = _getFormValues();
    const errs = _validate(vals);
    if (errs.length) { window.Toast.show(errs[0], 'error'); return false; }
    appState.commit('vlp', vals);
    window.Toast.show('VLP data saved.', 'success');
    return true;
  }

  function init() {
    document.getElementById('form-vlp').querySelectorAll('input, select').forEach(el => {
      el.addEventListener('input', _scheduleVLP);
    });

    document.getElementById('btn-vlp-apply').addEventListener('click', () => {
      if (apply()) window.Panels.close('vlp');
    });
  }

  window.VLPPanel = { init, fillFromState, apply };
})();
