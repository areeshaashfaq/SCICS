import sys
import api_client
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QFileDialog,
    QInputDialog, QSizePolicy, QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BG_APP    = "#0F1923"
BG_PANEL  = "#162230"
BG_CARD   = "#1C2D3E"
BORDER    = "#253D52"
ACCENT    = "#2E7DD1"
ACCENT_L  = "#3D8FE8"
SUCCESS   = "#27AE60"
DANGER    = "#C0392B"
TEXT_PRI  = "#E8EDF2"
TEXT_SEC  = "#8FA8BF"
TEXT_CODE = "#5BB8FF"

PAGE_SIZE = 10  # records per page


def make_label(text, size=12, bold=False, color=TEXT_PRI, wrap=False):
    lbl = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{color}; background:transparent;")
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

        lay.addWidget(make_label(self.doc.get("upload_date", "")[:10], 10, color=TEXT_SEC))

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
        self._current_page = 0
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
        top.setStyleSheet(f"background:#0A1520; border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(top)
        tb.setContentsMargins(24, 0, 24, 0)
        tb.addWidget(make_label("SIUT  ICD Coder", 14, bold=True, color=ACCENT))
        tb.addSpacing(16)
        tb.addWidget(make_label("Record Queue", 12, color=TEXT_SEC))
        tb.addStretch()

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

        self.upload_btn = QPushButton("+ Upload .txt File")
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
                background: #0A1520; color: {TEXT_PRI};
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
        root.addWidget(self.scroll, 1)

        # ── pagination bar ────────────────────────────────────────────────────
        page_bar = QWidget()
        page_bar.setFixedHeight(48)
        page_bar.setStyleSheet(f"background:{BG_PANEL}; border-top:1px solid {BORDER};")
        pb = QHBoxLayout(page_bar)
        pb.setContentsMargins(24, 0, 24, 0)
        pb.setSpacing(8)

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFixedSize(96, 30)
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:5px; font-size:11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
            QPushButton:disabled {{ color:#3A4A5A; border-color:#1C2D3E; }}
        """)
        self.prev_btn.clicked.connect(self._prev_page)
        pb.addWidget(self.prev_btn)

        self.page_lbl = make_label("Page 1 of 1", 11, color=TEXT_SEC)
        self.page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pb.addWidget(self.page_lbl)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setFixedSize(96, 30)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:5px; font-size:11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
            QPushButton:disabled {{ color:#3A4A5A; border-color:#1C2D3E; }}
        """)
        self.next_btn.clicked.connect(self._next_page)
        pb.addWidget(self.next_btn)

        root.addWidget(page_bar)

    def _load(self):
        self.status_lbl.setText("Loading…")
        try:
            self._all_docs = api_client.get_documents()
        except Exception as e:
            self.status_lbl.setText(f"Cannot connect to backend: {e}")
            return
        self._filtered_docs = self._all_docs
        self._current_page = 0
        self._render_page()

    def _on_search(self, text: str):
        if not text:
            self._filtered_docs = self._all_docs
        else:
            text = text.lower()
            self._filtered_docs = [
                d for d in self._all_docs
                if text in d.get("patient_ref", "").lower()
                or text in d.get("source_filename", "").lower()
            ]
        self._current_page = 0
        self._render_page()

    def _filter_by_status(self, status: str):
        if status == "all":
            self._filtered_docs = self._all_docs
        else:
            self._filtered_docs = [d for d in self._all_docs if d.get("status") == status]
        self._current_page = 0
        self._render_page()

    def _render_page(self):
        # clear list
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        docs = self._filtered_docs
        total = len(docs)

        if total == 0:
            self.status_lbl.setText("No records found.")
            self.page_lbl.setText("Page 0 of 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        start = self._current_page * PAGE_SIZE
        end   = min(start + PAGE_SIZE, total)
        page_docs = docs[start:end]

        for doc in page_docs:
            row = RecordRow(doc, on_open=self._open_record)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

        complete = len([d for d in docs if d.get("status") in ("reviewed", "finalized")])
        self.status_lbl.setText(
            f"{total} record{'s' if total != 1 else ''}  ·  {complete} reviewed  ·  {total - complete} pending"
            f"  ·  showing {start + 1}–{end}"
        )
        self.page_lbl.setText(f"Page {self._current_page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self._current_page > 0)
        self.next_btn.setEnabled(self._current_page < total_pages - 1)

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render_page()

    def _next_page(self):
        total_pages = max(1, (len(self._filtered_docs) + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._render_page()

    def _upload(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select discharge summary", "", "Text Files (*.txt)"
        )
        if not filepath:
            return

        patient_ref, ok = QInputDialog.getText(
            self, "Patient Reference", "Enter patient ref (e.g. 00247-KHI):"
        )
        if not ok:
            patient_ref = ""

        self.upload_btn.setEnabled(False)
        self.upload_btn.setText("Processing…")
        self.status_lbl.setText("Uploading and running NLP pipeline…")

        try:
            result = api_client.upload_document(filepath, patient_ref)
            doc_id = result.get("document_id")
            count  = result.get("suggestions_generated", 0)
            self.status_lbl.setText(f"Done — {count} suggestions generated.")
            self._load()
            if doc_id is not None:
                self._open_record(doc_id)
        except Exception as e:
            self.status_lbl.setText(f"Upload failed: {e}")
        finally:
            self.upload_btn.setEnabled(True)
            self.upload_btn.setText("+ Upload .txt File")

    def _open_record(self, document_id: int):
        if self.on_open_record:
            self.on_open_record(document_id)
        else:
            from codingworkspace import CodingWorkspace
            self._workspace = CodingWorkspace(
                document_id=document_id,
                on_back=lambda: (self.show(), self._load()),
            )
            self._workspace.show()
            self.hide()

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