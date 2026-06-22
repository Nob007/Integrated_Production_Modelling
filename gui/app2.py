"""
gui/main.py
===========
FlowNexus IPM v2.0 — Integrated Production Modelling & Nodal Analysis Platform
Three-panel layout: NavRail | WorkspaceStack | SummaryPanel
PRD v2.0 compliant — Deep Blue / Royal Blue / Cyan glassmorphism theme
All core/ engine calls (IPR, PVT, VLP, Nodal Solver) preserved unchanged.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from datetime import datetime

import numpy as np
from scipy.optimize import brentq

# ── path so imports from core/ work regardless of cwd ──────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.pvt import BlackOilPVT
from core.ipr import composite_ipr, darcy_ipr, vogel_ipr
from core.vlp import HagedornBrown, Beggs_Brill
from core.solver_other import find_operating_points

# ── Qt ─────────────────────────────────────────────────────────────────────────
from PyQt6.QtCore import (
    QObject, QPropertyAnimation, QRunnable, QRectF, QSize, Qt,
    QThreadPool, pyqtSignal, pyqtSlot, QPointF,
)
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QBrush, QRadialGradient, QIcon,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFrame, QGraphicsDropShadowEffect, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QListView, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget, QLineEdit,
)

# ── matplotlib ─────────────────────────────────────────────────────────────────
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 – registers 3D projection

# ══════════════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS  (PRD §2)
# ══════════════════════════════════════════════════════════════════════════════

# Primary
C_DEEP_BLUE  = "#0F4C81"
C_ROYAL_BLUE = "#2196F3"
C_BLUE_HOV   = "#1976D2"
C_BLUE_PRESS = "#0D47A1"

# Secondary
C_WHITE      = "#FFFFFF"
C_LIGHT_GRAY = "#F5F7FA"
C_GRAY_MID   = "#E8EDF3"
C_GRAY_DARK  = "#B0BEC5"

# Accent
C_CYAN       = "#00BCD4"
C_CYAN_LIGHT = "#E0F7FA"
C_CYAN_MID   = "#80DEEA"

# Status
C_SUCCESS    = "#43A047"
C_WARNING    = "#FFB300"
C_ERROR      = "#E53935"

# Text
C_INK        = "#1A2840"
C_SLATE      = "#546E7A"
C_NAVY       = "#0D2B55"

# Supplementary
C_CARD_BG    = "rgba(255,255,255,0.92)"
C_BORDER     = "#CFD8DC"
C_GOLD       = "#F9A825"
C_RED        = "#E53935"

SENS_PALETTE = [
    "#42A5F5", "#26C6DA", "#00ACC1", "#00838F", "#006064",
    "#4DD0E1", "#80DEEA", "#F9A825", "#66BB6A", "#AB47BC",
]

# ══════════════════════════════════════════════════════════════════════════════
#  QSS STYLESHEET  (PRD §2 — glassmorphism + rounded + shadows)
# ══════════════════════════════════════════════════════════════════════════════

QSS = f"""
/* ── Global ───────────────────────────────────────────────────────── */
QWidget {{
    background: {C_LIGHT_GRAY};
    color: {C_INK};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 12px;
}}

/* ── Main Window ──────────────────────────────────────────────────── */
QMainWindow {{
    background: {C_LIGHT_GRAY};
}}

/* ── Scroll Areas ─────────────────────────────────────────────────── */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    width: 6px; background: {C_LIGHT_GRAY}; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C_GRAY_DARK}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 6px; background: {C_LIGHT_GRAY}; border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {C_GRAY_DARK}; border-radius: 3px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Cards ────────────────────────────────────────────────────────── */
QFrame#card {{
    background: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
}}

/* ── Input widgets ────────────────────────────────────────────────── */
QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit {{
    border: 1.5px solid {C_BORDER};
    border-radius: 7px;
    padding: 5px 10px;
    background: {C_WHITE};
    color: {C_INK};
    min-height: 28px;
    selection-background-color: {C_ROYAL_BLUE};
    selection-color: {C_WHITE};
}}
QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
    border: 1.5px solid {C_ROYAL_BLUE};
    background: #F0F7FF;
}}
QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover {{
    border: 1.5px solid {C_CYAN};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView, QComboBox QListView {{
    border: 1.5px solid {C_BORDER};
    background: {C_WHITE};
    color: {C_INK};
    selection-background-color: {C_CYAN_LIGHT};
    selection-color: {C_DEEP_BLUE};
    outline: none;
    border-radius: 8px;
}}
QComboBox QAbstractItemView::item {{ min-height: 26px; color: {C_INK}; }}
QComboBox QAbstractItemView::item:selected {{
    background: {C_CYAN_LIGHT}; color: {C_DEEP_BLUE};
}}

/* ── Labels ───────────────────────────────────────────────────────── */
QLabel#field_label {{
    color: {C_SLATE}; font-size: 11px; background: transparent;
}}
QLabel#ro_label {{
    color: {C_DEEP_BLUE}; font-weight: 600;
    background: #EEF4FB; border: 1.5px solid {C_BORDER};
    border-radius: 7px; padding: 5px 10px; min-height: 28px;
}}
QLabel#section_title {{
    color: {C_DEEP_BLUE}; font-size: 13px; font-weight: 700;
    background: transparent;
}}
QLabel#module_title {{
    color: {C_WHITE}; font-size: 16px; font-weight: 700;
    background: transparent;
}}
QLabel#warning_label {{
    color: {C_WARNING}; font-size: 10px;
    background: #FFF8E1; border: 1px solid {C_WARNING};
    border-radius: 5px; padding: 3px 8px;
}}

/* ── Primary Buttons (Run) ────────────────────────────────────────── */
QPushButton#run_btn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C_DEEP_BLUE}, stop:1 {C_ROYAL_BLUE});
    color: {C_WHITE};
    border: none; border-radius: 9px;
    padding: 8px 22px; font-weight: 700; font-size: 13px;
    min-width: 160px; min-height: 38px;
}}
QPushButton#run_btn:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C_ROYAL_BLUE}, stop:1 {C_CYAN});
}}
QPushButton#run_btn:pressed {{
    background: {C_BLUE_PRESS};
}}
QPushButton#run_btn:disabled {{
    background: {C_GRAY_DARK}; color: {C_WHITE};
}}

/* ── Secondary Buttons ────────────────────────────────────────────── */
QPushButton#sec_btn {{
    background: {C_WHITE}; color: {C_DEEP_BLUE};
    border: 1.5px solid {C_ROYAL_BLUE}; border-radius: 8px;
    padding: 6px 16px; font-weight: 600; min-height: 32px;
}}
QPushButton#sec_btn:hover {{
    background: {C_CYAN_LIGHT}; border-color: {C_CYAN};
}}
QPushButton#sec_btn:disabled {{
    color: {C_GRAY_DARK}; border-color: {C_BORDER};
}}

/* ── Tabs ─────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1.5px solid {C_BORDER};
    border-radius: 10px;
    background: {C_WHITE};
    top: -1px;
}}
QTabBar::tab {{
    background: {C_LIGHT_GRAY};
    color: {C_SLATE};
    border: 1px solid {C_BORDER};
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 7px 18px;
    margin-right: 3px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background: {C_WHITE};
    color: {C_DEEP_BLUE};
    font-weight: 700;
    border-color: {C_ROYAL_BLUE};
}}
QTabBar::tab:hover:!selected {{
    background: {C_CYAN_LIGHT};
    color: {C_DEEP_BLUE};
}}

/* ── Table ────────────────────────────────────────────────────────── */
QTableWidget {{
    background: {C_WHITE};
    border: 1.5px solid {C_BORDER};
    border-radius: 8px;
    gridline-color: {C_GRAY_MID};
    alternate-background-color: #F8FBFF;
    selection-background-color: {C_CYAN_LIGHT};
    selection-color: {C_DEEP_BLUE};
}}
QTableWidget::item {{ padding: 5px 10px; }}
QHeaderView::section {{
    background: {C_DEEP_BLUE};
    color: {C_WHITE};
    font-weight: 600;
    padding: 6px 10px;
    border: none;
}}
QHeaderView::section:first {{ border-radius: 8px 0 0 0; }}
QHeaderView::section:last {{ border-radius: 0 8px 0 0; }}

/* ── Status Bar ───────────────────────────────────────────────────── */
QStatusBar {{
    background: {C_DEEP_BLUE};
    color: {C_WHITE};
    border-top: none;
    font-size: 11px;
    min-height: 36px;
    padding: 0 12px;
}}

/* ── Tool Button (collapsible) ────────────────────────────────────── */
QToolButton#section_header {{
    background: {C_LIGHT_GRAY};
    color: {C_DEEP_BLUE};
    border: none;
    border-left: 3px solid {C_ROYAL_BLUE};
    padding: 8px 14px;
    font-weight: 600;
    text-align: left;
    border-radius: 0;
}}
QToolButton#section_header:hover {{ background: {C_CYAN_LIGHT}; }}

/* ── CheckBox ─────────────────────────────────────────────────────── */
QCheckBox {{
    color: {C_INK}; background: transparent;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid {C_BORDER}; border-radius: 4px;
    background: {C_WHITE};
}}
QCheckBox::indicator:checked {{
    background: {C_ROYAL_BLUE}; border-color: {C_ROYAL_BLUE};
}}

