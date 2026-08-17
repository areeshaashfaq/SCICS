import sys
import api_client
import session
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BG_APP   = "#0F1923"
BG_CARD  = "#1C2D3E"
BG_DARK  = "#0A1520"
BORDER   = "#253D52"
ACCENT   = "#2E7DD1"
ACCENT_L = "#3D8FE8"
DANGER   = "#C0392B"
TEXT_PRI = "#E8EDF2"
TEXT_SEC = "#8FA8BF"


# ── clickable role button ─────────────────────────────────────────────────────
class RoleCard(QFrame):
    def __init__(self, icon: str, title: str, role: str, on_select):
        super().__init__()
        self.role      = role
        self.on_select = on_select
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        self._style_default()
        self._build(icon, title)

    def _build(self, icon, title):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12)
        lay.setSpacing(5)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI", 18))
        icon_lbl.setStyleSheet("background:transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color:{TEXT_PRI}; background:transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title_lbl)

    def _style_default(self):
        self.setStyleSheet(f"""
            RoleCard {{
                background: {BG_DARK};
                border: none;
                border-radius: 8px;
            }}
            RoleCard:hover {{
                background: #112030;
            }}
        """)

    def _style_selected(self):
        self.setStyleSheet(f"""
            RoleCard {{
                background: #0D2540;
                border: 2px solid {ACCENT};
                border-radius: 8px;
            }}
        """)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self._style_selected()
        else:
            self._style_default()

    def mousePressEvent(self, event):
        self.on_select(self.role)


# ── main login window ─────────────────────────────────────────────────────────
class LoginWindow(QMainWindow):
    def __init__(self, on_login=None):
        super().__init__()
        self.on_login       = on_login
        self._selected_role = None
        self.setWindowTitle("SIUT — ICD Coding System")
        self.resize(480, 580)
        self.setFixedSize(480, 580)
        self.setStyleSheet(
            f"QMainWindow {{ background:{BG_APP}; }} QWidget {{ background:{BG_APP}; }}"
        )
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        # ── centred card ──────────────────────────────────────────────────────
        card = QFrame()
        card.setFixedWidth(400)
        card.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: none;
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(40, 36, 40, 32)
        lay.setSpacing(0)

        # logo
        logo = QLabel("SIUT")
        logo.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        logo.setStyleSheet(f"color:{ACCENT}; background:transparent;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)

        sub = QLabel("ICD Clinical Coding System")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet(f"color:{TEXT_SEC}; background:transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)

        lay.addSpacing(28)

        # ── role selector (no label, no borders on cards) ─────────────────────
        role_row = QHBoxLayout()
        role_row.setSpacing(14)

        self.card_coder = RoleCard("⚕", "Coder",  "coder", self._select_role)
        self.card_admin = RoleCard("◈", "Admin",   "admin", self._select_role)
        role_row.addWidget(self.card_coder)
        role_row.addWidget(self.card_admin)

        role_w = QWidget()
        role_w.setStyleSheet("background:transparent;")
        role_w.setLayout(role_row)
        lay.addWidget(role_w)

        lay.addSpacing(26)

        # ── credentials ───────────────────────────────────────────────────────
        lay.addWidget(self._field_label("Username"))
        lay.addSpacing(4)
        self.username_input = self._input_field("Enter username")
        lay.addWidget(self.username_input)

        lay.addSpacing(14)

        lay.addWidget(self._field_label("Password"))
        lay.addSpacing(4)
        self.password_input = self._input_field("Enter password", password=True)
        self.password_input.returnPressed.connect(self._attempt_login)
        lay.addWidget(self.password_input)

        lay.addSpacing(22)

        # error label
        self.error_lbl = QLabel("")
        self.error_lbl.setFont(QFont("Segoe UI", 10))
        self.error_lbl.setStyleSheet(f"color:{DANGER}; background:transparent;")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_lbl.setVisible(False)
        lay.addWidget(self.error_lbl)

        lay.addSpacing(6)

        # login button
        self.login_btn = QPushButton("Log In")
        self.login_btn.setFixedHeight(42)
        self.login_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white;
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {ACCENT_L}; }}
            QPushButton:disabled {{ background: {BORDER}; color: {TEXT_SEC}; }}
        """)
        self.login_btn.clicked.connect(self._attempt_login)
        lay.addWidget(self.login_btn)

        lay.addSpacing(20)

        hint = QLabel("demo  ·  coder: fatimah / coder123    admin: admin / admin123")
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet(f"color:{BORDER}; background:transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        lay.addWidget(hint)

        # centre card horizontally
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        outer.addLayout(h)

        outer.addStretch()

        footer = QLabel("SIUT Khidmat Project  ·  2026")
        footer.setFont(QFont("Segoe UI", 9))
        footer.setStyleSheet(f"color:{BORDER}; background:transparent;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(footer)
        outer.addSpacing(14)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color:{TEXT_SEC}; background:transparent;")
        return lbl

    def _input_field(self, placeholder: str, password: bool = False) -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(38)
        inp.setFont(QFont("Segoe UI", 11))
        if password:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_DARK}; color: {TEXT_PRI};
                border: 1px solid {BORDER}; border-radius: 6px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        return inp

    def _select_role(self, role: str):
        self._selected_role = role
        self.card_coder.set_selected(role == "coder")
        self.card_admin.set_selected(role == "admin")
        self.error_lbl.setVisible(False)
        self.username_input.setFocus()

    def _attempt_login(self):
        if not self._selected_role:
            self._show_error("Please select a role first.")
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Logging in…")
        self.error_lbl.setVisible(False)

        try:
            result = api_client.login(username, password)
        except Exception as e:
            self._show_error(f"Cannot reach server: {e}")
            return
        finally:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Log In")

        error = result.get("error") if result else "invalid_credentials"
        if error == "user_not_found":
            self._show_error("Username not found.")
            self.username_input.setFocus()
            self.username_input.selectAll()
            return
        if error in ("wrong_password", "invalid_credentials"):
            self._show_error("Incorrect password.")
            self.password_input.clear()
            self.password_input.setFocus()
            return

        if result.get("role") != self._selected_role:
            self._show_error(f"This account is not registered as a {self._selected_role}.")
            self.password_input.clear()
            return

        session.set_user(
            name=result.get("name", username),
            role=result.get("role"),
            token=result.get("token", ""),
        )

        if self.on_login:
            self.on_login(session.current_user["role"])

    def _show_error(self, msg: str):
        self.error_lbl.setText(msg)
        self.error_lbl.setVisible(True)

    def clear_fields(self):
        self._selected_role = None
        self.card_coder.set_selected(False)
        self.card_admin.set_selected(False)
        self.username_input.clear()
        self.password_input.clear()
        self.error_lbl.setVisible(False)


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
