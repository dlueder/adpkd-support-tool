from PySide6.QtWidgets import QDialogButtonBox, QColorDialog


class ColorDialog(QColorDialog):

    def __init__(self, parent=None):
        super(ColorDialog, self).__init__(parent)
        self.setOption(QColorDialog.ShowAlphaChannel)
        self.setOption(QColorDialog.DontUseNativeDialog)
        self.default = None
        self.bb = self.layout().itemAt(1).widget()
        self.bb.addButton(QDialogButtonBox.RestoreDefaults)
        self.bb.clicked.connect(self.checkRestore)

    def getColor(self, value=None, title=None, default=None):
        self.default = default
        if title:
            self.setWindowTitle(title)
        if value:
            self.setCurrentColor(value)
        return self.currentColor() if self.exec_() else None

    def checkRestore(self, button):
        if self.bb.buttonRole(button) & QDialogButtonBox.ResetRole and self.default:
            self.setCurrentColor(self.default)
