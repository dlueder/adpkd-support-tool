from PySide6.QtWidgets import QListWidgetItem


class HashableQListWidgetItem(QListWidgetItem):
    """Fixes PyQt5: TypeError: unhashable type: 'QListWidgetItem'."""
    def __init__(self, *args):
        super(HashableQListWidgetItem, self).__init__(*args)

    def __hash__(self):
        return hash(id(self))
