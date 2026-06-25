# Product Requirements Document
## Integrated Production Modelling (IPM) App — Nodal Analysis Suite
**Version:** 2.0 (UI Redesign) | **Status:** Draft for Build | **Owner:** Production Engineering Tools

---

## 1. Purpose & Background

The current app is a working PyQt6 desktop tool that performs **IPR × VLP nodal analysis** for oil wells. The calculation engine (4 Python modules: `ipr.py`, `pvt.py`, `vlp.py`, `solver_other.py`) is correct and must be **fully retained** — this PRD is scoped to a **ground-up UI/UX redesign**, re-architected as a set of focused, button-launched workspaces instead of one dense sidebar.

The new app must feel like a modern engineering SaaS product (think Linear, Vercel, or a well-designed analytics dashboard) — **not** a legacy desktop form. White-and-blue, sleek, fast, with a strong sense of state continuity: **the user should never have to re-enter a value they've already given.**

### 1.1 What must be retained (no feature regression)
| Capability | Source module | Notes |
|---|---|---|
| Composite Darcy-Vogel IPR | `ipr.composite_ipr` | Default IPR model |
| Pure Vogel IPR | `ipr.vogel_ipr` | Saturated reservoirs |
| Pure Darcy IPR | `ipr.darcy_ipr` | Linear, undersaturated |
| Full Black-Oil PVT engine | `pvt.BlackOilPVT` | Standing, Beggs-Robinson, Lee-Gonzalez-Eakin, Dranchuk-Abou-Kassem, Vasquez-Beggs, Baker-Swerdloff correlations |
| Hagedorn-Brown VLP | `vlp.HagedornBrown` | With Griffith-Wallis bubble-flow detection |
| Beggs-Brill VLP | `vlp.Beggs_Brill` | Flow-regime-aware, smoothed holdup transitions |
| Nodal solver (root finding, stability classification) | `solver_other.find_operating_points` | Returns stable/unstable/all intersections |
| Pressure traverse (depth vs. P, holdup, friction, gradients) | `vlp.calculate_pressure_traverse` | Euler integration |
| PVT properties evaluated at the operating point | `pvt.fluid_properties_dict` | |
| CSV export (operating point, PVT@op, IPR curve, VLP curve, traverse table) | existing `export_csv` logic | |
| Sensitivity sweep (1 parameter today) | existing `_run_sens` | **Upgrade to 3 parameters in this redesign** |
| VLP calibration (holdup/friction factor regression) | `calibration.calibrate.VLPCalibrator`, `apply_calibration_factors` | Already implemented and wired into `build_vlp` in `app.py` — **retain**, extend with CSV upload (§6.10) |

### 1.2 New capability added in this revision

Two new analysis modules are added on top of the existing engine: **Gas Lift Analysis** and a **Choke Panel** for optimum choke sizing. Neither exists in the current codebase — both require **new, additive files**, not changes to existing physics:

- **`core/choke.py`** — new module containing the choke-correlation functions (§6.9, §9.1).
- **`gas_lift/gl.py`** (new package `gas_lift/` with `gas_lift/__init__.py`) — new module containing the gas-lift performance/optimization functions and the VLP-wrapping helper (§6.8, §9.1).

`app.py`'s `_open_gaslift` currently opens a `ComingSoonDialog` placeholder — this is replaced by a real `GasLiftPanel` (mirroring the structure of the existing `CalibrationPanel`). The existing `CalibrationPanel` itself is retained and extended, not replaced (§6.10).

---

## 2. Goals

1. **Modular workspace model** — replace the single dense sidebar with distinct buttons/cards that open dedicated input+result panels for IPR, PVT, VLP, and Sensitivity, each with its own input form, instant calculated outputs, and curve(s).
2. **One source of truth for inputs** — every value entered in any panel is saved to a shared app state and pre-fills every other panel/screen that needs it. No retyping reservoir pressure, depth, etc.
3. **Nodal Analysis as the hero workflow** — a dedicated full-screen result view showing the IPR×VLP intersection, with **synchronized side-by-side (parallel) windows**: main chart, pressure traverse table, PVT-at-operating-point panel — plus CSV export.
4. **3-way sensitivity analysis** — let the user vary up to **3 properties simultaneously** (independently or combined) and visualize the impact on the operating point.
5. **Calibration, extended** — the existing `CalibrationPanel` (manual pressure-survey table, holdup/friction factor regression) gains **CSV upload** of measured well data, and its sticky-by-default behavior is made explicit: once factors are applied, every VLP/Nodal computation uses them until the user resets.
6. **Visual identity** — clean white canvas, confident blue accent system, generous whitespace, subtle motion, modern data-viz styling.
7. **Gas Lift Analysis, live, with sticky design** — given the well's existing IPR/PVT/VLP data, let the user find the optimum continuous gas-lift injection depth, rate, and GLR (three dedicated sub-views) — and once a design is applied, **every VLP curve in the app uses it by default** until the user explicitly resets gas lift on that panel.
8. **Choke Panel, live** — let the user size (or rate-check) a surface choke as an extra outflow node, tying wellhead choke performance into the existing nodal framework.

## 3. Non-Goals (this release)
- Calibration's underlying regression method (`VLPCalibrator`) is unchanged — only the data-input path (CSV upload) and the sticky/reset UX are in scope.
- Intermittent gas lift / valve unloading-string design — only **continuous gas lift performance** is in scope (see §6.8).
- Multi-well / project management (saving multiple wells) — noted as a future opportunity in §10, not required now.
- User accounts/auth.

---

## 4. Users & Key Use Cases

**Primary persona:** Production/Reservoir Engineer doing well performance diagnostics.

**Core jobs-to-be-done:**
- "I want to quickly check if my well's IPR model and assumptions are reasonable, before running anything else."
- "I want to model fluid behavior (PVT) once and trust it's used everywhere downstream."
- "I want to define the wellbore/VLP setup and see the lift curve."
- "I want to overlay IPR and VLP and find where the well will actually operate — and trust the diagnosis if it's unstable or won't flow."
- "I want to know how sensitive my operating rate is to GOR, water cut, or THP — together, not one at a time."
- "I want to grab the underlying numbers (traverse table, PVT@op, curves) without re-running the model in Excel."

