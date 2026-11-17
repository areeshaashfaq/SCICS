import html
import re
import sys
import theme
from load_error import make_load_error

import api_client
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QScrollArea, QFrame,
    QSizePolicy, QMessageBox, QSplitter
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

# All colour constants are initialised from theme.DARK by _reload_colors().
# Call _reload_colors() again after theme.toggle() before rebuilding the UI.
BG_APP = BG_PANEL = BG_CARD = BG_CARD_ALT = BG_TOP = BG_EDIT = ""
BG_CHAT_H = BG_CHAT_H2 = BG_CHAT_USR = BG_CHAT_BOT = SEC_HOVER = ""
BORDER = ACCENT = ACCENT_LITE = SUCCESS = DANGER = ""
TEXT_PRI = TEXT_SEC = TEXT_CODE = TEXT_EVD = ""
CONF_HI = CONF_MID = CONF_LO = ""
DIALOG_STYLE = ""
SECTION_STYLE: dict = {}


def _reload_colors():
    global BG_APP, BG_PANEL, BG_CARD, BG_CARD_ALT, BG_TOP, BG_EDIT
    global BG_CHAT_H, BG_CHAT_H2, BG_CHAT_USR, BG_CHAT_BOT, SEC_HOVER
    global BORDER, ACCENT, ACCENT_LITE, SUCCESS, DANGER
    global TEXT_PRI, TEXT_SEC, TEXT_CODE, TEXT_EVD
    global CONF_HI, CONF_MID, CONF_LO
    global DIALOG_STYLE, SECTION_STYLE
    t = theme.current
    BG_APP      = t["BG_APP"]
    BG_PANEL    = t["BG_PANEL"]
    BG_CARD     = t["BG_CARD"]
    BG_CARD_ALT = t["BG_CARD_ALT"]
    BG_TOP      = t["BG_TOP"]
    BG_EDIT     = t["BG_EDIT"]
    BG_CHAT_H   = t["BG_CHAT_H"]
    BG_CHAT_H2  = t["BG_CHAT_H2"]
    BG_CHAT_USR = t["BG_CHAT_USR"]
    BG_CHAT_BOT = t["BG_CHAT_BOT"]
    SEC_HOVER   = t["SEC_HOVER"]
    BORDER      = t["BORDER"]
    ACCENT      = t["ACCENT"]
    ACCENT_LITE = t["ACCENT_LITE"]
    SUCCESS     = t["SUCCESS"]
    DANGER      = t["DANGER"]
    TEXT_PRI    = t["TEXT_PRI"]
    TEXT_SEC    = t["TEXT_SEC"]
    TEXT_CODE   = t["TEXT_CODE"]
    TEXT_EVD    = t["TEXT_EVD"]
    CONF_HI     = t["CONF_HI"]
    CONF_MID    = t["CONF_MID"]
    CONF_LO     = t["CONF_LO"]
    DIALOG_STYLE = (
        f"QMessageBox {{ background: {BG_PANEL}; }}"
        f"QLabel {{ color: {TEXT_PRI}; font-size: 12px; }}"
        f"QPushButton {{ background: {BG_CARD}; color: {TEXT_PRI};"
        f" border: 1px solid {BORDER}; border-radius: 4px;"
        f" padding: 5px 18px; font-size: 11px; min-width: 60px; }}"
        f"QPushButton:hover {{ border-color: {ACCENT}; color: white; }}"
    )
    SECTION_STYLE = {
        "Principal Diagnosis":   {"icon": "", "fg": "#2E7DD1", "bg": t["SEC_PRINCIPAL"]},
        "Associative Diagnoses": {"icon": "", "fg": "#5BB8FF", "bg": t["SEC_ASSOCIATIVE"]},
        "Procedures":            {"icon": "", "fg": "#4FC3A1", "bg": t["SEC_PROCEDURES"]},
        "Medications":           {"icon": "", "fg": "#F0C040", "bg": t["SEC_MEDICATIONS"]},
        "Needs manual coding":   {"icon": "⚠", "fg": "#8FA8BF", "bg": t["SEC_MANUAL"]},
    }


_reload_colors()  # initialise to dark theme on import


