import sys
import csv
import html
import api_client
import theme
from load_error import make_load_error
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QFileDialog, QComboBox, QDateEdit, QLineEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

BG_APP = BG_PANEL = BG_CARD = BG_TOP = BORDER = SEC_HOVER = ""
ACCENT = ACCENT_L = SUCCESS = DANGER = ""
TEXT_PRI = TEXT_SEC = TEXT_CODE = ""
WARNING = "#D4A017"

PAGE = 10
DONE_STATUSES = ("reviewed", "finalized", "complete")
RANGES = ["All time", "Today", "This week", "This month", "Custom range"]
UNKNOWN_CODER = "Unknown"
ACTION_NAMES = {"confirmed": "Accepted", "reclassified": "Edited",
                "rejected": "Rejected", "added_missed": "Added"}

# Date & time · Coder · Change · Patient · File (0 = takes the remaining width)
CHANGE_COLS = [("Date & time", 150), ("Coder", 130), ("Change", 190), ("Patient", 110), ("File", 0)]


def _reload_colors():
    global BG_APP, BG_PANEL, BG_CARD, BG_TOP, BORDER, SEC_HOVER
    global ACCENT, ACCENT_L, SUCCESS, DANGER
    global TEXT_PRI, TEXT_SEC, TEXT_CODE
    t = theme.current
    BG_APP    = t["BG_APP"]
    BG_PANEL  = t["BG_PANEL"]
    BG_CARD   = t["BG_CARD"]
    BG_TOP    = t["BG_TOP"]
    BORDER    = t["BORDER"]
    SEC_HOVER = t["SEC_HOVER"]
    ACCENT    = t["ACCENT"]
    ACCENT_L  = t["ACCENT_LITE"]
    SUCCESS   = t["SUCCESS"]
    DANGER    = t["DANGER"]
    TEXT_PRI  = t["TEXT_PRI"]
    TEXT_SEC  = t["TEXT_SEC"]
    TEXT_CODE = t["TEXT_CODE"]


_reload_colors()


# ── data helpers ──────────────────────────────────────────────────────────────

def _pct(fraction) -> str:
    """0.5714 -> '57.14%'. Two decimals, never truncated to a whole number."""
    return f"{(fraction or 0) * 100:.2f}%"


