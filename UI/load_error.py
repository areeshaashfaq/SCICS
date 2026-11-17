# load_error.py — the block a screen shows when it couldn't load from the server.
# Screens show this in place of their data, so a failed load never looks like
# "no records" or a row of zeros.
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

import theme


def make_load_error(detail: str, on_retry, title: str = "Couldn't reach the server") -> QFrame:
    t = theme.current
    box = QFrame()
    box.setObjectName("loadError")
    box.setStyleSheet(
        f"QFrame#loadError {{ background:{t['BG_CARD']}; border:1px solid {t['DANGER']};"
        f" border-radius:8px; }}"
    )
    lay = QVBoxLayout(box)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(6)

    title_lbl = QLabel(title)
    font = QFont("Segoe UI", 12)
    font.setBold(True)
    title_lbl.setFont(font)
    title_lbl.setStyleSheet(f"color:{t['DANGER']}; background:transparent; border:none;")
    lay.addWidget(title_lbl)

    detail_lbl = QLabel(detail or "The server didn't respond.")
    detail_lbl.setFont(QFont("Segoe UI", 10))
    detail_lbl.setWordWrap(True)
    detail_lbl.setStyleSheet(f"color:{t['TEXT_SEC']}; background:transparent; border:none;")
    lay.addWidget(detail_lbl)

    retry = QPushButton("Retry")
    retry.setFixedSize(80, 30)
    retry.setCursor(Qt.CursorShape.PointingHandCursor)
    retry.setStyleSheet(f"""
        QPushButton {{
            background:{t['ACCENT']}; color:white; border:none;
            border-radius:5px; font-size:11px; font-weight:bold;
        }}
        QPushButton:hover {{ background:{t['ACCENT_LITE']}; }}
    """)
    retry.clicked.connect(on_retry)
    lay.addSpacing(6)
    lay.addWidget(retry)
    return box