def markdown_to_html(text: str) -> str:
    """Render the small subset of markdown an LLM actually emits.

    The chat bubble is a RichText QLabel, so it understands HTML but not
    markdown — which is why raw ** and ### were showing up in answers. Rather
    than forbidding the model from formatting (brittle, and it loses useful
    emphasis on code names), convert what it sends.
    """
    if not text:
        return ""

    # Escape first so clinical text containing < or & cannot break the markup.
    out = html.escape(text)

    lines = out.split("\n")
    rendered = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Headings: ### Title -> bold line. Real <h3> would be oversized here.
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            if in_list:
                rendered.append("</ul>")
                in_list = False
            rendered.append(f"<p><b>{heading.group(2)}</b></p>")
            continue

        # Bullets: *, - or • at the start of a line.
        bullet = re.match(r"^[\*\-•]\s+(.*)$", stripped)
        if bullet:
            if not in_list:
                rendered.append("<ul style='margin:2px 0 2px 12px;'>")
                in_list = True
            rendered.append(f"<li>{bullet.group(1)}</li>")
            continue

        if in_list:
            rendered.append("</ul>")
            in_list = False

        # Blockquote: > evidence line
        quote = re.match(r"^&gt;\s*(.*)$", stripped)
        if quote:
            rendered.append(
                f"<p style='margin:2px 0 2px 8px; color:{TEXT_EVD};'>{quote.group(1)}</p>"
            )
            continue

        if stripped:
            rendered.append(f"<p style='margin:3px 0;'>{stripped}</p>")

    if in_list:
        rendered.append("</ul>")

    body = "".join(rendered)

    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body, flags=re.S)
    body = re.sub(r"(?<![\w\*])\*(?!\s)(.+?)(?<!\s)\*(?![\w\*])", r"<i>\1</i>", body, flags=re.S)
    body = re.sub(
        r"`([^`]+)`",
        lambda m: f"<span style='color:{TEXT_CODE};'>{m.group(1)}</span>",
        body,
    )

    return body


def conf_color(pct: int) -> str:
    if pct >= 85:
        return CONF_HI
    if pct >= 70:
        return CONF_MID
    return CONF_LO


