/**
 * nodal.js — Nodal Analysis Screen
 * Multi-pane results: IPR×VLP chart, Pressure Traverse table, PVT @ Op Point.
 */

(function () {
  let _lastResult = null;
  let _computing  = false;

  const PVT_OP_LABELS = {
    M: ['M', 'lbm/STB'], Pb: ['Pb', 'psia'], Rsb: ['Rsb', 'scf/STB'],
    producing_gor: ['Producing GOR', 'scf/STB'], gor: ['Rs (sol. GOR)', 'scf/STB'],
    glr: ['GLR', 'scf/STB liquid'],
    rho_l: ['ρ liquid', 'lbm/ft³'], rho_g: ['ρ gas', 'lbm/ft³'],
    mu_l: ['μ liquid', 'cp'], mu_g: ['μ gas', 'cp'],
    sigma_l: ['σ liquid', 'dyn/cm'],
    Bo: ['Bo', 'bbl/STB'], Bg: ['Bg', 'ft³/scf'], Bw: ['Bw', 'bbl/STB'],
    Pr: ['Pressure node', 'psia'], Tr: ['Temperature node', '°F'], Z: ['Z-factor', '—'],
  };

  async function run() {
    if (_computing) return;

    // Pre-flight check
    if (!appState.isComplete('ipr')) { window.Toast.show('IPR data incomplete — open the IPR panel first.', 'error'); return; }
    if (!appState.isComplete('vlp')) { window.Toast.show('VLP data incomplete — open the VLP panel first.', 'error'); return; }

    _computing = true;
    _setLoading(true);
    _clearResults();

    const data = appState.snapshot();

    try {
      // ── 1. Solve nodal ──────────────────────────────────────────────────
      const nodalResult = await API.nodalSolve(data);
      _lastResult = nodalResult;

      // ── 2. Build IPR & VLP curves for chart ─────────────────────────────
      const [iprData, vlpData] = await Promise.all([
        API.iprCurve(data),
        API.vlpCurve(data),
      ]);

      // ── 3. Render chart ──────────────────────────────────────────────────
      const chartLoading = document.getElementById('nodal-chart-loading');
      const chartEmpty   = document.getElementById('nodal-chart-empty');
      chartLoading.style.display = 'none';
      chartEmpty.style.display   = 'none';

      const allPoints = nodalResult.success ? nodalResult.all_points : [];
      Charts.createNodalChart('chart-nodal', iprData, vlpData, allPoints);

      // ── 4. Update banner ─────────────────────────────────────────────────
      if (nodalResult.success && nodalResult.stable_point) {
        _updateBanner(nodalResult.stable_point);
        document.getElementById('op-failure').style.display = 'none';
        document.getElementById('op-banner').style.display  = '';

        // ── 5. Fetch traverse ────────────────────────────────────────────
        const traverseData = await API.traverse({ ...data, Ql: nodalResult.stable_point.rate });
        _renderTraverseTable(traverseData.rows);

        // ── 6. Fetch PVT @ op ────────────────────────────────────────────
        const pvtOpData = await API.pvtProperties({
          ...data,
          P: nodalResult.stable_point.pwf,
          T: data.T_bh,
        });
        _renderPVTGrid(pvtOpData);
      } else {
        document.getElementById('op-banner').style.display  = 'none';
        document.getElementById('op-failure').style.display = '';
        document.getElementById('failure-reason-text').textContent =
          nodalResult.failure_reason || 'No intersecting operating point was found.';
        _renderTraverseTable([]);
        _renderPVTGrid(null);
      }

      // ── 7. Render legend ─────────────────────────────────────────────────
      _renderLegend(nodalResult);

    } catch (err) {
      window.Toast.show(`Nodal solve error: ${err.message}`, 'error');
      document.getElementById('op-failure').style.display = '';
      document.getElementById('failure-reason-text').textContent = err.message;
    } finally {
      _computing = false;
      _setLoading(false);
    }
  }

  function _setLoading(on) {
    const loading = document.getElementById('nodal-chart-loading');
    const empty   = document.getElementById('nodal-chart-empty');
    if (on) {
      loading.style.display = '';
      empty.style.display   = 'none';
    } else {
      loading.style.display = 'none';
    }
  }

  function _clearResults() {
    document.getElementById('nodal-chart-empty').style.display = '';
    document.getElementById('op-banner').style.display  = 'none';
    document.getElementById('op-failure').style.display = 'none';
    document.getElementById('traverse-empty').style.display  = '';
    document.getElementById('traverse-table').style.display  = 'none';
    document.getElementById('traverse-tbody').innerHTML = '';
    document.getElementById('pvt-op-empty').style.display = '';
    document.getElementById('pvt-op-grid').style.display  = 'none';
    document.getElementById('pvt-op-grid').innerHTML = '';
    document.getElementById('nodal-legend').innerHTML = '';
  }

  function _updateBanner(pt) {
    document.getElementById('op-rate').textContent     = pt.rate     != null ? pt.rate.toFixed(1)              : '—';
    document.getElementById('op-pwf').textContent      = pt.pwf      != null ? pt.pwf.toFixed(1)               : '—';
    document.getElementById('op-drawdown').textContent = pt.drawdown != null ? pt.drawdown.toFixed(1)          : '—';
    document.getElementById('op-pi').textContent       = pt.productivity_index != null
      ? pt.productivity_index.toFixed(4) : '—';

    const badge = document.getElementById('stability-badge');
    badge.textContent = pt.stability;
    badge.className = 'stability-badge ' + (pt.stability || '').toLowerCase();

    const msgEl = document.getElementById('op-message');
    msgEl.textContent = pt.message || '';
  }

  function _renderLegend(nodalResult) {
    const container = document.getElementById('nodal-legend');
    const items = [
      { color: '#E53935', label: 'IPR', type: 'line' },
      { color: '#1565C0', label: 'VLP', type: 'line' },
    ];
    if (nodalResult.success) {
      nodalResult.all_points.forEach(pt => {
        const color = pt.stability === 'Stable' ? '#2E7D32'
                    : pt.stability === 'Unstable' ? '#E53935'
                    : '#F9A825';
        items.push({ color, label: pt.stability, type: 'dot' });
      });
    }
    container.innerHTML = items.map(item => {
      if (item.type === 'line') {
        return `<span class="legend-item"><span class="legend-swatch" style="background:${item.color}"></span>${item.label}</span>`;
      }
      return `<span class="legend-item"><span class="legend-dot" style="border-color:${item.color};background:${item.color}"></span>${item.label} Op. Pt.</span>`;
    }).join('');
  }

  function _renderTraverseTable(rows) {
    const emptyEl = document.getElementById('traverse-empty');
    const tableEl = document.getElementById('traverse-table');
    const tbody   = document.getElementById('traverse-tbody');
    tbody.innerHTML = '';

    if (!rows || rows.length === 0) {
      emptyEl.style.display = '';
      tableEl.style.display = 'none';
      return;
    }
    emptyEl.style.display = 'none';
    tableEl.style.display = 'table';

    rows.forEach(row => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${(row.depth || 0).toFixed(0)}</td>
        <td>${(row.pressure || 0).toFixed(1)}</td>
        <td>${(row.holdup || 0).toFixed(4)}</td>
        <td>${(row.friction_factor || 0).toFixed(5)}</td>
        <td>${(row.hydrostatic_loss || 0).toFixed(5)}</td>
        <td>${(row.frictional_loss  || 0).toFixed(5)}</td>
        <td>${(row.total_gradient   || 0).toFixed(5)}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function _renderPVTGrid(pvtData) {
    const emptyEl = document.getElementById('pvt-op-empty');
    const gridEl  = document.getElementById('pvt-op-grid');
    gridEl.innerHTML = '';

    if (!pvtData) {
      emptyEl.style.display = '';
      gridEl.style.display  = 'none';
      return;
    }
    emptyEl.style.display = 'none';
    gridEl.style.display  = 'grid';

    const SKIP_KEYS = ['success', 'error', 'phase', 'api', 'Pb_calc'];
    Object.entries(PVT_OP_LABELS).forEach(([key, [label, unit]]) => {
      if (SKIP_KEYS.includes(key)) return;
      const val = pvtData[key];
      if (val == null) return;
      const div = document.createElement('div');
      div.className = 'pvt-op-row';
      div.innerHTML = `<span class="pvt-op-key">${label}</span>
        <span><span class="pvt-op-value">${typeof val === 'number' ? val.toFixed(4) : val}</span>
        <span class="pvt-op-unit">${unit}</span></span>`;
      gridEl.appendChild(div);
    });
  }

  async function _downloadCSV() {
    const data = appState.snapshot();
    try {
      const resp = await API.exportCsv(data);
      if (!resp.ok) throw new Error('Export failed');
      const blob = await resp.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = 'ipm_export.csv';
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      window.Toast.show('CSV exported successfully.', 'success');
    } catch (err) {
      window.Toast.show(`Export error: ${err.message}`, 'error');
    }
  }

  function init() {
    // Tab switching
    document.querySelectorAll('.pane-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        document.querySelectorAll('.pane-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === target));
        document.querySelectorAll('.pane-content').forEach(c => c.classList.toggle('active', c.id === `pane-${target}`));
      });
    });

    // Re-run
    document.getElementById('btn-nodal-rerun').addEventListener('click', run);

    // Back to home
    document.getElementById('btn-nodal-back').addEventListener('click', () => {
      window.Router.show('home');
    });

    // To sensitivity
    document.getElementById('btn-nodal-sensitivity').addEventListener('click', () => {
      window.Router.show('home');
      setTimeout(() => window.Panels.open('sensitivity'), 100);
    });

    // Export dropdown
    const btnExport = document.getElementById('btn-export');
    const menu      = document.getElementById('export-menu');
    btnExport.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.toggle('open');
    });
    document.addEventListener('click', () => menu.classList.remove('open'));
    menu.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', () => {
        menu.classList.remove('open');
        _downloadCSV();
      });
    });
  }

  window.NodalScreen = { init, run };
})();
