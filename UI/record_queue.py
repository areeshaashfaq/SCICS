import sys
import api_client
import theme
from load_error import make_load_error
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame,
    QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

BG_APP = BG_PANEL = BG_CARD = BG_TOP = BORDER = ""
ACCENT = ACCENT_L = SUCCESS = DANGER = ""
TEXT_PRI = TEXT_SEC = TEXT_CODE = ""


def _reload_colors():
    global BG_APP, BG_PANEL, BG_CARD, BG_TOP, BORDER
    global ACCENT, ACCENT_L, SUCCESS, DANGER
    global TEXT_PRI, TEXT_SEC, TEXT_CODE
    t = theme.current
    BG_APP    = t["BG_APP"]
    BG_PANEL  = t["BG_PANEL"]
    BG_CARD   = t["BG_CARD"]
    BG_TOP    = t["BG_TOP"]
    BORDER    = t["BORDER"]
    ACCENT    = t["ACCENT"]
    ACCENT_L  = t["ACCENT_LITE"]
    SUCCESS   = t["SUCCESS"]
    DANGER    = t["DANGER"]
    TEXT_PRI  = t["TEXT_PRI"]
    TEXT_SEC  = t["TEXT_SEC"]
    TEXT_CODE = t["TEXT_CODE"]


_reload_colors()

BATCH_SIZE = 25

URGENCY_AMBER = "#F39C12"
URGENCY_RED   = "#C0392B"


