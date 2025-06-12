from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap, QColor, QPolygon, QBrush, QPainter


class ManualMarker(QWidget):

    def __init__(self, *args, **kwargs):
        super(ManualMarker, self).__init__(*args, **kwargs)
        self.last_x, self.last_y = None, None
        self.pixmap = QPixmap()
        self.pen_color = QColor('#000000')
        self.pen_width = 1
        self.points = []
        self.startEndEqual = False

    def setPenColor(self, c):
        self.pen_color = QColor(c)

    def getPenColor(self):
        return self.pen_color

    def setPenWidth(self, w):
        self.pen_width = w

    def getPenWidth(self):
        return self.pen_width

    def drawPolygon(self):
        polygon = QPolygon(self.points)
        painter = QPainter(self.pixmap)

        p = painter.pen()
        p.setWidth(self.pen_width)
        p.setColor(self.pen_color)
        painter.setBrush(QBrush(Qt.red, Qt.VerPattern))
        painter.setPen(p)
        painter.drawPolygon(polygon)  # Draw the polygon with the brush

        painter.end()
        self.update()

    def mouseMoveEvent(self, e):
        print('manualMarker - mouseMoveEvent')
        if self.last_x is None:
            self.last_x = e.x()
            self.last_y = e.y()
            self.points.append(QPoint(e.x(), e.y()))
            return

        painter = QPainter(self.pixmap)
        p = painter.pen()
        p.setWidth(self.pen_width)
        p.setColor(self.pen_color)
        painter.setPen(p)
        painter.drawLine(self.last_x, self.last_y, e.x(), e.y())
        last_list_pos = self.points.__len__() - 1
        offset = 3
        if self.points[last_list_pos].x() > (self.points[0].x() - offset) \
            and self.points[last_list_pos].x() < (self.points[0].x() + offset) \
            and self.points[last_list_pos].y() > (self.points[0].y() - offset) \
            and self.points[last_list_pos].y() < (self.points[0].y() + offset) \
                and self.points.__len__() > offset:
            print("Start- and End-point matches!!!")
            self.startEndEqual = True
            p.setColor(Qt.green)
            painter.setPen(p)
            painter.drawEllipse(QPoint(e.x(), e.y()), 5, 5)
        elif self.startEndEqual:
            self.startEndEqual = False
        painter.end()
        self.update()
        self.points.append(QPoint(e.x(), e.y()))
        self.last_x = e.x()
        self.last_y = e.y()

    def mouseReleaseEvent(self, e):
        self.last_x = None
        self.last_y = None

        if self.startEndEqual:
            self.points.append(self.points[0])
            self.drawPolygon()
        self.points.clear()

    def loadPixmap(self, pixmap):
        self.pixmap = pixmap
