import sys
import session
from PyQt6.QtWidgets import QApplication
from login import LoginWindow
from record_queue import RecordQueueWindow
from admin_dash import AdminDashboard


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    _active = []   # holds the current main window so it isn't garbage collected

    def show_login():
        session.clear()
        for w in _active:
            w.close()
        _active.clear()
        login_win.clear_fields()
        login_win.show()

    def on_login(role: str):
        login_win.hide()
        if role == "admin":
            w = AdminDashboard(on_logout=show_login)
        else:
            w = RecordQueueWindow(on_logout=show_login)
        _active.append(w)
        w.show()

    login_win = LoginWindow(on_login=on_login)
    login_win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
