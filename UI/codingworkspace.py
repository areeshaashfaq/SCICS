import sys
import api_client
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QScrollArea, QFrame,
    QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

CATEGORY_MAP = {
    "diagnosis_principal":   "Principal Diagnosis",
    "diagnosis_associative": "Associative Diagnoses",
    "procedure_principal":   "Procedures",
    "procedure_associative": "Procedures",
    "medication":            "Medications",
}

BG_APP      = "#0F1923"
BG_PANEL    = "#162230"
BG_CARD     = "#1C2D3E"
BG_CARD_ALT = "#1A2B3C"
BORDER      = "#253D52"
ACCENT      = "#2E7DD1"
ACCENT_LITE = "#3D8FE8"
SUCCESS     = "#27AE60"
DANGER      = "#C0392B"
TEXT_PRI    = "#E8EDF2"
TEXT_SEC    = "#8FA8BF"
TEXT_CODE   = "#5BB8FF"
TEXT_EVD    = "#F0C040"
CONF_HI     = "#27AE60"
CONF_MID    = "#F39C12"
CONF_LO     = "#C0392B"
DIALOG_STYLE = f"""
    QMessageBox {{ background: {BG_PANEL}; }}
    QLabel {{ color: {TEXT_PRI}; font-size: 12px; }}
    QPushButton {{
        background: {BG_CARD}; color: {TEXT_PRI};
        border: 1px solid {BORDER}; border-radius: 4px;
        padding: 5px 18px; font-size: 11px; min-width: 60px;
    }}
    QPushButton:hover {{ border-color: {ACCENT}; color: white; }}
"""
def conf_color(pct: int) -> str:
    if pct >= 85:
        return CONF_HI
    if pct >= 70:
        return CONF_MID
    return CONF_LO


