import sys
import api_client
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QFileDialog,
    QInputDialog, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ── palette (matches codingworkspace) ─────────────────────────────────────────
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


def make_label(text, size=12, bold=False, color=TEXT_PRI, wrap=False):
    lbl = QLabel(text)
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color:{color}; background:transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


# ── single row card ───────────────────────────────────────────────────────────
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

        # left: patient ref + filename
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(make_label(
            self.doc.get("patient_ref", "—"), 12, bold=True
        ))
        left.addWidget(make_label(
            self.doc.get("source_filename", ""), 10, color=TEXT_SEC
        ))
        lay.addLayout(left)

        lay.addStretch()

        # date
        lay.addWidget(make_label(
            self.doc.get("upload_date", "")[:10], 10, color=TEXT_SEC
        ))

        # status chip
        status = self.doc.get("status", "pending")
        chip_color = SUCCESS if status == "complete" else TEXT_SEC
        chip = QLabel(status.upper())
        chip.setStyleSheet(
            f"color:{chip_color}; border:1px solid {chip_color};"
            f"border-radius:4px; padding:2px 10px; font-size:10px; font-weight:bold;"
        )
        lay.addWidget(chip)

        # open button
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


# ── main queue window ─────────────────────────────────────────────────────────
class RecordQueueWindow(QMainWindow):
    def __init__(self, on_open_record=None, on_logout=None):
        super().__init__()
        self.on_open_record = on_open_record  # callback(document_id)
        self.on_logout = on_logout
        self.setWindowTitle("SIUT — Record Queue")
        self.resize(860, 640)
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

        # ── status bar ────────────────────────────────────────────────────────
        self.status_bar = QWidget()
        self.status_bar.setFixedHeight(36)
        self.status_bar.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
        sb = QHBoxLayout(self.status_bar)
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
        root.addWidget(self.status_bar)

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
        # clear existing rows
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.status_lbl.setText("Loading…")

        try:
            docs = api_client.get_documents()
        except Exception as e:
            self.status_lbl.setText(f"Cannot connect to backend: {e}")
            return

        if not docs:
            self.status_lbl.setText("No records yet — upload a .txt file to begin.")
            return

        pending  = [d for d in docs if d.get("status") != "complete"]
        complete = [d for d in docs if d.get("status") == "complete"]

        # pending first, then complete
        for doc in pending + complete:
            row = RecordRow(doc, on_open=self._open_record)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

        total    = len(docs)
        n_done   = len(complete)
        self.status_lbl.setText(f"{total} record{'s' if total != 1 else ''}  ·  {n_done} complete  ·  {total - n_done} pending")

    # ── upload ────────────────────────────────────────────────────────────────
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
            self._load()                      # refresh list
            if doc_id is not None:
                self._open_record(doc_id)    # jump straight to workspace
        except Exception as e:
            self.status_lbl.setText(f"Upload failed: {e}")
        finally:
            self.upload_btn.setEnabled(True)
            self.upload_btn.setText("+ Upload .txt File")

    # ── open record ───────────────────────────────────────────────────────────
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

    # ── logout ────────────────────────────────────────────────────────────────
    def _logout(self):
        if self.on_logout:
            self.on_logout()
        self.close()

    # ── open history ──────────────────────────────────────────────────────────
    def _open_history(self):
        from coder_history import CoderHistoryWindow
        self._history = CoderHistoryWindow(on_back=lambda: self.show())
        self._history.show()
        self.hide()


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = RecordQueueWindow()
    window.show()
    sys.exit(app.exec())
