import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.app_window import AppWindow
from ui.qt_utils import APP_QSS

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("DHIS2 Dashboard Builder")
    app.setStyleSheet(APP_QSS)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())
