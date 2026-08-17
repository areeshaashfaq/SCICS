import sys
import api_client
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ── palette ────────────────────────────────────────────────────────────────────
BG_APP   = "#0F1923"
BG_PANEL = "#162230"
BG_CARD  = "#1C2D3E"
BG_DARK  = "#0A1520"
BORDER   = "#253D52"
ACCENT   = "#2E7DD1"
ACCENT_L = "#3D8FE8"
SUCCESS  = "#27AE60"
DANGER   = "#C0392B"
WARNING  = "#D4A017"
TEXT_PRI = "#E8EDF2"
TEXT_SEC = "#8FA8BF"
TEXT_CODE= "#5BB8FF"


def make_label(text, size=12, bold=False, color=TEXT_PRI, wrap=False):
    lbl = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{color}; background:transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


# ── stat tile ─────────────────────────────────────────────────────────────────
class StatTile(QFrame):
    def __init__(self, value: str, label: str, accent: str, sub: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            StatTile {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-top: 3px solid {accent};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)

        val_lbl = QLabel(value)
        val_lbl.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color:{accent}; background:transparent;")
        lay.addWidget(val_lbl)

        lay.addWidget(make_label(label, 11, color=TEXT_PRI))
        if sub:
            lay.addWidget(make_label(sub, 10, color=TEXT_SEC))
        lay.addStretch()


# ── bar row for top corrected codes ───────────────────────────────────────────
class BarRow(QFrame):
    def __init__(self, icd_code: str, description: str, count: int, max_count: int):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(52)
        self.setStyleSheet("background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(4)

        # label row
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(make_label(icd_code, 10, bold=True, color=TEXT_CODE))
        top.addWidget(make_label(description, 10, color=TEXT_SEC), 1)
        top.addWidget(make_label(str(count), 10, bold=True, color=TEXT_PRI))
        lay.addLayout(top)

        # bar
        bar_bg = QFrame()
        bar_bg.setFixedHeight(6)
        bar_bg.setStyleSheet(f"background:{BORDER}; border-radius:3px;")
        bar_bg.setMinimumWidth(1)

        bar_fill = QFrame(bar_bg)
        bar_fill.setFixedHeight(6)
        pct = (count / max_count) if max_count else 0
        bar_fill.setStyleSheet(f"background:{ACCENT}; border-radius:3px;")

        def _resize_bar(event, fill=bar_fill, p=pct, bg=bar_bg):
            fill.setFixedWidth(max(4, int(bg.width() * p)))

        bar_bg.resizeEvent = _resize_bar
        lay.addWidget(bar_bg)


# ── activity row ──────────────────────────────────────────────────────────────
class ActivityRow(QFrame):
    ACTION_COLORS = {"accept": SUCCESS, "reject": DANGER, "edit": WARNING}
    ACTION_ICONS  = {"accept": "✓", "reject": "✗", "edit": "✎"}

    def __init__(self, entry: dict):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(46)
        self.setStyleSheet(f"background:transparent; border-bottom:1px solid {BORDER};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        action = entry.get("correction_type", "")
        color  = self.ACTION_COLORS.get(action, TEXT_SEC)
        icon   = self.ACTION_ICONS.get(action, "·")

        badge = QLabel(f"{icon}")
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color:{color}; border:1px solid {color}; border-radius:12px;"
            f"font-size:11px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(badge)

        code_lbl = make_label(entry.get("icd_code", ""), 11, bold=True, color=TEXT_CODE)
        code_lbl.setFixedWidth(130)
        lay.addWidget(code_lbl)

        lay.addWidget(make_label(entry.get("coder_name", ""), 10, color=TEXT_SEC))
        lay.addWidget(make_label(entry.get("patient_ref", ""), 10, color=TEXT_SEC))
        lay.addStretch()

        ts = entry.get("corrected_at", "")[:16].replace("T", "  ")
        lay.addWidget(make_label(ts, 9, color=BORDER))


# ── main admin window ─────────────────────────────────────────────────────────
class AdminDashboard(QMainWindow):
    def __init__(self, on_logout=None):
        super().__init__()
        self.on_logout = on_logout
        self.setWindowTitle("SIUT — Admin Dashboard")
        self.resize(1100, 720)
        self.setStyleSheet(f"QMainWindow {{ background:{BG_APP}; }} QWidget {{ background:{BG_APP}; }}")
        self._build_ui()
        self._load()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top bar ───────────────────────────────────────────────────────────
        top = QWidget()
        top.setFixedHeight(56)
        top.setStyleSheet(f"background:{BG_DARK}; border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(top)
        tb.setContentsMargins(24, 0, 24, 0)
        tb.setSpacing(12)

        tb.addWidget(make_label("SIUT  ICD Coder", 14, bold=True, color=ACCENT))

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{BORDER};")
        tb.addWidget(div)

        tb.addWidget(make_label("Admin Dashboard", 12, color=TEXT_SEC))
        tb.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(72, 32)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:6px; font-size:11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        refresh_btn.clicked.connect(self._load)
        tb.addWidget(refresh_btn)

        logout_btn = QPushButton("Log Out")
        logout_btn.setFixedSize(80, 32)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{DANGER};
                border:1px solid {DANGER}; border-radius:6px; font-size:11px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{DANGER}; color:white; }}
        """)
        logout_btn.clicked.connect(self._logout)
        tb.addWidget(logout_btn)

        root.addWidget(top)

        # ── scrollable body ───────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{BG_APP}; }}
            QScrollBar:vertical {{ background:{BG_APP}; width:8px; border-radius:4px; }}
            QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:4px; }}
        """)

        self.body = QWidget()
        self.body.setStyleSheet(f"background:{BG_APP};")
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(28, 24, 28, 28)
        self.body_lay.setSpacing(20)

        scroll.setWidget(self.body)
        root.addWidget(scroll, 1)

    # ── load data ─────────────────────────────────────────────────────────────
    def _load(self):
        # clear body
        while self.body_lay.count():
            item = self.body_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            data = api_client.get_analytics()
        except Exception as e:
            self.body_lay.addWidget(make_label(f"Cannot load analytics: {e}", color=DANGER))
            return

        self._build_stats(data)
        self._build_middle(data)
        self.body_lay.addStretch()

    def _build_stats(self, data: dict):
        accepted      = data.get("accepted", 0)
        rejected      = data.get("rejected", 0)
        edited        = data.get("edited", 0)
        total_decided = accepted + rejected + edited
        acc_rate      = data.get("acceptance_rate", 0)
        avg_conf      = data.get("avg_confidence", 0)

        row = QHBoxLayout()
        row.setSpacing(14)

        tiles = [
            StatTile(
                str(data.get("total_documents", 0)),
                "Total Records",
                ACCENT,
                f"{data.get('complete_documents', 0)} complete  ·  {data.get('pending_documents', 0)} pending",
            ),
            StatTile(
                f"{int(acc_rate * 100)}%",
                "Acceptance Rate",
                SUCCESS,
                f"{accepted} accepted  ·  {rejected} rejected",
            ),
            StatTile(
                f"{int(avg_conf * 100)}%",
                "Avg NLP Confidence",
                ACCENT_L,
                f"across {data.get('total_suggestions', 0)} suggestions",
            ),
            StatTile(
                str(data.get("flagged_ambiguous", 0)),
                "Flagged Ambiguous",
                WARNING,
                "require coder attention",
            ),
        ]
        for t in tiles:
            row.addWidget(t)

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")
        wrapper.setLayout(row)
        self.body_lay.addWidget(wrapper)

    def _build_middle(self, data: dict):
        mid = QHBoxLayout()
        mid.setSpacing(18)

        mid.addWidget(self._build_top_codes(data), 55)
        mid.addWidget(self._build_activity(data),  45)

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")
        wrapper.setLayout(mid)
        self.body_lay.addWidget(wrapper)

    def _build_top_codes(self, data: dict) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setStyleSheet(f"""
            QFrame {{
                background:{BG_CARD}; border:1px solid {BORDER}; border-radius:8px;
            }}
        """)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(make_label("Most Corrected ICD Codes", 12, bold=True))
        header.addStretch()
        header.addWidget(make_label("CORRECTIONS", 9, color=TEXT_SEC))
        lay.addLayout(header)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BORDER};")
        lay.addWidget(sep)

        codes = data.get("top_corrected_codes", [])
        max_count = max((c.get("corrections", 0) for c in codes), default=1)
        for entry in codes:
            lay.addWidget(BarRow(
                entry.get("icd_code", ""),
                entry.get("description", ""),
                entry.get("corrections", 0),
                max_count,
            ))

        if not codes:
            lay.addWidget(make_label("No corrections recorded yet.", 11, color=TEXT_SEC))

        lay.addStretch()
        return panel

    def _build_activity(self, data: dict) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setStyleSheet(f"""
            QFrame {{
                background:{BG_CARD}; border:1px solid {BORDER}; border-radius:8px;
            }}
        """)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(0)

        lay.addWidget(make_label("Recent Activity", 12, bold=True))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BORDER}; margin-top:8px; margin-bottom:4px;")
        lay.addWidget(sep)

        # column headers
        col = QHBoxLayout()
        col.setSpacing(12)
        col.setContentsMargins(0, 0, 0, 4)
        for txt, w in [("", 24), ("CODE / CHANGE", 130), ("CODER", 80), ("PATIENT", 80)]:
            lbl = make_label(txt, 9, bold=True, color=TEXT_SEC)
            if w:
                lbl.setFixedWidth(w)
            col.addWidget(lbl)
        col.addStretch()
        col.addWidget(make_label("TIME", 9, bold=True, color=TEXT_SEC))
        col_w = QWidget(); col_w.setStyleSheet("background:transparent;")
        col_w.setLayout(col)
        lay.addWidget(col_w)

        activity = data.get("recent_activity", [])
        for entry in activity:
            lay.addWidget(ActivityRow(entry))

        if not activity:
            lay.addWidget(make_label("No recent activity.", 11, color=TEXT_SEC))

        lay.addStretch()
        return panel

    def _logout(self):
        if self.on_logout:
            self.on_logout()
        self.close()


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AdminDashboard()
    window.show()
    sys.exit(app.exec())