def make_label(text: str, size: int = 12, bold: bool = False,
               color: str = TEXT_PRI, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    font = QFont("Segoe UI", size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


class DischargeSummaryPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background:{BG_PANEL}; border-bottom: 1px solid {BORDER};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        h_lay.addWidget(make_label("Discharge Summary", 13, bold=True))
        self.patient_chip = QLabel("—")
        self.patient_chip.setStyleSheet(
            f"color:{TEXT_CODE}; background:#0D2035; border:1px solid {ACCENT};"
            f"border-radius:4px; padding:2px 8px; font-size:11px;"
        )
        h_lay.addStretch()
        h_lay.addWidget(self.patient_chip)
        root.addWidget(header)

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setPlainText("Loading...")
        self.text_view.setFont(QFont("Consolas", 11))
        self.text_view.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_PANEL};
                color: {TEXT_PRI};
                border: none;
                padding: 16px;
                line-height: 1.6;
            }}
            QScrollBar:vertical {{
                background: {BG_APP};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER};
                border-radius: 4px;
            }}
        """)
        root.addWidget(self.text_view)

    def set_text(self, raw_text: str, patient_ref: str = ""):
        self.text_view.setPlainText(raw_text)
        if patient_ref:
            self.patient_chip.setText(patient_ref)


class SuggestionCard(QFrame):
    def __init__(self, item: dict, is_principal: bool = False):
        super().__init__()
        self.item = item
        self._is_principal = is_principal
        self.setFrameShape(QFrame.Shape.NoFrame)
        border_color = ACCENT if is_principal else BORDER
        self.setStyleSheet(f"""
            SuggestionCard {{
                background: {BG_CARD};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        self._decided = False

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.code_lbl = make_label(self.item.get("icd_code", "—"), 11, bold=True, color=TEXT_CODE)
        row1.addWidget(self.code_lbl)

        conf = int((self.item.get("confidence_score") or 0) * 100)
        conf_badge = QLabel(f"{conf}%")
        conf_badge.setStyleSheet(
            f"color:{conf_color(conf)}; background:transparent;"
            f"border:1px solid {conf_color(conf)}; border-radius:4px;"
            f"padding:1px 6px; font-size:10px; font-weight:bold;"
        )
        row1.addWidget(conf_badge)
        row1.addStretch()

        self.btn_accept = QPushButton("Accept  [A]")
        self.btn_accept.setFixedSize(80, 26)
        self.btn_accept.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: white;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #2ECC71; }}
        """)
        self.btn_accept.clicked.connect(self._accept)

        self.btn_reject = QPushButton("Reject  [R]")
        self.btn_reject.setFixedSize(80, 26)
        self.btn_reject.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {DANGER};
                border: 1px solid {DANGER}; border-radius: 4px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {DANGER}; color: white; }}
        """)
        self.btn_reject.clicked.connect(self._reject)

        self.btn_edit = QPushButton("Edit  [E]")
        self.btn_edit.setFixedSize(64, 26)
        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {TEXT_PRI}; border-color: {ACCENT}; }}
        """)
        self.btn_edit.clicked.connect(self._toggle_edit)

        self.btn_undo = QPushButton("↩ Undo")
        self.btn_undo.setFixedSize(64, 26)
        self.btn_undo.setVisible(False)
        self.btn_undo.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 10px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        self.btn_undo.clicked.connect(self._undo)

        self._undo_timer = QTimer()
        self._undo_timer.setSingleShot(True)
        self._undo_timer.timeout.connect(lambda: self.btn_undo.setVisible(False))

        row1.addWidget(self.btn_accept)
        row1.addWidget(self.btn_reject)
        row1.addWidget(self.btn_edit)
        row1.addWidget(self.btn_undo)
        lay.addLayout(row1)

        lay.addWidget(make_label(self.item.get("icd_description", ""), 11, wrap=True))

        evd_row = QHBoxLayout()
        evd_row.setSpacing(4)
        evd_icon = make_label("⟦", 10, color=TEXT_EVD)
        evd_text = make_label(f'"{self.item.get("source_snippet", "")}"', 10, color=TEXT_EVD, wrap=True)
        evd_row.addWidget(evd_icon, 0, Qt.AlignmentFlag.AlignTop)
        evd_row.addWidget(evd_text, 1)
        lay.addLayout(evd_row)

        sec_lbl = QLabel(self.item.get("suggestion_type", "").replace("_", " ").title())
        sec_lbl.setStyleSheet(
            f"color:{TEXT_SEC}; background:#0D1E2E; border-radius:3px;"
            f"padding:1px 6px; font-size:10px;"
        )
        sec_lbl.setFixedHeight(20)
        lay.addWidget(sec_lbl)

        if self.item.get("is_ambiguous"):
            reason = self.item.get("ambiguity_reason") or "Flagged as ambiguous"
            warn = make_label(f"⚠  {reason}", 10, color="#F39C12", wrap=True)
            lay.addWidget(warn)

        self.edit_row = QWidget()
        self.edit_row.setStyleSheet(
            f"background:#0D1E2E; border-radius:5px; border:1px solid {ACCENT};"
        )
        self.edit_row.setVisible(False)
        er = QHBoxLayout(self.edit_row)
        er.setContentsMargins(8, 6, 8, 6)
        er.setSpacing(8)

        er.addWidget(make_label("ICD:", 10, color=TEXT_SEC))

        self.edit_input = QLineEdit(self.item.get("icd_code", ""))
        self.edit_input.setFont(QFont("Consolas", 11))
        self.edit_input.setFixedHeight(26)
        self.edit_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_APP}; color: {TEXT_CODE};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 0 6px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self.edit_input.returnPressed.connect(self._save_edit)
        er.addWidget(self.edit_input, 1)

        btn_save = QPushButton("Save")
        btn_save.setFixedSize(52, 26)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_LITE}; }}
        """)
        btn_save.clicked.connect(self._save_edit)
        er.addWidget(btn_save)

        btn_cancel = QPushButton("✕")
        btn_cancel.setFixedSize(26, 26)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {DANGER}; border-color: {DANGER}; }}
        """)
        btn_cancel.clicked.connect(self._toggle_edit)
        er.addWidget(btn_cancel)

        lay.addWidget(self.edit_row)

    def _show_undo(self):
        self.btn_undo.setVisible(True)
        self._undo_timer.start(5000)

    def _undo(self):
        self._undo_timer.stop()
        self._decided = False
        self.btn_undo.setVisible(False)
        self.btn_accept.setEnabled(True)
        self.btn_reject.setEnabled(True)
        self.btn_edit.setEnabled(True)
        border = ACCENT if self._is_principal else BORDER
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:1px solid {border}; border-radius:8px; }}"
        )

    def _toggle_edit(self):
        if self._decided:
            return
        self.edit_row.setVisible(not self.edit_row.isVisible())
        if self.edit_row.isVisible():
            self.edit_input.setFocus()
            self.edit_input.selectAll()

    def _save_edit(self):
        if self._decided:
            return
        corrected_code = self.edit_input.text().strip()
        if not corrected_code:
            return
        # Record the correction first. If that fails, do not mark the
        # suggestion approved, or the correction would be lost silently.
        correction = api_client.submit_correction(self.item["suggestion_id"], corrected_code)
        if isinstance(correction, dict) and correction.get("error"):
            return
        decision = api_client.submit_decision(self.item["suggestion_id"], "approved")
        if isinstance(decision, dict) and decision.get("error"):
            return
        self._decided = True
        self.code_lbl.setText(corrected_code)
        self.edit_row.setVisible(False)
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid #D4A017; border-radius:8px; }}"
        )
        self.btn_accept.setEnabled(False)
        self.btn_reject.setEnabled(False)
        self.btn_edit.setEnabled(False)

    def _accept(self):
        if self._decided:
            return
        result = api_client.submit_decision(self.item["suggestion_id"], "approved")
        # api_client has already shown the coder a dialog. Leave the card
        # actionable so nothing looks saved when it wasn't.
        if isinstance(result, dict) and result.get("error"):
            return
        self._decided = True
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid {SUCCESS}; border-radius:8px; }}"
        )
        self.btn_accept.setEnabled(False)
        self.btn_reject.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.edit_row.setVisible(False)
        self._show_undo()

    def _reject(self):
        if self._decided:
            return
        result = api_client.submit_decision(self.item["suggestion_id"], "rejected")
        if isinstance(result, dict) and result.get("error"):
            return
        self._decided = True
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid {DANGER}; border-radius:8px; }}"
        )
        self.btn_accept.setEnabled(False)
        self.btn_reject.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.edit_row.setVisible(False)
        self._show_undo()

class SuggestionsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._cards = []
        self._current_index = 0
        self.setMinimumWidth(340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        h_lay.addWidget(make_label("ICD Suggestions", 13, bold=True))

        # keyboard shortcut hint
        hint = make_label("A=Accept  R=Reject  E=Edit", 9, color=TEXT_SEC)
        h_lay.addWidget(hint)
        h_lay.addStretch()

        accept_all = QPushButton("Accept All")
        accept_all.setFixedSize(86, 30)
        accept_all.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white;
                border: none; border-radius: 5px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_LITE}; }}
        """)
        accept_all.clicked.connect(self._accept_all)
        h_lay.addWidget(accept_all)
        root.addWidget(header)

        # loading spinner label
        self.loading_lbl = QLabel("⏳  Loading suggestions...")
        self.loading_lbl.setFont(QFont("Segoe UI", 11))
        self.loading_lbl.setStyleSheet(f"color:{TEXT_SEC}; background:transparent; padding:20px;")
        self.loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_lbl.setVisible(False)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {BG_APP}; }}
            QScrollBar:vertical {{
                background: {BG_APP}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 4px;
            }}
        """)

        self.container = QWidget()
        self.container.setStyleSheet(f"background: {BG_APP};")
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(12, 12, 12, 12)
        self.cards_layout.setSpacing(16)
        self.cards_layout.addStretch()

        scroll.setWidget(self.container)
        root.addWidget(self.loading_lbl)
        root.addWidget(scroll)

    def show_loading(self):
        self.loading_lbl.setVisible(True)

    def hide_loading(self):
        self.loading_lbl.setVisible(False)

    def _accept_all(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Accept All")
        box.setText("Accept all suggestions? This cannot be undone.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setStyleSheet(DIALOG_STYLE)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        for card in self._cards:
            card._accept()

    def accept_current(self):
        if self._cards and self._current_index < len(self._cards):
            self._cards[self._current_index]._accept()
            self._current_index = min(self._current_index + 1, len(self._cards) - 1)

    def reject_current(self):
        if self._cards and self._current_index < len(self._cards):
            self._cards[self._current_index]._reject()
            self._current_index = min(self._current_index + 1, len(self._cards) - 1)

    def edit_current(self):
        if self._cards and self._current_index < len(self._cards):
            self._cards[self._current_index]._toggle_edit()

    def load(self, suggestions: list):
        self._cards = []
        self._current_index = 0
        self.hide_loading()

        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not suggestions:
            self.cards_layout.insertWidget(0, make_label("No suggestions generated.", 11, color=TEXT_SEC))
            return

        grouped = {}
        seen_codes = set()
        for s in suggestions:
            code = s.get("icd_code", "")
            if code and code in seen_codes:
                continue
            seen_codes.add(code)
            category = CATEGORY_MAP.get(s.get("suggestion_type"), "Associative Diagnoses")
            grouped.setdefault(category, []).append(s)

        insert_pos = 0
        for category in ["Principal Diagnosis", "Associative Diagnoses", "Procedures", "Medications"]:
            items = grouped.get(category, [])
            if not items:
                continue
            is_principal_section = (category == "Principal Diagnosis")

            sec_header = QWidget()
            sec_header.setFixedHeight(30)
            sec_header.setStyleSheet(
                f"background: {'#0D2035' if is_principal_section else '#12202E'};"
                f"border-radius: 5px;"
            )
            sh_lay = QHBoxLayout(sec_header)
            sh_lay.setContentsMargins(10, 0, 10, 0)
            icon = "★" if is_principal_section else "◆"
            sh_lay.addWidget(make_label(f"{icon}  {category}", 11, bold=True,
                                        color=ACCENT if is_principal_section else TEXT_SEC))
            count_lbl = QLabel(str(len(items)))
            count_lbl.setStyleSheet(
                f"color:{TEXT_SEC}; background:{BORDER}; border-radius:9px;"
                f"padding:0px 7px; font-size:10px;"
            )
            sh_lay.addStretch()
            sh_lay.addWidget(count_lbl)
            self.cards_layout.insertWidget(insert_pos, sec_header)
            insert_pos += 1

            for item in items:
                card = SuggestionCard(item, is_principal=is_principal_section)
                self._cards.append(card)
                self.cards_layout.insertWidget(insert_pos, card)
                insert_pos += 1


class ChatBubble(QFrame):
    def __init__(self, role: str, text: str):
        super().__init__()
        is_user = (role == "user")

        if is_user:
            self.setStyleSheet(f"""
                ChatBubble {{
                    background: #1A3554;
                    border-radius: 10px;
                    border-top-right-radius: 3px;
                    border-left: 2px solid {ACCENT};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ChatBubble {{
                    background: #111E2B;
                    border-radius: 10px;
                    border-top-left-radius: 3px;
                    border-left: 2px solid #1E5A3A;
                }}
            """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(4)

        sender_row = QHBoxLayout()
        sender_row.setSpacing(6)

        indicator = QLabel("▶" if is_user else "◈")
        indicator.setStyleSheet(
            f"color:{ACCENT_LITE if is_user else '#2ECC71'}; "
            f"background:transparent; font-size:8px;"
        )
        sender_row.addWidget(indicator)
        sender_row.addWidget(make_label(
            "CODER" if is_user else "ASSISTANT",
            8, bold=True,
            color=ACCENT_LITE if is_user else "#2ECC71"
        ))
        sender_row.addStretch()
        lay.addLayout(sender_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{BORDER};")
        line.setFixedHeight(1)
        lay.addWidget(line)

        msg = QLabel(text)
        msg.setFont(QFont("Segoe UI", 11))
        msg.setStyleSheet(f"color:{TEXT_PRI}; background:transparent;")
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)

        time_lbl = QLabel(datetime.now().strftime("%H:%M"))
        time_lbl.setFont(QFont("Segoe UI", 8))
        time_lbl.setStyleSheet(f"color:{BORDER}; background:transparent;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(time_lbl)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)


class ChatPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.document_id = None
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"stop:0 #0D1E30, stop:1 #112238);"
            f"border-bottom: 1px solid {BORDER};"
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(16, 8, 16, 8)
        h_lay.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        title = make_label("◈  CLINICAL QUERY INTERFACE", 11, bold=True, color=TEXT_CODE)
        top_row.addWidget(title)
        top_row.addStretch()
        dot = QLabel("● LIVE")
        dot.setStyleSheet("color:#27AE60; font-size:9px; font-weight:bold;")
        top_row.addWidget(dot)
        h_lay.addLayout(top_row)

        bot_row = QHBoxLayout()
        bot_row.setSpacing(6)
        for tag in ["DB-BACKED", "RULE-BASED", "SECURE"]:
            t = QLabel(tag)
            t.setStyleSheet(
                f"color:{TEXT_SEC}; background:#0A1520; border:1px solid {BORDER};"
                f"border-radius:3px; padding:0px 5px; font-size:9px;"
            )
            bot_row.addWidget(t)
        bot_row.addStretch()
        h_lay.addLayout(bot_row)

        root.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {BG_APP}; }}
            QScrollBar:vertical {{
                background: {BG_APP}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 4px;
            }}
        """)

        self.msg_container = QWidget()
        self.msg_container.setStyleSheet(f"background: {BG_APP};")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(12, 12, 12, 12)
        self.msg_layout.setSpacing(10)
        self.msg_layout.addStretch()

        self.scroll.setWidget(self.msg_container)
        root.addWidget(self.scroll, 1)

        input_bar = QWidget()
        input_bar.setFixedHeight(72)
        input_bar.setStyleSheet(
            f"background:#0D1E30; border-top:1px solid {ACCENT};"
        )
        ib_outer = QVBoxLayout(input_bar)
        ib_outer.setContentsMargins(12, 8, 12, 8)
        ib_outer.setSpacing(4)

        prompt_lbl = QLabel("ENTER QUERY")
        prompt_lbl.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:9px; font-weight:bold; background:transparent;"
        )
        ib_outer.addWidget(prompt_lbl)

        ib_lay = QHBoxLayout()
        ib_lay.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("e.g. Why was N17.9 suggested as principal?")
        self.input_box.setFont(QFont("Consolas", 11))
        self.input_box.setFixedHeight(34)
        self.input_box.setStyleSheet(f"""
            QLineEdit {{
                background: #0A1520;
                color: {TEXT_CODE};
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 4px 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
                color: {TEXT_PRI};
            }}
        """)
        self.input_box.returnPressed.connect(self._send_message)
        ib_lay.addWidget(self.input_box)

        send_btn = QPushButton("▶")
        send_btn.setFixedSize(34, 34)
        send_btn.setToolTip("Send (Enter)")
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white;
                border: none; border-radius: 5px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_LITE}; }}
        """)
        send_btn.clicked.connect(self._send_message)
        ib_lay.addWidget(send_btn)

        ib_outer.addLayout(ib_lay)
        root.addWidget(input_bar)

    def load_history(self, document_id: int):
        self.document_id = document_id
        messages = api_client.get_chat_history(document_id)
        for msg in messages:
            role = "user" if msg.get("sender") == "coder" else "system"
            self._add_bubble(role, msg.get("message_text", ""))

    def _add_bubble(self, role: str, text: str):
        bubble = ChatBubble(role, text)

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")
        w_lay = QHBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)

        if role == "user":
            w_lay.addStretch()
            bubble.setMaximumWidth(340)
            w_lay.addWidget(bubble)
        else:
            bubble.setMaximumWidth(360)
            w_lay.addWidget(bubble)
            w_lay.addStretch()

        self.msg_layout.insertWidget(self.msg_layout.count() - 1, wrapper)

    def _add_typing_indicator(self):
        bubble = QFrame()
        bubble.setStyleSheet(
            f"background:#111E2B; border-radius:10px; border-left:2px solid #1E5A3A;"
        )
        b_lay = QHBoxLayout(bubble)
        b_lay.setContentsMargins(12, 8, 12, 8)
        lbl = QLabel("◈  typing…")
        lbl.setStyleSheet(f"color:{TEXT_SEC}; font-size:11px; background:transparent;")
        b_lay.addWidget(lbl)

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")
        w_lay = QHBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)
        bubble.setMaximumWidth(160)
        w_lay.addWidget(bubble)
        w_lay.addStretch()

        self.msg_layout.insertWidget(self.msg_layout.count() - 1, wrapper)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
        return wrapper

    def _send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self._add_bubble("user", text)
        self.input_box.clear()
        self.input_box.setEnabled(False)

        typing = self._add_typing_indicator()
        QTimer.singleShot(50, lambda: self._do_send(text, typing))

    def _do_send(self, text: str, typing_wrapper):
        try:
            answer = None
            if self.document_id is not None:
                response = api_client.send_chat(self.document_id, text)
                answer = response.get("answer") or response.get("response")
        except Exception as e:
            answer = f"Error: {e}"
        finally:
            typing_wrapper.setParent(None)
            typing_wrapper.deleteLater()
            self.input_box.setEnabled(True)
            self.input_box.setFocus()

        if answer:
            self._add_bubble("system", answer)

        self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        )


class CodingWorkspace(QMainWindow):
    def __init__(self, document_id: int = 1, on_back=None):
        super().__init__()
        self.document_id = document_id
        self.on_back = on_back
        self.setWindowTitle("SIUT — Clinical Coding Workspace")
        self.resize(1400, 860)
        self._apply_global_style()
        self._build_ui()
        self._setup_shortcuts()
        self._load_data()

    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background: {BG_APP}; }}
            QWidget {{ background: {BG_APP}; }}
            QToolTip {{
                background: {BG_CARD}; color: {TEXT_PRI};
                border: 1px solid {BORDER}; padding: 4px;
            }}
        """)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("A"), self, activated=self.suggestions_panel.accept_current)
        QShortcut(QKeySequence("R"), self, activated=self.suggestions_panel.reject_current)
        QShortcut(QKeySequence("E"), self, activated=self.suggestions_panel.edit_current)

    def _build_ui(self):
        top_bar = QWidget()
        top_bar.setFixedHeight(52)
        top_bar.setStyleSheet(
            f"background:#0A1520; border-bottom:1px solid {BORDER};"
        )
        tb_lay = QHBoxLayout(top_bar)
        tb_lay.setContentsMargins(20, 0, 20, 0)
        tb_lay.setSpacing(16)

        back_btn = QPushButton("← Back")
        back_btn.setFixedSize(78, 32)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        back_btn.clicked.connect(self._go_back)
        tb_lay.addWidget(back_btn)
        tb_lay.addSpacing(16)
        logo = make_label("SIUT  ICD Coder", 14, bold=True, color=ACCENT)
        tb_lay.addWidget(logo)
        tb_lay.addSpacing(16)

        tb_lay.addWidget(make_label("Coding Workspace", 12, color=TEXT_SEC))
        tb_lay.addStretch()

        self.submit_btn = QPushButton("Submit Review")
        self.submit_btn.setFixedSize(120, 34)
        self.submit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white;
                border: none; border-radius: 6px;
                font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_LITE}; }}
        """)
        self.submit_btn.clicked.connect(self._submit_review)
        tb_lay.addWidget(self.submit_btn)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(1)

        self.discharge_panel   = DischargeSummaryPanel()
        self.suggestions_panel = SuggestionsPanel()
        self.chat_panel        = ChatPanel()

        def framed(w: QWidget) -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.NoFrame)
            f.setStyleSheet(f"background:{BG_PANEL}; border-right:1px solid {BORDER};")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(0)
            fl.addWidget(w)
            return f

        body_lay.addWidget(framed(self.discharge_panel),   30)
        body_lay.addWidget(framed(self.suggestions_panel), 37)
        body_lay.addWidget(self.chat_panel,                33)

        central = QWidget()
        central.setStyleSheet(f"background:{BG_APP};")
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(top_bar)
        main_lay.addWidget(body, 1)

        self.setCentralWidget(central)

    def _load_data(self):
        self.suggestions_panel.show_loading()

        try:
            raw_text = api_client.get_raw_text(self.document_id)
            docs     = api_client.get_documents()
            doc      = next((d for d in docs if d["document_id"] == self.document_id), {})
            self.discharge_panel.set_text(raw_text, doc.get("patient_ref", ""))
        except Exception as e:
            self.discharge_panel.set_text(f"Error loading document: {e}")

        try:
            suggestions = api_client.get_suggestions(self.document_id)
            self.suggestions_panel.load(suggestions)
        except Exception:
            self.suggestions_panel.load([])

        try:
            self.chat_panel.load_history(self.document_id)
        except Exception:
            pass

    def _submit_review(self):
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Submitting…")
        result = api_client.mark_complete(self.document_id)
        if isinstance(result, dict) and result.get("error"):
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Submit Review")
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Review Submitted")
        box.setText("Review submitted. This document is now marked as reviewed.")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(DIALOG_STYLE)
        box.exec()
        self._go_back()
        
    def _go_back(self):
        if self.on_back:
            self.on_back()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CodingWorkspace()
    window.show()
    sys.exit(app.exec())