def _parse_time(value):
    """Server times are UTC without a zone (like the record queue assumes); show local."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _fmt_time(dt) -> str:
    return dt.strftime("%d %b %Y, %H:%M") if dt else "—"


def _clean_corrections(rows):
    """Copy the rows with a parsed time, and drop the automatic accept after an edit.

    Saving an edit sends the new code and then an "approved" decision, so the
    server records a reclassified row followed by a confirmed row for the same
    suggestion. Counting both would show every edit twice and as an accept.
    """
    rows = [dict(c, _at=_parse_time(c.get("corrected_at")),
                 coder_name=c.get("coder_name") or UNKNOWN_CODER) for c in rows]
    edit_times = defaultdict(list)
    for c in rows:
        if c.get("correction_type") == "reclassified" and c["_at"]:
            edit_times[c.get("suggestion_id")].append(c["_at"])
    kept = []
    for c in rows:
        if c.get("correction_type") == "confirmed" and c["_at"]:
            if any(0 <= (c["_at"] - t).total_seconds() <= 60
                   for t in edit_times.get(c.get("suggestion_id"), [])):
                continue
        kept.append(c)
    kept.sort(key=lambda c: c["_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return kept


def _change_parts(c):
    """(icon, colour, text) for the Change column."""
    kind = c.get("correction_type")
    orig = c.get("original_icd_code") or ""
    new = c.get("corrected_icd_code") or ""
    if kind == "reclassified":
        return "✎", WARNING, f"{orig or '?'} → {new}"
    if kind == "rejected":
        return "✗", DANGER, orig
    if kind == "added_missed":
        return "+", ACCENT, f"{new or orig} added"
    return "✓", SUCCESS, orig or new


def _range_start_end(key, frm: QDate, to: QDate):
    now = datetime.now().astimezone()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if key == "Today":
        return today, None
    if key == "This week":
        return today - timedelta(days=today.weekday()), None
    if key == "This month":
        return today.replace(day=1), None
    if key == "Custom range":
        start = datetime(frm.year(), frm.month(), frm.day()).astimezone()
        end = datetime(to.year(), to.month(), to.day()).astimezone() + timedelta(days=1)
        return start, end
    return None, None


def _counts(rows):
    n = Counter(c.get("correction_type") for c in rows)
    decisions = n["confirmed"] + n["reclassified"] + n["rejected"]
    return n, decisions


# ── small widgets ─────────────────────────────────────────────────────────────

def make_label(text, size=12, bold=False, color=None, wrap=False):
    lbl = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{color or TEXT_PRI}; background:transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()   # gone at once, not on the next event-loop pass
            item.widget().deleteLater()


def _plain():
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    return w


def _grid(cells, widths, indent=0):
    """One row of fixed-width columns; a width of 0 takes the remaining space."""
    w = _plain()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(indent, 0, 0, 0)
    lay.setSpacing(12)
    for cell, width in zip(cells, widths):
        if not isinstance(cell, QWidget):
            cell = make_label(str(cell), 10)
            cell.setToolTip(cell.text())
        if width:
            cell.setFixedWidth(width)
            lay.addWidget(cell)
        else:
            lay.addWidget(cell, 1)
    return w


def _header(names_widths, indent=0):
    cells = [make_label(n.upper(), 8, bold=True, color=TEXT_SEC) for n, _ in names_widths]
    w = _grid(cells, [wd for _, wd in names_widths], indent)
    w.layout().setContentsMargins(indent, 6, 0, 6)
    return w


def _change_label(c):
    icon, colour, text = _change_parts(c)
    lbl = QLabel(
        f'<span style="color:{colour}; font-weight:bold">{icon}</span>&nbsp;&nbsp;'
        f'<span style="color:{TEXT_CODE}; font-weight:bold">{html.escape(text)}</span>'
    )
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setFont(QFont("Segoe UI", 10))
    lbl.setStyleSheet("background:transparent;")
    return lbl


class _Line(QFrame):
    """A table row with a bottom rule. With on_click it highlights and is clickable."""

    def __init__(self, content: QWidget, on_click=None):
        super().__init__()
        self._on_click = on_click
        self.setObjectName("line")
        hover = f"QFrame#line:hover {{ background:{SEC_HOVER}; }}" if on_click else ""
        self.setStyleSheet(
            f"QFrame#line {{ background:transparent; border:none;"
            f" border-bottom:1px solid {BORDER}; }} {hover}"
        )
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 9, 0, 9)
        lay.addWidget(content)

    def mousePressEvent(self, event):
        if self._on_click and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()


def _change_line(c, indent=0):
    cells = [
        make_label(_fmt_time(c["_at"]), 10, color=TEXT_SEC),
        c["coder_name"],
        _change_label(c),
        c.get("patient_ref") or "—",
        c.get("source_filename") or "—",
    ]
    return _Line(_grid(cells, [w for _, w in CHANGE_COLS], indent))


def _change_list(rows):
    """The who / when / which file list shown when a row is opened."""
    box = QFrame()
    box.setObjectName("detail")
    box.setStyleSheet(f"QFrame#detail {{ background:{BG_PANEL}; border-radius:6px; }}")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(14, 6, 14, 8)
    lay.setSpacing(0)
    lay.addWidget(_header(CHANGE_COLS))
    for c in rows:
        lay.addWidget(_change_line(c))
    return box


class _ExpandLine(QFrame):
    """A clickable row that opens a detail panel underneath it."""

    def __init__(self, content: QWidget, build_detail, key, open_keys: set):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._build_detail = build_detail
        self._key = key
        self._open_keys = open_keys
        self._detail = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        row = _plain()
        r = QHBoxLayout(row)
        r.setContentsMargins(0, 0, 0, 0)
        r.setSpacing(6)
        self.arrow = make_label("▸", 10, color=TEXT_SEC)
        self.arrow.setFixedWidth(12)
        r.addWidget(self.arrow, 0, Qt.AlignmentFlag.AlignTop)
        r.addWidget(content, 1)
        lay.addWidget(_Line(row, on_click=self.toggle))

        self._holder = _plain()
        self._holder_lay = QVBoxLayout(self._holder)
        self._holder_lay.setContentsMargins(18, 8, 0, 12)
        self._holder.setVisible(False)
        lay.addWidget(self._holder)

        if key in open_keys:
            self.toggle()

    def toggle(self):
        if self._detail is None:
            self._detail = self._build_detail()
            self._holder_lay.addWidget(self._detail)
        shown = not self._holder.isVisible()
        self._holder.setVisible(shown)
        self.arrow.setText("▾" if shown else "▸")
        if shown:
            self._open_keys.add(self._key)
        else:
            self._open_keys.discard(self._key)


class Section(QFrame):
    """A card with a clickable title bar that collapses its body."""

    def __init__(self, title: str, expanded: bool, on_toggle):
        super().__init__()
        self.setObjectName("section")
        self.setStyleSheet(
            f"QFrame#section {{ background:{BG_CARD}; border:1px solid {BORDER}; border-radius:8px; }}"
        )
        self._expanded = expanded
        self._on_toggle = on_toggle

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = _Line(_plain(), on_click=self._toggle)
        head.setStyleSheet(
            f"QFrame#line {{ background:transparent; border:none; }}"
            f"QFrame#line:hover {{ background:{SEC_HOVER}; border-radius:8px; }}"
        )
        h = QHBoxLayout(head.layout().itemAt(0).widget())
        h.setContentsMargins(20, 5, 20, 5)
        h.setSpacing(10)
        self.arrow = make_label("▾" if expanded else "▸", 11, color=TEXT_SEC)
        h.addWidget(self.arrow)
        h.addWidget(make_label(title, 12, bold=True))
        self.count_lbl = make_label("", 10, color=TEXT_SEC)
        h.addWidget(self.count_lbl)
        h.addStretch()
        lay.addWidget(head)

        self.body = _plain()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(20, 0, 20, 16)
        self.body_lay.setSpacing(0)
        self.body.setVisible(expanded)
        lay.addWidget(self.body)

    def _toggle(self):
        self._expanded = not self._expanded
        self.arrow.setText("▾" if self._expanded else "▸")
        self.body.setVisible(self._expanded)
        self._on_toggle(self._expanded)

    def set_count(self, text: str):
        self.count_lbl.setText(text)


class StatTile(QFrame):
    def __init__(self, value: str, label: str, accent: str, sub: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
            lay.addWidget(make_label(sub, 10, color=TEXT_SEC, wrap=True))
        lay.addStretch()


# ── dashboard ─────────────────────────────────────────────────────────────────

class AdminDashboard(QMainWindow):
    def __init__(self, on_logout=None):
        super().__init__()
        self.on_logout = on_logout
        self._docs = []
        self._corr = []
        self._loaded = False
        self._loaded_at = ""
        # Kept outside the widgets so a theme switch doesn't reset them.
        today = QDate.currentDate()
        self._f = {"coder": "", "range": "All time", "frm": today.addDays(-7), "to": today, "q": ""}
        self._expanded = {"activity": True, "codes": False, "coders": True}
        self._shown = {"activity": PAGE, "codes": PAGE}
        self._open = set()
        self.setWindowTitle("SIUT — Admin Dashboard")
        self.resize(1180, 760)
        self.setStyleSheet(f"QMainWindow {{ background:{BG_APP}; }} QWidget {{ background:{BG_APP}; }}")
        self._build_ui()
        self._load()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QWidget()
        top.setFixedHeight(56)
        top.setStyleSheet(f"background:{BG_TOP}; border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(top)
        tb.setContentsMargins(24, 0, 24, 0)
        tb.setSpacing(12)

        tb.addWidget(make_label("SIUT  ICD Coder", 14, bold=True, color=ACCENT))

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet(f"color:{BORDER};")
        tb.addWidget(div)

        tb.addWidget(make_label("Admin Dashboard", 12, color=TEXT_SEC))
        tb.addStretch()

        self.last_refresh_lbl = make_label("", 9, color=TEXT_SEC)
        tb.addWidget(self.last_refresh_lbl)

        export_btn = QPushButton("Export CSV")
        export_btn.setFixedSize(90, 32)
        export_btn.setToolTip("Export everything that matches the current filters")
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{SUCCESS};
                border:1px solid {SUCCESS}; border-radius:6px; font-size:11px;
            }}
            QPushButton:hover {{ background:{SUCCESS}; color:white; }}
        """)
        export_btn.clicked.connect(self._export_csv)
        tb.addWidget(export_btn)

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

        theme_btn = QPushButton("☀" if theme.is_dark() else "◑")
        theme_btn.setFixedSize(32, 32)
        theme_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:6px;
                font-size:14px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        theme_btn.setToolTip("Switch to light theme" if theme.is_dark() else "Switch to dark theme")
        theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(theme_btn)

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

        # Shown when a refresh fails but older numbers are still on screen.
        self.error_strip = make_label("", 10, color="white", wrap=True)
        self.error_strip.setStyleSheet(f"color:white; background:{DANGER}; padding:8px 24px;")
        self.error_strip.setVisible(False)
        root.addWidget(self.error_strip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{BG_APP}; }}
            QScrollBar:vertical {{ background:{BG_APP}; width:8px; border-radius:4px; }}
            QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:4px; }}
        """)

        body = QWidget()
        body.setStyleSheet(f"background:{BG_APP};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(28, 24, 28, 28)
        body_lay.setSpacing(20)

        # Holds the "couldn't reach the server" block when nothing has loaded yet.
        self.first_error = _plain()
        self.first_error_lay = QVBoxLayout(self.first_error)
        self.first_error_lay.setContentsMargins(0, 0, 0, 0)
        self.first_error.setVisible(False)
        body_lay.addWidget(self.first_error)

        self.content = _plain()
        c = QVBoxLayout(self.content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(20)

        tiles = _plain()
        self.tiles_lay = QHBoxLayout(tiles)
        self.tiles_lay.setContentsMargins(0, 0, 0, 0)
        self.tiles_lay.setSpacing(14)
        c.addWidget(tiles)

        c.addWidget(self._build_filters())

        self.sec_activity = Section("Recent Activity", self._expanded["activity"],
                                    lambda s: self._expanded.__setitem__("activity", s))
        self.sec_codes = Section("Most Corrected ICD Codes", self._expanded["codes"],
                                 lambda s: self._expanded.__setitem__("codes", s))
        self.sec_coders = Section("Coders", self._expanded["coders"],
                                  lambda s: self._expanded.__setitem__("coders", s))
        for sec in (self.sec_activity, self.sec_codes, self.sec_coders):
            c.addWidget(sec)

        body_lay.addWidget(self.content)
        body_lay.addStretch()

        scroll.setWidget(body)
        self.scroll = scroll
        root.addWidget(scroll, 1)

    def _build_filters(self) -> QWidget:
        bar = _plain()
        bar.setStyleSheet(f"""
            QWidget {{ background:transparent; }}
            QComboBox, QDateEdit, QLineEdit {{
                background:{BG_CARD}; color:{TEXT_PRI};
                border:1px solid {BORDER}; border-radius:5px;
                padding:4px 8px; min-height:22px; font-size:11px;
            }}
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus {{ border-color:{ACCENT}; }}
            QComboBox QAbstractItemView {{
                background:{BG_CARD}; color:{TEXT_PRI};
                selection-background-color:{ACCENT}; selection-color:white;
                border:1px solid {BORDER};
            }}
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:5px; padding:4px 12px; font-size:11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(make_label("Coder", 10, color=TEXT_SEC))
        self.coder_box = QComboBox()
        self.coder_box.setMinimumWidth(170)
        lay.addWidget(self.coder_box)

        lay.addSpacing(6)
        lay.addWidget(make_label("Date", 10, color=TEXT_SEC))
        self.range_box = QComboBox()
        self.range_box.addItems(RANGES)
        self.range_box.setCurrentText(self._f["range"])
        lay.addWidget(self.range_box)

        self.from_edit = QDateEdit(self._f["frm"])
        self.to_edit = QDateEdit(self._f["to"])
        self.to_lbl = make_label("to", 10, color=TEXT_SEC)
        for e in (self.from_edit, self.to_edit):
            e.setCalendarPopup(True)
            e.setDisplayFormat("dd MMM yyyy")
        lay.addWidget(self.from_edit)
        lay.addWidget(self.to_lbl)
        lay.addWidget(self.to_edit)

        lay.addSpacing(6)
        self.search_box = QLineEdit(self._f["q"])
        self.search_box.setPlaceholderText("Search patient, file or code")
        self.search_box.setClearButtonEnabled(True)
        lay.addWidget(self.search_box, 1)

        clear_btn = QPushButton("Clear filters")
        clear_btn.clicked.connect(self._clear_filters)
        lay.addWidget(clear_btn)

        self.coder_box.currentIndexChanged.connect(self._on_filter_change)
        self.range_box.currentIndexChanged.connect(self._on_filter_change)
        self.from_edit.dateChanged.connect(self._on_filter_change)
        self.to_edit.dateChanged.connect(self._on_filter_change)
        self.search_box.textChanged.connect(self._on_filter_change)
        self._show_custom_dates()
        return bar

    def _show_custom_dates(self):
        custom = self.range_box.currentText() == "Custom range"
        for w in (self.from_edit, self.to_lbl, self.to_edit):
            w.setVisible(custom)

    # ── data ──────────────────────────────────────────────────────────────────

    def _load(self):
        docs = api_client.get_documents()
        corr = [] if api_client.LAST_ERROR else api_client.get_corrections()
        if api_client.LAST_ERROR:
            if self._loaded:
                # Keep the last numbers that loaded and say how old they are.
                self.error_strip.setText(
                    f"Couldn't reach the server — showing data from {self._loaded_at}. "
                    f"Press Refresh to try again.   ({api_client.LAST_ERROR})"
                )
                self.error_strip.setVisible(True)
            else:
                _clear(self.first_error_lay)
                self.first_error_lay.addWidget(make_load_error(api_client.LAST_ERROR, self._load))
                self.first_error.setVisible(True)
                self.content.setVisible(False)
            return

        self.error_strip.setVisible(False)
        self.first_error.setVisible(False)
        self.content.setVisible(True)
        self._docs = docs
        self._corr = _clean_corrections(corr)
        self._loaded = True
        self._loaded_at = datetime.now().strftime("%H:%M:%S")
        self.last_refresh_lbl.setText(f"Last refreshed: {self._loaded_at}")
        self._render_all()

    def _filtered(self):
        coder = self._f["coder"]
        start, end = _range_start_end(self._f["range"], self._f["frm"], self._f["to"])
        q = self._f["q"].strip().lower()
        out = []
        for c in self._corr:
            if coder and c["coder_name"] != coder:
                continue
            at = c["_at"]
            if start and (not at or at < start):
                continue
            if end and (not at or at >= end):
                continue
            if q:
                hay = " ".join(str(c.get(k) or "") for k in
                               ("patient_ref", "source_filename", "original_icd_code", "corrected_icd_code"))
                if q not in hay.lower():
                    continue
            out.append(c)
        return out

    def _on_filter_change(self, *_):
        self._f.update(
            coder=self.coder_box.currentData() or "",
            range=self.range_box.currentText(),
            frm=self.from_edit.date(),
            to=self.to_edit.date(),
            q=self.search_box.text(),
        )
        self._show_custom_dates()
        self._shown = {"activity": PAGE, "codes": PAGE}
        self._render_sections()

    def _clear_filters(self):
        for w in (self.coder_box, self.range_box, self.search_box):
            w.blockSignals(True)
        self.coder_box.setCurrentIndex(0)
        self.range_box.setCurrentText("All time")
        self.search_box.clear()
        for w in (self.coder_box, self.range_box, self.search_box):
            w.blockSignals(False)
        self._on_filter_change()

    def _show_coder(self, name: str):
        """Filter the whole page to one coder (from the Coders section)."""
        i = self.coder_box.findData(name)
        if i >= 0:
            self.coder_box.setCurrentIndex(i)
        self.scroll.verticalScrollBar().setValue(0)

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render_all(self):
        self._render_tiles()
        self._fill_coder_box()
        self._render_sections()

    def _fill_coder_box(self):
        names = sorted({c["coder_name"] for c in self._corr})
        self.coder_box.blockSignals(True)
        self.coder_box.clear()
        self.coder_box.addItem("All coders", "")
        for n in names:
            self.coder_box.addItem(n, n)
        i = self.coder_box.findData(self._f["coder"])
        self.coder_box.setCurrentIndex(i if i >= 0 else 0)
        self._f["coder"] = self.coder_box.currentData() or ""
        self.coder_box.blockSignals(False)

    def _render_sections(self):
        rows = self._filtered()
        self._render_activity(rows)
        self._render_codes(rows)
        self._render_coders(rows)

    def _tile_values(self):
        now = datetime.now().astimezone()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today - timedelta(days=today.weekday())

        waiting = [d for d in self._docs if d.get("status") not in DONE_STATUSES]
        uploads = [t for t in (_parse_time(d.get("upload_date")) for d in waiting) if t]
        if uploads:
            days = (now - min(uploads)).days
            oldest = "oldest waiting since today" if days == 0 else \
                f"oldest waiting {days} day{'s' if days != 1 else ''}"
        else:
            oldest = "nothing waiting" if not waiting else ""

        # Until the server stores a completion time, use the last change made
        # on the record as the moment it was finished.
        last_change = {}
        for c in self._corr:
            d = c.get("document_id")
            if c["_at"] and (d not in last_change or c["_at"] > last_change[d]):
                last_change[d] = c["_at"]
        done_times = []
        for d in self._docs:
            if d.get("status") in DONE_STATUSES:
                t = _parse_time(d.get("completed_at")) or last_change.get(d.get("document_id"))
                if t:
                    done_times.append(t)
        this_week = sum(1 for t in done_times if t >= week_start)
        done_today = sum(1 for t in done_times if t >= today)

        n, decisions = _counts(self._corr)
        def share(k):
            return n[k] / decisions if decisions else 0

        return [
            (str(len(waiting)), "Waiting to be coded", ACCENT, oldest),
            (str(this_week), "Completed this week", SUCCESS, f"{done_today} today"),
            (_pct(share("confirmed")), "Accepted as suggested", ACCENT_L,
             f"{_pct(share('reclassified'))} edited  ·  {_pct(share('rejected'))} rejected"),
            # Needs the medication endpoints (added_by_coder) on the server.
            ("—", "Medications coders added", WARNING, "Shows once the server saves added medications"),
        ]

    def _render_tiles(self):
        _clear(self.tiles_lay)
        for value, label, colour, sub in self._tile_values():
            self.tiles_lay.addWidget(StatTile(value, label, colour, sub))

    def _more_footer(self, lay, shown, total, key):
        if total <= PAGE and shown >= total:
            return
        row = _plain()
        r = QHBoxLayout(row)
        r.setContentsMargins(0, 10, 0, 0)
        r.addWidget(make_label(f"Showing {min(shown, total)} of {total}", 10, color=TEXT_SEC))
        r.addStretch()
        if shown < total:
            more = QPushButton(f"Show {min(PAGE, total - shown)} more")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{ACCENT_L};
                    border:1px solid {BORDER}; border-radius:5px;
                    padding:5px 14px; font-size:11px;
                }}
                QPushButton:hover {{ border-color:{ACCENT}; color:{TEXT_PRI}; }}
            """)
            more.clicked.connect(lambda: self._show_more(key))
            r.addWidget(more)
        lay.addWidget(row)

    def _show_more(self, key):
        self._shown[key] += PAGE
        rows = self._filtered()
        if key == "activity":
            self._render_activity(rows)
        else:
            self._render_codes(rows)

    def _empty(self, lay, text):
        lbl = make_label(text, 11, color=TEXT_SEC)
        lbl.setContentsMargins(0, 8, 0, 4)
        lay.addWidget(lbl)

    def _render_activity(self, rows):
        sec = self.sec_activity
        _clear(sec.body_lay)
        sec.set_count(f"{len(rows)} change{'s' if len(rows) != 1 else ''}")
        if not rows:
            self._empty(sec.body_lay, "No changes match these filters.")
            return
        sec.body_lay.addWidget(_header(CHANGE_COLS))
        shown = self._shown["activity"]
        for c in rows[:shown]:
            sec.body_lay.addWidget(_change_line(c))
        self._more_footer(sec.body_lay, shown, len(rows), "activity")

    def _code_groups(self, rows):
        # Description of the code the NLP suggested. Rows without a new code
        # carry that description; edit rows describe the new code instead.
        desc = {}
        for c in self._corr:
            if not c.get("corrected_icd_code") and c.get("original_icd_code") and c.get("icd_description"):
                desc.setdefault(c["original_icd_code"], c["icd_description"])

        groups = {}
        for c in rows:
            kind = c.get("correction_type")
            if kind not in ("reclassified", "rejected"):
                continue
            code = c.get("original_icd_code") or "?"
            g = groups.setdefault(code, {"code": code, "desc": desc.get(code, ""),
                                         "edits": 0, "rejects": 0, "to": Counter(), "rows": []})
            g["rows"].append(c)
            if kind == "reclassified":
                g["edits"] += 1
                g["to"][c.get("corrected_icd_code") or "?"] += 1
            else:
                g["rejects"] += 1
        return sorted(groups.values(), key=lambda g: (-(g["edits"] + g["rejects"]), g["code"]))

    def _render_codes(self, rows):
        sec = self.sec_codes
        _clear(sec.body_lay)
        groups = self._code_groups(rows)
        sec.set_count(f"{len(groups)} code{'s' if len(groups) != 1 else ''}")
        if not groups:
            self._empty(sec.body_lay, "No edits or rejections match these filters.")
            return
        hint = make_label("Codes the NLP suggested that coders changed or rejected. "
                          "Click a code to see who changed it, when, and in which file.",
                          10, color=TEXT_SEC, wrap=True)
        hint.setContentsMargins(0, 2, 0, 6)
        sec.body_lay.addWidget(hint)

        shown = self._shown["codes"]
        for g in groups[:shown]:
            content = _plain()
            v = QVBoxLayout(content)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(3)

            top = QHBoxLayout()
            top.setSpacing(10)
            code = make_label(g["code"], 11, bold=True, color=TEXT_CODE)
            code.setFixedWidth(90)
            top.addWidget(code)
            top.addWidget(make_label(g["desc"], 10, color=TEXT_SEC), 1)
            parts = []
            if g["edits"]:
                parts.append(f"{g['edits']} edit{'s' if g['edits'] != 1 else ''}")
            if g["rejects"]:
                parts.append(f"{g['rejects']} rejected")
            top.addWidget(make_label("  ·  ".join(parts), 10, bold=True))
            v.addLayout(top)

            if g["to"]:
                to = "     ".join(f"→ {new} ×{n}" for new, n in g["to"].most_common())
                changed = make_label(f"changed to   {to}", 10, color=WARNING)
                changed.setContentsMargins(100, 0, 0, 0)
                v.addWidget(changed)

            sec.body_lay.addWidget(_ExpandLine(
                content, lambda rs=g["rows"]: _change_list(rs), f"code:{g['code']}", self._open,
            ))
        self._more_footer(sec.body_lay, shown, len(groups), "codes")

    def _render_coders(self, rows):
        sec = self.sec_coders
        _clear(sec.body_lay)
        by_coder = defaultdict(list)
        for c in rows:
            by_coder[c["coder_name"]].append(c)
        sec.set_count(f"{len(by_coder)} coder{'s' if len(by_coder) != 1 else ''}")
        if not by_coder:
            self._empty(sec.body_lay, "No coder activity matches these filters.")
            return

        # Shown once the server records who completed each record.
        finished = None
        if any("completed_by" in d for d in self._docs):
            finished = Counter(d.get("completed_by") for d in self._docs
                               if d.get("status") in DONE_STATUSES)

        cols = [("Coder", 160), ("Records", 70)]
        if finished is not None:
            cols.append(("Finished", 70))
        cols += [("Decisions", 80), ("Accepted", 80), ("Edited", 80), ("Rejected", 80), ("Last active", 0)]
        sec.body_lay.addWidget(_header(cols, indent=18))

        for name in sorted(by_coder, key=lambda n: -len(by_coder[n])):
            cr = by_coder[name]
            n, decisions = _counts(cr)
            def share(k, n=n, d=decisions):
                return _pct(n[k] / d) if d else "—"
            cells = [make_label(name, 10, bold=True), str(len({c.get("document_id") for c in cr}))]
            if finished is not None:
                cells.append(str(finished.get(name, 0)))
            cells += [str(decisions), share("confirmed"), share("reclassified"), share("rejected"),
                      _fmt_time(max((c["_at"] for c in cr if c["_at"]), default=None))]
            sec.body_lay.addWidget(_ExpandLine(
                _grid(cells, [w for _, w in cols]),
                lambda nm=name, cr=cr: self._coder_files(nm, cr),
                f"coder:{name}", self._open,
            ))

    def _coder_files(self, name, rows):
        """Every file this coder worked on; click a file to see each change."""
        box = QFrame()
        box.setObjectName("detail")
        box.setStyleSheet(f"QFrame#detail {{ background:{BG_PANEL}; border-radius:6px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(0)

        top = QHBoxLayout()
        top.addWidget(make_label("Files worked on", 10, bold=True, color=TEXT_SEC))
        top.addStretch()
        only = QPushButton(f"Show only {name}'s changes")
        only.setCursor(Qt.CursorShape.PointingHandCursor)
        only.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{ACCENT_L}; border:none; font-size:11px; }}
            QPushButton:hover {{ color:{TEXT_PRI}; text-decoration:underline; }}
        """)
        only.clicked.connect(lambda: self._show_coder(name))
        top.addWidget(only)
        lay.addLayout(top)

        by_doc = defaultdict(list)
        for c in rows:
            by_doc[c.get("document_id")].append(c)
        cols = [("File", 0), ("Patient", 110), ("Decisions", 80), ("Edits", 70), ("Last worked on", 150)]
        lay.addWidget(_header(cols, indent=18))
        ordered = sorted(by_doc.items(), key=lambda kv: max(
            (c["_at"] for c in kv[1] if c["_at"]), default=datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True)
        for doc_id, cr in ordered:
            n, decisions = _counts(cr)
            first = cr[0]
            cells = [
                first.get("source_filename") or f"Record {doc_id}",
                first.get("patient_ref") or "—",
                str(decisions),
                str(n["reclassified"]),
                make_label(_fmt_time(max((c["_at"] for c in cr if c["_at"]), default=None)),
                           10, color=TEXT_SEC),
            ]
            lay.addWidget(_ExpandLine(
                _grid(cells, [w for _, w in cols]),
                lambda cr=cr: _change_list(cr),
                f"file:{name}:{doc_id}", self._open,
            ))
        return box

    # ── actions ───────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        theme.toggle()
        _reload_colors()

        old = self.centralWidget()
        self.setStyleSheet(
            f"QMainWindow {{ background:{BG_APP}; }} QWidget {{ background:{BG_APP}; }}"
        )
        self._build_ui()
        if self._loaded:
            self.last_refresh_lbl.setText(f"Last refreshed: {self._loaded_at}")
            self._render_all()
        else:
            self._load()

        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.get_app_style())

        if old:
            old.setParent(None)
            old.deleteLater()

    def _export_csv(self):
        if not self._loaded:
            QMessageBox.warning(self, "No Data", "Nothing has loaded yet, so there is nothing to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Analytics",
            f"khidmat_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if not filepath:
            return

        rows = self._filtered()
        f = self._f
        if f["range"] == "Custom range":
            period = f"{f['frm'].toString('dd MMM yyyy')} to {f['to'].toString('dd MMM yyyy')}"
        else:
            period = f["range"]

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["KHIDMAT ANALYTICS EXPORT"])
                writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow([f"Coder: {f['coder'] or 'All coders'}", f"Period: {period}",
                                 f"Search: {f['q'] or '—'}"])
                writer.writerow([])

                writer.writerow(["SUMMARY"])
                writer.writerow(["Metric", "Value", "Detail"])
                for value, label, _, sub in self._tile_values():
                    writer.writerow([label, value, sub])
                writer.writerow([])

                # Every change that matches the filters, not just the rows on screen.
                writer.writerow(["CHANGES"])
                writer.writerow(["Date & time", "Coder", "Action", "Suggested code",
                                 "New code", "Patient", "File", "Comment"])
                for c in rows:
                    writer.writerow([
                        _fmt_time(c["_at"]), c["coder_name"],
                        ACTION_NAMES.get(c.get("correction_type"), c.get("correction_type", "")),
                        c.get("original_icd_code") or "", c.get("corrected_icd_code") or "",
                        c.get("patient_ref") or "", c.get("source_filename") or "",
                        c.get("comment") or "",
                    ])
                writer.writerow([])

                writer.writerow(["MOST CORRECTED ICD CODES"])
                writer.writerow(["Suggested code", "Description", "Edits", "Rejected", "Changed to"])
                for g in self._code_groups(rows):
                    writer.writerow([
                        g["code"], g["desc"], g["edits"], g["rejects"],
                        ", ".join(f"{new} x{n}" for new, n in g["to"].most_common()),
                    ])
                writer.writerow([])

                writer.writerow(["CODERS"])
                writer.writerow(["Coder", "Records", "Decisions", "Accepted", "Edited", "Rejected"])
                by_coder = defaultdict(list)
                for c in rows:
                    by_coder[c["coder_name"]].append(c)
                for name, cr in sorted(by_coder.items()):
                    n, decisions = _counts(cr)
                    writer.writerow([
                        name, len({c.get("document_id") for c in cr}), decisions,
                        *(_pct(n[k] / decisions) if decisions else "—"
                          for k in ("confirmed", "reclassified", "rejected")),
                    ])

            QMessageBox.information(self, "Exported", f"Exported {len(rows)} changes to:\n{filepath}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export: {e}")

    def _logout(self):
        reply = QMessageBox.question(
            self, "Log Out",
            "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.on_logout:
                self.on_logout()
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AdminDashboard()
    window.show()
    sys.exit(app.exec())