---

## 5. Information Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  TOP NAV BAR (app name, well/project name, global status pill)  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│                     HOME / LAUNCHPAD SCREEN                      │
│                                                                   │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│   │ IPR Data│ │ PVT Data│ │ VLP Data│ │Sensitiv.│ │  Choke   │  │
│   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────┘  │
│                                                                   │
│   ┌───────────────────┐ ┌───────────┐ ┌─────────────────────┐   │
│   │  ▶ NODAL ANALYSIS  │ │Calibration│ │   Gas Lift Analysis │   │
│   │   (primary CTA)    │ │           │ │                     │   │
│   └───────────────────┘ └───────────┘ └─────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

Each of **IPR Data**, **PVT Data**, **VLP Data**, **Sensitivity**, **Choke**, **Gas Lift Analysis**, **Calibration** opens as its own **panel/window** (modal-style overlay or routed full view — see §9 for implementation options) containing:
- Left: input form (pre-filled from shared state where applicable)
- Right: calculated outputs + curve(s)
- A persistent "Save & Close" / "Apply" action that commits to shared state

**Nodal Analysis** opens a dedicated multi-pane results screen (§7).

A **status strip** is always visible at the bottom (or top, see §6.6) summarizing data completeness ("IPR ✓ · PVT ✓ · VLP — missing tubing ID") so the user always knows what's left before Nodal Analysis can run.

---

## 6. Screen-by-Screen Requirements

### 6.0 Shared App State (read this before the rest of §6)

A single global state object (`appState`) holds **every input field across all panels**, keyed by canonical parameter name (see Data Dictionary, §11). Rules:

- Any panel's "Apply"/"Save" commits its fields into `appState`.
- Opening any panel **pre-fills** its form from `appState` — the user is never shown an empty field if a value already exists.
- Defaults (sensible engineering defaults, §11) are used only when `appState` has no value yet.
- `appState` persists for the lifetime of the session (and should be persisted to local storage / a session file so a refresh doesn't lose work — implementation detail, not a hard requirement).
- A visible "Reset all inputs" action (with confirmation) clears `appState`.

---

### 6.1 Home / Launchpad

**Purpose:** single entry point; visual map of the workflow; surfaces data-readiness.

**Requirements:**
- 7 buttons/cards as shown in §5's IA diagram (IPR, PVT, VLP, Sensitivity, Choke, Gas Lift Analysis, Calibration are all **fully active**), each with: icon, title, 1-line description, and a small **completion badge** (e.g., a filled blue dot once that panel's required fields are saved, gray ring if not started).
- "Nodal Analysis" card is visually the primary CTA (larger, filled blue, slightly elevated) — it's the destination the other data panels feed into.
- "Gas Lift Analysis" and "Calibration" cards additionally show a small **"Active" indicator** (e.g., a filled lightning/checkmark glyph) whenever the user has applied a gas-lift design or calibration factors that are currently affecting VLP results elsewhere in the app — this is the visual cue that "something is silently modifying my VLP curves right now," which both features introduce (§6.8, §6.10).
- Optional: a thin "readiness" progress bar across the top (IPR → PVT → VLP → Ready for Nodal Analysis).

---

### 6.2 IPR Data Panel