/* ── Splitter ─────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {C_BORDER};
    width: 2px; height: 2px;
}}

/* ── Group Box ────────────────────────────────────────────────────── */
QGroupBox {{
    border: 1.5px solid {C_BORDER};
    border-radius: 10px;
    margin-top: 18px;
    padding-top: 8px;
    background: {C_WHITE};
    font-weight: 600;
    color: {C_DEEP_BLUE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px; top: 0px;
    padding: 0 6px;
    color: {C_DEEP_BLUE};
    background: {C_WHITE};
}}
"""

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _dspin(val: float, lo: float, hi: float, step: float, dec: int) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    s.setSingleStep(step)
    s.setDecimals(dec)
    return s


def _row(label: str, widget: QWidget, unit: str = "", label_width: int = 110) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 2, 0, 2)
    h.setSpacing(8)
    lbl = QLabel(label)
    lbl.setObjectName("field_label")
    lbl.setFixedWidth(label_width)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    h.addWidget(lbl)
    h.addWidget(widget, 1)
    if unit:
        u = QLabel(unit)
        u.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent; min-width:60px;")
        h.addWidget(u)
    return w


def _card(title: str | None = None, min_height: int = 0) -> tuple[QFrame, QVBoxLayout]:
    """Return a glassmorphism card frame and its inner VBoxLayout."""
    frame = QFrame()
    frame.setObjectName("card")
    if min_height:
        frame.setMinimumHeight(min_height)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(16)
    shadow.setColor(QColor(0, 0, 0, 30))
    shadow.setOffset(0, 3)
    frame.setGraphicsEffect(shadow)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setObjectName("section_title")
        lay.addWidget(t)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; max-height:1px; border:none;")
        lay.addWidget(sep)
    return frame, lay


def _pill(text: str, bg: str, fg: str = C_WHITE) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background:{bg}; color:{fg}; border-radius:8px; "
        f"padding:2px 10px; font-size:10px; font-weight:700;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def _summary_value(val: str, unit: str = "") -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    lbl = QLabel(val)
    lbl.setStyleSheet(
        f"color:{C_DEEP_BLUE}; font-weight:700; font-size:13px; background:transparent;")
    h.addWidget(lbl)
    if unit:
        u = QLabel(unit)
        u.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent;")
        h.addWidget(u)
    h.addStretch()
    return w


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE HELPERS  (unchanged from original)
# ══════════════════════════════════════════════════════════════════════════════

def _build_pvt_vlp(p: dict) -> tuple[BlackOilPVT, object]:
    pvt = BlackOilPVT(
        sg_gas=p["sg_gas"], sg_oil=p["sg_oil"],
        sg_water=p["sg_water"], watercut=p["wc"]
    )
    Rsb = p["gor"]
    fp0 = pvt.fluid_properties_dict(p["thp"], p["T_surface"], Rsb, p["gor"], p["Pb"])
    if p["model"] == "Hagedron-Brown":
        vlp = HagedornBrown(
            tubing_id=p["tubing_id"], tubing_od=p["tubing_od"],
            casing_id=p["casing_id"], roughness=p["roughness"],
            pvt_model=pvt, fluid_properties=fp0,
            watercut=p["wc"], theta=p["theta"],
        )
    elif p["model"] == "Beggs and Brill":
        vlp = Beggs_Brill(
            tubing_id=p["tubing_id"], tubing_od=p["tubing_od"],
            casing_id=p["casing_id"], roughness=p["roughness"],
            pvt_model=pvt, fluid_properties=fp0,
            watercut=p["wc"], theta=p["theta"],
        )
    else:
        vlp = HagedornBrown(
            tubing_id=p["tubing_id"], tubing_od=p["tubing_od"],
            casing_id=p["casing_id"], roughness=p["roughness"],
            pvt_model=pvt, fluid_properties=fp0,
            watercut=p["wc"], theta=p["theta"],
        )
    return pvt, vlp


def _vlp_pwf(vlp, p: dict, q: float) -> float:
    _, pressures, _ = vlp.calculate_pressure_traverse(
        Pth=p["thp"], surface_temp=p["T_surface"],
        bottomhole_temp=p["T_bh"], total_depth=p["depth"],
        step_size=p["dz_step"], Ql=q,
    )
    return float(pressures[-1])


def _build_ipr(p: dict) -> object:
    model = p.get("ipr_model", "Composite")
    Pr, Pb = p["Pr"], p["Pb"]
    qt, pwft = p["Qo_test"], p["Pwf_test"]
    if model == "Darcy":
        return darcy_ipr(Pr=Pr, Pb=Pb, q_test=qt, Pwf_test=pwft)
    elif model == "Composite":
        return composite_ipr(Pr=Pr, Pb=Pb, q_test=qt, Pwf_test=pwft)
    elif model == "Vogel":
        return vogel_ipr(Pr=Pr, Pb=Pb, q_test=qt, Pwf_test=pwft)
    else:
        return composite_ipr(Pr=Pr, Pb=Pb, q_test=qt, Pwf_test=pwft)


# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT STORE  (global singleton — enter data once, share everywhere)
# ══════════════════════════════════════════════════════════════════════════════

class ProjectStore(QObject):
    """
    Central data store. All modules read/write from here.
    Emits `changed` whenever any value is updated.
    """
    changed = pyqtSignal()
    results_ready = pyqtSignal(dict)

    # Default reservoir / fluid / wellbore parameters
    DEFAULTS = {
        # IPR
        "Pr": 2500.0, "Pb": 1800.0, "Qo_test": 800.0, "Pwf_test": 1200.0,
        "ipr_model": "Composite",
        # Fluid
        "sg_oil": 0.85, "sg_gas": 0.65, "sg_water": 1.07, "wc": 0.33,
        "gor": 500.0,
        # VLP / Wellbore
        "model": "Hagedron-Brown",
        "tubing_id": 2.441 / 12, "tubing_od": 2.875 / 12,
        "casing_id": 5.5 / 12, "roughness": 0.0 / 12,
        "thp": 150.0, "depth": 6000.0,
        "T_surface": 100.0, "T_bh": 200.0,
        "theta": 0.0,
        # Rate sweep
        "q_min": 0.0, "q_max": 3000.0, "q_step": 50.0, "dz_step": 200.0,
    }

    def __init__(self) -> None:
        super().__init__()
        self._data: dict = dict(self.DEFAULTS)
        self.last_result: dict | None = None
        self.project_path: str | None = None
        self.well_name: str = "Well-1"
        self.recent: list[str] = []

    # ── data access ────────────────────────────────────────────────────────
    def get(self, key: str):
        return self._data.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        if self._data.get(key) != value:
            self._data[key] = value
            self.changed.emit()

    def update(self, d: dict) -> None:
        self._data.update(d)
        self.changed.emit()

    def all_values(self) -> dict:
        return dict(self._data)

    # ── templates ──────────────────────────────────────────────────────────
    def load_template(self, name: str) -> None:
        templates = {
            "Light Oil": {
                "Pr": 2500.0, "Pb": 1800.0, "Qo_test": 800.0, "Pwf_test": 1200.0,
                "sg_oil": 0.825, "sg_gas": 0.65, "sg_water": 1.07, "wc": 0.20,
                "gor": 600.0, "thp": 150.0, "depth": 6000.0,
                "T_surface": 100.0, "T_bh": 200.0,
                "tubing_id": 2.441/12, "tubing_od": 2.875/12, "casing_id": 5.5/12,
                "roughness": 0.0, "theta": 0.0,
            },
            "Heavy Oil": {
                "Pr": 1800.0, "Pb": 800.0, "Qo_test": 400.0, "Pwf_test": 900.0,
                "sg_oil": 0.966, "sg_gas": 0.70, "sg_water": 1.10, "wc": 0.40,
                "gor": 150.0, "thp": 120.0, "depth": 4500.0,
                "T_surface": 90.0, "T_bh": 170.0,
                "tubing_id": 2.992/12, "tubing_od": 3.5/12, "casing_id": 7.0/12,
                "roughness": 0.00015/12, "theta": 0.0,
            },
            "Gas Condensate": {
                "Pr": 5000.0, "Pb": 4500.0, "Qo_test": 2500.0, "Pwf_test": 3000.0,
                "sg_oil": 0.75, "sg_gas": 0.70, "sg_water": 1.05, "wc": 0.05,
                "gor": 3000.0, "thp": 800.0, "depth": 12000.0,
                "T_surface": 110.0, "T_bh": 280.0,
                "tubing_id": 2.441/12, "tubing_od": 2.875/12, "casing_id": 5.5/12,
                "roughness": 0.0, "theta": 0.0,
            },
            "Water Producer": {
                "Pr": 2200.0, "Pb": 500.0, "Qo_test": 1200.0, "Pwf_test": 1500.0,
                "sg_oil": 0.85, "sg_gas": 0.65, "sg_water": 1.08, "wc": 0.80,
                "gor": 100.0, "thp": 100.0, "depth": 5000.0,
                "T_surface": 95.0, "T_bh": 185.0,
                "tubing_id": 2.992/12, "tubing_od": 3.5/12, "casing_id": 7.0/12,
                "roughness": 0.0, "theta": 0.0,
            },
        }
        if name in templates:
            self._data.update(templates[name])
            self.changed.emit()

    # ── persistence ────────────────────────────────────────────────────────
    def save(self, path: str) -> None:
        payload = {
            "version": "2.0",
            "well_name": self.well_name,
            "saved_at": datetime.now().isoformat(),
            "data": self._data,
            "result": self.last_result,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        self.project_path = path
        if path not in self.recent:
            self.recent.insert(0, path)
            self.recent = self.recent[:5]

    def load(self, path: str) -> None:
        with open(path) as f:
            payload = json.load(f)
        self._data.update(payload.get("data", {}))
        self.well_name = payload.get("well_name", "Well-1")
        self.last_result = payload.get("result")
        self.project_path = path
        if path not in self.recent:
            self.recent.insert(0, path)
            self.recent = self.recent[:5]
        self.changed.emit()


# ── Global singleton
_store = ProjectStore()


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER THREADS  (retained + unchanged from original)
# ══════════════════════════════════════════════════════════════════════════════

class _Signals(QObject):
    result = pyqtSignal(object)
    error  = pyqtSignal(str)
    status = pyqtSignal(str)


class AnalysisWorker(QRunnable):
    """Computes IPR, VLP, operating point, pressure traverse."""

    def __init__(self, params: dict) -> None:
        super().__init__()
        self.p = params
        self.signals = _Signals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            p = self.p
            self.signals.status.emit("⏳  Building IPR curve…")
            ipr = _build_ipr(p)
            rates_ipr = np.linspace(0.0, ipr.q_max, 200)
            pwf_ipr   = [ipr.calculate_Pwf(float(q)) for q in rates_ipr]

            self.signals.status.emit("⏳  Building VLP curve…")
            _, vlp = _build_pvt_vlp(p)
            n_vlp     = max(int((p["q_max"] - p["q_min"]) / p["q_step"]) + 1, 20)
            rates_vlp = np.linspace(p["q_min"], p["q_max"], n_vlp)
            pwf_vlp   = []
            for i, q in enumerate(rates_vlp):
                if i % 5 == 0:
                    self.signals.status.emit(
                        f"⏳  VLP sweep {i + 1}/{n_vlp}  (q = {q:.0f} STB/d)…")
                pwf_vlp.append(_vlp_pwf(vlp, p, float(q)))

            self.signals.status.emit("⏳  Finding operating points…")
            sol: dict = {
                "success": False, "operating_rate": None,
                "operating_pwf": None, "message": "", "all_points": []
            }
            traverse_depths: list = []
            traverse_pressures: list = []
            traverse_profiles: dict = {}
            fp_op: dict = {}

            q_lo, q_hi = float(p["q_min"]), float(p["q_max"])
            try:
                vlp_params_dict = {
                    "Pth": p["thp"], "surface_temp": p["T_surface"],
                    "bottomhole_temp": p["T_bh"], "depth": p["depth"],
                    "step_size": p["dz_step"]
                }
                nodal_result = find_operating_points(
                    ipr_model=ipr, vlp_model=vlp, vlp_params=vlp_params_dict,
                    pr=p["Pr"], q_min=q_lo, q_max=q_hi, xtol=0.1
                )
                if not nodal_result.success:
                    sol["message"] = nodal_result.failure_reason
                else:
                    op_point = nodal_result.stable_point
                    if op_point is None:
                        op_point = nodal_result.unstable_point
                    if op_point is None and nodal_result.all_points:
                        op_point = nodal_result.all_points[0]
                    if op_point:
                        q_star, p_star = op_point.rate, op_point.pwf
                        sol.update(
                            success=True,
                            operating_rate=q_star, operating_pwf=p_star,
                            message="Converged.",
                            all_points=[(pt.rate, pt.pwf, pt.stability.value)
                                        for pt in nodal_result.all_points]
                        )
                        self.signals.status.emit(
                            f"⏳  Computing traverse at q* = {q_star:.1f} STB/d…")
                        traverse_depths, traverse_pressures, traverse_profiles = \
                            vlp.calculate_pressure_traverse(
                                Pth=p["thp"], surface_temp=p["T_surface"],
                                bottomhole_temp=p["T_bh"], total_depth=p["depth"],
                                step_size=p["dz_step"], Ql=q_star,
                            )
                        pvt_m = vlp.pvt_model
                        rsb_true = pvt_m.calc_true_rsb(p["Pb"], p["T_bh"])
                        fp_op = pvt_m.fluid_properties_dict(
                            p_star, p["T_bh"], rsb_true, p["gor"], p["Pb"])
            except Exception as solve_err:
                sol["message"] = str(solve_err)

            self.signals.result.emit({
                "rates_ipr": rates_ipr.tolist(), "pwf_ipr": pwf_ipr,
                "rates_vlp": rates_vlp.tolist(), "pwf_vlp": pwf_vlp,
                "sol": sol,
                "traverse_depths": list(traverse_depths),
                "traverse_pressures": list(traverse_pressures),
                "traverse_profiles": traverse_profiles,
                "fp_op": fp_op,
                "params": p,
            })
        except Exception:
            self.signals.error.emit(traceback.format_exc())


class SensWorker(QRunnable):
    """Single-variable sensitivity sweep."""
    _KEY_MAP = {
        "GOR": "gor", "THP": "thp", "Depth": "depth",
        "Water Cut": "wc", "Tubing ID": "tubing_id",
        "Reservoir Pressure": "Pr", "Bubble Point": "Pb",
    }

    def __init__(self, params: dict, values: list[float], param_name: str) -> None:
        super().__init__()
        self.p, self.values, self.pname = params, values, param_name
        self.signals = _Signals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            key = self._KEY_MAP.get(self.pname, self.pname.lower())
            results = []
            total = len(self.values)
            op_rates, op_pwfs = [], []
            for i, val in enumerate(self.values):
                self.signals.status.emit(
                    f"⏳  Sensitivity {i + 1}/{total} — {self.pname} = {val:.2f}…")
                p2 = dict(self.p)
                p2[key] = val
                _, vlp2 = _build_pvt_vlp(p2)
                n = max(int((p2["q_max"] - p2["q_min"]) / p2["q_step"]) + 1, 20)
                rates = np.linspace(p2["q_min"], p2["q_max"], n)
                pwfs  = [_vlp_pwf(vlp2, p2, float(q)) for q in rates]
                # Find approx operating point
                ipr2 = _build_ipr(p2)
                ipr_at_vlp = [ipr2.calculate_Pwf(float(q)) for q in rates]
                diffs = [abs(pwfs[j] - ipr_at_vlp[j]) for j in range(len(rates))]
                best_idx = int(np.argmin(diffs))
                op_rates.append(float(rates[best_idx]))
                op_pwfs.append(float(pwfs[best_idx]))
                results.append({
                    "label": f"{self.pname} = {val:.2f}",
                    "rates": rates.tolist(), "pwf": pwfs,
                    "op_rate": float(rates[best_idx]),
                    "op_pwf": float(pwfs[best_idx]),
                    "param_val": val,
                })
            self.signals.result.emit({
                "curves": results,
                "param_name": self.pname,
                "values": self.values,
                "op_rates": op_rates,
                "op_pwfs": op_pwfs,
            })
        except Exception:
            self.signals.error.emit(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
#  COLLAPSIBLE SECTION  (reusable panel widget)
# ══════════════════════════════════════════════════════════════════════════════

class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._open = True
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.btn = QToolButton()
        self.btn.setObjectName("section_header")
        self.btn.setCheckable(True)
        self.btn.setChecked(True)
        self.btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn.setMinimumHeight(36)
        self._title = title
        self._refresh()
        self.btn.clicked.connect(self._toggle)

        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.bl = QVBoxLayout(self.body)
        self.bl.setContentsMargins(12, 6, 12, 10)
        self.bl.setSpacing(5)

        root.addWidget(self.btn)
        root.addWidget(self.body)

    def _refresh(self) -> None:
        arrow = "▼" if self._open else "▶"
        self.btn.setText(f"   {arrow}  {self._title}")

    def _toggle(self) -> None:
        self._open = not self._open
        self.body.setVisible(self._open)
        self._refresh()

    def add(self, widget: QWidget) -> None:
        self.bl.addWidget(widget)


# ══════════════════════════════════════════════════════════════════════════════
#  MINI TRAVERSE MAP  (floating pressure traverse chart)
# ══════════════════════════════════════════════════════════════════════════════

class MiniMap(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(240, 290))
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,235);
                border: 1.5px solid {C_CYAN_MID};
                border-radius: 12px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        hdr = QHBoxLayout()
        title_lbl = QLabel("📊 Traverse @ q*")
        title_lbl.setStyleSheet(
            f"font-size: 9pt; font-weight: 700; color: {C_DEEP_BLUE}; "
            "background: transparent; border: none;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        lay.addLayout(hdr)

        self.fig = Figure(figsize=(2.2, 2.6), dpi=85)
        self.fig.patch.set_facecolor("white")
        self.ax = self.fig.add_subplot(111)
        self._blank()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet("background: white; border: none;")
        lay.addWidget(self.canvas, 1)

    def update_traverse(self, depths: list, pressures: list) -> None:
        ax = self.ax
        ax.clear()
        ax.set_facecolor("#FAFCFF")
        ax.plot(pressures, depths, color=C_CYAN, linewidth=2,
                solid_capstyle="round")
        ax.fill_betweenx(depths, pressures,
                         alpha=0.12, color=C_CYAN)
        ax.invert_yaxis()
        ax.set_xlabel("P (psia)", fontsize=7, color=C_INK)
        ax.set_ylabel("Depth (ft)", fontsize=7, color=C_INK)
        ax.tick_params(labelsize=6, colors=C_INK)
        ax.grid(True, linestyle="--", alpha=0.4, linewidth=0.5, color=C_GRAY_MID)
        for sp in ax.spines.values():
            sp.set_edgecolor(C_BORDER)
            sp.set_linewidth(0.5)
        self.fig.tight_layout(pad=0.4)
        self.canvas.draw_idle()

    def reset(self) -> None:
        self._blank()
        self.canvas.draw_idle()

    def _blank(self) -> None:
        self.ax.clear()
        self.ax.set_facecolor("#FAFCFF")
        self.ax.text(0.5, 0.5, "Run analysis\nto see traverse.",
                     ha="center", va="center", transform=self.ax.transAxes,
                     fontsize=8, color=C_SLATE)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.fig.tight_layout(pad=0.4)


# ══════════════════════════════════════════════════════════════════════════════
#  WELL DIGITAL TWIN PANEL  (PRD Feature 7 — QPainter schematic)
# ══════════════════════════════════════════════════════════════════════════════

class WellDigitalTwin(QWidget):
    """Live engineering well schematic drawn with QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 340)
        self.setStyleSheet("background: transparent;")
        self._store = _store
        self._store.changed.connect(self.update)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background card
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W, H), 10, 10)
        p.fillPath(path, QColor(C_WHITE))

        # Title
        p.setPen(QColor(C_DEEP_BLUE))
        f = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(10, 18, "Well Digital Twin™")

        cx = W // 2
        surface_y = 40
        bh_y = H - 40
        tube_w = 16
        ann_w = 28

        # Reservoir block (bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E3F2FD"))
        p.drawRoundedRect(cx - 50, bh_y - 10, 100, 30, 5, 5)
        p.setPen(QColor(C_DEEP_BLUE))
        f2 = QFont("Segoe UI", 7, QFont.Weight.Bold)
        p.setFont(f2)
        p.drawText(cx - 45, bh_y + 10, "RESERVOIR")

        # Pr annotation
        Pr = _store.get("Pr")
        p.setPen(QColor(C_SLATE))
        f3 = QFont("Segoe UI", 7)
        p.setFont(f3)
        p.drawText(cx + 35, bh_y + 10, f"{Pr:.0f} psi")

        # Casing (annulus)
        p.setPen(QPen(QColor(C_GRAY_DARK), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(cx - ann_w, surface_y + 20, cx - ann_w, bh_y - 10)
        p.drawLine(cx + ann_w, surface_y + 20, cx + ann_w, bh_y - 10)

        # Tubing
        p.setPen(QPen(QColor(C_ROYAL_BLUE), 3))
        p.drawLine(cx - tube_w, surface_y + 20, cx - tube_w, bh_y - 10)
        p.drawLine(cx + tube_w, surface_y + 20, cx + tube_w, bh_y - 10)

        # Tubing fill (gradient)
        grad = QLinearGradient(QPointF(cx - tube_w, 0), QPointF(cx + tube_w, 0))
        grad.setColorAt(0, QColor(C_CYAN_LIGHT))
        grad.setColorAt(1, QColor("#E3F2FD"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(cx - tube_w + 2, surface_y + 20, tube_w * 2 - 4, bh_y - surface_y - 30)

        # Flow arrows inside tubing
        p.setPen(QPen(QColor(C_CYAN), 1.5))
        arrow_y = bh_y - 40
        while arrow_y > surface_y + 40:
            p.drawLine(cx, arrow_y, cx - 4, arrow_y + 8)
            p.drawLine(cx, arrow_y, cx + 4, arrow_y + 8)
            arrow_y -= 30

        # Surface box
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E8F5E9"))
        p.drawRoundedRect(cx - 50, surface_y, 100, 24, 5, 5)
        p.setPen(QColor(C_SUCCESS))
        f4 = QFont("Segoe UI", 7, QFont.Weight.Bold)
        p.setFont(f4)
        p.drawText(cx - 45, surface_y + 15, "SURFACE  (THP)")

        thp = _store.get("thp")
        p.setPen(QColor(C_SLATE))
        p.setFont(f3)
        p.drawText(cx + 35, surface_y + 15, f"{thp:.0f} psi")

        # Depth label mid-point
        depth = _store.get("depth")
        mid_y = (surface_y + bh_y) // 2
        p.setPen(QColor(C_SLATE))
        p.drawText(cx + ann_w + 4, mid_y, f"{depth:.0f} ft")

        # Temp indicators
        T_sf = _store.get("T_surface")
        T_bh = _store.get("T_bh")
        p.setPen(QColor(C_SLATE))
        p.setFont(f3)
        p.drawText(cx - ann_w - 50, surface_y + 15, f"T={T_sf:.0f}°F")
        p.drawText(cx - ann_w - 50, bh_y + 8, f"T={T_bh:.0f}°F")

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
#  LEFT NAVIGATION RAIL  (PRD §3 left panel)
# ══════════════════════════════════════════════════════════════════════════════

NAV_ITEMS = [
    ("📈", "IPR",         "IPR Data",         True),
    ("💧", "PVT",         "PVT Data",         True),
    ("⛽", "VLP",         "VLP Data",         True),
    ("🎯", "Nodal",       "Nodal Analysis",   True),
    ("📊", "Sensitivity", "Sensitivity",      True),
    ("⚙️", "Calibration", "Calibration",      False),
    ("🚀", "Gas Lift",    "Gas Lift",         False),
]


class NavRail(QWidget):
    module_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(80)
        self.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {C_NAVY}, stop:1 {C_DEEP_BLUE});"
        )
        self._active = "IPR"
        self._btns: dict[str, QPushButton] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # App logo pill
        logo = QLabel("⚡")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"color:{C_CYAN}; font-size:22px; background:transparent; "
            "padding-bottom:4px;")
        lay.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C_ROYAL_BLUE}; max-height:1px; border:none;")
        lay.addWidget(sep)
        lay.addSpacing(4)

        for icon, key, label, enabled in NAV_ITEMS:
            btn = self._make_btn(icon, label, key, enabled)
            self._btns[key] = btn
            lay.addWidget(btn)

        lay.addStretch()
        self._highlight(self._active)

    def _make_btn(self, icon: str, label: str, key: str, enabled: bool) -> QPushButton:
        btn = QPushButton()
        btn.setEnabled(enabled)
        btn.setFixedHeight(66)
        btn.setFixedWidth(80)
        btn.setCheckable(True)

        inner = QVBoxLayout(btn)
        inner.setContentsMargins(2, 6, 2, 4)
        inner.setSpacing(2)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ico_lbl = QLabel(icon)
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet("background:transparent; border:none; font-size:18px;")
        inner.addWidget(ico_lbl)

        txt_lbl = QLabel(label if enabled else label)
        txt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_lbl.setStyleSheet(
            "background:transparent; border:none; font-size:8px; "
            f"color:{'#B0BEC5' if not enabled else '#CFD8DC'}; font-weight: 500;")
        txt_lbl.setWordWrap(True)
        inner.addWidget(txt_lbl)

        if not enabled:
            pill = QLabel("SOON")
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                "background:#37474F; color:#B0BEC5; border-radius:5px; "
                "font-size:7px; font-weight:700; padding:1px 4px;")
            inner.addWidget(pill)

        # Store refs for highlight
        btn._icon_lbl = ico_lbl
        btn._txt_lbl  = txt_lbl
        btn._key = key

        btn.setStyleSheet(self._btn_style(False, enabled))
        if enabled:
            btn.clicked.connect(lambda _, k=key: self._on_click(k))
        return btn

    def _btn_style(self, active: bool, enabled: bool = True) -> str:
        if not enabled:
            return ("QPushButton { background: transparent; border: none; }"
                    "QPushButton:disabled { background: transparent; }")
        if active:
            return (
                f"QPushButton {{ background: rgba(0,188,212,0.18); "
                f"border-left: 3px solid {C_CYAN}; border-radius: 0; }}")
        return (
            "QPushButton { background: transparent; border: none; border-radius: 0; }"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.08); }}")

    def _highlight(self, key: str) -> None:
        for k, btn in self._btns.items():
            enabled = btn.isEnabled()
            btn.setStyleSheet(self._btn_style(k == key, enabled))
            if hasattr(btn, "_txt_lbl"):
                btn._txt_lbl.setStyleSheet(
                    "background:transparent; border:none; font-size:8px; "
                    f"color:{'#00BCD4' if k == key else ('#B0BEC5' if not enabled else '#CFD8DC')}; font-weight:700;")

    def _on_click(self, key: str) -> None:
        self._active = key
        self._highlight(key)
        self.module_selected.emit(key)

    def select(self, key: str) -> None:
        if key in self._btns and self._btns[key].isEnabled():
            self._on_click(key)


