/**
 * panels/ipr.js — IPR Data Panel logic
 * Live compute on input, 250ms debounce.
 */

(function () {
  let _debounceTimer = null;
  let _lastData = null;

  function _getFormValues() {
    return {
      ipr_model: document.getElementById('ipr-model').value,
      Pr:        parseFloat(document.getElementById('ipr-Pr').value) || '',
      Pb:        parseFloat(document.getElementById('ipr-Pb').value) || '',
      Qo_test:   parseFloat(document.getElementById('ipr-Qo-test').value) || '',
      Pwf_test:  parseFloat(document.getElementById('ipr-Pwf-test').value) || '',
    };
  }

  function _validate(vals) {
    const msgs = [];
    if (!vals.Pr || vals.Pr <= 0)        msgs.push('Reservoir pressure required (> 0)');
    if (!vals.Qo_test || vals.Qo_test <= 0) msgs.push('Test rate required (> 0)');
    if (!vals.Pwf_test || vals.Pwf_test <= 0) msgs.push('Test Pwf required (> 0)');
    if (vals.Pwf_test >= vals.Pr)        msgs.push('Pwf_test must be less than Pr');
    if (vals.ipr_model === 'composite' && (!vals.Pb || vals.Pb <= 0))
      msgs.push('Bubble point required for Composite model');
    if (vals.Pb && vals.Pb >= vals.Pr)   msgs.push('Pb must be less than Pr');
    return msgs;
  }

  function _showValidation(msgs) {
    const el = document.getElementById('ipr-validation');
    el.textContent = msgs.length ? msgs[0] : '';
  }

  function _updateModelUI(model) {
    const wrapPb   = document.getElementById('wrap-Pb');
    const hint     = document.getElementById('ipr-model-hint');
    const hintMap  = {
      composite: '<strong>Composite:</strong> Darcy (linear) above bubble point, Vogel (quadratic) below.',
      vogel:     '<strong>Vogel:</strong> Fully saturated reservoir. Pb used for shared-state only.',
      darcy:     '<strong>Darcy:</strong> Linear IPR for undersaturated reservoirs.',
    };
    wrapPb.style.opacity = (model === 'vogel') ? '0.4' : '1';
    wrapPb.querySelector('input').disabled = (model === 'vogel');
    hint.innerHTML = hintMap[model] || '';

    // Hide q_bp chip for non-composite
    const chipWrapQbp = document.getElementById('chip-wrap-qbp');
    if (chipWrapQbp) chipWrapQbp.style.display = (model === 'composite') ? '' : 'none';
  }

  async function _compute() {
    const vals = _getFormValues();
    const errs = _validate(vals);
    _showValidation(errs);
    if (errs.length) return;

    const placeholder = document.getElementById('ipr-chart-placeholder');
    const canvas      = document.getElementById('chart-ipr');

    try {
      const data = await API.iprCurve(vals);
      _lastData  = data;

      // Update output chips
      document.getElementById('chip-J').textContent    = (data.J    != null) ? data.J.toFixed(4)   : '—';
      document.getElementById('chip-qbp').textContent  = (data.q_bp != null) ? data.q_bp.toFixed(0) : '—';
      document.getElementById('chip-qmax').textContent = (data.q_max != null) ? data.q_max.toFixed(0) : '—';
      document.getElementById('ipr-output-chips').style.display = 'flex';

      // Show chart
      placeholder.style.display = 'none';
      canvas.style.display = '';
      Charts.createIPRChart('chart-ipr', data);
    } catch (err) {
      _showValidation([`Compute error: ${err.message}`]);
    }
  }

  function _scheduleCompute() {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(_compute, 250);
  }

  function fillFromState() {
    const s = appState;
    document.getElementById('ipr-model').value      = s.get('ipr_model') || 'composite';
    document.getElementById('ipr-Pr').value         = s.get('Pr');
    document.getElementById('ipr-Pb').value         = s.get('Pb');
    document.getElementById('ipr-Qo-test').value    = s.get('Qo_test');
    document.getElementById('ipr-Pwf-test').value   = s.get('Pwf_test');
    _updateModelUI(s.get('ipr_model') || 'composite');
    _showValidation([]);

    // If already complete, auto-compute
    const vals = _getFormValues();
    if (_validate(vals).length === 0) _compute();
  }

  function apply() {
    const vals = _getFormValues();
    const errs = _validate(vals);
    if (errs.length) { _showValidation(errs); window.Toast.show(errs[0], 'error'); return false; }
    appState.commit('ipr', vals);
    window.Toast.show('IPR data saved.', 'success');
    return true;
  }

  function init() {
    const form = document.getElementById('form-ipr');
    form.querySelectorAll('input, select').forEach(el => {
      el.addEventListener('input', _scheduleCompute);
    });

    document.getElementById('ipr-model').addEventListener('change', e => {
      _updateModelUI(e.target.value);
      _scheduleCompute();
    });

    document.getElementById('btn-ipr-apply').addEventListener('click', () => {
      if (apply()) window.Panels.close('ipr');
    });
  }

  window.IPRPanel = { init, fillFromState, apply };
})();