**Inputs:**
| Field | Param | Unit | Notes |
|---|---|---|---|
| IPR Model | `ipr_model` | — | Dropdown: Composite (Darcy-Vogel) / Vogel / Darcy |
| Reservoir Pressure | `Pr` | psia | |
| Bubble Point Pressure | `Pb` | psia | Hidden/disabled when model = Vogel (Vogel doesn't use Pb directly, but field stays in shared state for PVT reuse) |
| Test Rate | `Qo_test` | STB/day | |
| Test Pwf | `Pwf_test` | psia | |

**Outputs (instant, recalculated on any input change):**
- Productivity Index, **J** (STB/day/psi)
- Flow rate at bubble point, **q_bp** (STB/day) — composite model only
- Absolute Open Flow, **q_max** (STB/day, AOF)
- **IPR curve**: Pwf (y) vs. q (x), 0 → q_max, styled per §8. Test point marked distinctly; bubble-point transition marked (composite model).
- A small inline "what does this mean" tooltip/legend explaining Darcy vs. Vogel regions when composite is selected.

**Validation:** `Pwf_test < Pr`; `Pb` required & sane only when relevant to selected model; numeric, non-negative.

**Engine mapping:** `ipr.composite_ipr` / `ipr.vogel_ipr` / `ipr.darcy_ipr`, methods `calculate_q`, `calculate_Pwf`.

---

### 6.3 PVT Data Panel

**Purpose:** fully optional, comprehensive fluid-property input — if the user supplies values, they are used everywhere downstream (VLP, Nodal); if left blank, sensible defaults apply.

**Inputs — Fluid Composition:**
| Field | Param | Unit | Default |
|---|---|---|---|
| Gas Specific Gravity | `sg_gas` | (air=1) | 0.65 |
| Oil Specific Gravity *or* API Gravity (toggle) | `sg_oil` / `oil_api` | (water=1) / °API | 0.84 / — |
| Water Specific Gravity | `sg_water` | (water=1) | 1.03 |
| Watercut | `wc` | fraction (0–1) | 0.0 |
| Producing GOR | `gor` | scf/STB | from IPR/test data if available |
| Bubble Point Pressure | `Pb` | psia | linked from IPR panel |

**Inputs — Evaluation Node (for the standalone PVT curve view):**
| Field | Param | Unit |
|---|---|---|
| Pressure range (min/max) | `P_min_pvt`, `P_max_pvt` | psia |
| Temperature | `T_pvt` | °F |

**Outputs:**
- A property table & curve set, computed across the pressure range, for: Rs (solution GOR), Bo, Bg, Bw, Z-factor, oil/gas/water viscosity, oil/water/gas density, oil & water surface tension. Each as a toggleable curve (checkboxes) over a shared pressure x-axis, tabbed or multi-select chart.
- Calculated Bubble Point (if not user-overridden) and API gravity displayed as derived read-only chips.

**Validation:** watercut in [0,1); all specific gravities > 0; if both sg_oil and oil_api provided, oil_api takes precedence (per engine logic) — show a note when this override happens.

**Engine mapping:** `pvt.BlackOilPVT.fluid_properties_dict`, plus the individual `calc_*` methods for the curve sweep.

**Standout feature:** a live "Phase diagnosis" badge — automatically tells the user whether the evaluation node is *above bubble point (undersaturated)* or *below (two-phase)*, updating as they drag the pressure slider.

---

### 6.4 VLP Data Panel

**Inputs — Wellbore Geometry:**
| Field | Param | Unit | Default |
|---|---|---|---|
| VLP Correlation | `vlp_model` | — | Hagedorn-Brown / Beggs-Brill |
| Tubing ID | `tubing_id` | ft | |
| Tubing OD | `tubing_od` | ft | |
| Casing ID | `casing_id` | ft | |
| Roughness | `roughness` | ft | 0.00015 |
| Deviation Angle | `theta` | ° from vertical | 0 |
| Total Depth | `depth` | ft | |
| Depth Step | `dz_step` | ft | 50 |

**Inputs — Surface/Thermal:**
| Field | Param | Unit |
|---|---|---|
| Wellhead (Tubing Head) Pressure | `thp` | psia |
| Surface Temperature | `T_surface` | °F |
| Bottomhole Temperature | `T_bh` | °F |

**Inputs — Rate Sweep (for the standalone VLP curve):**
| Field | Param | Unit | Default |
|---|---|---|---|
| Min Rate | `q_min` | STB/day | 50 |
| Max Rate | `q_max_sweep` | STB/day | 5000 |
| Rate Step | `q_step` | STB/day | 100 |

**Outputs:**
- **VLP curve**: Pwf (y) vs. q (x) across the rate sweep — computed via full pressure-traverse integration at each rate (not the simplified linear-gradient shortcut), per current engine behavior.
- A flow-regime indicator (bubble / slug / transition / mist for Beggs-Brill; bubble/non-bubble for Hagedorn-Brown) shown for the currently-hovered point on the curve.

**Validation:** `tubing_id < casing_id`; `T_bh ≥ T_surface`; all geometry > 0; depth step ≤ depth.

**Engine mapping:** `vlp.HagedornBrown` / `vlp.Beggs_Brill`, `calculate_pressure_traverse`. Fluid properties for VLP are built from the PVT panel's saved values (no duplicate PVT entry — pulled from `appState`).

**Sticky modifiers (new in this revision):** the VLP object returned by `build_vlp(state, ...)` is wrapped, in order, by (1) `apply_calibration_factors` if calibration factors are active (already implemented), then (2) the new gas-lift wrapper from `gas_lift.gl` if a gas-lift design has been applied (§6.8, §9.1). The VLP curve shown in this panel **always reflects the currently-active calibration and gas-lift state** — a small inline note ("Calibrated · Gas-lift applied") appears above the chart whenever either is active, with a one-click link to the owning panel to review/reset it.

---

### 6.5 Sensitivity Panel

**Purpose:** vary up to **3** parameters and see the effect on IPR/VLP curves and the resulting operating point — single biggest functional upgrade vs. the legacy 1-parameter sweep.

**Requirements:**
- Three "Sensitivity Slot" cards (Slot 1 / 2 / 3), each independently optional:
  - Parameter picker (dropdown spanning IPR, PVT, and VLP parameters — e.g., Pr, GOR, watercut, THP, tubing ID, roughness, Pb)
  - Min / Max / Steps (or explicit value list)
  - A small color swatch indicating the color ramp used for that slot's curve family
- **Run modes:**
  - *Independent sweep*: each active slot is swept on its own (current parameter varies, all others held at their `appState` value) — produces one curve family per slot, all rendered on the same chart with distinct color ramps + a combined legend.
  - *Combined grid* (stretch capability): if 2–3 slots active, optionally run the Cartesian product (e.g., 3×3 = 9 combinations) and show a small multiple / heatmap of resulting operating rate. Flag this as a secondary mode (toggle "Combined matrix"), not required for MVP parity but listed as a standout feature (§10).
- Output: overlaid IPR and/or VLP curve families (color-ramped per slot, matching legacy `SENS_PALETTE` blue→teal styling, extended per active slot), plus a small results table: each swept value → resulting operating rate/Pwf where solvable.
- "Clear sensitivity" action removes all overlays without resetting base curves.

**Validation:** at least 1 slot must be active to run; min < max; steps ≥ 2; max 3 active slots (UI should simply not offer a 4th slot).

**Engine mapping:** repeated calls into `_build_ipr` / `_build_pvt_vlp` / `find_operating_points` with the swept parameter substituted into a cloned `appState` snapshot per run — same underlying engine, just looped.

---

### 6.6 Nodal Analysis Screen (Hero Workflow)

**Entry condition:** enabled once IPR, PVT, and VLP panels each have the minimum required fields saved (status strip on Home reflects this); if incomplete, clicking the button routes the user to the first incomplete panel with a contextual message rather than failing silently.

**Layout — "parallel windows" requirement, interpreted as a multi-pane workspace:**

```
┌──────────────────────────────────────────────────────────────────┐
│  Operating Point banner: q* | Pwf* | Stability | Drawdown | PI   │
├───────────────────────────────┬──────────────────────────────────┤
│                                │  Pane B (tabbed):                │
│   Pane A: Main Chart           │   [Pressure Traverse Table]      │
│   IPR × VLP curves,            │   [PVT @ Operating Point]        │
│   intersection marker(s),      │                                  │
│   mini traverse map overlay    │   (each tab independently         │
│   (signature feature, retain)  │    scrollable; both update live   │
│                                │    when the operating point        │
│                                │    recomputes)                    │
├───────────────────────────────┴──────────────────────────────────┤
│  [Export CSV ▾]   [Re-run]   [Open in Sensitivity →]              │
└──────────────────────────────────────────────────────────────────┘
```

**Pane A — Main Chart:**
- IPR curve, VLP curve, operating point marker(s) — including secondary/unstable intersections if present, each labeled with stability classification (Stable / Unstable / Indeterminate) using distinct marker styles (not just color, for accessibility).
- Floating mini pressure-traverse map (existing signature feature — retain, modernize styling).
- Hover tooltip showing q/Pwf at cursor.
- If no operating point is found: render the message from `NodalResult.failure_reason` prominently (not just a toast) with a suggested next action (e.g., "VLP exceeds IPR everywhere — try reducing THP or increasing tubing ID").

**Pane B — Tab 1: Pressure Traverse Table:**
- Full depth-indexed table at the operating rate: Depth, Pressure, Holdup, Friction Factor, Hydrostatic Loss, Frictional Loss, Total Gradient (matches `calculate_pressure_traverse` output / current CSV export columns).
- Sortable columns, sticky header, virtualized scroll for long tables.

**Pane B — Tab 2: PVT at Operating Point:**
- All fields from `fluid_properties_dict` evaluated at (Pwf*, T_bh): Rs, Bo, Bg, Bw, Z, densities, viscosities, surface tensions, GLR, etc. — presented as a clean labeled grid, not a raw dict dump.

**Export:**
- Single "Export CSV ▾" button with sub-options matching legacy sections: Operating Point(s), PVT @ Operating Point, IPR Curve, VLP Curve, Pressure Traverse — and an "Export All" that bundles them exactly as the current `export_csv` does (sectioned CSV).

**All operating-point math runs via `solver_other.find_operating_points`; no new solver logic required.**

---

### 6.8 Gas Lift Analysis Panel

**Purpose:** for a well already defined via IPR/PVT/VLP, find the optimum **continuous gas-lift design** — depth, rate, and GLR — and, once the user is satisfied, **apply it as the active design** so every VLP-driven view in the app (VLP Panel, Sensitivity, Nodal Analysis) reflects gas-lifted performance by default, exactly the way calibration factors already work today.

**Concept:** injecting gas at a point in the tubing lightens the fluid column **above** the injection point (lower hydrostatic gradient → lower Pwf required for a given rate), while the segment **below** the injection point still flows at the natural producing GOR. Sweeping injection rate, depth, or GLR and re-solving the nodal intersection at each step produces performance curves that rise steeply then flatten (diminishing returns) as more gas just adds friction without much more lift.

**Panel structure — multiple sub-windows (tabs), mirroring the Sensitivity panel's slot pattern:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Gas Lift Analysis                         [Active: Off ▾]      │
├─────────────────────────────────────────────────────────────────┤
│  [ Optimum Depth ] [ Optimum Rate ] [ Optimum GLR ] [ Summary ]  │
├─────────────────────────────────────────────────────────────────┤
│   (selected tab's input form)   │   (selected tab's chart)       │
│                                  │                                │
├─────────────────────────────────────────────────────────────────┤
│  [ Apply Design ]            [ Reset Gas Lift ]                  │
└─────────────────────────────────────────────────────────────────┘
```

**Tab 1 — Optimum Injection Depth:**
| Field | Param | Unit | Notes |
|---|---|---|---|
| Candidate Depths (min/max/step) | `gl_depth_min`, `gl_depth_max`, `gl_depth_step` | ft | Swept against `depth` |
| Injection Gas Rate (held constant for this sweep) | `gl_rate_for_depth_sweep` | Mscf/day | |
*Output:* liquid rate vs. injection depth, with the depth that maximizes rate (or minimizes required injection pressure) marked.

**Tab 2 — Optimum Injection Rate:**
| Field | Param | Unit | Notes |
|---|---|---|---|
| Injection Depth (held constant, pre-filled from Tab 1's pick if set) | `gl_inj_depth` | ft | Must be ≤ `depth` |
| Injection Gas Specific Gravity | `gl_sg_gas` | (air=1) | Defaults to `sg_gas` |
| Min / Max / Step Injection Gas Rate | `gl_q_min`, `gl_q_max`, `gl_q_step` | Mscf/day | Sweep range for the Gas Lift Performance Curve (GLPC) |
| Available Injection Pressure (surface/casing) | `gl_p_inj` | psia | Feasibility check |
| Compressor / Lift-Gas Capacity (optional) | `gl_q_available` | Mscf/day | Hard ceiling on the chart, if set |
| Economic slope threshold (optional) | `gl_econ_slope` | STB/day per Mscf/day | Default 0.5–1.0; auto-marks the optimum |
*Output:* the GLPC — liquid rate vs. injection gas rate — with the diminishing-returns optimum, the no-lift baseline, and the injection-feasibility shading described below.

**Tab 3 — Optimum GLR:**
| Field | Param | Unit | Notes |
|---|---|---|---|
| Target/Candidate total GLR range (min/max/step) | `gl_glr_min`, `gl_glr_max`, `gl_glr_step` | scf/STB | Total (formation + injected) GLR above the injection point |
*Output:* liquid rate vs. total GLR, useful when the engineer thinks in terms of GLR (common field convention) rather than raw injection rate — same underlying solve, different x-axis.

**Tab 4 — Summary:** consolidates the best pick from Tabs 1–3 into one design (`gl_opt_depth`, `gl_opt_rate`, implied `gl_opt_glr`), shows the resulting `q*`/`Pwf*`/% improvement vs. no-lift, and is where **Apply Design** is actually committed.

All other required inputs (`Pr`, `Pb`, IPR model, PVT composition, tubing geometry, `thp`, temperatures) are **inherited from `appState`** across all four tabs — no re-entry.

**Outputs common to Tabs 1–3:**
- **Injection feasibility flag** — at each swept value, checks that `gl_p_inj` (minus the static gas column to depth) exceeds the local flowing tubing pressure at the injection depth; values that fail this check are shown grayed-out/dashed with a tooltip explaining insufficient injection pressure.
- **No-lift baseline** shown as a reference line/point (natural-flow operating rate) so the lift benefit is visually obvious.

**Sticky-by-default behavior (new in this revision — mirrors Calibration exactly):**
- Clicking **"Apply Design"** on the Summary tab sets `gl_applied = True` and stores `gl_opt_depth`, `gl_opt_rate`, `gl_sg_gas` in `appState`. From that point on, `build_vlp` wraps the VLP object with the gas-lift injection (via `gas_lift.gl`) **unconditionally**, exactly as it already does for calibration factors — the VLP Panel, Sensitivity Panel, and Nodal Analysis all silently pick up gas-lifted performance with zero extra steps.
- A persistent **"Reset Gas Lift"** button (always visible on the panel, not buried in a tab) sets `gl_applied = False` and clears the three stored values, immediately reverting all VLP curves app-wide to natural (no-lift) flow.
- The Home screen and VLP Panel both show an **"Active" indicator** whenever `gl_applied = True`, per §6.1, so the user is never surprised by a curve that's quietly using gas lift.
- The dropdown in the panel's title bar ("Active: On/Off") is a read-only reflection of `gl_applied`, with a link to the Summary tab — there is intentionally **no quick-toggle** here; resetting always goes through the explicit "Reset Gas Lift" action so the user can't accidentally discard a design.

**Validation:** `gl_inj_depth ≤ depth` on every tab; all min < max; warn (not block) if `gl_q_available` is below the computed optimum, showing the curve truncated at the actual ceiling with a note.

**Engine mapping (new, additive, in `gas_lift/gl.py`):**
- `compute_glpc(state, sweep_param, sweep_values) -> dict` — the shared sweep engine behind all three tabs; for each swept value (depth, rate, or GLR) it builds the VLP/IPR pair via the existing `build_vlp`/`build_ipr` helpers, injects gas via the depth/rate it's holding, and calls `find_operating_points` once per sweep point — exactly how Sensitivity already loops parameter values today.
- `apply_gas_lift_design(vlp_obj, injection_depth, injection_rate, injection_sg) -> wrapped_vlp_obj` — a wrapper function in the same style as `calibration.calibrate.apply_calibration_factors`, intercepting `calculate_pressure_traverse` so that **below** `injection_depth` the natural `glr` is used, and **at/above** it an augmented GLR (natural + injected/liquid-rate) is substituted into the existing `fluid_properties_dict` call at each depth step. **No change to the holdup/friction correlations themselves** — both `HagedornBrown` and `Beggs_Brill` already key off `self.fp["glr"]`.
- `build_vlp` in `app.py` is extended to apply this wrapper **after** the calibration wrapper (order: raw VLP → calibration → gas lift), whenever `state.gl_applied` is `True`.

---

### 6.9 Choke Panel — Optimum Choke Sizing

**Purpose:** model the surface (wellhead) choke as the production system's final outflow restriction, and either (a) predict rate/pressure for a given bean size, or (b) recommend the **optimum bean size** for a target plateau rate or downstream pressure constraint.

**Inputs:**
| Field | Param | Unit | Notes |
|---|---|---|---|
| Choke Correlation | `choke_model` | — | Gilbert / Ros / Achong / Baxendell (critical-flow constant-set) or Sachdeva (critical + subcritical) |
| Upstream (Wellhead) Pressure | inherited `thp` | psia | Pulled from `appState`/VLP, editable override |
| Downstream Pressure | `choke_p_down` | psia | Flowline/manifold/separator pressure |
| Bean Size | `choke_size_64` | 1/64 in | Single value for "rate-check" mode |
| Candidate Bean Sizes | `choke_sizes_list` | 1/64 in | Multi-select (e.g., 16,20,24,28,32,36,40,48,64) for "sizing" mode |
| GLR at wellhead | inherited `glr`/`gor` & `wc` | scf/STB | From PVT/VLP, editable override |
| Target Plateau Rate (sizing mode) | `choke_target_q` | STB/day | Used to recommend a bean size |
| Erosional Velocity Limit (optional, API RP 14E) | `choke_c_factor` | — | Default c = 100 (standard service) / 125 (limited corrosive) |

**Modes:**
1. **Rate-Check** — given a single bean size + upstream pressure, compute the resulting liquid rate and/or downstream pressure (whichever isn't fixed), and the flow regime (critical vs. subcritical).
2. **Sizing (recommend optimum)** — given a target plateau rate (or a target downstream/flowline pressure), sweep the candidate bean-size list and recommend the **smallest bean size that meets the target without violating the erosional velocity limit**, with the full set of candidate curves shown for comparison.

**Outputs:**
- **Choke performance curve(s)**: wellhead pressure (or rate) vs. bean size, one curve per candidate size, with the operating point for the active rate/pressure combination marked.
- **Flow regime badge**: Critical (sonic, choke-controlled) vs. Subcritical (downstream-pressure-sensitive), per the selected correlation's critical pressure-ratio check.
- **Erosional velocity check**: actual fluid velocity through the bean vs. API RP 14E erosional limit, shown as a pass/fail badge — a candidate size that fails is flagged red even if it otherwise meets the rate target.
- **Recommended bean size** (sizing mode): highlighted in the candidate list/chart with a short rationale ("32/64\" — smallest size meeting 2,200 STB/day target while staying below erosional limit").
- **Downstream temperature estimate (Joule-Thomson cooling)** — optional standout: flags potential hydrate-formation risk downstream of the choke if the estimated temperature drop pushes below a hydrate-formation temperature threshold.

**Interaction with Nodal Analysis:** the Choke Panel can optionally **replace the fixed `thp`** in the VLP/Nodal solve with a choke-derived outflow relationship (Pwh as a function of rate, for the selected bean size) — i.e., the choke becomes an additional outflow node. This is exposed as a toggle ("Use choke as outflow boundary") on the Nodal Analysis screen once a bean size has been chosen here; default behavior (toggle off) keeps today's fixed-THP nodal solve unchanged.

**Validation:** `choke_p_down < thp` for critical flow assumptions to hold (flag, don't block, if violated — subcritical correlations handle it); bean size > 0; candidate list non-empty in sizing mode.

**Engine mapping (new, additive, in `core/choke.py`):** a new lightweight module implementing the selected correlation(s) as pure functions of (Pwh, Pdown, bean size, rate, GLR) — does not touch `core/ipr.py`, `core/pvt.py`, `core/vlp.py`, or `core/solver_other.py`. Fluid properties (density, GLR) for the velocity/erosional check are pulled from the existing `pvt.fluid_properties_dict` at wellhead conditions.

---

### 6.10 Calibration Panel (extended)

The `CalibrationPanel` already exists in `app.py` — manual pressure-survey table entry, `VLPCalibrator` regression for holdup/friction factors, Apply/Clear actions, and sticky application via `apply_calibration_factors` inside `build_vlp`. This revision adds one new input path and makes the sticky/reset behavior explicit and visible.

**New — CSV Upload of Well Data:**
- An **"Upload CSV"** button next to the existing manual table, accepting a measured pressure-survey file (columns: depth (ft), pressure (psia) — header row required, extra columns ignored with a warning).
- On upload, the parsed rows **populate the same table** used for manual entry (rows are replaced, not appended, with a confirmation if the table already has manual data) — so the regression (`VLPCalibrator`) and the rest of the panel are completely unchanged downstream of the table.
- Validation: at least 2 valid (depth, pressure) rows, depths within `[0, depth]`, ascending depth order (auto-sorted if not); malformed rows are skipped with a row-by-row warning list rather than failing the whole upload.
- The user can still hand-edit rows after a CSV upload (add/remove row tools are retained) before clicking **Run Calibration**.

**Sticky-by-default behavior (already implemented — documented explicitly here for parity with Gas Lift, §6.8):**
- Clicking **"Apply Factors"** stores `calib_holdup_factor`/`calib_friction_factor` in `appState` and they are used **unconditionally** in `build_vlp` from then on — VLP Panel, Sensitivity, and Nodal Analysis all reflect calibrated performance with zero extra steps.
- The existing **"Clear Calibration"** button resets both factors to `1.0`, immediately reverting all VLP curves app-wide to uncalibrated performance.
- Per §6.1, the Home screen and VLP Panel show an **"Active" indicator** whenever either factor ≠ `1.0`, with a link back to this panel.

---

## 7. Cross-Cutting Functional Requirements

- **No repeated input:** any field that exists in more than one panel (e.g., `Pb`, `gor`, `wc`, `T_bh`) is entered once and reused everywhere via `appState`. If a panel needs a field owned by another panel, show it as a **read-only "inherited" chip** with a link to "edit in [panel]" rather than a duplicate editable field.
- **Live recompute:** IPR, PVT, and VLP panels recalculate their own outputs/curves as the user edits inputs (debounced ~250ms), without requiring a separate "Run" click for in-panel results. Nodal Analysis and Sensitivity (heavier, multi-call computations) keep an explicit "Run" action, with a loading state.
- **Background computation:** Nodal Analysis and Sensitivity sweeps run asynchronously (mirrors existing `QRunnable` worker pattern) with a non-blocking progress indicator; the UI must never freeze.
- **Error handling:** any engine exception is caught and shown as a readable inline message tied to the panel/field likely responsible — never a raw traceback in the UI (console/log only).
- **Units:** every numeric field shows its unit as a fixed suffix/adornment, consistent with the Data Dictionary (§11).

---

## 8. Design System — "White & Blue, Modern"

**Direction:** clean engineering-SaaS aesthetic — generous white space, a single confident blue as the accent (not multiple competing blues), crisp typography, soft elevation instead of heavy borders, restrained motion.

**Color tokens (evolve, don't discard, the existing palette):**
| Token | Hex | Use |
|---|---|---|
| `--navy` | #0D2B55 | Headlines, primary chart title |
| `--blue` | #1565C0 | Primary actions, active states |
| `--blue-hover` | #1976D2 | Hover |
| `--blue-light` | #E3F0FB | Backgrounds for active/selected chips, cards |
| `--blue-mid` | #90CAF9 | Borders, gridlines |
| `--white` | #FFFFFF | Base surface |
| `--off-white` | #F7FAFD | Secondary surface (sidebars, panels) |
| `--ink` | #1A2840 | Primary text |
| `--slate` | #4A6080 | Secondary text, labels |
| `--success` | #2E7D32 | Stable operating point |
| `--warning/red` | #E53935 | Unstable point, errors, traverse highlight |
| `--gold` | #F9A825 | Caution / indeterminate stability |

**Typography:** a single modern sans (e.g., Inter / Segoe UI fallback) — large, confident numerals for KPI readouts (J, q*, Pwf*), smaller uppercase tracked labels for field names.

**Components:**
- Cards with soft shadow (not hard borders) on Home screen, gentle hover-lift.
- Inputs: rounded (6–8px), blue focus ring, inline unit suffix.
- Charts: white background, dashed light-blue gridlines, navy bold titles, distinct stable/unstable marker glyphs (not color-only).
- Status chips ("✓ saved", "Active", "Stable", "Unstable") as small pill badges.
- Motion: 150–200ms ease transitions on panel open/close and chart updates; no gratuitous animation.

---

## 9. Architecture Notes (for the build agent)

- The 4 existing Python modules are the **calculation engine** and should be exposed behind a thin API layer (e.g., a local REST/WS service or an embedded Python bridge) so the new frontend is decoupled from the engine's current PyQt6 coupling.
- Recommended split:
  - **Engine service**: wraps `ipr.py`, `pvt.py`, `vlp.py`, `solver_other.py` 1:1 — no logic changes, just callable endpoints (e.g., `/ipr/curve`, `/vlp/curve`, `/pvt/properties`, `/nodal/solve`, `/sensitivity/run`, `/traverse`, `/export/csv`).
  - **Frontend**: a modern SPA (component-based) consuming that API, owning `appState`, panel routing, and the chart/table rendering described above.
- Long-running calls (Nodal solve, Sensitivity, VLP rate sweep) should be async with progress/status events, mirroring the current worker-thread + signals pattern.
- Panels can be implemented as routed views, modal overlays, or a docked multi-panel workspace — the requirement is the **parallel-window feel** for Nodal Analysis (Pane A + Pane B simultaneously visible), not a specific windowing technology.

### 9.1 Engine extensions required for Gas Lift, Choke & Calibration CSV

These are the only backend changes implied by this revision. The Gas Lift and Choke additions are **new files**; the Calibration change is additive to existing code:

1. **New file: `core/choke.py`.** Pure-function implementation of the chosen choke correlation(s) (Gilbert/Ros/Achong/Baxendell for critical flow; Sachdeva for critical+subcritical). Independent of the other engine modules — only consumes PVT outputs for density/GLR at wellhead conditions.
2. **New package: `gas_lift/`** with `gas_lift/__init__.py` and **`gas_lift/gl.py`**, exposing:
   - `compute_glpc(state, sweep_param, sweep_values)` — the shared sweep engine behind all three Gas Lift tabs (depth / rate / GLR), looping `find_operating_points` exactly as Sensitivity already does.
   - `apply_gas_lift_design(vlp_obj, injection_depth, injection_rate, injection_sg)` — a VLP-wrapping function in the same style as `calibration.calibrate.apply_calibration_factors`, splitting the GLR profile above/below the injection depth inside `calculate_pressure_traverse`. No changes to `HagedornBrown` / `Beggs_Brill` holdup or friction logic.
3. **`app.py` changes (wiring only, no new physics):**
   - `_open_gaslift` is changed from opening `ComingSoonDialog` to opening a new `GasLiftPanel(self.state, self)` (modeled on `CalibrationPanel`'s structure: tabs instead of a single form, plus an Apply/Reset action pair).
   - `build_vlp(state, pvt_model, fp_dict)` gains a second wrap step, applied **after** the existing calibration wrap: `if state.gl_applied: obj = apply_gas_lift_design(obj, state.gl_opt_depth, state.gl_opt_rate, state.gl_sg_gas)`.
   - `AppState` gains the new fields listed in §11 (gas lift sweep + applied-design fields, choke fields). No existing `AppState` fields are renamed or removed.
   - `CalibrationPanel._setup_ui` gains the "Upload CSV" button and parser described in §6.10; `CalibrationWorker`/regression logic is untouched.
4. **New endpoints / worker classes** (if a service API is used instead of in-process PyQt calls, per the architecture options above): `/gaslift/curve` (one per tab — depth, rate, GLR), `/gaslift/apply`, `/gaslift/reset`, `/choke/curve`, `/calibration/upload-csv`.
5. **Nodal solve toggle (Choke):** `find_operating_points` is called unchanged; only the **VLP evaluator function it wraps** changes when "Use choke as outflow boundary" is enabled (THP becomes choke-derived instead of the fixed `thp` value).

---

## 10. Standout / Differentiator Features (beyond parity)

1. **Live "Phase diagnosis" badge** in PVT panel (undersaturated vs. two-phase, updates as pressure node changes).
2. **Inherited-field chips** — visually distinguishes data owned elsewhere vs. entered locally, reinforcing "enter once."
3. **3-parameter combined sensitivity matrix** (Cartesian grid / small-multiples) — materially more powerful than the legacy single-parameter sweep.
4. **Readiness progress bar** on Home — turns the multi-panel data entry into a guided flow rather than a maze of buttons.
5. **Dual operating-point visualization** with distinct stable/unstable glyphs and a plain-language diagnosis message (not just a status code).
6. **Contextual failure guidance** — when no operating point is found, the UI suggests *why* and *what to change*, using the engine's existing `failure_reason` text as a foundation.
7. **"Active" state indicators app-wide** — Home, VLP Panel, and Nodal Analysis all surface a small badge whenever calibration or gas-lift design is silently shaping the numbers being shown, so engineers are never caught off guard by a curve that isn't natural flow.
8. **Diminishing-returns auto-marker on the GLPC** — the optimum gas-lift rate is flagged automatically from the slope threshold, not left for the user to eyeball.
9. **Injection-feasibility shading** — gas-lift values (depth, rate, or GLR) that aren't actually achievable at the available injection pressure are visually distinguished, preventing a common gas-lift design mistake.
10. **Choke-as-outflow-node toggle in Nodal Analysis** — lets the engineer see, in one click, how a chosen bean size changes the well's operating point versus the fixed-THP assumption, without leaving the nodal screen.
11. **Combined erosional + hydrate risk badges in the Choke panel** — surfaces two real field risks (erosion, hydrate formation) that pure rate/pressure choke charts usually omit.
12. **One-click CSV ingest for calibration** — turns a raw memory-stick pressure survey into a calibrated VLP in two clicks (upload → Run Calibration), no manual retyping of a multi-row table.

---

## 11. Data Dictionary (canonical `AppState` keys — must match `app.py`'s existing dataclass; additions only, no renames)

| Key | Description | Unit | Owning Panel | Default |
|---|---|---|---|---|
| `ipr_model` | Composite / Vogel / Darcy | — | IPR | Composite |
| `Pr` | Static reservoir pressure | psia | IPR | — |
| `Pb` | Bubble point pressure | psia | IPR (PVT can override) | — |
| `Qo_test` | Test liquid rate | STB/day | IPR | — |
| `Pwf_test` | Test BHP | psia | IPR | — |
| `sg_gas` | Gas SG | (air=1) | PVT | 0.65 |
| `sg_oil` / `oil_api` | Oil SG / API | — / °API | PVT | 0.84 |
| `sg_water` | Water SG | (water=1) | PVT | 1.03 |
| `wc` | Watercut | fraction | PVT | 0.0 |
| `gor` | Producing GOR | scf/STB | PVT (or IPR test) | — |
| `T_pvt`, `P_min_pvt`, `P_max_pvt` | PVT evaluation node temp/pressure range | °F / psia | PVT | 180 / 14.7 / 5000 |
| `vlp_model` | Hagedorn-Brown / Beggs-Brill | — | VLP | Hagedorn-Brown |
| `tubing_id`, `tubing_od`, `casing_id` | Geometry | ft | VLP | — |
| `roughness` | Pipe roughness | ft | VLP | 0.00015 |
| `theta` | Deviation from vertical | ° | VLP | 0 |
| `depth` | Total depth | ft | VLP | — |
| `dz_step` | Integration step | ft | VLP | 50 |
| `thp` | Wellhead pressure | psia | VLP | — |
| `T_surface`, `T_bh` | Surface/bottomhole temp | °F | VLP | — |
| `q_min`, `q_max_sweep`, `q_step` | Rate sweep range | STB/day | VLP | 50 / 5000 / 100 |
| `calib_holdup_factor`, `calib_friction_factor` | Calibration multipliers (existing) | — | Calibration | 1.0 / 1.0 |
| `calib_csv_path` *(new)* | Last-uploaded measured survey file path/name, for display only | — | Calibration | — |
| `ipr_saved`, `pvt_saved`, `vlp_saved` | Panel save flags (existing) | bool | respective panel | False |
| `gl_depth_min`, `gl_depth_max`, `gl_depth_step` *(new)* | Depth-sweep range (Tab 1) | ft | Gas Lift | — |
| `gl_inj_depth` *(new)* | Injection depth used for the rate/GLR sweeps (Tabs 2–3) | ft | Gas Lift | ~0.55 × `depth` |
| `gl_sg_gas` *(new)* | Injection gas SG | (air=1) | Gas Lift | = `sg_gas` |
| `gl_q_min`, `gl_q_max`, `gl_q_step` *(new)* | Injection gas rate sweep (Tab 2) | Mscf/day | Gas Lift | 100 / 3000 / 100 |
| `gl_glr_min`, `gl_glr_max`, `gl_glr_step` *(new)* | Total GLR sweep (Tab 3) | scf/STB | Gas Lift | — |
| `gl_p_inj` *(new)* | Available injection pressure | psia | Gas Lift | — |
| `gl_q_available` *(new)* | Compressor capacity ceiling | Mscf/day | Gas Lift | — (optional) |
| `gl_econ_slope` *(new)* | Economic optimum slope threshold | STB/day per Mscf/day | Gas Lift | 0.5 |
| `gl_applied` *(new)* | **Sticky flag** — whether the active design is used in `build_vlp` | bool | Gas Lift | False |
| `gl_opt_depth`, `gl_opt_rate` *(new)* | The currently-applied design (from Summary tab) | ft, Mscf/day | Gas Lift | — |
| `choke_model` *(new)* | Gilbert / Ros / Achong / Baxendell / Sachdeva | — | Choke | Gilbert |
| `choke_p_down` *(new)* | Downstream (flowline) pressure | psia | Choke | — |
| `choke_size_64` *(new)* | Bean size (rate-check mode) | 1/64 in | Choke | 32 |
| `choke_sizes_list` *(new)* | Candidate bean sizes (sizing mode) | 1/64 in | Choke | 16–64 standard set |
| `choke_target_q` *(new)* | Target plateau rate (sizing mode) | STB/day | Choke | — |
| `choke_c_factor` *(new)* | API RP 14E erosional velocity constant | — | Choke | 100 |

---

## 12. Acceptance Criteria (high level)

- [ ] All engine modules (`core/ipr.py`, `core/pvt.py`, `core/vlp.py`, `core/solver_other.py`, `calibration/calibrate.py`) remain unmodified in calculation logic; new functionality is additive (`core/choke.py`, `gas_lift/gl.py`) or wiring-only (`app.py`).
- [ ] A value entered in any one panel appears pre-filled, read-only-with-edit-link, in every other panel that uses it.
- [ ] Nodal Analysis screen displays chart + traverse table + PVT@op simultaneously (no single-pane-at-a-time navigation).
- [ ] CSV export reproduces all sections currently in `export_csv` (operating point, PVT@op, IPR curve, VLP curve, traverse).
- [ ] Sensitivity panel supports 1, 2, or 3 simultaneously active parameters with independent ranges.
- [ ] Visual design uses the white/blue token system in §8 throughout, with no off-brand colors except semantic status colors (success/warning/gold).
- [ ] Calibration panel accepts a measured-survey CSV upload (in addition to the existing manual table) and populates the same table the regression already uses.
- [ ] Calibration factors, once applied, are used in **every** subsequent VLP/Nodal computation by default; "Clear Calibration" immediately reverts all of them — no app restart or panel re-visit needed.
- [ ] Gas Lift panel has four sub-views (Optimum Depth, Optimum Rate, Optimum GLR, Summary) sharing one `appState`, with "Apply Design" and "Reset Gas Lift" actions on the panel.
- [ ] Once a gas-lift design is applied, **every** VLP curve in the app (VLP Panel, Sensitivity, Nodal Analysis) reflects it by default; "Reset Gas Lift" immediately reverts all of them to natural flow.
- [ ] Gas-lift/depth/rate/GLR values that fail the injection-pressure feasibility check are visually distinguished, not silently included as valid.
- [ ] Choke panel supports both rate-check (single bean) and sizing (candidate list + target rate) modes, with flow-regime and erosional-velocity badges on every candidate.
- [ ] Nodal Analysis screen offers a working "Use choke as outflow boundary" toggle that swaps the fixed-THP VLP evaluator for the choke-derived one without altering the underlying solver call.
- [ ] Home screen shows an "Active" indicator on the Gas Lift and Calibration cards whenever their respective sticky state is non-default.