# ══════════════════════════════════════════════════════════════════════════════
#  RIGHT SUMMARY PANEL  (PRD §3 right — always visible)
# ══════════════════════════════════════════════════════════════════════════════

class SummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setStyleSheet(f"background: {C_LIGHT_GRAY};")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(10)

        # ── Well Summary card ──────────────────────────────────────────────
        ws_card, ws_lay = _card("🛢  Well Summary")
        ws_lay.setSpacing(6)

        self._ws_rows: dict[str, QLabel] = {}
        ws_fields = [
            ("Pr",           "psia"),
            ("Pb",           "psia"),
            ("THP",          "psia"),
            ("GOR",          "scf/STB"),
            ("Water Cut",    "frac"),
            ("Tubing ID",    "in"),
            ("Correlation",  ""),
        ]
        for field, unit in ws_fields:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(4)
            fl = QLabel(field)
            fl.setObjectName("field_label")
            fl.setFixedWidth(70)
            rh.addWidget(fl)
            vl = QLabel("—")
            vl.setStyleSheet(
                f"color:{C_DEEP_BLUE}; font-weight:600; "
                "background:transparent; font-size:11px;")
            self._ws_rows[field] = vl
            rh.addWidget(vl, 1)
            if unit:
                ul = QLabel(unit)
                ul.setStyleSheet(
                    f"color:{C_SLATE}; font-size:9px; background:transparent;")
                rh.addWidget(ul)
            ws_lay.addWidget(row_w)
        root.addWidget(ws_card)

        # ── Results card ──────────────────────────────────────────────────
        res_card, res_lay = _card("🎯  Results")
        res_lay.setSpacing(6)
        self._res_rows: dict[str, QLabel] = {}
        res_fields = [
            ("Op. Rate",  "STB/d"),
            ("Op. Pwf",   "psia"),
            ("PI (J)",    "STB/d/psi"),
            ("Drawdown",  "psia"),
            ("Status",    ""),
        ]
        for field, unit in res_fields:
            row_w2 = QWidget()
            row_w2.setStyleSheet("background:transparent;")
            rh2 = QHBoxLayout(row_w2)
            rh2.setContentsMargins(0, 0, 0, 0)
            rh2.setSpacing(4)
            fl2 = QLabel(field)
            fl2.setObjectName("field_label")
            fl2.setFixedWidth(70)
            rh2.addWidget(fl2)
            vl2 = QLabel("—")
            vl2.setStyleSheet(
                f"color:{C_DEEP_BLUE}; font-weight:600; "
                "background:transparent; font-size:11px;")
            self._res_rows[field] = vl2
            rh2.addWidget(vl2, 1)
            if unit:
                ul2 = QLabel(unit)
                ul2.setStyleSheet(
                    f"color:{C_SLATE}; font-size:9px; background:transparent;")
                rh2.addWidget(ul2)
            res_lay.addWidget(row_w2)
        root.addWidget(res_card)

        # ── Well Digital Twin ──────────────────────────────────────────────
        twin_card, twin_lay = _card("🏗  Digital Twin")
        self.twin = WellDigitalTwin()
        twin_lay.addWidget(self.twin)
        root.addWidget(twin_card)

        root.addStretch()
        _store.changed.connect(self._on_store_change)
        self._on_store_change()

    def _on_store_change(self) -> None:
        tid_in = _store.get("tubing_id") * 12  # convert ft → in
        corr = _store.get("model") or "—"
        self._ws_rows["Pr"].setText(f"{_store.get('Pr'):.0f}")
        self._ws_rows["Pb"].setText(f"{_store.get('Pb'):.0f}")
        self._ws_rows["THP"].setText(f"{_store.get('thp'):.0f}")
        self._ws_rows["GOR"].setText(f"{_store.get('gor'):.0f}")
        self._ws_rows["Water Cut"].setText(f"{_store.get('wc'):.2f}")
        self._ws_rows["Tubing ID"].setText(f"{tid_in:.3f}")
        self._ws_rows["Correlation"].setText(corr[:14])

    def update_results(self, data: dict) -> None:
        sol = data.get("sol", {})
        p = data.get("params", {})
        if sol.get("success"):
            q = sol["operating_rate"]
            pw = sol["operating_pwf"]
            pr = p.get("Pr", _store.get("Pr"))
            ipr = _build_ipr(p)
            j = ipr.J if hasattr(ipr, "J") else 0.0
            dd = pr - pw
            self._res_rows["Op. Rate"].setText(f"{q:.1f}")
            self._res_rows["Op. Pwf"].setText(f"{pw:.1f}")
            self._res_rows["PI (J)"].setText(f"{j:.4f}")
            self._res_rows["Drawdown"].setText(f"{dd:.1f}")
            self._res_rows["Status"].setText("✅ Stable")
            self._res_rows["Status"].setStyleSheet(
                f"color:{C_SUCCESS}; font-weight:700; background:transparent;")
        else:
            for k in self._res_rows:
                self._res_rows[k].setText("—")
            self._res_rows["Status"].setText("⚠️ No solution")
            self._res_rows["Status"].setStyleSheet(
                f"color:{C_WARNING}; font-weight:700; background:transparent;")


# ══════════════════════════════════════════════════════════════════════════════
#  TITLE BAR  (PRD §13 — upgraded)
# ══════════════════════════════════════════════════════════════════════════════

