/**
 * panels/sensitivity.js — Sensitivity Analysis Panel
 * Manages 3 parameter slots, runs sweep, renders overlaid curve families.
 */

(function () {
  let _running = false;

  const SLOT_COLORS = ['#1565C0', '#00897B', '#8E24AA'];

  function _getSlot(n) {
    const active = document.getElementById(`slot-${n}-active`).checked;
    return {
      slot:   n,
      active,
      param:  document.getElementById(`slot-${n}-param`).value,
      min:    parseFloat(document.getElementById(`slot-${n}-min`).value),
      max:    parseFloat(document.getElementById(`slot-${n}-max`).value),
      steps:  parseInt(document.getElementById(`slot-${n}-steps`).value) || 5,
    };
  }

  function _validateSlots(slots) {
    const active = slots.filter(s => s.active);
    if (!active.length) return 'Enable at least one slot.';
    for (const s of active) {
      if (isNaN(s.min) || isNaN(s.max)) return `Slot ${s.slot}: min and max are required.`;
      if (s.min >= s.max)               return `Slot ${s.slot}: min must be < max.`;
      if (s.steps < 2)                  return `Slot ${s.slot}: steps must be ≥ 2.`;
    }
    return null;
  }

  async function _run() {
    if (_running) return;
    const slots = [_getSlot(1), _getSlot(2), _getSlot(3)];
    const errMsg = _validateSlots(slots);
    const validEl = document.getElementById('sens-validation');
    validEl.textContent = errMsg || '';
    if (errMsg) return;

    _running = true;
    document.getElementById('sens-run-label').textContent = 'Running…';
    document.getElementById('sens-spinner').style.display = '';

    const base = appState.snapshot();
    try {
      const result = await API.sensitivityRun({ slots, base });
      if (!result.success) throw new Error(result.error || 'Sensitivity failed');

      // Render chart
      const canvas = document.getElementById('chart-sens');
      const placeholder = document.getElementById('sens-chart-placeholder');
      placeholder.style.display = 'none';
      canvas.style.display = '';
      Charts.createSensChart('chart-sens', result.families);

      // Render results table
      _renderResultsTable(result.families, slots);
    } catch (err) {
      validEl.textContent = `Error: ${err.message}`;
      window.Toast.show(err.message, 'error');
    } finally {
      _running = false;
      document.getElementById('sens-run-label').textContent = 'Run Sensitivity';
      document.getElementById('sens-spinner').style.display = 'none';
    }
  }

  function _renderResultsTable(families, slots) {
    const tbody = document.getElementById('sens-results-tbody');
    const table = document.getElementById('sens-results-table');
    tbody.innerHTML = '';

    families.forEach((family, fi) => {
      const slotNum = slots.filter(s => s.active)[fi]?.slot || (fi + 1);
      const color = SLOT_COLORS[fi % SLOT_COLORS.length];
      family.values.forEach((val, vi) => {
        const pt = family.op_points[vi];
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${color};margin-right:6px;"></span>Slot ${slotNum}</td>
          <td>${family.param}</td>
          <td>${typeof val === 'number' ? val.toFixed(3) : val}</td>
          <td>${pt ? pt.rate.toFixed(1) : '—'}</td>
          <td>${pt ? pt.pwf.toFixed(1)  : '—'}</td>
          <td>${pt ? pt.stability : '—'}</td>
        `;
        tbody.appendChild(tr);
      });
    });
    table.style.display = 'table';
  }

  function _clearResults() {
    const canvas = document.getElementById('chart-sens');
    const placeholder = document.getElementById('sens-chart-placeholder');
    placeholder.style.display = '';
    canvas.style.display = 'none';
    if (canvas._chartInst) { canvas._chartInst.destroy(); canvas._chartInst = null; }
    document.getElementById('sens-results-table').style.display = 'none';
    document.getElementById('sens-results-tbody').innerHTML = '';
  }

  function _updateSlotUI(n) {
    const active = document.getElementById(`slot-${n}-active`).checked;
    const body   = document.querySelector(`#sens-slot-${n} .slot-body`);
    const slot   = document.getElementById(`sens-slot-${n}`);
    body.classList.toggle('slot-body--inactive', !active);
    slot.classList.toggle('slot-active', active);
  }

  // Jump to sensitivity from nodal screen
  function openFromNodal() {
    window.Panels.open('sensitivity');
  }

  function init() {
    document.getElementById('btn-sens-run').addEventListener('click', _run);
    document.getElementById('btn-sens-clear').addEventListener('click', _clearResults);

    [1, 2, 3].forEach(n => {
      document.getElementById(`slot-${n}-active`).addEventListener('change', () => _updateSlotUI(n));
    });
  }

  window.SensPanel = { init, openFromNodal };
})();
