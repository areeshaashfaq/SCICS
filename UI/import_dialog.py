"""
import_dialog.py — how a coder gets a discharge summary into Khidmat.

SIUT asked for two routes, because copying from their hospital system into a
saved .txt file first was wasting coder time:

  1. paste the summary text straight in
  2. pick a PDF or TXT file

The dialog returns (patient_ref, text_or_none, filepath_or_none) so the caller
can send whichever the coder actually used.
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

BG_APP    = "#0F1923"
BG_PANEL  = "#162230"
BG_DARK   = "#0A1520"
BORDER    = "#253D52"
ACCENT    = "#2E7DD1"
ACCENT_L  = "#3D8FE8"
DANGER    = "#C0392B"
TEXT_PRI  = "#E8EDF2"
TEXT_SEC  = "#8FA8BF"

# Below this a "summary" is almost certainly a mis-paste, and the pipeline
# would produce nothing useful from it.
MIN_CHARS = 40


class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Discharge Summary")
        self.setMinimumSize(620, 520)
        self.setStyleSheet(f"QDialog {{ background:{BG_APP}; }}")

        self._filepath = None
        self._build_ui()

    # ── ui ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(10)

        root.addWidget(self._label("Patient reference", bold=True))
        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("e.g. 00247-KHI")
        self.ref_input.setFixedHeight(34)
        self.ref_input.setStyleSheet(self._input_style())
        root.addWidget(self.ref_input)

        root.addSpacing(6)
        root.addWidget(self._label("Paste the discharge summary", bold=True))
        root.addWidget(self._label(
            "Copy the summary from your system and paste it here.", size=9,
            color=TEXT_SEC))

        self.text_box = QTextEdit()
        self.text_box.setPlaceholderText("Paste the discharge summary text…")
        self.text_box.setFont(QFont("Consolas", 10))
        self.text_box.setStyleSheet(f"""
            QTextEdit {{
                background:{BG_DARK}; color:{TEXT_PRI};
                border:1px solid {BORDER}; border-radius:6px; padding:8px;
            }}
            QTextEdit:focus {{ border-color:{ACCENT}; }}
        """)
        self.text_box.textChanged.connect(self._on_text_changed)
        root.addWidget(self.text_box, 1)

        # ── or, a file ────────────────────────────────────────────────────
        sep = QHBoxLayout()
        sep.addWidget(self._rule())
        sep.addWidget(self._label("  or  ", size=9, color=TEXT_SEC))
        sep.addWidget(self._rule())
        root.addLayout(sep)

        file_row = QHBoxLayout()
        file_row.setSpacing(10)

        self.browse_btn = QPushButton("Choose PDF or TXT file…")
        self.browse_btn.setFixedHeight(34)
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_PRI};
                border:1px solid {BORDER}; border-radius:6px;
                padding:0 16px; font-size:11px;
            }}
            QPushButton:hover {{ border-color:{ACCENT}; }}
        """)
        self.browse_btn.clicked.connect(self._choose_file)
        file_row.addWidget(self.browse_btn)

        self.file_lbl = self._label("No file selected", size=10, color=TEXT_SEC)
        file_row.addWidget(self.file_lbl, 1)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setVisible(False)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:4px; font-size:11px;
            }}
            QPushButton:hover {{ color:{DANGER}; border-color:{DANGER}; }}
        """)
        self.clear_btn.clicked.connect(self._clear_file)
        file_row.addWidget(self.clear_btn)

        root.addLayout(file_row)

        self.error_lbl = self._label("", size=10, color=DANGER)
        self.error_lbl.setVisible(False)
        root.addWidget(self.error_lbl)

        root.addSpacing(4)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setFixedSize(92, 36)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{TEXT_SEC};
                border:1px solid {BORDER}; border-radius:6px; font-size:11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)

        self.ok_btn = QPushButton("Add and code")
        self.ok_btn.setFixedSize(130, 36)
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:white;
                border:none; border-radius:6px;
                font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{ACCENT_L}; }}
            QPushButton:disabled {{ background:{BORDER}; color:{TEXT_SEC}; }}
        """)
        self.ok_btn.clicked.connect(self._accept)
        buttons.addWidget(self.ok_btn)

        root.addLayout(buttons)
        self._refresh_ok()

    def _label(self, text, size=11, bold=False, color=TEXT_PRI):
        lbl = QLabel(text)
        font = QFont("Segoe UI", size)
        font.setBold(bold)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color:{color}; background:transparent;")
        return lbl

    def _rule(self):
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{BORDER};")
        return line

    def _input_style(self):
        return f"""
            QLineEdit {{
                background:{BG_DARK}; color:{TEXT_PRI};
                border:1px solid {BORDER}; border-radius:6px; padding:0 10px;
            }}
            QLineEdit:focus {{ border-color:{ACCENT}; }}
        """

    # ── behaviour ─────────────────────────────────────────────────────────
    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select discharge summary", "",
            "Discharge summaries (*.pdf *.txt);;PDF files (*.pdf);;Text files (*.txt)",
        )
        if not path:
            return
        self._filepath = path
        self.file_lbl.setText(os.path.basename(path))
        self.file_lbl.setStyleSheet(f"color:{TEXT_PRI}; background:transparent;")
        self.clear_btn.setVisible(True)
        # A file and pasted text would be ambiguous, so picking a file takes over.
        self.text_box.clear()
        self.text_box.setEnabled(False)
        self.text_box.setPlaceholderText("Using the selected file instead.")
        self._refresh_ok()

    def _clear_file(self):
        self._filepath = None
        self.file_lbl.setText("No file selected")
        self.file_lbl.setStyleSheet(f"color:{TEXT_SEC}; background:transparent;")
        self.clear_btn.setVisible(False)
        self.text_box.setEnabled(True)
        self.text_box.setPlaceholderText("Paste the discharge summary text…")
        self._refresh_ok()

    def _on_text_changed(self):
        self.error_lbl.setVisible(False)
        self._refresh_ok()

    def _refresh_ok(self):
        has_text = len(self.text_box.toPlainText().strip()) >= MIN_CHARS
        self.ok_btn.setEnabled(bool(self._filepath) or has_text)

    def _accept(self):
        ref = self.ref_input.text().strip()
        if not ref:
            self._error("Please enter a patient reference.")
            return
        if not self._filepath:
            body = self.text_box.toPlainText().strip()
            if len(body) < MIN_CHARS:
                self._error("That summary looks too short. Please paste the full text.")
                return
        self.accept()

    def _error(self, message):
        self.error_lbl.setText(message)
        self.error_lbl.setVisible(True)

    def result_values(self):
        """(patient_ref, pasted_text_or_None, filepath_or_None)."""
        if self._filepath:
            return self.ref_input.text().strip(), None, self._filepath
        return self.ref_input.text().strip(), self.text_box.toPlainText().strip(), None