def make_label(text: str, size: int = 12, bold: bool = False,
               color: str = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    font = QFont("Segoe UI", size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color or TEXT_PRI}; background: transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


class SectionHeader(QFrame):
    """A clickable section bar that expands or collapses the cards beneath it."""

    def __init__(self, title: str, count: int, on_toggle, expanded: bool = True,
                 style_key: str = None, compact: bool = False):
        super().__init__()
        self._expanded = expanded
        self._on_toggle = on_toggle
        style = SECTION_STYLE.get(style_key or title,
                                  SECTION_STYLE["Associative Diagnoses"])

        self.setFixedHeight(28 if compact else 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"SectionHeader {{ background:{style['bg']}; border-radius:5px;"
            f" border:none; border-left:3px solid {style['fg']}; }}"
            f"SectionHeader:hover {{ background:{SEC_HOVER}; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10 if not compact else 8, 0, 10, 0)
        lay.setSpacing(8)

        self.arrow = QLabel("▾" if expanded else "▸")
        self.arrow.setStyleSheet(
            f"color:{style['fg']}; background:transparent; font-size:10px;"
        )
        lay.addWidget(self.arrow)

        title_lbl = QLabel(f"{style['icon']}  {title}" if style["icon"] else title)
        font = QFont("Segoe UI", 10 if compact else 11)
        font.setBold(not compact)
        title_lbl.setFont(font)
        title_lbl.setStyleSheet(f"color:{style['fg']}; background:transparent;")
        lay.addWidget(title_lbl)

        lay.addStretch()

        badge = QLabel(str(count))
        badge.setStyleSheet(
            f"color:{style['fg']}; background:transparent;"
            f"border:1px solid {style['fg']}; border-radius:9px;"
            f"padding:0px 7px; font-size:10px; font-weight:bold;"
        )
        lay.addWidget(badge)

    def mousePressEvent(self, event):
        self._expanded = not self._expanded
        self.arrow.setText("▾" if self._expanded else "▸")
        self._on_toggle(self._expanded)


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
            f"color:{TEXT_CODE}; background:{BG_EDIT}; border:1px solid {ACCENT};"
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
        self._is_medication = (self.item.get("suggestion_type", "") == "medication")

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

        if self._is_medication:
            self.btn_remove = QPushButton("✕ Remove")
            self.btn_remove.setFixedSize(76, 26)
            self.btn_remove.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {DANGER};
                    border: 1px solid {DANGER}55; border-radius: 4px;
                    font-size: 10px;
                }}
                QPushButton:hover {{ background: {DANGER}22; border-color: {DANGER}; }}
            """)
            self.btn_remove.clicked.connect(self._remove_medication)

            self.btn_undo_remove = QPushButton("↩ Undo")
            self.btn_undo_remove.setFixedSize(64, 26)
            self.btn_undo_remove.setVisible(False)
            self.btn_undo_remove.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TEXT_SEC};
                    border: 1px solid {BORDER}; border-radius: 4px;
                    font-size: 10px;
                }}
                QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
            """)
            self.btn_undo_remove.clicked.connect(self._undo_remove_medication)

            row1.addWidget(self.btn_remove)
            row1.addWidget(self.btn_undo_remove)

        if not self._is_medication:
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

            row1.addWidget(self.btn_accept)
            row1.addWidget(self.btn_reject)
            row1.addWidget(self.btn_edit)
            row1.addWidget(self.btn_undo)

        lay.addLayout(row1)

        lay.addWidget(make_label(self.item.get("icd_description", ""), 11, wrap=True))

        snippet = self.item.get("source_snippet", "")
        if snippet:
            evd_toggle = QPushButton("▸  source text")
            evd_toggle.setFlat(True)
            evd_toggle.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TEXT_EVD};
                    border: none; font-size: 10px; text-align: left; padding: 0;
                }}
                QPushButton:hover {{ color: #F8D878; }}
            """)

            evd_body = QWidget()
            evd_body.setVisible(False)
            evd_body.setStyleSheet("background:transparent;")
            evd_inner = QHBoxLayout(evd_body)
            evd_inner.setContentsMargins(0, 2, 0, 0)
            evd_inner.setSpacing(4)
            evd_inner.addWidget(make_label("⟦", 10, color=TEXT_EVD), 0, Qt.AlignmentFlag.AlignTop)
            evd_inner.addWidget(make_label(f'"{snippet}"', 10, color=TEXT_EVD, wrap=True), 1)

            def _toggle_evd(checked, btn=evd_toggle, body=evd_body):
                body.setVisible(not body.isVisible())
                btn.setText("▾  source text" if body.isVisible() else "▸  source text")

            evd_toggle.clicked.connect(_toggle_evd)
            lay.addWidget(evd_toggle)
            lay.addWidget(evd_body)

        sec_lbl = QLabel(self.item.get("suggestion_type", "").replace("_", " ").title())
        sec_lbl.setStyleSheet(
            f"color:{TEXT_SEC}; background:{BG_EDIT}; border-radius:3px;"
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
            f"background:{BG_EDIT}; border-radius:5px; border:1px solid {ACCENT};"
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

        # The backend already knows what this coder decided. Without this the
        # card rebuilds as undecided on every reload and their work looks lost.
        existing = (self.item.get("coder_decision") or "pending").lower()
        if existing == "approved":
            self._apply_decided(SUCCESS)
        elif existing == "rejected":
            self._apply_decided(DANGER)

    def _apply_decided(self, colour):
        """Show a card as already decided, without re-sending it to the server."""
        self._decided = True
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid {colour}; border-radius:8px; }}"
        )
        self.btn_accept.setEnabled(False)
        self.btn_reject.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.edit_row.setVisible(False)
        self._show_undo()

    def set_focused(self, focused: bool):
        if self._decided:
            return
        if focused:
            self.setStyleSheet(
                f"SuggestionCard {{ background:{BG_CARD}; border:2px solid {ACCENT}; border-radius:8px; }}"
            )
        else:
            border = ACCENT if self._is_principal else BORDER
            self.setStyleSheet(
                f"SuggestionCard {{ background:{BG_CARD}; border:1px solid {border}; border-radius:8px; }}"
            )

    def _remove_medication(self):
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid {DANGER}55; border-radius:8px; }}"
        )
        self.btn_remove.setVisible(False)
        self.btn_undo_remove.setVisible(True)

    def _undo_remove_medication(self):
        self.btn_remove.setVisible(True)
        self.btn_undo_remove.setVisible(False)
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:1px solid {BORDER}; border-radius:8px; }}"
        )

    def _show_undo(self):
        self.btn_undo.setVisible(True)

    def _undo(self):
        self._decided = False
        self.item["coder_decision"] = None
        self.btn_undo.setVisible(False)
        self.btn_accept.setEnabled(True)
        self.btn_reject.setEnabled(True)
        self.btn_edit.setEnabled(True)
        if hasattr(self, "_original_code"):
            self.item["icd_code"] = self._original_code
            self.code_lbl.setText(self._original_code)
            del self._original_code
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
        correction = api_client.submit_correction(self.item["suggestion_id"], corrected_code)
        if isinstance(correction, dict) and correction.get("error"):
            return
        decision = api_client.submit_decision(self.item["suggestion_id"], "approved")
        if isinstance(decision, dict) and decision.get("error"):
            return
        self._original_code = self.item.get("icd_code", "")
        self.item["coder_decision"] = "approved"
        self._decided = True
        self.code_lbl.setText(corrected_code)
        self.item["icd_code"] = corrected_code
        self.edit_row.setVisible(False)
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid #D4A017; border-radius:8px; }}"
        )
        self.btn_accept.setEnabled(False)
        self.btn_reject.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self._show_undo()

    def _accept(self):
        if self._decided or self._is_medication:
            return
        result = api_client.submit_decision(self.item["suggestion_id"], "approved")
        if isinstance(result, dict) and result.get("error"):
            return
        self._decided = True
        self.item["coder_decision"] = "approved"
        self.setStyleSheet(
            f"SuggestionCard {{ background:{BG_CARD}; border:2px solid {SUCCESS}; border-radius:8px; }}"
        )
        self.btn_accept.setEnabled(False)
        self.btn_reject.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.edit_row.setVisible(False)
        self._show_undo()

    def _reject(self):
        if self._decided or self._is_medication:
            return
        result = api_client.submit_decision(self.item["suggestion_id"], "rejected")
        if isinstance(result, dict) and result.get("error"):
            return
        self._decided = True
        self.item["coder_decision"] = "rejected"
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

        h_lay.addStretch()

        accept_80 = QPushButton("Accept ≥80%")
        accept_80.setFixedSize(104, 30)
        accept_80.setToolTip("Accept all undecided suggestions with ≥80% confidence")
        accept_80.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: white;
                border: none; border-radius: 5px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #2ECC71; }}
        """)
        accept_80.clicked.connect(self._accept_high_confidence)
        h_lay.addWidget(accept_80)

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
        self.scroll = scroll
        root.addWidget(self.loading_lbl)
        root.addWidget(scroll)

    def show_loading(self):
        self.loading_lbl.setVisible(True)

    def hide_loading(self):
        self.loading_lbl.setVisible(False)

    def show_load_error(self, detail: str, on_retry):
        self._cards = []
        self._current_index = 0
        self.hide_loading()
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards_layout.insertWidget(0, make_load_error(detail, on_retry))

    def _accept_high_confidence(self):
        eligible = [
            card for card in self._cards
            if not card._decided
            and int((card.item.get("confidence_score") or 0) * 100) >= 80
        ]
        if not eligible:
            box = QMessageBox(self)
            box.setWindowTitle("Accept ≥80%")
            box.setText("No undecided suggestions with ≥80% confidence found.")
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            box.setStyleSheet(DIALOG_STYLE)
            box.exec()
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Accept ≥80%")
        box.setText(f"Accept {len(eligible)} suggestion(s) with ≥80% confidence?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setStyleSheet(DIALOG_STYLE)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        for card in eligible:
            card._accept()

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

    def _set_focus(self, index: int):
        if not self._cards:
            return
        old = self._current_index
        if 0 <= old < len(self._cards):
            self._cards[old].set_focused(False)
        self._current_index = max(0, min(index, len(self._cards) - 1))
        card = self._cards[self._current_index]
        card.set_focused(True)
        self._scroll_to(card)

    def _scroll_to(self, card):
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(card, 0, 40))

    def _step(self, direction: int):
        """Move focus to the next card the coder can actually see.

        Cards inside a collapsed section (e.g. Needs manual coding) are skipped.
        """
        i = self._current_index + direction
        while 0 <= i < len(self._cards):
            if self._cards[i].isVisibleTo(self):
                self._set_focus(i)
                return
            i += direction

    def _focus_first(self):
        if not self._cards:
            return
        if self._cards[0].isVisibleTo(self):
            self._set_focus(0)
        else:
            self._current_index = 0
            self._step(1)

    def nav_next(self):
        self._step(1)

    def nav_prev(self):
        self._step(-1)

    def accept_current(self):
        if self._cards and self._current_index < len(self._cards):
            self._cards[self._current_index]._accept()
            self._step(1)

    def reject_current(self):
        if self._cards and self._current_index < len(self._cards):
            self._cards[self._current_index]._reject()
            self._step(1)

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

        # Anything the NLP couldn't code goes into one collapsed section at the
        # bottom, so the coded sections only hold real suggestions. Medications
        # stay put: they normally have no ICD code.
        categories = ["Principal Diagnosis", "Associative Diagnoses", "Procedures", "Medications"]
        manual = []
        for category in categories[:3]:
            manual += [s for s in grouped.get(category, []) if not s.get("icd_code")]
            grouped[category] = [s for s in grouped.get(category, []) if s.get("icd_code")]

        insert_pos = 0
        for category in categories:
            items = grouped.get(category, [])
            if not items:
                continue
            is_principal_section = (category == "Principal Diagnosis")

            coded   = [s for s in items if s.get("icd_code")]
            uncoded = [s for s in items if not s.get("icd_code")]
            coded.sort(key=lambda s: -(s.get("confidence_score") or 0))

            body = QWidget()
            body.setStyleSheet("background:transparent;")
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(0, 0, 0, 0)
            body_lay.setSpacing(16)

            for item in coded + uncoded:
                card = SuggestionCard(item, is_principal=is_principal_section)
                if category != "Medications":
                    self._cards.append(card)
                body_lay.addWidget(card)

            if category == "Medications":
                body_lay.addWidget(self._make_add_medication_row(body_lay))

            header = SectionHeader(
                category, len(items),
                on_toggle=lambda shown, b=body: b.setVisible(shown),
                expanded=True, style_key=category,
            )
            self.cards_layout.insertWidget(insert_pos, header)
            insert_pos += 1
            self.cards_layout.insertWidget(insert_pos, body)
            insert_pos += 1

        if manual:
            manual_body = self._make_card_holder(manual, False, visible=False)
            manual_header = SectionHeader(
                "Needs manual coding", len(manual),
                on_toggle=lambda shown, b=manual_body: b.setVisible(shown),
                expanded=False, style_key="Needs manual coding",
            )
            self.cards_layout.insertWidget(insert_pos, manual_header)
            insert_pos += 1
            self.cards_layout.insertWidget(insert_pos, manual_body)
            insert_pos += 1

        if self._cards:
            QTimer.singleShot(100, self._focus_first)

    def _make_add_medication_row(self, parent_layout: QVBoxLayout) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background:{BG_EDIT}; border-radius:6px; border:1px dashed {BORDER};"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        field = QLineEdit()
        field.setPlaceholderText("Add medication…")
        field.setFont(QFont("Segoe UI", 11))
        field.setFixedHeight(28)
        field.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_APP}; color: {TEXT_PRI};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 0 8px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)

        btn_add = QPushButton("+ Add")
        btn_add.setFixedSize(54, 28)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_LITE}; }}
        """)

        def _add():
            name = field.text().strip()
            if not name:
                return
            new_item = {"icd_code": "", "icd_description": name,
                        "suggestion_type": "medication", "confidence_score": None,
                        "source_snippet": ""}
            card = SuggestionCard(new_item)
            parent_layout.insertWidget(parent_layout.count() - 1, card)
            field.clear()

        btn_add.clicked.connect(_add)
        field.returnPressed.connect(_add)
        lay.addWidget(field, 1)
        lay.addWidget(btn_add)
        return row

    def _make_card_holder(self, items, is_principal, visible):
        """Wrap a set of cards so the whole group can be shown or hidden at once."""
        holder = QWidget()
        holder.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        for item in items:
            card = SuggestionCard(item, is_principal=is_principal)
            self._cards.append(card)
            lay.addWidget(card)
        holder.setVisible(visible)
        return holder


class ChatBubble(QFrame):
    def __init__(self, role: str, text: str):
        super().__init__()
        is_user = (role == "user")

        if is_user:
            self.setStyleSheet(f"""
                ChatBubble {{
                    background: {BG_CHAT_USR};
                    border-radius: 10px;
                    border-top-right-radius: 3px;
                    border-left: 2px solid {ACCENT};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ChatBubble {{
                    background: {BG_CHAT_BOT};
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

        msg = QLabel(markdown_to_html(text))
        msg.setFont(QFont("Segoe UI", 11))
        msg.setStyleSheet(f"color:{TEXT_PRI}; background:transparent;")
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
            f"stop:0 {BG_CHAT_H}, stop:1 {BG_CHAT_H2});"
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
            f"background:{BG_CHAT_H}; border-top:1px solid {ACCENT};"
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
                background: {BG_TOP};
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
        if api_client.LAST_ERROR:
            self._add_bubble("system", "Couldn't load earlier messages for this record.")
            return
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
            f"background:{BG_CHAT_BOT}; border-radius:10px; border-left:2px solid #1E5A3A;"
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
        self._shortcuts = []
        self._cached_raw_text = ""
        self._cached_patient_ref = ""
        self._cached_suggestions = []
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
        for sc in self._shortcuts:
            sc.setEnabled(False)
        self._shortcuts = [
            QShortcut(QKeySequence("A"),    self, activated=self.suggestions_panel.accept_current),
            QShortcut(QKeySequence("R"),    self, activated=self.suggestions_panel.reject_current),
            QShortcut(QKeySequence("E"),    self, activated=self.suggestions_panel.edit_current),
            QShortcut(QKeySequence("Down"), self, activated=self.suggestions_panel.nav_next),
            QShortcut(QKeySequence("Up"),   self, activated=self.suggestions_panel.nav_prev),
            QShortcut(QKeySequence("J"),    self, activated=self.suggestions_panel.nav_next),
            QShortcut(QKeySequence("K"),    self, activated=self.suggestions_panel.nav_prev),
        ]

    def _build_ui(self):
        top_bar = QWidget()
        top_bar.setFixedHeight(52)
        top_bar.setStyleSheet(
            f"background:{BG_TOP}; border-bottom:1px solid {BORDER};"
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

        theme_label = "☀  Light" if theme.is_dark() else "🌙  Dark"
        self.theme_btn = QPushButton(theme_label)
        self.theme_btn.setFixedSize(88, 34)
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color:{TEXT_PRI}; border-color:{ACCENT}; }}
        """)
        self.theme_btn.clicked.connect(self._toggle_theme)
        tb_lay.addWidget(self.theme_btn)

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

        self.discharge_panel   = DischargeSummaryPanel()
        self.suggestions_panel = SuggestionsPanel()
        self.chat_panel        = ChatPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {BORDER};
            }}
            QSplitter::handle:hover {{
                background: {ACCENT};
            }}
        """)
        splitter.addWidget(self.discharge_panel)
        splitter.addWidget(self.suggestions_panel)
        splitter.addWidget(self.chat_panel)
        splitter.setSizes([420, 500, 450])

        central = QWidget()
        central.setStyleSheet(f"background:{BG_APP};")
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(top_bar)
        main_lay.addWidget(splitter, 1)

        self.setCentralWidget(central)

    def _toggle_theme(self):
        theme.toggle()
        _reload_colors()
        old_central = self.centralWidget()
        self._apply_global_style()
        self._build_ui()
        self._setup_shortcuts()
        if self._cached_raw_text:
            self.discharge_panel.set_text(self._cached_raw_text, self._cached_patient_ref)
        if self._cached_suggestions:
            self.suggestions_panel.load(self._cached_suggestions)
        if old_central:
            old_central.setParent(None)
            old_central.deleteLater()

    def _load_data(self):
        self.suggestions_panel.show_loading()

        # Stop at the first failed call: one clear message instead of three
        # failures in a row and a blank screen that looks like "no suggestions".
        raw_text = api_client.get_raw_text(self.document_id)
        docs = [] if api_client.LAST_ERROR else api_client.get_documents()
        suggestions = [] if api_client.LAST_ERROR else api_client.get_suggestions(self.document_id)
        if api_client.LAST_ERROR:
            self.discharge_panel.set_text("Couldn't load this discharge summary.")
            self.suggestions_panel.show_load_error(api_client.LAST_ERROR, self._load_data)
            return

        doc = next((d for d in docs if d["document_id"] == self.document_id), {})
        self._cached_raw_text    = raw_text
        self._cached_patient_ref = doc.get("patient_ref", "")
        self.discharge_panel.set_text(raw_text, self._cached_patient_ref)

        self._cached_suggestions = suggestions
        self.suggestions_panel.load(suggestions)

        self.chat_panel.load_history(self.document_id)

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
        else:
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CodingWorkspace()
    window.show()
    sys.exit(app.exec())
