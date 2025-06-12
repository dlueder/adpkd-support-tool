import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize
from .window import MainWindow


def prepare_ui(appname, icon, scriptPath, argv=None):
    if argv is None:
        argv = []

    app = QApplication(argv)
    app.setApplicationName(appname)
    app_icon = QIcon()
    app_icon.addFile(icon, QSize(225, 225))
    app.setWindowIcon(app_icon)
    win = MainWindow(
        appname=appname,
        scriptPath=scriptPath,
        defaultFilename=argv[1] if len(argv) >= 2 else None,
        defaultPrefdefClassFile=argv[2] if len(argv) >= 3 else os.path.join(os.path.dirname(sys.argv[0]), 'data', 'predefined_classes.txt'))
    win.show()
    return app, win
