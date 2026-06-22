/**
 * charts.js — Chart.js factory helpers
 * All charts use the IPM design system tokens.
 */

const CHART_COLORS = {
  ipr:    '#E53935',   // red for IPR
  vlp:    '#1565C0',   // blue for VLP
  stable:    '#2E7D32',
  unstable:  '#E53935',
  indet:     '#F9A825',
  grid:      '#DDE6F0',
  gridDash:  [4, 4],
  sens: [
    { line: '#1565C0', fill: 'rgba(21,101,192,0.08)' },
    { line: '#00897B', fill: 'rgba(0,137,123,0.08)'  },
    { line: '#8E24AA', fill: 'rgba(142,36,170,0.08)' },
  ],
  pvtPalette: ['#1565C0','#00897B','#E53935','#8E24AA','#F9A825','#3949AB','#00838F','#558B2F'],
};

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 300, easing: 'easeOutQuart' },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#1A2840',
      titleColor: '#90CAF9',
      bodyColor: '#FFFFFF',
      borderColor: '#90CAF9',
      borderWidth: 1,
      padding: 10,
      cornerRadius: 6,
    },
  },
  scales: {
    x: {
      grid: { color: CHART_COLORS.grid, borderDash: CHART_COLORS.gridDash },
      ticks: { color: '#4A6080', font: { family: "'Inter', sans-serif", size: 11 } },
      border: { color: '#DDE6F0' },
    },
    y: {
      grid: { color: CHART_COLORS.grid, borderDash: CHART_COLORS.gridDash },
      ticks: { color: '#4A6080', font: { family: "'Inter', sans-serif", size: 11 } },
      border: { color: '#DDE6F0' },
    },
  },
};

function _deepMerge(target, source) {
  const out = Object.assign({}, target);
  for (const key of Object.keys(source)) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      out[key] = _deepMerge(target[key] || {}, source[key]);
    } else {
      out[key] = source[key];
    }
  }
  return out;
}

/** Build a base chart config merged with custom options */
function _baseConfig(type, datasets, xLabel, yLabel, extra = {}) {
  return _deepMerge({
    type,
    data: { datasets },
    options: {
      ..._deepMerge(CHART_DEFAULTS, {
        scales: {
          x: { title: { display: true, text: xLabel, color: '#4A6080', font: { size: 11, weight: '600', family: "'Inter', sans-serif" } } },
          y: { title: { display: true, text: yLabel, color: '#4A6080', font: { size: 11, weight: '600', family: "'Inter', sans-serif" } } },
        },
      }),
    },
  }, { options: extra });
}

/** ── IPR Chart ─────────────────────────────────────────────────────────── */
function createIPRChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  // Destroy existing
  if (ctx._chartInst) { ctx._chartInst.destroy(); }

  // Filter null
  const valid = data.q.map((q, i) => ({ x: q, y: data.pwf[i] })).filter(p => p.y !== null);

  const datasets = [
    {
      label: 'IPR Curve',
      data: valid,
      borderColor: CHART_COLORS.ipr,
      backgroundColor: 'rgba(229,57,53,0.06)',
      borderWidth: 2.5,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
    },
    {
      label: 'Test Point',
      data: [{ x: data.q_test, y: data.pwf_test }],
      borderColor: '#0D2B55',
      backgroundColor: '#0D2B55',
      pointRadius: 7,
      pointStyle: 'circle',
      pointHoverRadius: 9,
      showLine: false,
    },
  ];

  // Bubble point marker (composite model)
  if (data.q_bp != null && data.Pb != null) {
    datasets.push({
      label: 'Bubble Point',
      data: [{ x: data.q_bp, y: data.Pb }],
      borderColor: CHART_COLORS.vlp,
      backgroundColor: 'white',
      pointRadius: 7,
      pointStyle: 'crossRot',
      pointBorderWidth: 2.5,
      showLine: false,
    });
  }

  const chart = new Chart(ctx, _baseConfig('scatter', datasets,
    'Rate q (STB/day)', 'Pwf (psia)',
    {
      plugins: { tooltip: {
        callbacks: {
          label: ctx => {
            if (ctx.datasetIndex === 1) return `Test: q=${ctx.parsed.x.toFixed(0)} STB/d, Pwf=${ctx.parsed.y.toFixed(0)} psia`;
            if (ctx.datasetIndex === 2) return `Bubble Point: q=${ctx.parsed.x.toFixed(0)}, Pb=${ctx.parsed.y.toFixed(0)} psia`;
            return `q=${ctx.parsed.x.toFixed(0)} STB/d, Pwf=${ctx.parsed.y.toFixed(0)} psia`;
          }
        }
      }},
    }
  ));
  ctx._chartInst = chart;
  return chart;
}

