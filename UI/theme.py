DARK = {
    "BG_APP":         "#0F1923",
    "BG_PANEL":       "#162230",
    "BG_CARD":        "#1C2D3E",
    "BG_CARD_ALT":    "#1A2B3C",
    "BG_TOP":         "#0A1520",
    "BG_EDIT":        "#0D1E2E",
    "BG_CHAT_H":      "#0D1E30",
    "BG_CHAT_H2":     "#112238",
    "BG_CHAT_USR":    "#1A3554",
    "BG_CHAT_BOT":    "#111E2B",
    "SEC_HOVER":      "#1A2836",
    "SEC_PRINCIPAL":  "#0D2035",
    "SEC_ASSOCIATIVE":"#122536",
    "SEC_PROCEDURES": "#0F2A26",
    "SEC_MEDICATIONS":"#2A2416",
    "SEC_MANUAL":     "#161F2A",
    "BORDER":         "#253D52",
    "ACCENT":         "#2E7DD1",
    "ACCENT_LITE":    "#3D8FE8",
    "SUCCESS":        "#27AE60",
    "DANGER":         "#C0392B",
    "TEXT_PRI":       "#E8EDF2",
    "TEXT_SEC":       "#8FA8BF",
    "TEXT_CODE":      "#5BB8FF",
    "TEXT_EVD":       "#F0C040",
    "CONF_HI":        "#27AE60",
    "CONF_MID":       "#F39C12",
    "CONF_LO":        "#C0392B",
}

LIGHT = {
    "BG_APP":         "#E8EDF2",
    "BG_PANEL":       "#D8E3EC",
    "BG_CARD":        "#FFFFFF",
    "BG_CARD_ALT":    "#F0F4F8",
    "BG_TOP":         "#F5F8FA",
    "BG_EDIT":        "#F0F6FC",
    "BG_CHAT_H":      "#DCE8F2",
    "BG_CHAT_H2":     "#D4E2EE",
    "BG_CHAT_USR":    "#DDE9F7",
    "BG_CHAT_BOT":    "#F0F6FB",
    "SEC_HOVER":      "#D4DDE6",
    "SEC_PRINCIPAL":  "#EBF3FB",
    "SEC_ASSOCIATIVE":"#EEF7FF",
    "SEC_PROCEDURES": "#EBF8F4",
    "SEC_MEDICATIONS":"#FEFAE8",
    "SEC_MANUAL":     "#F2F6F8",
    "BORDER":         "#B0C4D4",
    "ACCENT":         "#2E7DD1",
    "ACCENT_LITE":    "#3D8FE8",
    "SUCCESS":        "#27AE60",
    "DANGER":         "#C0392B",
    "TEXT_PRI":       "#0F1923",
    "TEXT_SEC":       "#3A5570",
    "TEXT_CODE":      "#1A6BB5",
    "TEXT_EVD":       "#B8860B",
    "CONF_HI":        "#27AE60",
    "CONF_MID":       "#F39C12",
    "CONF_LO":        "#C0392B",
}

current = DARK


def toggle():
    global current
    current = LIGHT if current is DARK else DARK


def is_dark() -> bool:
    return current is DARK


def get_app_style() -> str:
    t = current
    return f"""
        QMessageBox {{ background: {t['BG_PANEL']}; }}
        QMessageBox QLabel {{ color: {t['TEXT_PRI']}; font-size: 12px; }}
        QMessageBox QPushButton {{
            background: {t['BG_CARD']}; color: {t['TEXT_PRI']};
            border: 1px solid {t['BORDER']}; border-radius: 4px;
            padding: 5px 18px; min-width: 60px;
        }}
        QMessageBox QPushButton:hover {{ border-color: {t['ACCENT']}; color: white; }}
        QInputDialog {{ background: {t['BG_PANEL']}; }}
        QInputDialog QLabel {{ color: {t['TEXT_PRI']}; }}
        QInputDialog QLineEdit {{
            background: {t['BG_TOP']}; color: {t['TEXT_PRI']};
            border: 1px solid {t['BORDER']}; border-radius: 4px;
            padding: 4px 8px; min-height: 22px;
        }}
    """