class TitleBar(QWidget):
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(54)
        self.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C_NAVY}, stop:0.5 {C_DEEP_BLUE}, stop:1 #1a5276);"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(10)

        # Logo
        logo = QLabel("⚡")
        logo.setStyleSheet(
            f"color:{C_CYAN}; font-size:20px; background:transparent;")
        lay.addWidget(logo)

        # App name
        name = QLabel("FlowNexus IPM")
        name.setStyleSheet(
            "color:#FFFFFF; font-size:15pt; font-weight:800; background:transparent;")
        lay.addWidget(name)

        # Version pill
        ver = _pill("v2.0", C_CYAN, C_NAVY)
        lay.addWidget(ver)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background:{C_ROYAL_BLUE}; max-width:1px; margin:8px 4px;")
        lay.addWidget(sep)

        # Project name (editable on double-click)
        self.proj_lbl = QLabel("Untitled Project")
        self.proj_lbl.setStyleSheet(
            "color:#90CAF9; font-size:11pt; background:transparent; "
            "font-style:italic;")
        lay.addWidget(self.proj_lbl)

        lay.addStretch()

        # Unit toggle stub
        self.unit_btn = QPushButton("🔄  Field Units")
        self.unit_btn.setObjectName("sec_btn")
        self.unit_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.12); color:#90CAF9; "
            "border: 1px solid rgba(255,255,255,0.25); border-radius:8px; "
            "padding:5px 14px; font-size:11px; font-weight:600; }"
            "QPushButton:hover { background: rgba(255,255,255,0.2); }")
        self.unit_btn.setToolTip("SI ↔ Field unit conversion (coming soon)")
        lay.addWidget(self.unit_btn)

        # Save button
        self.save_btn = QPushButton("💾  Save")
        self.save_btn.setStyleSheet(
            "QPushButton { background: rgba(0,188,212,0.18); color:#80DEEA; "
            "border: 1px solid rgba(0,188,212,0.4); border-radius:8px; "
            "padding:5px 14px; font-size:11px; font-weight:600; }"
            "QPushButton:hover { background: rgba(0,188,212,0.35); }")
        self.save_btn.clicked.connect(self.save_requested.emit)
        lay.addWidget(self.save_btn)

        # Load button
        self.load_btn = QPushButton("📂  Load")
        self.load_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.10); color:#CFD8DC; "
            "border: 1px solid rgba(255,255,255,0.2); border-radius:8px; "
            "padding:5px 14px; font-size:11px; font-weight:600; }"
            "QPushButton:hover { background: rgba(255,255,255,0.2); }")
        self.load_btn.clicked.connect(self.load_requested.emit)
        lay.addWidget(self.load_btn)

    def set_project(self, name: str) -> None:
        self.proj_lbl.setText(name)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE  (PRD §13 — landing page)
# ══════════════════════════════════════════════════════════════════════════════