def _relative_date(date_str: str):
    """Return (label, color) like ('2 days ago', URGENCY_RED)."""
    if not date_str:
        return "—", TEXT_SEC
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now  = datetime.now(timezone.utc)
        diff = now - dt
        hours = diff.total_seconds() / 3600
        if hours < 1:
            label = "Just now"
        elif hours < 24:
            h = int(hours)
            label = f"{h}h ago"
        elif hours < 48:
            label = "Yesterday"
        else:
            days = int(hours // 24)
            label = f"{days} days ago"

        if hours > 48:
            color = URGENCY_RED
        elif hours > 24:
            color = URGENCY_AMBER
        else:
            color = SUCCESS
        return label, color
    except Exception:
        return date_str[:10], TEXT_SEC


def make_label(text, size=12, bold=False, color=None, wrap=False):
    lbl = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{color or TEXT_PRI}; background:transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


class RecordRow(QFrame):
    def __init__(self, doc: dict, on_open):
        super().__init__()
        self.doc = doc
        self.on_open = on_open
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            RecordRow {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            RecordRow:hover {{
                border: 1px solid {ACCENT};
            }}
        """)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(make_label(self.doc.get("patient_ref", "—"), 12, bold=True))
        left.addWidget(make_label(self.doc.get("source_filename", ""), 10, color=TEXT_SEC))
        lay.addLayout(left)

        lay.addStretch()

        rel_label, rel_color = _relative_date(self.doc.get("upload_date", ""))
        lay.addWidget(make_label(rel_label, 10, color=rel_color))

        status = self.doc.get("status", "pending")
        chip_color = SUCCESS if status in ("reviewed", "finalized") else TEXT_SEC
        chip = QLabel(status.upper())
        chip.setStyleSheet(
            f"color:{chip_color}; border:1px solid {chip_color};"
            f"border-radius:4px; padding:2px 10px; font-size:10px; font-weight:bold;"
        )
        lay.addWidget(chip)

        btn = QPushButton("Open →")
        btn.setFixedSize(80, 32)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:white;
                border:none; border-radius:5px;
                font-size:11px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{ACCENT_L}; }}
        """)
        btn.clicked.connect(lambda: self.on_open(self.doc["document_id"]))
        lay.addWidget(btn)



class RecordQueueWindow(QMainWindow):
    def __init__(self, on_open_record=None, on_logout=None):
        super().__init__()
        self.on_open_record = on_open_record
        self.on_logout = on_logout
        self._all_docs = []
        self._filtered_docs = []
        self._rendered_count = 0
        self._sort_order = "newest"   # "newest" | "oldest"
        self._saved_scroll = 0
        self.setWindowTitle("SIUT — Record Queue")
        self.resize(860, 680)
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
        top.setStyleSheet(f"background:{BG_TOP}; border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(top)
        tb.setContentsMargins(24, 0, 24, 0)
        tb.addWidget(make_label("SIUT  ICD Coder", 14, bold=True, color=ACCENT))
        tb.addSpacing(16)
        tb.addWidget(make_label("Record Queue", 12, color=TEXT_SEC))
        tb.addStretch()

        theme_btn = QPushButton("☀" if theme.is_dark() else "◑")
        theme_btn.setFixedSize(34, 34)
        theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        theme_btn.setToolTip("Switch to light theme" if theme.is_dark() else "Switch to dark theme")
        theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(theme_btn)

        history_btn = QPushButton("History")
        history_btn.setFixedSize(80, 34)
        history_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        history_btn.clicked.connect(self._open_history)
        tb.addWidget(history_btn)

        logout_btn = QPushButton("Log Out")
        logout_btn.setFixedSize(80, 34)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {DANGER};
                border: 1px solid {DANGER}; border-radius: 6px;
                font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background:{DANGER}; color:white; }}
        """)
        logout_btn.clicked.connect(self._logout)
        tb.addWidget(logout_btn)

        self.upload_btn = QPushButton("+ Add Summary")
        self.upload_btn.setFixedSize(140, 34)
        self.upload_btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:white;
                border:none; border-radius:6px;
                font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{ACCENT_L}; }}
        """)
        self.upload_btn.clicked.connect(self._upload)
        tb.addWidget(self.upload_btn)
        root.addWidget(top)

        # ── search bar ────────────────────────────────────────────────────────
        search_bar = QWidget()
        search_bar.setFixedHeight(48)
        search_bar.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
        sb_lay = QHBoxLayout(search_bar)
        sb_lay.setContentsMargins(24, 8, 24, 8)
        sb_lay.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by patient ref or filename...")
        self.search_input.setFixedHeight(30)
        self.search_input.setFont(QFont("Segoe UI", 11))
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_TOP}; color: {TEXT_PRI};
                border: 1px solid {BORDER}; border-radius: 5px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self.search_input.textChanged.connect(self._on_search)
        sb_lay.addWidget(self.search_input)

        for label, status in [("All", "all"), ("Pending", "pending"), ("Reviewed", "reviewed")]:
            btn = QPushButton(label)
            btn.setFixedSize(72, 26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TEXT_SEC};
                    border: 1px solid {BORDER}; border-radius: 5px;
                    font-size: 11px;
                }}
                QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
            """)
            btn.clicked.connect(lambda checked, s=status: self._filter_by_status(s))
            sb_lay.addWidget(btn)

        divider = make_label("|", 11, color=BORDER)
        sb_lay.addWidget(divider)

        self._sort_btn = QPushButton("↓ Newest")
        self._sort_btn.setFixedSize(90, 26)
        self._sort_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {ACCENT};
                border: 1px solid {ACCENT}55; border-radius: 5px;
                font-size: 11px;
            }}
            QPushButton:hover {{ border-color:{ACCENT}; }}
        """)
        self._sort_btn.clicked.connect(self._toggle_sort)
        sb_lay.addWidget(self._sort_btn)

        root.addWidget(search_bar)

        # ── status bar ────────────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(36)
        status_bar.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(24, 0, 24, 0)
        self.status_lbl = make_label("Loading records…", 11, color=TEXT_SEC)
        sb.addWidget(self.status_lbl)
        sb.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(70, 24)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:4px; font-size:11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        refresh_btn.clicked.connect(self._load)
        sb.addWidget(refresh_btn)
        root.addWidget(status_bar)

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
        self.list_layout.setContentsMargins(24, 20, 24, 12)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.list_container)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        root.addWidget(self.scroll, 1)

    def _toggle_theme(self):
        theme.toggle()
        _reload_colors()

        search_text   = self.search_input.text()
        sort_order    = self._sort_order
        sort_text     = self._sort_btn.text()
        status_filter = getattr(self, "_status_filter", "all")
        all_docs      = list(self._all_docs)
        filtered_docs = list(self._filtered_docs)

        old = self.centralWidget()
        self.setStyleSheet(
            f"QMainWindow {{ background:{BG_APP}; }} QWidget {{ background:{BG_APP}; }}"
        )
        self._build_ui()

        self._sort_order    = sort_order
        self._sort_btn.setText(sort_text)
        self._status_filter = status_filter
        self._all_docs      = all_docs
        self._filtered_docs = filtered_docs
        self.search_input.blockSignals(True)
        self.search_input.setText(search_text)
        self.search_input.blockSignals(False)

        self._render_page()

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.get_app_style())

        if old:
            old.setParent(None)
            old.deleteLater()

    def _load(self):
        self.status_lbl.setText("Loading…")
        docs = api_client.get_documents()
        if api_client.LAST_ERROR:
            # An empty list here would read as "No records found", which is wrong.
            self._show_load_error(api_client.LAST_ERROR)
            return
        self._all_docs = docs
        self._apply_filters()

    def _show_load_error(self, detail: str):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.list_layout.insertWidget(0, make_load_error(detail, self._load))
        self.status_lbl.setText("Couldn't load records.")

    def _on_search(self, text: str):
        self._apply_filters()

    def _filter_by_status(self, status: str):
        self._status_filter = status
        self._apply_filters()

    def _toggle_sort(self):
        if self._sort_order == "newest":
            self._sort_order = "oldest"
            self._sort_btn.setText("↑ Oldest")
        else:
            self._sort_order = "newest"
            self._sort_btn.setText("↓ Newest")
        self._apply_filters()

    def _apply_filters(self):
        query = self.search_input.text().strip().lower()
        docs = self._all_docs

        status = getattr(self, "_status_filter", "all")
        if status != "all":
            docs = [d for d in docs if d.get("status") == status]

        if query:
            docs = [
                d for d in docs
                if query in str(d.get("patient_ref", "")).lower()
                or query in str(d.get("source_filename", "")).lower()
            ]

        reverse = (self._sort_order == "newest")
        docs = sorted(docs, key=lambda d: d.get("upload_date", "") or "", reverse=reverse)

        self._filtered_docs = docs
        self._rendered_count = 0
        self._render_page()

    def _render_page(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._rendered_count = 0
        docs = self._filtered_docs
        if not docs:
            self.status_lbl.setText("No records found.")
            return

        self._append_rows(min(BATCH_SIZE, len(docs)))
        self._update_status_lbl()

    def _append_rows(self, up_to: int):
        docs = self._filtered_docs
        end = min(up_to, len(docs))
        for doc in docs[self._rendered_count:end]:
            row = RecordRow(doc, on_open=self._open_record)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self._rendered_count = end

    def _append_more(self):
        if self._rendered_count >= len(self._filtered_docs):
            return
        self._append_rows(self._rendered_count + BATCH_SIZE)
        self._update_status_lbl()

    def _update_status_lbl(self):
        docs = self._filtered_docs
        total = len(docs)
        complete = len([d for d in docs if d.get("status") in ("reviewed", "finalized")])
        shown = self._rendered_count
        self.status_lbl.setText(
            f"{total} record{'s' if total != 1 else ''}  ·  {complete} reviewed  ·  {total - complete} pending"
            + (f"  ·  showing {shown} of {total}" if shown < total else "")
        )

    def _on_scroll(self, value: int):
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() > 0 and value >= bar.maximum() * 0.85:
            self._append_more()

    def _upload(self):
        """Take a pasted summary or a PDF/TXT file, then code it.

        SIUT asked for both routes: saving a .txt first just to upload it was
        wasting coder time when the summary is already on their screen.
        """
        from import_dialog import ImportDialog

        dialog = ImportDialog(self)
        if dialog.exec() != ImportDialog.DialogCode.Accepted:
            return

        patient_ref, pasted_text, filepath = dialog.result_values()

        self.upload_btn.setEnabled(False)
        self.upload_btn.setText("Processing…")
        self.status_lbl.setText("Reading the summary and running the NLP pipeline…")

        try:
            if filepath:
                result = api_client.upload_document(filepath, patient_ref)
            else:
                result = api_client.upload_text(pasted_text, patient_ref)

            # api_client returns an error dict rather than raising, so the
            # failure has to be checked here or a failed upload looks fine.
            if isinstance(result, dict) and result.get("error"):
                self.status_lbl.setText("Upload failed — see the message above.")
                return

            doc_id = result.get("document_id")
            count  = result.get("suggestions_generated", 0)
            self.status_lbl.setText(f"Done — {count} suggestions generated.")
            self._load()
            if doc_id is not None:
                self._open_record(doc_id)
        finally:
            self.upload_btn.setEnabled(True)
            self.upload_btn.setText("+ Add Summary")

    def _open_record(self, document_id: int):
        if self.on_open_record:
            self.on_open_record(document_id)
        else:
            from codingworkspace import CodingWorkspace
            self._saved_scroll = self.scroll.verticalScrollBar().value()
            self._workspace = CodingWorkspace(
                document_id=document_id,
                on_back=lambda: self._return_from_workspace(),
            )
            self._workspace.setGeometry(self.geometry())
            self._workspace.showMaximized() if self.isMaximized() else self._workspace.show()
            self.hide()

    def _return_from_workspace(self):
        self._workspace.hide()
        self.show()
        saved = self._saved_scroll
        self._load()
        QTimer.singleShot(150, lambda: self.scroll.verticalScrollBar().setValue(saved))

    def _logout(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Log Out")
        box.setText("Are you sure you want to log out?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setStyleSheet(
            f"QMessageBox {{ background:{BG_PANEL}; }}"
            f"QLabel {{ color:{TEXT_PRI}; font-size:12px; }}"
            f"QPushButton {{ background:{BG_CARD}; color:{TEXT_PRI};"
            f" border:1px solid {BORDER}; border-radius:4px;"
            f" padding:5px 18px; min-width:60px; }}"
        )
        if box.exec() == QMessageBox.StandardButton.Yes:
            if self.on_logout:
                self.on_logout()
            self.close()

    def _open_history(self):
        from coder_history import CoderHistoryWindow
        self._history = CoderHistoryWindow(on_back=lambda: self.show())
        self._history.show()
        self.hide()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = RecordQueueWindow()
    window.show()
    sys.exit(app.exec())