/** ── VLP Chart ─────────────────────────────────────────────────────────── */
function createVLPChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInst) { ctx._chartInst.destroy(); }

  const valid = data.q.map((q, i) => ({ x: q, y: data.pwf[i] })).filter(p => p.y !== null);

  const datasets = [{
    label: 'VLP Curve',
    data: valid,
    borderColor: CHART_COLORS.vlp,
    backgroundColor: 'rgba(21,101,192,0.06)',
    borderWidth: 2.5,
    pointRadius: 0,
    fill: false,
    tension: 0.3,
  }];

  const chart = new Chart(ctx, _baseConfig('scatter', datasets,
    'Rate q (STB/day)', 'Pwf (psia)'));
  ctx._chartInst = chart;
  return chart;
}

/** ── PVT Curve Chart ────────────────────────────────────────────────────── */
function createPVTChart(canvasId, data, activeProps) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInst) { ctx._chartInst.destroy(); }

  const PROP_LABELS = {
    Rs: 'Rs (scf/STB)', Bo: 'Bo (bbl/STB)', Bg: 'Bg (ft³/scf)',
    Bw: 'Bw (bbl/STB)', Z: 'Z-factor',
    mu_o: 'μ oil (cp)', mu_g: 'μ gas (cp)', mu_w: 'μ water (cp)',
    rho_o_ins: 'ρ oil (lbm/ft³)', rho_g: 'ρ gas (lbm/ft³)',
    sigma_o: 'σ oil (dyn/cm)', sigma_w: 'σ water (dyn/cm)',
  };

  const datasets = activeProps.map((prop, i) => {
    if (!data[prop]) return null;
    const pts = data.P.map((p, j) => ({ x: p, y: data[prop][j] })).filter(pt => pt.y !== null);
    return {
      label: PROP_LABELS[prop] || prop,
      data: pts,
      borderColor: CHART_COLORS.pvtPalette[i % CHART_COLORS.pvtPalette.length],
      borderWidth: 2,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
    };
  }).filter(Boolean);

  const chart = new Chart(ctx, _baseConfig('scatter', datasets, 'Pressure (psia)', 'Property Value',
    {
      plugins: {
        legend: { display: true, position: 'bottom', labels: { boxWidth: 16, font: { size: 11, family: "'Inter', sans-serif" }, color: '#4A6080' } },
      },
    }
  ));
  ctx._chartInst = chart;
  return chart;
}