class DashboardPage(QWidget):
    navigate_to = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Header
        hdr = QLabel("Welcome to FlowNexus IPM")
        hdr.setStyleSheet(
            f"color:{C_DEEP_BLUE}; font-size:22px; font-weight:800; "
            "background:transparent;")
        root.addWidget(hdr)

        sub = QLabel("Integrated Production Modelling & Nodal Analysis Platform  —  v2.0")
        sub.setStyleSheet(
            f"color:{C_SLATE}; font-size:11px; background:transparent;")
        root.addWidget(sub)

        # Main content row
        content_row = QHBoxLayout()
        content_row.setSpacing(16)

        # ── Quick Start / Navigation Flow ─────────────────────────────────
        flow_card, flow_lay = _card("🚀  Workflow Guide")
        steps = [
            ("1", "IPR",         "Set up reservoir inflow model",  "IPR"),
            ("2", "PVT",         "Configure fluid properties",     "PVT"),
            ("3", "VLP",         "Define wellbore / VLP model",    "VLP"),
            ("4", "Nodal",       "Run Nodal Analysis",             "Nodal"),
            ("5", "Sensitivity", "Multi-variable sensitivity",     "Sensitivity"),
        ]
        for num, title, desc, key in steps:
            step_w = QWidget()
            step_w.setStyleSheet("background:transparent;")
            sh = QHBoxLayout(step_w)
            sh.setContentsMargins(0, 2, 0, 2)
            sh.setSpacing(10)

            num_lbl = QLabel(num)
            num_lbl.setFixedSize(28, 28)
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num_lbl.setStyleSheet(
                f"background:{C_ROYAL_BLUE}; color:#FFF; border-radius:14px; "
                "font-weight:800; font-size:11px;")
            sh.addWidget(num_lbl)

            txt_col = QVBoxLayout()
            txt_col.setSpacing(0)
            t1 = QLabel(title)
            t1.setStyleSheet(
                f"color:{C_DEEP_BLUE}; font-weight:700; background:transparent;")
            t2 = QLabel(desc)
            t2.setStyleSheet(
                f"color:{C_SLATE}; font-size:10px; background:transparent;")
            txt_col.addWidget(t1)
            txt_col.addWidget(t2)
            sh.addLayout(txt_col, 1)

            go_btn = QPushButton("→")
            go_btn.setObjectName("sec_btn")
            go_btn.setFixedSize(32, 28)
            go_btn.clicked.connect(lambda _, k=key: self.navigate_to.emit(k))
            sh.addWidget(go_btn)

            flow_lay.addWidget(step_w)

        content_row.addWidget(flow_card, 1)

        # ── Engineering Templates ──────────────────────────────────────────
        tpl_card, tpl_lay = _card("📋  Engineering Templates")
        tpl_desc = QLabel("One-click loading of preset well configurations")
        tpl_desc.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent;")
        tpl_lay.addWidget(tpl_desc)

        templates = [
            ("🛢  Light Oil",      "Light Oil",      C_ROYAL_BLUE),
            ("⚫  Heavy Oil",      "Heavy Oil",      "#5D4037"),
            ("💨  Gas Condensate", "Gas Condensate", C_CYAN),
            ("💧  Water Producer", "Water Producer", C_SUCCESS),
        ]
        for label, key, col in templates:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background:{col}; color:#FFF; border:none; "
                f"border-radius:8px; padding:8px 12px; font-weight:700; "
                f"font-size:11px; text-align:left; }}"
                f"QPushButton:hover {{ opacity: 0.85; }}")
            btn.clicked.connect(lambda _, k=key: _store.load_template(k))
            tpl_lay.addWidget(btn)

        content_row.addWidget(tpl_card, 1)

        # ── Recent Cases ───────────────────────────────────────────────────
        rec_card, rec_lay = _card("🕒  Recent Cases")
        self._recent_lay = rec_lay
        no_rec = QLabel("No recent projects.\nSave a project to see it here.")
        no_rec.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent;")
        no_rec.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_lay.addWidget(no_rec)
        rec_lay.addStretch()
        content_row.addWidget(rec_card, 1)

        root.addLayout(content_row, 1)

        # ── Footer strip ───────────────────────────────────────────────────
        footer = QLabel(
            "FlowNexus IPM v2.0  |  Petroleum Engineering Nodal Analysis Platform  "
            "|  All calculations: core/ engine")
        footer.setStyleSheet(
            f"color:{C_SLATE}; font-size:9px; background:transparent;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(footer)


# ══════════════════════════════════════════════════════════════════════════════
#  IPR MODULE PAGE
# ══════════════════════════════════════════════════════════════════════════════

class IprPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self._warn_visible = False

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Left: input panel ──────────────────────────────────────────────
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(310)
        left.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        left_w = QWidget()
        left_w.setStyleSheet("background: transparent;")
        left_v = QVBoxLayout(left_w)
        left_v.setContentsMargins(0, 0, 8, 0)
        left_v.setSpacing(10)

        # Model card
        model_card, model_lay = _card("⚙️  IPR Model")
        self.model_cb = QComboBox()
        view = QListView()
        view.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.model_cb.setView(view)
        self.model_cb.addItems(["Composite", "Vogel", "Darcy"])
        model_lay.addWidget(_row("Model", self.model_cb))
        left_v.addWidget(model_card)

        # Inputs card
        inp_card, inp_lay = _card("📥  Reservoir Inputs")
        self.pr  = _dspin(2500.0, 0, 20000, 50, 2)
        self.pb  = _dspin(1800.0, 0, 20000, 50, 2)
        self.pwf = _dspin(1200.0, 0, 20000, 50, 2)
        self.qt  = _dspin(800.0,  0, 50000, 50, 2)
        inp_lay.addWidget(_row("Pr", self.pr, "psia"))
        self._pb_row = _row("Pb (bubble pt)", self.pb, "psia")
        inp_lay.addWidget(self._pb_row)
        inp_lay.addWidget(_row("Pwf (test)", self.pwf, "psia"))
        inp_lay.addWidget(_row("Qo (test)", self.qt, "STB/d"))

        # Validation warning
        self._warn_lbl = QLabel("⚠️  Pb cannot exceed Pr")
        self._warn_lbl.setObjectName("warning_label")
        self._warn_lbl.setVisible(False)
        inp_lay.addWidget(self._warn_lbl)
        left_v.addWidget(inp_card)

        # Outputs card
        out_card, out_lay = _card("📊  Live IPR Results")
        self.aof_lbl = QLabel("—")
        self.aof_lbl.setObjectName("ro_label")
        self.pi_lbl  = QLabel("—")
        self.pi_lbl.setObjectName("ro_label")
        self.qbp_lbl = QLabel("—")
        self.qbp_lbl.setObjectName("ro_label")
        out_lay.addWidget(_row("AOF",      self.aof_lbl, "STB/d"))
        out_lay.addWidget(_row("PI (J)",   self.pi_lbl,  "STB/d/psi"))
        out_lay.addWidget(_row("q @ Pb",   self.qbp_lbl, "STB/d"))
        left_v.addWidget(out_card)

        left_v.addStretch()
        left.setWidget(left_w)
        root.addWidget(left)

        # ── Right: chart ───────────────────────────────────────────────────
        chart_card, chart_lay = _card("📈  IPR Curve")
        self.fig = Figure(facecolor=C_WHITE)
        self.ax  = self.fig.add_subplot(111)
        self._init_ax()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{C_WHITE};")
        self.toolbar = NavToolbar(self.canvas, self)
        self.toolbar.setStyleSheet(
            f"QToolBar {{ background:{C_LIGHT_GRAY}; border:none; }}"
            "QToolButton { background:transparent; border-radius:4px; padding:2px; }"
            f"QToolButton:hover {{ background:{C_CYAN_LIGHT}; }}")
        chart_lay.addWidget(self.toolbar)
        chart_lay.addWidget(self.canvas, 1)
        root.addWidget(chart_card, 1)

        # ── Signals ────────────────────────────────────────────────────────
        for sp in [self.pr, self.pb, self.pwf, self.qt]:
            sp.valueChanged.connect(self._live)
        self.model_cb.currentIndexChanged.connect(self._on_model)
        _store.changed.connect(self._sync_from_store)
        self._syncing = False
        self._sync_from_store()
        self._on_model()

    def _init_ax(self) -> None:
        ax = self.ax
        ax.set_facecolor("#FAFCFF")
        ax.set_xlabel("Liquid Rate, q  (STB/day)", fontsize=11, color=C_INK, labelpad=8)
        ax.set_ylabel("Bottomhole Flowing Pressure, Pwf  (psia)", fontsize=11, color=C_INK, labelpad=8)
        ax.set_title("Inflow Performance Relationship (IPR)", fontsize=13,
                     fontweight="bold", color=C_DEEP_BLUE, pad=10)
        ax.grid(True, linestyle="--", alpha=0.35, color=C_GRAY_MID, linewidth=0.7)
        ax.tick_params(colors=C_INK, labelsize=10)
        for sp in ax.spines.values():
            sp.set_edgecolor(C_BORDER)
        self.fig.tight_layout(pad=1.8)

    def _on_model(self) -> None:
        darcy = self.model_cb.currentText() == "Darcy"
        self._pb_row.setVisible(not darcy)
        self._live()

    def _live(self) -> None:
        # Validate Pb < Pr
        if self.pb.value() > self.pr.value():
            self._warn_lbl.setVisible(True)
        else:
            self._warn_lbl.setVisible(False)

        # Push to store
        if not self._syncing:
            _store.update({
                "Pr": self.pr.value(), "Pb": self.pb.value(),
                "Qo_test": self.qt.value(), "Pwf_test": self.pwf.value(),
                "ipr_model": self.model_cb.currentText(),
            })

        # Live AOF / PI
        try:
            model_txt = self.model_cb.currentText()
            if model_txt == "Composite":
                ipr = composite_ipr(Pr=self.pr.value(), Pb=self.pb.value(),
                                    q_test=self.qt.value(), Pwf_test=self.pwf.value())
            elif model_txt == "Darcy":
                ipr = darcy_ipr(Pr=self.pr.value(), Pb=self.pr.value() * 1.001,
                                q_test=self.qt.value(), Pwf_test=self.pwf.value())
            elif model_txt == "Vogel":
                ipr = vogel_ipr(Pr=self.pr.value(), Pb=self.pb.value(),
                                q_test=self.qt.value(), Pwf_test=self.pwf.value())
            else:
                ipr = composite_ipr(Pr=self.pr.value(), Pb=self.pb.value(),
                                    q_test=self.qt.value(), Pwf_test=self.pwf.value())

            self.aof_lbl.setText(f"{ipr.q_max:.1f}")
            self.pi_lbl.setText(f"{ipr.J:.4f}")
            qbp = getattr(ipr, "q_bp", 0.0)
            self.qbp_lbl.setText(f"{qbp:.1f}")
            self._draw_ipr(ipr)
        except Exception:
            self.aof_lbl.setText("—")
            self.pi_lbl.setText("—")
            self.qbp_lbl.setText("—")

    def _draw_ipr(self, ipr) -> None:
        self.ax.clear()
        self._init_ax()
        rates = np.linspace(0, ipr.q_max, 200)
        pwfs  = [ipr.calculate_Pwf(float(q)) for q in rates]
        self.ax.plot(rates, pwfs, color=C_RED, linewidth=2.5,
                     solid_capstyle="round", label="IPR Curve")
        self.ax.fill_between(rates, pwfs, alpha=0.07, color=C_RED)

        # Bubble point marker
        pb = getattr(ipr, "Pb", None)
        qbp = getattr(ipr, "q_bp", None)
        if pb and qbp:
            self.ax.axhline(pb, color=C_ROYAL_BLUE, linestyle="--",
                            linewidth=1, alpha=0.6, label="Bubble Point")
            self.ax.plot(qbp, pb, marker="D", markersize=7,
                         color=C_ROYAL_BLUE, zorder=9, linestyle="None",
                         markeredgecolor=C_NAVY, markeredgewidth=0.8)

        # Test point
        self.ax.plot(self.qt.value(), self.pwf.value(),
                     marker="o", markersize=8, color=C_GOLD, zorder=10,
                     linestyle="None", markeredgecolor="#C67C00",
                     markeredgewidth=0.8, label="Test Point")

        # AOF annotation
        self.ax.annotate(
            f"AOF = {ipr.q_max:.0f} STB/d",
            xy=(ipr.q_max, 0), xytext=(ipr.q_max * 0.75, ipr.Pr * 0.1),
            fontsize=9, color=C_DEEP_BLUE,
            arrowprops=dict(arrowstyle="->", color=C_DEEP_BLUE, lw=1.2))

        if rates.size > 0:
            self.ax.set_xlim(0, max(rates) * 1.08)
        self.ax.set_ylim(0, max(ipr.Pr * 1.08, 1.0))
        self.ax.legend(fontsize=9, loc="upper right",
                       framealpha=0.9, edgecolor=C_BORDER)
        self.canvas.draw_idle()

    def _sync_from_store(self) -> None:
        self._syncing = True
        self.pr.setValue(_store.get("Pr"))
        self.pb.setValue(_store.get("Pb"))
        self.pwf.setValue(_store.get("Pwf_test"))
        self.qt.setValue(_store.get("Qo_test"))
        idx = self.model_cb.findText(_store.get("ipr_model"))
        if idx >= 0:
            self.model_cb.setCurrentIndex(idx)
        self._syncing = False


# ══════════════════════════════════════════════════════════════════════════════
#  PVT MODULE PAGE
# ══════════════════════════════════════════════════════════════════════════════

class PvtPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Left: input cards ─────────────────────────────────────────────
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(360)
        left.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        left_w = QWidget()
        left_w.setStyleSheet("background: transparent;")
        left_v = QVBoxLayout(left_w)
        left_v.setContentsMargins(0, 0, 8, 0)
        left_v.setSpacing(10)

        # Oil card
        oil_card, oil_lay = _card("🛢  Oil Properties")
        self.sg_o = _dspin(0.850, 0.50, 1.10, 0.005, 3)
        self.pb_pvt = _dspin(1800.0, 0, 20000, 50, 2)
        self.gor = _dspin(500.0, 0, 10000, 10, 1)
        self.api_lbl = QLabel("—")
        self.api_lbl.setObjectName("ro_label")
        oil_lay.addWidget(_row("SG Oil", self.sg_o, "(w=1)"))
        oil_lay.addWidget(_row("API Gravity", self.api_lbl, "°API"))
        oil_lay.addWidget(_row("Bubble Pt", self.pb_pvt, "psia"))
        oil_lay.addWidget(_row("GOR", self.gor, "scf/STB"))
        left_v.addWidget(oil_card)

        # Gas card
        gas_card, gas_lay = _card("💨  Gas Properties")
        self.sg_g = _dspin(0.650, 0.35, 1.50, 0.005, 3)
        gas_lay.addWidget(_row("SG Gas", self.sg_g, "(air=1)"))
        left_v.addWidget(gas_card)

        # Water card
        water_card, water_lay = _card("💧  Water Properties")
        self.sg_w = _dspin(1.070, 0.90, 1.20, 0.005, 3)
        self.wc   = _dspin(0.330, 0.0,  1.0,  0.01,  3)
        water_lay.addWidget(_row("SG Water", self.sg_w, "(w=1)"))
        water_lay.addWidget(_row("Water Cut", self.wc, "fraction"))
        left_v.addWidget(water_card)

        left_v.addStretch()
        left.setWidget(left_w)
        root.addWidget(left)

        # ── Right: Live PVT table + override ─────────────────────────────
        right_v = QVBoxLayout()
        right_v.setSpacing(10)

        pvt_card, pvt_lay = _card("📊  Live PVT Properties")

        desc = QLabel(
            "Properties calculated at Bubble Point conditions. "
            "Check ✏ to override with a user value.")
        desc.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent;")
        desc.setWordWrap(True)
        pvt_lay.addWidget(desc)

        self._pvt_table = QTableWidget(8, 3)
        self._pvt_table.setHorizontalHeaderLabels(["Property", "Calculated", "User Override"])
        self._pvt_table.setAlternatingRowColors(True)
        self._pvt_table.verticalHeader().setVisible(False)
        self._pvt_table.horizontalHeader().setStretchLastSection(True)
        self._pvt_table.setMinimumHeight(260)
        pvt_props = ["Rs  (scf/STB)", "Bo  (RB/STB)", "Bg  (RB/Mscf)",
                     "Bw  (RB/STB)", "μo  (cp)", "μg  (cp)", "μw  (cp)", "Z-factor"]
        for i, prop in enumerate(pvt_props):
            self._pvt_table.setItem(i, 0, QTableWidgetItem(prop))
            self._pvt_table.setItem(i, 1, QTableWidgetItem("—"))
            override = QWidget()
            oh = QHBoxLayout(override)
            oh.setContentsMargins(4, 2, 4, 2)
            oh.setSpacing(4)
            chk = QCheckBox()
            val_edit = QLineEdit()
            val_edit.setPlaceholderText("user value")
            val_edit.setEnabled(False)
            chk.toggled.connect(val_edit.setEnabled)
            oh.addWidget(chk)
            oh.addWidget(val_edit, 1)
            self._pvt_table.setCellWidget(i, 2, override)
        pvt_lay.addWidget(self._pvt_table)

        calc_btn = QPushButton("🔄  Recalculate PVT")
        calc_btn.setObjectName("run_btn")
        calc_btn.clicked.connect(self._calc_pvt)
        pvt_lay.addWidget(calc_btn, alignment=Qt.AlignmentFlag.AlignRight)

        right_v.addWidget(pvt_card, 1)
        root.addLayout(right_v, 1)

        # Signals
        for sp in [self.sg_o, self.sg_g, self.sg_w, self.wc, self.pb_pvt, self.gor]:
            sp.valueChanged.connect(self._live)
        self.sg_o.valueChanged.connect(self._update_api)
        _store.changed.connect(self._sync_from_store)
        self._syncing = False
        self._sync_from_store()
        self._update_api()

    def _update_api(self) -> None:
        sg = self.sg_o.value()
        self.api_lbl.setText(f"{141.5 / sg - 131.5:.1f}" if sg > 0 else "—")

    def _live(self) -> None:
        if not self._syncing:
            _store.update({
                "sg_oil": self.sg_o.value(), "sg_gas": self.sg_g.value(),
                "sg_water": self.sg_w.value(), "wc": self.wc.value(),
                "gor": self.gor.value(), "Pb": self.pb_pvt.value(),
            })

    def _sync_from_store(self) -> None:
        self._syncing = True
        self.sg_o.setValue(_store.get("sg_oil"))
        self.sg_g.setValue(_store.get("sg_gas"))
        self.sg_w.setValue(_store.get("sg_water"))
        self.wc.setValue(_store.get("wc"))
        self.gor.setValue(_store.get("gor"))
        self.pb_pvt.setValue(_store.get("Pb"))
        self._syncing = False

    def _calc_pvt(self) -> None:
        try:
            pvt = BlackOilPVT(
                sg_gas=self.sg_g.value(), sg_oil=self.sg_o.value(),
                sg_water=self.sg_w.value(), watercut=self.wc.value()
            )
            Rsb = self.gor.value()
            Pb  = self.pb_pvt.value()
            T   = _store.get("T_bh")
            fp  = pvt.fluid_properties_dict(Pb, T, Rsb, self.gor.value(), Pb)
            keys = ["Rs", "Bo", "Bg", "Bw", "oil_viscosity",
                    "gas_viscosity", "water_viscosity", "Z"]
            for i, k in enumerate(keys):
                val = fp.get(k, fp.get(k.lower(), "—"))
                item = QTableWidgetItem(f"{val:.4f}" if isinstance(val, float) else str(val))
                self._pvt_table.setItem(i, 1, item)
        except Exception as e:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  VLP MODULE PAGE
# ══════════════════════════════════════════════════════════════════════════════

class VlpPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self._last_worker = None

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Left: input panel ─────────────────────────────────────────────
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(310)
        left.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        left_w = QWidget()
        left_w.setStyleSheet("background: transparent;")
        left_v = QVBoxLayout(left_w)
        left_v.setContentsMargins(0, 0, 8, 0)
        left_v.setSpacing(10)

        model_card, model_lay = _card("⚙️  VLP Model")
        self.model_cb = QComboBox()
        view = QListView()
        view.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.model_cb.setView(view)
        self.model_cb.addItems(["Hagedron-Brown", "Beggs and Brill"])
        model_lay.addWidget(_row("Correlation", self.model_cb))
        left_v.addWidget(model_card)

        geo_card, geo_lay = _card("📐  Well Geometry")
        self.tid   = _dspin(2.441, 0.5, 6.0, 0.1, 3)
        self.tod   = _dspin(2.875, 0.5, 7.0, 0.1, 3)
        self.cid   = _dspin(5.500, 1.0, 20.0, 0.1, 3)
        self.rough = _dspin(0.0,   0.0, 1.0, 0.0001, 5)
        self.theta = _dspin(0.0,   0.0, 90.0, 1.0, 1)
        geo_lay.addWidget(_row("Tubing ID", self.tid, "in"))
        geo_lay.addWidget(_row("Tubing OD", self.tod, "in"))
        geo_lay.addWidget(_row("Casing ID", self.cid, "in"))
        geo_lay.addWidget(_row("Roughness", self.rough, "in"))
        geo_lay.addWidget(_row("Deviation", self.theta, "°"))
        left_v.addWidget(geo_card)

        cond_card, cond_lay = _card("🌡  Well Conditions")
        self.thp   = _dspin(150.0,  0, 5000, 10, 1)
        self.depth = _dspin(6000.0, 100, 30000, 50, 1)
        self.t_sf  = _dspin(100.0, -20, 300, 1, 1)
        self.t_bh  = _dspin(200.0, 50, 500, 1, 1)
        cond_lay.addWidget(_row("THP",       self.thp,   "psia"))
        cond_lay.addWidget(_row("TVD",       self.depth, "ft"))
        cond_lay.addWidget(_row("T Surface", self.t_sf,  "°F"))
        cond_lay.addWidget(_row("T BH",      self.t_bh,  "°F"))
        left_v.addWidget(cond_card)

        flow_card, flow_lay = _card("💧  Flow Parameters")
        self.qmin  = _dspin(10.0,   1, 1000, 10, 1)
        self.qmax  = _dspin(3000.0, 100, 50000, 100, 1)
        self.qstep = _dspin(50.0,   1, 500, 10, 1)
        self.dz    = _dspin(200.0,  10, 1000, 10, 1)
        flow_lay.addWidget(_row("q min",   self.qmin,  "STB/d"))
        flow_lay.addWidget(_row("q max",   self.qmax,  "STB/d"))
        flow_lay.addWidget(_row("q step",  self.qstep, "STB/d"))
        flow_lay.addWidget(_row("dz step", self.dz,    "ft"))
        left_v.addWidget(flow_card)

        run_vlp_btn = QPushButton("▶  Generate VLP Curve")
        run_vlp_btn.setObjectName("run_btn")
        run_vlp_btn.clicked.connect(self._run_vlp)
        left_v.addWidget(run_vlp_btn)
        self._run_vlp_btn = run_vlp_btn

        left_v.addStretch()
        left.setWidget(left_w)
        root.addWidget(left)

        # ── Right: chart ───────────────────────────────────────────────────
        chart_card, chart_lay = _card("📈  VLP Curve")
        self.fig = Figure(facecolor=C_WHITE)
        self.ax  = self.fig.add_subplot(111)
        self._init_ax()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{C_WHITE};")
        self.toolbar = NavToolbar(self.canvas, self)
        self.toolbar.setStyleSheet(
            f"QToolBar {{ background:{C_LIGHT_GRAY}; border:none; }}"
            "QToolButton { background:transparent; border-radius:4px; padding:2px; }"
            f"QToolButton:hover {{ background:{C_CYAN_LIGHT}; }}")
        chart_lay.addWidget(self.toolbar)
        chart_lay.addWidget(self.canvas, 1)
        root.addWidget(chart_card, 1)

        # Signals
        for sp in [self.tid, self.tod, self.cid, self.rough, self.theta,
                   self.thp, self.depth, self.t_sf, self.t_bh,
                   self.qmin, self.qmax, self.qstep, self.dz]:
            sp.valueChanged.connect(self._push_store)
        self.model_cb.currentIndexChanged.connect(self._push_store)
        _store.changed.connect(self._sync_from_store)
        self._syncing = False
        self._sync_from_store()

    def _init_ax(self) -> None:
        self.ax.set_facecolor("#FAFCFF")
        self.ax.set_xlabel("Liquid Rate, q  (STB/day)", fontsize=11, color=C_INK)
        self.ax.set_ylabel("Bottomhole Flowing Pressure, Pwf  (psia)", fontsize=11, color=C_INK)
        self.ax.set_title("Vertical Lift Performance (VLP)", fontsize=13,
                          fontweight="bold", color=C_DEEP_BLUE, pad=10)
        self.ax.grid(True, linestyle="--", alpha=0.35, color=C_GRAY_MID, linewidth=0.7)
        self.ax.tick_params(colors=C_INK, labelsize=10)
        for sp in self.ax.spines.values():
            sp.set_edgecolor(C_BORDER)
        self.fig.tight_layout(pad=1.8)

    def _push_store(self) -> None:
        if not self._syncing:
            _store.update({
                "model":     self.model_cb.currentText(),
                "tubing_id": self.tid.value() / 12,
                "tubing_od": self.tod.value() / 12,
                "casing_id": self.cid.value() / 12,
                "roughness": self.rough.value() / 12,
                "theta":     self.theta.value(),
                "thp":       self.thp.value(),
                "depth":     self.depth.value(),
                "T_surface": self.t_sf.value(),
                "T_bh":      self.t_bh.value(),
                "q_min":     self.qmin.value(),
                "q_max":     self.qmax.value(),
                "q_step":    self.qstep.value(),
                "dz_step":   self.dz.value(),
            })

    def _sync_from_store(self) -> None:
        self._syncing = True
        self.tid.setValue(_store.get("tubing_id") * 12)
        self.tod.setValue(_store.get("tubing_od") * 12)
        self.cid.setValue(_store.get("casing_id") * 12)
        self.rough.setValue(_store.get("roughness") * 12)
        self.theta.setValue(_store.get("theta"))
        self.thp.setValue(_store.get("thp"))
        self.depth.setValue(_store.get("depth"))
        self.t_sf.setValue(_store.get("T_surface"))
        self.t_bh.setValue(_store.get("T_bh"))
        self.qmin.setValue(_store.get("q_min"))
        self.qmax.setValue(_store.get("q_max"))
        self.qstep.setValue(_store.get("q_step"))
        self.dz.setValue(_store.get("dz_step"))
        idx = self.model_cb.findText(_store.get("model"))
        if idx >= 0:
            self.model_cb.setCurrentIndex(idx)
        self._syncing = False

    def _run_vlp(self) -> None:
        self._push_store()
        self._run_vlp_btn.setEnabled(False)
        p = _store.all_values()
        worker = _VlpOnlyWorker(p)
        worker.signals.result.connect(self._on_vlp_done)
        worker.signals.error.connect(lambda e: self._run_vlp_btn.setEnabled(True))
        QThreadPool.globalInstance().start(worker)

    def _on_vlp_done(self, result: dict) -> None:
        self._run_vlp_btn.setEnabled(True)
        rates, pwfs = result["rates"], result["pwfs"]
        self.ax.clear()
        self._init_ax()
        self.ax.plot(rates, pwfs, color=C_ROYAL_BLUE, linewidth=2.5,
                     solid_capstyle="round", label="VLP Curve")
        self.ax.fill_between(rates, pwfs, alpha=0.07, color=C_ROYAL_BLUE)
        if rates:
            self.ax.set_xlim(0, max(rates) * 1.08)
        if pwfs:
            self.ax.set_ylim(0, max(pwfs) * 1.08)
        self.ax.legend(fontsize=9, framealpha=0.9, edgecolor=C_BORDER)
        self.canvas.draw_idle()


class _VlpOnlyWorker(QRunnable):
    def __init__(self, p: dict) -> None:
        super().__init__()
        self.p = p
        self.signals = _Signals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            p = self.p
            _, vlp = _build_pvt_vlp(p)
            n = max(int((p["q_max"] - p["q_min"]) / p["q_step"]) + 1, 20)
            rates = np.linspace(p["q_min"], p["q_max"], n).tolist()
            pwfs  = [_vlp_pwf(vlp, p, float(q)) for q in rates]
            self.signals.result.emit({"rates": rates, "pwfs": pwfs})
        except Exception:
            self.signals.error.emit(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
#  NODAL ANALYSIS PAGE  (PRD §8 — 4-tab output panel)
# ══════════════════════════════════════════════════════════════════════════════

class NodalPage(QWidget):
    result_ready = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self._last_data: dict | None = None
        self._pool = QThreadPool.globalInstance()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Header row ─────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(10)

        self.run_btn = QPushButton("▶  Run Nodal Analysis")
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self._run)
        hdr_row.addWidget(self.run_btn)

        self.export_btn = QPushButton("💾  Export CSV")
        self.export_btn.setObjectName("sec_btn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_csv)
        hdr_row.addWidget(self.export_btn)

        self.pdf_btn = QPushButton("📄  Export PDF (soon)")
        self.pdf_btn.setObjectName("sec_btn")
        self.pdf_btn.setEnabled(False)
        self.pdf_btn.setToolTip("PDF report generator — coming soon")
        hdr_row.addWidget(self.pdf_btn)

        hdr_row.addStretch()

        self._status_lbl = QLabel("Configure inputs in IPR / PVT / VLP tabs, then click Run.")
        self._status_lbl.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent;")
        hdr_row.addWidget(self._status_lbl)
        root.addLayout(hdr_row)

        # ── Main split: chart | tabs ───────────────────────────────────────
        spl = QSplitter(Qt.Orientation.Horizontal)
        spl.setHandleWidth(3)

        # Left: IPR-VLP chart
        left_card, left_lay = _card("📈  IPR × VLP — Nodal Plot")
        self.fig = Figure(facecolor=C_WHITE)
        self.ax  = self.fig.add_subplot(111)
        self._init_ax()
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{C_WHITE};")
        self.toolbar = NavToolbar(self.canvas, self)
        self.toolbar.setStyleSheet(
            f"QToolBar {{ background:{C_LIGHT_GRAY}; border:none; }}"
            "QToolButton { background:transparent; border-radius:4px; }"
            f"QToolButton:hover {{ background:{C_CYAN_LIGHT}; }}")
        left_lay.addWidget(self.toolbar)
        left_lay.addWidget(self.canvas, 1)

        # Hover tooltip
        self._tip = QLabel("", self.canvas)
        self._tip.setStyleSheet(
            "background:rgba(13,43,85,0.88); color:white; "
            "border-radius:5px; padding:3px 8px; font-size:11px;")
        self._tip.hide()
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.canvas.mpl_connect("axes_leave_event", lambda _e: self._tip.hide())

        # Mini-map
        self.mini = MiniMap(left_card)
        self.mini.raise_()
        left_card.resizeEvent = lambda ev: self._reposition_mini(left_card)
        spl.addWidget(left_card)

        # Right: tab container
        right_tab = QTabWidget()
        right_tab.setMinimumWidth(360)

        # Tab 1: Operating Point Summary
        op_tab = QWidget()
        op_tab.setStyleSheet("background: transparent;")
        op_v = QVBoxLayout(op_tab)
        op_v.setContentsMargins(14, 14, 14, 14)
        op_v.setSpacing(10)

        self._op_labels: dict[str, QLabel] = {}
        op_fields = [
            ("Operating Rate", "STB/d"), ("Operating Pwf",  "psia"),
            ("Drawdown",       "psia"),  ("PI (J)",          "STB/d/psi"),
            ("AOF",            "STB/d"), ("Stability",       ""),
        ]
        for field, unit in op_fields:
            rw = QWidget()
            rw.setStyleSheet("background:transparent;")
            rh = QHBoxLayout(rw)
            rh.setContentsMargins(0, 0, 0, 0)
            fl = QLabel(field)
            fl.setObjectName("field_label")
            fl.setFixedWidth(120)
            vl = QLabel("—")
            vl.setObjectName("ro_label")
            self._op_labels[field] = vl
            rh.addWidget(fl)
            rh.addWidget(vl, 1)
            if unit:
                ul = QLabel(unit)
                ul.setStyleSheet(
                    f"color:{C_SLATE}; font-size:10px; background:transparent;")
                rh.addWidget(ul)
            op_v.addWidget(rw)
        op_v.addStretch()
        right_tab.addTab(op_tab, "🎯 Operating Point")

        # Tab 2: Pressure Traverse
        trav_tab = QWidget()
        trav_tab.setStyleSheet("background: transparent;")
        trav_v = QVBoxLayout(trav_tab)
        trav_v.setContentsMargins(8, 8, 8, 8)
        trav_v.setSpacing(6)
        self._trav_table = QTableWidget(0, 7)
        self._trav_table.setHorizontalHeaderLabels([
            "Depth (ft)", "Pressure (psia)", "Holdup",
            "f", "dp/dz_el", "dp/dz_fr", "dp/dz_total"])
        self._trav_table.setAlternatingRowColors(True)
        self._trav_table.horizontalHeader().setStretchLastSection(True)
        trav_v.addWidget(self._trav_table, 1)
        right_tab.addTab(trav_tab, "📊 Traverse")

        # Tab 3: PVT at Operating Point
        pvt_tab = QWidget()
        pvt_tab.setStyleSheet("background: transparent;")
        pvt_v = QVBoxLayout(pvt_tab)
        pvt_v.setContentsMargins(8, 8, 8, 8)
        self._pvt_op_table = QTableWidget(0, 2)
        self._pvt_op_table.setHorizontalHeaderLabels(["Property", "Value"])
        self._pvt_op_table.setAlternatingRowColors(True)
        self._pvt_op_table.horizontalHeader().setStretchLastSection(True)
        pvt_v.addWidget(self._pvt_op_table, 1)
        right_tab.addTab(pvt_tab, "🔬 PVT @ Op. Pt.")

        # Tab 4: Diagnostics
        diag_tab = QWidget()
        diag_tab.setStyleSheet("background: transparent;")
        diag_v = QVBoxLayout(diag_tab)
        diag_v.setContentsMargins(14, 14, 14, 14)
        diag_v.setSpacing(8)
        self._diag_table = QTableWidget(0, 2)
        self._diag_table.setHorizontalHeaderLabels(["Diagnostic", "Value"])
        self._diag_table.setAlternatingRowColors(True)
        self._diag_table.horizontalHeader().setStretchLastSection(True)
        diag_v.addWidget(self._diag_table, 1)
        right_tab.addTab(diag_tab, "🔧 Diagnostics")

        spl.addWidget(right_tab)
        spl.setSizes([700, 400])
        root.addWidget(spl, 1)

        self._ipr_line = None
        self._vlp_line = None

    def _init_ax(self) -> None:
        ax = self.ax
        ax.set_facecolor("#FAFCFF")
        ax.set_xlabel("Liquid Rate, q  (STB/day)", fontsize=11, color=C_INK, labelpad=8)
        ax.set_ylabel("Bottomhole Flowing Pressure, Pwf  (psia)", fontsize=11, color=C_INK, labelpad=8)
        ax.set_title("IPR × VLP — Nodal Analysis", fontsize=13,
                     fontweight="bold", color=C_DEEP_BLUE, pad=10)
        ax.grid(True, linestyle="--", alpha=0.35, color=C_GRAY_MID, linewidth=0.7)
        ax.tick_params(colors=C_INK, labelsize=10)
        for sp in ax.spines.values():
            sp.set_edgecolor(C_BORDER)
        self.fig.tight_layout(pad=1.8)

    def _reposition_mini(self, parent: QFrame) -> None:
        mm = self.mini
        cr = self.canvas.geometry()
        mm.move(cr.right() - mm.width() - 14, cr.bottom() - mm.height() - 14)

    def _on_hover(self, ev) -> None:
        if ev.inaxes != self.ax or ev.x is None:
            self._tip.hide()
            return
        lines = []
        if self._ipr_line:
            lines.append((self._ipr_line, "IPR"))
        if self._vlp_line:
            lines.append((self._vlp_line, "VLP"))
        best_dist, best_data = 20.0, None
        for line, label in lines:
            xdata, ydata = line.get_data()
            if not len(xdata):
                continue
            xy = np.column_stack((xdata, ydata))
            xy_disp = self.ax.transData.transform(xy)
            dist = np.hypot(xy_disp[:, 0] - ev.x, xy_disp[:, 1] - ev.y)
            idx = int(np.argmin(dist))
            if dist[idx] < best_dist:
                best_dist = dist[idx]
                best_data = (xdata[idx], ydata[idx], label)
        if best_data is None:
            self._tip.hide()
            return
        q, pw, lbl = best_data
        self._tip.setText(f"{lbl}:  q = {q:.0f} STB/d  |  Pwf = {pw:.0f} psia")
        self._tip.adjustSize()
        cx = min(int(ev.x) + 14, self.canvas.width() - self._tip.width() - 4)
        cy = max(self.canvas.height() - int(ev.y) + 4, 4)
        self._tip.move(cx, cy)
        self._tip.show()

    def _run(self) -> None:
        params = _store.all_values()
        self.run_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self._set_status("⏳  Running Nodal Analysis…", C_ROYAL_BLUE)

        worker = AnalysisWorker(params)
        worker.signals.status.connect(lambda t: self._set_status(t, C_ROYAL_BLUE))
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._on_error)
        self._pool.start(worker)

    @pyqtSlot(object)
    def _on_result(self, data: dict) -> None:
        self.run_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self._last_data = data
        _store.last_result = data
        self._plot(data)
        self._fill_tabs(data)
        self.result_ready.emit(data)
        sol = data["sol"]
        if sol["success"]:
            q, pw = sol["operating_rate"], sol["operating_pwf"]
            self._set_status(
                f"✅  q* = {q:.1f} STB/d  |  Pwf* = {pw:.1f} psia  |  Converged",
                C_SUCCESS)
        else:
            self._set_status(f"⚠️  No solution — {sol['message']}", C_WARNING)

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        self.run_btn.setEnabled(True)
        last = msg.strip().splitlines()[-1]
        self._set_status(f"❌  {last}", C_ERROR)
        print(msg, file=sys.stderr)

    def _set_status(self, text: str, color: str = C_SLATE) -> None:
        self._status_lbl.setStyleSheet(
            f"color:{color}; font-size:10px; background:transparent;")
        self._status_lbl.setText(text)

    def _plot(self, data: dict) -> None:
        self.ax.clear()
        self._init_ax()
        ri, pi = data["rates_ipr"], data["pwf_ipr"]
        rv, pv = data["rates_vlp"], data["pwf_vlp"]
        sol = data["sol"]

        self._ipr_line, = self.ax.plot(ri, pi, color=C_RED, linewidth=2.5,
                                       solid_capstyle="round", label="IPR")
        self._vlp_line, = self.ax.plot(rv, pv, color=C_ROYAL_BLUE, linewidth=2.5,
                                       solid_capstyle="round", label="VLP")
        self.ax.fill_between(ri, pi, alpha=0.05, color=C_RED)
        self.ax.fill_between(rv, pv, alpha=0.05, color=C_ROYAL_BLUE)

        if sol["success"]:
            for q_val, p_val, stab in sol.get("all_points", []):
                is_stable = stab == "Stable"
                self.ax.plot(q_val, p_val,
                             marker="*" if is_stable else "o",
                             markersize=18 if is_stable else 9,
                             color=C_GOLD if is_stable else C_ERROR,
                             zorder=10, linestyle="None",
                             markeredgecolor="#C67C00" if is_stable else "#B71C1C",
                             markeredgewidth=0.9)
                self.ax.annotate(
                    f"q*={q_val:.0f}\nPwf={p_val:.0f}",
                    xy=(q_val, p_val), xytext=(q_val + 20, p_val + 50),
                    fontsize=8, color=C_DEEP_BLUE,
                    arrowprops=dict(arrowstyle="->", color=C_DEEP_BLUE, lw=1))

        all_q = ri + rv
        all_p = pi + pv
        if all_q:
            self.ax.set_xlim(0, max(all_q) * 1.08)
        if all_p:
            self.ax.set_ylim(0, max(all_p) * 1.08)
        self.ax.legend(fontsize=10, loc="upper right",
                       framealpha=0.92, edgecolor=C_BORDER)
        self.canvas.draw_idle()

        if sol["success"] and data.get("traverse_depths"):
            self.mini.update_traverse(data["traverse_depths"], data["traverse_pressures"])
        else:
            self.mini.reset()

    def _fill_tabs(self, data: dict) -> None:
        sol = data["sol"]
        p   = data.get("params", _store.all_values())

        # Tab 1 — Operating point
        if sol["success"]:
            q = sol["operating_rate"]
            pw = sol["operating_pwf"]
            ipr = _build_ipr(p)
            j = getattr(ipr, "J", 0.0)
            dd = p.get("Pr", _store.get("Pr")) - pw
            all_pts = sol.get("all_points", [])
            stab_txt = "Stable ✅" if any(s == "Stable" for _, _, s in all_pts) else "Unstable ⚠️"
            vals = {
                "Operating Rate": f"{q:.2f}",
                "Operating Pwf":  f"{pw:.2f}",
                "Drawdown":       f"{dd:.2f}",
                "PI (J)":         f"{j:.4f}",
                "AOF":            f"{ipr.q_max:.2f}",
                "Stability":      stab_txt,
            }
            for field, val in vals.items():
                lbl = self._op_labels[field]
                lbl.setText(val)
                if field == "Stability":
                    lbl.setStyleSheet(
                        f"color:{'#43A047' if 'Stable' in val else C_WARNING}; "
                        "font-weight:700; background:#EEF4FB; border:1.5px solid #CFD8DC; "
                        "border-radius:7px; padding:5px 10px; min-height:28px;")

        # Tab 2 — Traverse
        depths = data.get("traverse_depths", [])
        pressures = data.get("traverse_pressures", [])
        profs = data.get("traverse_profiles", {})
        self._trav_table.setRowCount(len(depths))
        for i in range(len(depths)):
            row_vals = [
                f"{depths[i]:.1f}",
                f"{pressures[i]:.1f}",
                f"{profs.get('holdup', [0]*len(depths))[i]:.4f}",
                f"{profs.get('friction_factor', [0]*len(depths))[i]:.4f}",
                f"{profs.get('hydrostatic_loss', [0]*len(depths))[i]:.4f}",
                f"{profs.get('frictional_loss', [0]*len(depths))[i]:.4f}",
                f"{profs.get('total_gradient', [0]*len(depths))[i]:.4f}",
            ]
            for j, val in enumerate(row_vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._trav_table.setItem(i, j, item)

        # Tab 3 — PVT at op. point
        fp = data.get("fp_op", {})
        self._pvt_op_table.setRowCount(len(fp))
        for i, (k, v) in enumerate(fp.items()):
            self._pvt_op_table.setItem(i, 0, QTableWidgetItem(str(k)))
            val_str = f"{v:.5f}" if isinstance(v, float) else str(v)
            self._pvt_op_table.setItem(i, 1, QTableWidgetItem(val_str))

        # Tab 4 — Diagnostics
        diag_rows = []
        if sol["success"]:
            all_pts = sol.get("all_points", [])
            diag_rows = [
                ("Total intersections found", str(len(all_pts))),
                ("Stable point found", "Yes ✅" if any(s == "Stable" for _, _, s in all_pts) else "No ❌"),
                ("Unstable point found", "Yes" if any(s != "Stable" for _, _, s in all_pts) else "No"),
                ("Solver message", sol.get("message", "—")),
                ("Operating Rate", f"{sol['operating_rate']:.2f} STB/d"),
                ("Operating Pwf",  f"{sol['operating_pwf']:.2f} psia"),
                ("Traverse points", str(len(depths))),
            ]
        else:
            diag_rows = [
                ("Status", "Failed ❌"),
                ("Reason", sol.get("message", "Unknown error")),
            ]
        self._diag_table.setRowCount(len(diag_rows))
        for i, (k, v) in enumerate(diag_rows):
            self._diag_table.setItem(i, 0, QTableWidgetItem(k))
            self._diag_table.setItem(i, 1, QTableWidgetItem(v))

    def _export_csv(self) -> None:
        if not self._last_data:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        data = self._last_data
        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                sol = data["sol"]
                writer.writerow(["--- OPERATING POINT ---"])
                if sol["success"]:
                    writer.writerow(["Rate (STB/d)", "Pwf (psia)", "Stability"])
                    for pt in sol.get("all_points", []):
                        writer.writerow(pt)
                writer.writerow([])
                if data.get("fp_op"):
                    writer.writerow(["--- PVT AT OPERATING POINT ---"])
                    writer.writerow(["Property", "Value"])
                    for k, v in data["fp_op"].items():
                        writer.writerow([k, v])
                    writer.writerow([])
                writer.writerow(["--- IPR CURVE ---"])
                writer.writerow(["Rate (STB/d)", "Pwf (psia)"])
                for q, pw in zip(data["rates_ipr"], data["pwf_ipr"]):
                    writer.writerow([q, pw])
                writer.writerow([])
                writer.writerow(["--- VLP CURVE ---"])
                writer.writerow(["Rate (STB/d)", "Pwf (psia)"])
                for q, pw in zip(data["rates_vlp"], data["pwf_vlp"]):
                    writer.writerow([q, pw])
                writer.writerow([])
                if data.get("traverse_depths"):
                    writer.writerow(["--- PRESSURE TRAVERSE ---"])
                    writer.writerow(["Depth (ft)", "Pressure (psia)", "Holdup",
                                     "f", "dp/dz_el", "dp/dz_fr", "dp/dz_total"])
                    profs = data.get("traverse_profiles", {})
                    for i in range(len(data["traverse_depths"])):
                        writer.writerow([
                            data["traverse_depths"][i],
                            data["traverse_pressures"][i],
                            profs.get("holdup", [0]*999)[i],
                            profs.get("friction_factor", [0]*999)[i],
                            profs.get("hydrostatic_loss", [0]*999)[i],
                            profs.get("frictional_loss", [0]*999)[i],
                            profs.get("total_gradient", [0]*999)[i],
                        ])
            self._set_status(f"✅  Exported to {path}", C_SUCCESS)
        except Exception as e:
            self._set_status(f"❌  Export failed: {e}", C_ERROR)


# ══════════════════════════════════════════════════════════════════════════════
#  SENSITIVITY ANALYSIS PAGE  (PRD §9 — single/dual/triple + charts)
# ══════════════════════════════════════════════════════════════════════════════

class SensPage(QWidget):

    _DEFAULTS: dict[str, tuple[float, float]] = {
        "GOR":                (200.0,  1500.0),
        "THP":                (100.0,   600.0),
        "Water Cut":          (0.0,      0.80),
        "Reservoir Pressure": (2000.0, 4000.0),
        "Bubble Point":       (1000.0, 3000.0),
        "Depth":              (4000.0, 10000.0),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self._pool = QThreadPool.globalInstance()
        self._sens_results: list[dict] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Left: controls ────────────────────────────────────────────────
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(310)
        left.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        left_w = QWidget()
        left_w.setStyleSheet("background: transparent;")
        left_v = QVBoxLayout(left_w)
        left_v.setContentsMargins(0, 0, 8, 0)
        left_v.setSpacing(10)

        mode_card, mode_lay = _card("⚙️  Analysis Mode")
        self.mode_tabs = QTabWidget()
        self.mode_tabs.setStyleSheet(
            "QTabBar::tab { padding:4px 10px; font-size:10px; }"
            "QTabBar::tab:selected { font-weight:700; }")
        self.mode_tabs.addTab(QWidget(), "Single Variable")
        self.mode_tabs.addTab(QWidget(), "Dual Variable")
        self.mode_tabs.addTab(QWidget(), "Triple Variable")
        mode_lay.addWidget(self.mode_tabs)
        left_v.addWidget(mode_card)

        var_card, var_lay = _card("📋  Variable Setup")

        param_names = list(self._DEFAULTS.keys())

        # Param 1
        var_lay.addWidget(QLabel("Variable 1"))
        self.p1 = QComboBox()
        self.p1.addItems(param_names)
        self.min1 = _dspin(200.0, 0, 99999, 10, 2)
        self.max1 = _dspin(1000.0, 0, 99999, 10, 2)
        var_lay.addWidget(_row("Parameter", self.p1, label_width=80))
        var_lay.addWidget(_row("Min", self.min1, label_width=80))
        var_lay.addWidget(_row("Max", self.max1, label_width=80))

        # Param 2 (dual+)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background:{C_BORDER}; max-height:1px; border:none;")
        var_lay.addWidget(sep2)
        var_lay.addWidget(QLabel("Variable 2 (Dual / Triple)"))
        self.p2 = QComboBox()
        self.p2.addItems(param_names)
        self.p2.setCurrentIndex(1)
        self.min2 = _dspin(100.0, 0, 99999, 10, 2)
        self.max2 = _dspin(500.0, 0, 99999, 10, 2)
        var_lay.addWidget(_row("Parameter", self.p2, label_width=80))
        var_lay.addWidget(_row("Min", self.min2, label_width=80))
        var_lay.addWidget(_row("Max", self.max2, label_width=80))

        # Param 3 (triple only)
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"background:{C_BORDER}; max-height:1px; border:none;")
        var_lay.addWidget(sep3)
        var_lay.addWidget(QLabel("Variable 3 (Triple)"))
        self.p3 = QComboBox()
        self.p3.addItems(param_names)
        self.p3.setCurrentIndex(2)
        self.min3 = _dspin(0.1, 0, 99999, 0.1, 2)
        self.max3 = _dspin(0.8, 0, 99999, 0.1, 2)
        var_lay.addWidget(_row("Parameter", self.p3, label_width=80))
        var_lay.addWidget(_row("Min", self.min3, label_width=80))
        var_lay.addWidget(_row("Max", self.max3, label_width=80))

        left_v.addWidget(var_card)

        steps_card, steps_lay = _card("📏  Resolution")
        self.steps = QSpinBox()
        self.steps.setRange(2, 10)
        self.steps.setValue(5)
        steps_lay.addWidget(_row("# Steps", self.steps))
        left_v.addWidget(steps_card)

        self.run_sens_btn = QPushButton("▶  Run Sensitivity")
        self.run_sens_btn.setObjectName("run_btn")
        self.run_sens_btn.clicked.connect(self._run_sens)
        left_v.addWidget(self.run_sens_btn)

        self.clear_btn = QPushButton("✖  Clear Results")
        self.clear_btn.setObjectName("sec_btn")
        self.clear_btn.clicked.connect(self._clear)
        left_v.addWidget(self.clear_btn)

        self._status_lbl = QLabel("Ready.")
        self._status_lbl.setStyleSheet(
            f"color:{C_SLATE}; font-size:10px; background:transparent;")
        left_v.addWidget(self._status_lbl)

        left_v.addStretch()
        left.setWidget(left_w)
        root.addWidget(left)

        # ── Right: output tabs ────────────────────────────────────────────
        self.out_tabs = QTabWidget()

        # Overlay curves
        overlay_w = QWidget()
        overlay_w.setStyleSheet("background: transparent;")
        ov_lay = QVBoxLayout(overlay_w)
        ov_lay.setContentsMargins(8, 8, 8, 8)
        self.ov_fig = Figure(facecolor=C_WHITE)
        self.ov_ax  = self.ov_fig.add_subplot(111)
        self._init_ov_ax()
        self.ov_canvas = FigureCanvas(self.ov_fig)
        self.ov_canvas.setStyleSheet(f"background:{C_WHITE};")
        ov_toolbar = NavToolbar(self.ov_canvas, overlay_w)
        ov_toolbar.setStyleSheet(
            f"QToolBar {{ background:{C_LIGHT_GRAY}; border:none; }}")
        ov_lay.addWidget(ov_toolbar)
        ov_lay.addWidget(self.ov_canvas, 1)
        self.out_tabs.addTab(overlay_w, "📈 Overlay Curves")

        # Tornado chart
        tornado_w = QWidget()
        tornado_w.setStyleSheet("background: transparent;")
        to_lay = QVBoxLayout(tornado_w)
        to_lay.setContentsMargins(8, 8, 8, 8)
        self.to_fig = Figure(facecolor=C_WHITE)
        self.to_ax  = self.to_fig.add_subplot(111)
        self.to_canvas = FigureCanvas(self.to_fig)
        to_toolbar = NavToolbar(self.to_canvas, tornado_w)
        to_toolbar.setStyleSheet(
            f"QToolBar {{ background:{C_LIGHT_GRAY}; border:none; }}")
        to_lay.addWidget(to_toolbar)
        to_lay.addWidget(self.to_canvas, 1)
        self.out_tabs.addTab(tornado_w, "🌪 Tornado Chart")

        # Heat Map
        hmap_w = QWidget()
        hmap_w.setStyleSheet("background: transparent;")
        hm_lay = QVBoxLayout(hmap_w)
        hm_lay.setContentsMargins(8, 8, 8, 8)
        self.hm_fig = Figure(facecolor=C_WHITE)
        self.hm_ax  = self.hm_fig.add_subplot(111)
        self.hm_canvas = FigureCanvas(self.hm_fig)
        hm_toolbar = NavToolbar(self.hm_canvas, hmap_w)
        hm_toolbar.setStyleSheet(
            f"QToolBar {{ background:{C_LIGHT_GRAY}; border:none; }}")
        hm_lay.addWidget(hm_toolbar)
        hm_lay.addWidget(self.hm_canvas, 1)
        self.out_tabs.addTab(hmap_w, "🗺 Heat Map")

        # 3D surface (triple variable)
        surf_w = QWidget()
        surf_w.setStyleSheet("background: transparent;")
        sf_lay = QVBoxLayout(surf_w)
        sf_lay.setContentsMargins(8, 8, 8, 8)
        self.sf_fig = Figure(facecolor=C_WHITE)
        self.sf_ax  = self.sf_fig.add_subplot(111, projection="3d")
        self.sf_canvas = FigureCanvas(self.sf_fig)
        sf_lay.addWidget(self.sf_canvas, 1)
        self.out_tabs.addTab(surf_w, "🔷 3D Surface")

        # Results table
        tbl_w = QWidget()
        tbl_w.setStyleSheet("background: transparent;")
        tbl_lay = QVBoxLayout(tbl_w)
        tbl_lay.setContentsMargins(8, 8, 8, 8)
        self._sens_table = QTableWidget(0, 3)
        self._sens_table.setHorizontalHeaderLabels(["Parameter Value", "Op. Rate (STB/d)", "Op. Pwf (psia)"])
        self._sens_table.setAlternatingRowColors(True)
        self._sens_table.horizontalHeader().setStretchLastSection(True)
        tbl_lay.addWidget(self._sens_table, 1)

        export_sens_btn = QPushButton("💾  Export Sensitivity CSV")
        export_sens_btn.setObjectName("sec_btn")
        export_sens_btn.clicked.connect(self._export_csv)
        tbl_lay.addWidget(export_sens_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.out_tabs.addTab(tbl_w, "📋 Results Table")

        root.addWidget(self.out_tabs, 1)

        # Prefill ranges
        self.p1.currentIndexChanged.connect(self._prefill1)
        self._prefill1()

    def _init_ov_ax(self) -> None:
        self.ov_ax.set_facecolor("#FAFCFF")
        self.ov_ax.set_xlabel("Liquid Rate, q  (STB/day)", fontsize=10, color=C_INK)
        self.ov_ax.set_ylabel("Pwf  (psia)", fontsize=10, color=C_INK)
        self.ov_ax.set_title("Sensitivity — VLP Overlay Curves",
                              fontsize=12, fontweight="bold", color=C_DEEP_BLUE)
        self.ov_ax.grid(True, linestyle="--", alpha=0.35, color=C_GRAY_MID)
        self.ov_ax.tick_params(colors=C_INK, labelsize=9)
        for sp in self.ov_ax.spines.values():
            sp.set_edgecolor(C_BORDER)
        self.ov_fig.tight_layout(pad=1.6)

    def _prefill1(self) -> None:
        name = self.p1.currentText()
        lo, hi = self._DEFAULTS.get(name, (0.0, 100.0))
        self.min1.setValue(lo)
        self.max1.setValue(hi)

    def _run_sens(self) -> None:
        params = _store.all_values()
        steps = self.steps.value()
        p1_name = self.p1.currentText()
        values = np.linspace(self.min1.value(), self.max1.value(), steps).tolist()

        self.run_sens_btn.setEnabled(False)
        self._status("⏳  Running sensitivity sweep…", C_ROYAL_BLUE)

        worker = SensWorker(params, values, p1_name)
        worker.signals.status.connect(lambda t: self._status(t, C_ROYAL_BLUE))
        worker.signals.result.connect(self._on_sens_done)
        worker.signals.error.connect(self._on_error)
        self._pool.start(worker)

    @pyqtSlot(object)
    def _on_sens_done(self, result: dict) -> None:
        self.run_sens_btn.setEnabled(True)
        curves = result["curves"]
        self._sens_results = curves
        self._status(f"✅  {len(curves)} sensitivity curves complete.", C_SUCCESS)

        # ── Overlay curves ───────────────────────────────────────────────
        self.ov_ax.clear()
        self._init_ov_ax()
        ipr = _build_ipr(_store.all_values())
        rates_ipr = np.linspace(0, ipr.q_max, 150)
        pwf_ipr   = [ipr.calculate_Pwf(float(q)) for q in rates_ipr]
        self.ov_ax.plot(rates_ipr, pwf_ipr, color=C_RED, linewidth=2,
                        linestyle="-", label="IPR")
        for i, r in enumerate(curves):
            col = SENS_PALETTE[i % len(SENS_PALETTE)]
            self.ov_ax.plot(r["rates"], r["pwf"], color=col,
                            linewidth=1.8, linestyle="--", label=r["label"])
        self.ov_ax.legend(fontsize=8, loc="upper right",
                          framealpha=0.9, edgecolor=C_BORDER)
        self.ov_canvas.draw_idle()

        # ── Tornado chart ────────────────────────────────────────────────
        self.to_ax.clear()
        self.to_ax.set_facecolor("#FAFCFF")
        op_rates = result.get("op_rates", [r["op_rate"] for r in curves])
        param_vals = result.get("values", [r["param_val"] for r in curves])
        base_rate = op_rates[len(op_rates) // 2] if op_rates else 0.0
        deltas = [r - base_rate for r in op_rates]
        colors_tor = [C_SUCCESS if d >= 0 else C_ERROR for d in deltas]
        labels_tor = [f"{result['param_name']}={v:.1f}" for v in param_vals]
        y_pos = np.arange(len(labels_tor))
        self.to_ax.barh(y_pos, deltas, color=colors_tor, edgecolor="white",
                        height=0.55)
        self.to_ax.set_yticks(y_pos)
        self.to_ax.set_yticklabels(labels_tor, fontsize=9)
        self.to_ax.axvline(0, color=C_INK, linewidth=1)
        self.to_ax.set_xlabel("ΔRate vs. Base (STB/d)", fontsize=10, color=C_INK)
        self.to_ax.set_title("Tornado — Impact on Operating Rate",
                             fontsize=11, fontweight="bold", color=C_DEEP_BLUE)
        self.to_ax.grid(True, axis="x", linestyle="--", alpha=0.4)
        for sp in self.to_ax.spines.values():
            sp.set_edgecolor(C_BORDER)
        self.to_fig.tight_layout(pad=1.2)
        self.to_canvas.draw_idle()

        # ── Heat map ─────────────────────────────────────────────────────
        self.hm_ax.clear()
        grid_size = int(np.ceil(np.sqrt(len(op_rates))))
        grid = np.zeros((grid_size, grid_size))
        for i, r in enumerate(op_rates):
            row, col = divmod(i, grid_size)
            if row < grid_size and col < grid_size:
                grid[row, col] = r
        im = self.hm_ax.imshow(grid, cmap="RdYlGn", aspect="auto",
                                interpolation="nearest")
        self.hm_fig.colorbar(im, ax=self.hm_ax, label="Op. Rate (STB/d)")
        self.hm_ax.set_title(f"{result['param_name']} — 2D Rate Grid",
                              fontsize=11, fontweight="bold", color=C_DEEP_BLUE)
        self.hm_fig.tight_layout(pad=1.2)
        self.hm_canvas.draw_idle()

        # ── 3D surface (if dual/triple mode active) ──────────────────────
        self.sf_ax.clear()
        n = len(op_rates)
        X = np.arange(n)
        Y = np.array(param_vals)
        Z = np.array(op_rates)
        if n > 2:
            self.sf_ax.bar3d(X[:-1], Y[:-1], np.zeros(n - 1),
                             0.6, np.diff(Y) * 0.8, Z[:-1],
                             color=SENS_PALETTE[:n], alpha=0.8)
        self.sf_ax.set_xlabel(result["param_name"], fontsize=8, color=C_INK)
        self.sf_ax.set_ylabel("Index", fontsize=8, color=C_INK)
        self.sf_ax.set_zlabel("Op. Rate (STB/d)", fontsize=8, color=C_INK)
        self.sf_ax.set_title("3D Sensitivity Surface", fontsize=10,
                             fontweight="bold", color=C_DEEP_BLUE)
        self.sf_fig.tight_layout(pad=0.8)
        self.sf_canvas.draw_idle()

        # ── Results table ────────────────────────────────────────────────
        self._sens_table.setRowCount(len(curves))
        for i, c in enumerate(curves):
            self._sens_table.setItem(i, 0, QTableWidgetItem(c["label"]))
            self._sens_table.setItem(i, 1, QTableWidgetItem(f"{c['op_rate']:.2f}"))
            self._sens_table.setItem(i, 2, QTableWidgetItem(f"{c['op_pwf']:.2f}"))

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        self.run_sens_btn.setEnabled(True)
        self._status(f"❌  {msg.strip().splitlines()[-1]}", C_ERROR)
        print(msg, file=sys.stderr)

    def _status(self, text: str, color: str = C_SLATE) -> None:
        self._status_lbl.setStyleSheet(
            f"color:{color}; font-size:10px; background:transparent;")
        self._status_lbl.setText(text)

    def _clear(self) -> None:
        self._sens_results.clear()
        self.ov_ax.clear()
        self._init_ov_ax()
        self.ov_canvas.draw_idle()
        self.to_ax.clear()
        self.to_canvas.draw_idle()
        self.hm_ax.clear()
        self.hm_canvas.draw_idle()
        self.sf_ax.clear()
        self.sf_canvas.draw_idle()
        self._sens_table.setRowCount(0)
        self._status("Results cleared.", C_SLATE)

    def _export_csv(self) -> None:
        if not self._sens_results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Sensitivity CSV", "", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Label", "Op. Rate (STB/d)", "Op. Pwf (psia)"])
            for c in self._sens_results:
                writer.writerow([c["label"], c["op_rate"], c["op_pwf"]])
        self._status(f"✅  Exported to {path}", C_SUCCESS)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW  (three-panel assembly: NavRail | WorkspaceStack | SummaryPanel)
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FlowNexus IPM — Integrated Production Modelling")
        self.setMinimumSize(1400, 820)
        self.setStyleSheet(f"background:{C_LIGHT_GRAY};")

        # ── Central widget ──────────────────────────────────────────────────
        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar ───────────────────────────────────────────────────────
        self.tbar = TitleBar()
        self.tbar.save_requested.connect(self._save_project)
        self.tbar.load_requested.connect(self._load_project)
        root.addWidget(self.tbar)

        # ── Three-panel body ────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Left: navigation rail
        self.nav = NavRail()
        self.nav.module_selected.connect(self._switch_module)
        body.addWidget(self.nav)

        # Thin separator
        nav_sep = QFrame()
        nav_sep.setFrameShape(QFrame.Shape.VLine)
        nav_sep.setStyleSheet(f"background:{C_BORDER}; max-width:1px;")
        body.addWidget(nav_sep)

        # Center: workspace stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        self.dash_page  = DashboardPage()
        self.ipr_page   = IprPage()
        self.pvt_page   = PvtPage()
        self.vlp_page   = VlpPage()
        self.nodal_page = NodalPage()
        self.sens_page  = SensPage()

        self.stack.addWidget(self.dash_page)   # index 0 (dashboard, shown on start)
        self.stack.addWidget(self.ipr_page)    # 1
        self.stack.addWidget(self.pvt_page)    # 2
        self.stack.addWidget(self.vlp_page)    # 3
        self.stack.addWidget(self.nodal_page)  # 4
        self.stack.addWidget(self.sens_page)   # 5

        body.addWidget(self.stack, 1)

        # Right: summary panel separator + panel
        sum_sep = QFrame()
        sum_sep.setFrameShape(QFrame.Shape.VLine)
        sum_sep.setStyleSheet(f"background:{C_BORDER}; max-width:1px;")
        body.addWidget(sum_sep)

        self.summary = SummaryPanel()
        body.addWidget(self.summary)

        root.addLayout(body, 1)

        # ── Status bar ──────────────────────────────────────────────────────
        self._sb_lbl = QLabel("  Ready — configure inputs and click  ▶ Run Nodal Analysis.")
        self._sb_lbl.setStyleSheet("color:#CFD8DC; font-size:11px; background:transparent;")
        sb = QStatusBar()
        sb.setFixedHeight(36)
        sb.addWidget(self._sb_lbl, 1)
        self._unit_lbl = QLabel("📐  Field Units  |  FlowNexus IPM v2.0")
        self._unit_lbl.setStyleSheet(
            "color:#90CAF9; font-size:10px; background:transparent; padding-right:12px;")
        sb.addPermanentWidget(self._unit_lbl)
        self.setStatusBar(sb)

        # ── Wire-up dashboard navigation ────────────────────────────────────
        self.dash_page.navigate_to.connect(self._switch_module)

        # ── Wire-up nodal results → summary panel ───────────────────────────
        self.nodal_page.result_ready.connect(self.summary.update_results)
        self.nodal_page.result_ready.connect(
            lambda d: self._sb_status(
                f"✅  q* = {d['sol']['operating_rate']:.1f} STB/d  |  "
                f"Pwf* = {d['sol']['operating_pwf']:.1f} psia"
                if d['sol']['success'] else "⚠️  No operating point found.",
                C_SUCCESS if d['sol']['success'] else C_WARNING
            ))

        # Show dashboard by default
        self.stack.setCurrentIndex(0)

    # ── Module switching ────────────────────────────────────────────────────

    _MODULE_MAP = {
        "IPR": 1, "PVT": 2, "VLP": 3, "Nodal": 4, "Sensitivity": 5
    }

    @pyqtSlot(str)
    def _switch_module(self, key: str) -> None:
        idx = self._MODULE_MAP.get(key, 0)
        self.nav.select(key)
        titles = {
            "IPR": "IPR Data  —  Inflow Performance",
            "PVT": "PVT Data  —  Fluid Properties",
            "VLP": "VLP Data  —  Wellbore Model",
            "Nodal": "Nodal Analysis  —  IPR × VLP",
            "Sensitivity": "Sensitivity Analysis",
        }
        self.tbar.set_project(titles.get(key, "FlowNexus IPM"))
        self.stack.setCurrentIndex(idx)

    def _on_nav_selected(self, key: str):
        """Handler for nav rail clicks to change the workspace."""
        idx = self._MODULE_MAP.get(key, 0)
        self.stack.setCurrentIndex(idx)

    # ── Project save / load ─────────────────────────────────────────────────

    def _save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "IPM Project (*.ipmproj);;JSON (*.json)")
        if not path:
            return
        try:
            _store.save(path)
            self.tbar.set_project(os.path.basename(path))
            self._sb_status(f"✅  Project saved → {path}", C_SUCCESS)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "", "IPM Project (*.ipmproj);;JSON (*.json)")
        if not path:
            return
        try:
            _store.load(path)
            self.tbar.set_project(os.path.basename(path))
            self._sb_status(f"✅  Project loaded ← {path}", C_SUCCESS)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    # ── Status bar ──────────────────────────────────────────────────────────

    def _sb_status(self, text: str, color: str = "#CFD8DC") -> None:
        self._sb_lbl.setStyleSheet(
            f"color:{color}; font-size:11px; background:transparent;")
        self._sb_lbl.setText(f"  {text}")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FlowNexus IPM")
    app.setApplicationVersion("2.0")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    # Load Inter font if available, else fall back to Segoe UI
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Inter-Regular.ttf")
    QFontDatabase.addApplicationFont(font_path)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
