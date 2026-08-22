import sys
import api_client
from collections import defaultdict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

# ── palette (matches other screens) ───────────────────────────────────────────
BG_APP    = "#0F1923"
BG_PANEL  = "#162230"
BG_CARD   = "#1C2D3E"
BG_DARK   = "#0A1520"
BORDER    = "#253D52"
ACCENT    = "#2E7DD1"
ACCENT_L  = "#3D8FE8"
SUCCESS   = "#27AE60"
DANGER    = "#C0392B"
WARNING   = "#D4A017"
TEXT_PRI  = "#E8EDF2"
TEXT_SEC  = "#8FA8BF"
TEXT_CODE = "#5BB8FF"


def make_label(text, size=12, bold=False, color=TEXT_PRI, wrap=False):
    lbl = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{color}; background:transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


# ── single correction detail row ──────────────────────────────────────────────
class CorrectionDetailRow(QFrame):
    ICONS = {"confirmed": "✓", "rejected": "✗", "reclassified": "✎"}
    COLORS = {"confirmed": SUCCESS, "rejected": DANGER, "reclassified": WARNING}

    def __init__(self, corr: dict):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            CorrectionDetailRow {{
                background: {BG_APP};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        self._build(corr)

    def _build(self, corr):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(48, 0, 18, 0)
        lay.setSpacing(14)

        ctype  = corr.get("correction_type", "confirmed")
        color  = self.COLORS.get(ctype, TEXT_SEC)
        icon   = self.ICONS.get(ctype, "·")

        # type badge
        badge = QLabel(f"{icon}  {ctype.upper()}")
        badge.setFixedWidth(82)
        badge.setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:bold;"
            f"background:transparent;"
        )
        lay.addWidget(badge)

        # ICD code
        original = corr.get("original_icd_code", "—")
        corrected = corr.get("corrected_icd_code")
        if corrected:
            code_text = f"{original}  →  {corrected}"
        else:
            code_text = original
        code_lbl = make_label(code_text, 11, bold=True, color=TEXT_CODE)
        code_lbl.setFixedWidth(160)
        lay.addWidget(code_lbl)

        # description
        desc = corr.get("icd_description", "")
        lay.addWidget(make_label(desc, 10, color=TEXT_SEC, wrap=False), 1)

        # comment (if any)
        comment = corr.get("comment", "")
        if comment:
            lay.addWidget(make_label(f'"{comment}"', 9, color=TEXT_SEC))

        lay.addStretch()

        # coder name
        coder = corr.get("coder_name", "")
        if coder:
            lay.addWidget(make_label(coder, 9, color=ACCENT))

        # timestamp
        ts = corr.get("corrected_at", "")[:16].replace("T", "  ")
        lay.addWidget(make_label(ts, 9, color=TEXT_SEC))


# ── document summary row (expandable) ─────────────────────────────────────────
class DocumentHistoryRow(QFrame):
    def __init__(self, doc_id: int, corrections: list):
        super().__init__()
        self.doc_id      = doc_id
        self.corrections = corrections
        self._expanded   = False
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            DocumentHistoryRow {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        self._build()

    def _build(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # ── header row ────────────────────────────────────────────────────────
        header_w = QWidget()
        header_w.setFixedHeight(68)
        header_w.setStyleSheet("background:transparent;")
        hlay = QHBoxLayout(header_w)
        hlay.setContentsMargins(18, 0, 18, 0)
        hlay.setSpacing(16)

        sample = self.corrections[0] if self.corrections else {}

        # left: patient ref + filename
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(make_label(sample.get("patient_ref", "—"), 12, bold=True))
        left.addWidget(make_label(sample.get("source_filename", ""), 10, color=TEXT_SEC))
        hlay.addLayout(left)

        hlay.addStretch()

        # coder name(s)
        coders = list(dict.fromkeys(c.get("coder_name", "") for c in self.corrections if c.get("coder_name")))
        coder_str = coders[0] if len(coders) == 1 else "Multiple coders"
        hlay.addWidget(make_label(f"Coded by  {coder_str}", 10, color=ACCENT))

        hlay.addSpacing(8)

        # stats chips
        n_accept = sum(1 for c in self.corrections if c.get("correction_type") == "confirmed")
        n_reject = sum(1 for c in self.corrections if c.get("correction_type") == "rejected")
        n_edit   = sum(1 for c in self.corrections if c.get("correction_type") == "reclassified")

        for label, count, color in [
            (f"✓ {n_accept} accepted", n_accept, SUCCESS),
            (f"✗ {n_reject} rejected", n_reject, DANGER),
            (f"✎ {n_edit} edited",   n_edit,   WARNING),
        ]:
            chip = QLabel(label)
            chip.setStyleSheet(
                f"color:{color}; border:1px solid {color}; border-radius:4px;"
                f"padding:2px 8px; font-size:10px; font-weight:bold; background:transparent;"
            )
            chip.setVisible(count > 0)
            hlay.addWidget(chip)

        # last date
        dates = [c.get("corrected_at", "")[:10] for c in self.corrections if c.get("corrected_at")]
        last_date = max(dates) if dates else ""
        hlay.addWidget(make_label(last_date, 10, color=TEXT_SEC))

        # expand toggle
        self._toggle_btn = QPushButton("▾  Details")
        self._toggle_btn.setFixedSize(90, 30)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 5px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle)
        hlay.addWidget(self._toggle_btn)

        self._root.addWidget(header_w)

        # ── expandable detail area ─────────────────────────────────────────────
        self._detail_w = QWidget()
        self._detail_w.setStyleSheet(f"background:{BG_APP}; border-top:1px solid {BORDER};")
        detail_layout = QVBoxLayout(self._detail_w)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        # column headers
        col_header = QFrame()
        col_header.setFixedHeight(30)
        col_header.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
        ch = QHBoxLayout(col_header)
        ch.setContentsMargins(48, 0, 18, 0)
        ch.setSpacing(14)
        for txt, w in [("DECISION", 82), ("ICD CODE", 160), ("DESCRIPTION", -1), ("CODER", 100), ("TIMESTAMP", 130)]:
            lbl = make_label(txt, 9, bold=True, color=TEXT_SEC)
            if w > 0:
                lbl.setFixedWidth(w)
            else:
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            ch.addWidget(lbl)
        detail_layout.addWidget(col_header)

        for corr in self.corrections:
            detail_layout.addWidget(CorrectionDetailRow(corr))

        self._detail_w.setVisible(False)
        self._root.addWidget(self._detail_w)

    def _toggle(self):
        self._expanded = not self._expanded
        self._detail_w.setVisible(self._expanded)
        self._toggle_btn.setText("▴  Collapse" if self._expanded else "▾  Details")


# ── main history window ────────────────────────────────────────────────────────
class CoderHistoryWindow(QMainWindow):
    def __init__(self, on_back=None):
        super().__init__()
        self.on_back = on_back
        self.setWindowTitle("SIUT — Coder History")
        self.resize(900, 660)
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

        # back button
        back_btn = QPushButton("← Back")
        back_btn.setFixedSize(80, 32)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        back_btn.clicked.connect(self._go_back)
        tb.addWidget(back_btn)
        tb.addSpacing(16)
        tb.addWidget(make_label("SIUT  ICD Coder", 14, bold=True, color=ACCENT))
        tb.addSpacing(16)

        tb.addWidget(make_label("Coder History", 12, color=TEXT_SEC))
        tb.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(72, 32)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px; font-size: 11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        refresh_btn.clicked.connect(self._load)
        tb.addWidget(refresh_btn)

        root.addWidget(top)

        # ── summary bar ───────────────────────────────────────────────────────
        self.summary_bar = QWidget()
        self.summary_bar.setFixedHeight(36)
        self.summary_bar.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
        sb = QHBoxLayout(self.summary_bar)
        sb.setContentsMargins(24, 0, 24, 0)
        self.summary_lbl = make_label("Loading history…", 11, color=TEXT_SEC)
        sb.addWidget(self.summary_lbl)
        sb.addStretch()
        root.addWidget(self.summary_bar)

        # ── scrollable list ───────────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{BG_APP}; }}
            QScrollBar:vertical {{
                background:{BG_APP}; width:8px; border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:{BORDER}; border-radius:4px;
            }}
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet(f"background:{BG_APP};")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(24, 20, 24, 20)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.list_container)
        root.addWidget(self.scroll, 1)

    # ── data loading ──────────────────────────────────────────────────────────
    def _load(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.summary_lbl.setText("Loading…")

        try:
            corrections = api_client.get_corrections()
        except Exception as e:
            self.summary_lbl.setText(f"Cannot load history: {e}")
            return

        if not corrections:
            self.summary_lbl.setText("No corrections recorded yet.")
            return

        # group by document_id
        by_doc = defaultdict(list)
        for c in corrections:
            by_doc[c["document_id"]].append(c)

        for doc_id, corrs in sorted(by_doc.items(), reverse=True):
            row = DocumentHistoryRow(doc_id, corrs)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

        n_docs   = len(by_doc)
        n_total  = len(corrections)
        n_accept = sum(1 for c in corrections if c.get("correction_type") == "confirmed")
        n_reject = sum(1 for c in corrections if c.get("correction_type") == "rejected")
        n_edit   = sum(1 for c in corrections if c.get("correction_type") == "reclassified")
        self.summary_lbl.setText(
            f"{n_docs} document{'s' if n_docs != 1 else ''}  ·  "
            f"{n_total} decisions  ·  "
            f"{n_accept} accepted  ·  {n_reject} rejected  ·  {n_edit} edited"
        )

    def _go_back(self):
        if self.on_back:
            self.on_back()
            self.close()
        else:
            self.close()


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CoderHistoryWindow()
    window.show()
    sys.exit(app.exec())