/** ── Nodal Analysis Chart ───────────────────────────────────────────────── */
function createNodalChart(canvasId, iprData, vlpData, operatingPoints) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInst) { ctx._chartInst.destroy(); }

  const iprPts = iprData.q.map((q, i) => ({ x: q, y: iprData.pwf[i] })).filter(p => p.y !== null);
  const vlpPts = vlpData.q.map((q, i) => ({ x: q, y: vlpData.pwf[i] })).filter(p => p.y !== null);

  const datasets = [
    {
      label: 'IPR',
      data: iprPts,
      borderColor: CHART_COLORS.ipr,
      borderWidth: 2.5,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
    },
    {
      label: 'VLP',
      data: vlpPts,
      borderColor: CHART_COLORS.vlp,
      borderWidth: 2.5,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
    },
  ];

  // Operating points
  if (operatingPoints) {
    operatingPoints.forEach(pt => {
      if (!pt) return;
      const color   = pt.stability === 'Stable' ? CHART_COLORS.stable
                    : pt.stability === 'Unstable' ? CHART_COLORS.unstable
                    : CHART_COLORS.indet;
      const style   = pt.stability === 'Stable' ? 'circle'
                    : pt.stability === 'Unstable' ? 'rectRot'
                    : 'triangle';
      datasets.push({
        label: `${pt.stability} Op. Point`,
        data: [{ x: pt.rate, y: pt.pwf }],
        borderColor: color,
        backgroundColor: color,
        pointStyle: style,
        pointRadius: 10,
        pointBorderWidth: 2,
        pointHoverRadius: 13,
        showLine: false,
      });
    });
  }

  const chart = new Chart(ctx, _baseConfig('scatter', datasets,
    'Rate q (STB/day)', 'Pwf (psia)',
    {
      plugins: {
        legend: { display: true, position: 'top', labels: { boxWidth: 16, font: { size: 11, family: "'Inter', sans-serif" }, color: '#4A6080', usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: c => {
              if (c.datasetIndex >= 2) return `${c.dataset.label}: q*=${c.parsed.x.toFixed(1)}, Pwf*=${c.parsed.y.toFixed(1)} psia`;
              return `q=${c.parsed.x.toFixed(0)}, Pwf=${c.parsed.y.toFixed(0)} psia`;
            }
          }
        }
      }
    }
  ));
  ctx._chartInst = chart;
  return chart;
}

/** ── Sensitivity Chart ──────────────────────────────────────────────────── */
function createSensChart(canvasId, families) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInst) { ctx._chartInst.destroy(); }

  const datasets = [];
  families.forEach((family, fi) => {
    const palette = CHART_COLORS.sens[fi % CHART_COLORS.sens.length];
    family.vlp_curves.forEach((curve, vi) => {
      if (!curve) return;
      const alpha = 0.3 + 0.7 * (vi / Math.max(family.vlp_curves.length - 1, 1));
      const pts = curve.q.map((q, i) => ({ x: q, y: curve.pwf[i] })).filter(p => p.y !== null);
      datasets.push({
        label: `${family.param}=${family.values[vi].toFixed(2)}`,
        data: pts,
        borderColor: palette.line,
        borderWidth: 1.8,
        borderOpacity: alpha,
        pointRadius: 0,
        fill: false,
        tension: 0.3,
      });
    });

    // IPR curves in slot 0 only
    if (fi === 0) {
      family.ipr_curves.forEach((curve, vi) => {
        if (!curve) return;
        const pts = curve.q.map((q, i) => ({ x: q, y: curve.pwf[i] })).filter(p => p.y !== null);
        datasets.push({
          label: `IPR (${family.param}=${family.values[vi].toFixed(2)})`,
          data: pts,
          borderColor: CHART_COLORS.ipr,
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.3,
          borderDash: [4, 3],
        });
      });
    }

    // Operating points
    family.op_points.forEach((pt, vi) => {
      if (!pt) return;
      datasets.push({
        data: [{ x: pt.rate, y: pt.pwf }],
        borderColor: palette.line,
        backgroundColor: palette.line,
        pointRadius: 6,
        showLine: false,
      });
    });
  });

  const chart = new Chart(ctx, _baseConfig('scatter', datasets,
    'Rate q (STB/day)', 'Pwf (psia)',
    { plugins: { legend: { display: false } } }
  ));
  ctx._chartInst = chart;
  return chart;
}

window.Charts = { createIPRChart, createVLPChart, createPVTChart, createNodalChart, createSensChart };
