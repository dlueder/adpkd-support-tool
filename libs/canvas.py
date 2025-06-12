import math
import numpy as np
from libs.shape import Shape
from libs.lib import distance
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import QMenu, QApplication, QWidget
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush, QPen, QPolygonF


CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor


class Canvas(QWidget):
    zoomRequest = Signal(int)
    scrollRequest = Signal(int, int)
    newShape = Signal()
    selectionChanged = Signal(bool)
    shapeMoved = Signal()
    drawingPolygon = Signal(bool)
    saveFileSignal = Signal()
    CREATE, EDIT = list(range(2))
    epsilon = 11.0

    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        self.mode = self.EDIT
        self.contourMode = False
        self.shapes = []
        self.current = None
        self.selectedShape = None  # save the selected shape here
        self.selectedShapeCopy = None
        self.globalMousePos = None
        self.memIdx = list()
        self.currentIdx = 0  # only needed for toggling between multiple overlaying cells
        self.cntOldidx = None  # preeventing error on mouseReleaseEvent without contour
        self.drawingLineColor = QColor(255, 255, 255, 255)
        self.drawingRectColor = QColor(255, 255, 255, 255)
        self.drawingContourColor = QColor(255, 0, 0)
        self.line = Shape(line_color=self.drawingLineColor)
        self.prevPoint = QPoint()
        self.offsets = QPoint(), QPoint()
        self.scale = 1.0
        self.pixmap = QPixmap()
        self.visible = {}
        self._hideBackround = False
        self.hideBackround = False
        self.hShape = None
        self.hVertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        self.menus = (QMenu(), QMenu())
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.verified = False
        self.showContourOverlay = False
        self.last_x, self.last_y = None, None   # Last x- and y-coordinate of the mouse pointer during drawing
        self.pen_color = QColor('#000000')  # Color of the pen
        self.pen_width = 3  # Pen thickness
        self.points = []  # Listing of all coordinate points.
        self.startEndEqual = False  # Is set to True if the start and end point is the same with a margin.
        self.manualMarkingMode = False
        self.enabledDrawing = False
        self.pixmapCopy = QPixmap()

    def setPenColor(self, c):
        self.pen_color = QColor(c)

    def getPenColor(self):
        return self.pen_color

    def setPenWidth(self, w):
        self.pen_width = w

    def getPenWidth(self):
        return self.pen_width

    def setDrawingColor(self, qColor):
        self.drawingLineColor = qColor
        self.drawingRectColor = qColor

    def enterEvent(self, ev):
        self.overrideCursor(self._cursor)

    def leaveEvent(self, ev):
        self.restoreCursor()

    def focusOutEvent(self, ev):
        self.restoreCursor()

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def setEditing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.unHighlight()
            self.deSelectShape()
        self.prevPoint = QPoint()
        self.repaint()

    def unHighlight(self):
        if self.hShape:
            self.hShape.highlightClear()
        self.hVertex = self.hShape = None

    def selectedVertex(self):
        return self.hVertex is not None

    def endManualMark(self):
        self.pixmap = QPixmap.copy(self.pixmapCopy)  # set the orginal pixmap from picture with his previous polygons
        self.update()  # repaint the pixmap
        if self.startEndEqual:
            self.points.append(self.points[0])
            painter = QPainter(self.pixmap)
            p = painter.pen()
            p.setWidth(self.pen_width)
            p.setColor(self.pen_color)
            painter.end()
            self.update()
            self.pixmapCopy = QPixmap.copy(self.pixmap)
            mmshape = Shape(label='cell')
            mmshape.contourEdited = True
            points = [(p.x(), p.y()) for p in self.points]
            ymax = max(points, key=lambda x: x[1])[1]
            ymin = min(points, key=lambda x: x[1])[1]
            xmax = max(points, key=lambda x: x[0])[0]
            xmin = min(points, key=lambda x: x[0])[0]
            bnd_box_offset = 5
            cnt_pnts = list()
            for p in self.points:
                cnt_pnts.append((p.y() - ymin + bnd_box_offset, p.x() - xmin + bnd_box_offset))

            bng_box = list()
            bng_box.append(QPoint(xmin - bnd_box_offset, ymin - bnd_box_offset))  # The left upper point
            bng_box.append(QPoint(xmax + bnd_box_offset, ymin - bnd_box_offset))  # The right upper point
            bng_box.append(QPoint(xmax + bnd_box_offset, ymax + bnd_box_offset))  # The right lower point
            bng_box.append(QPoint(xmin - bnd_box_offset, ymax + bnd_box_offset))  # The left lower point

            if self.selectedShape:
                self.selectedShape.contour_points = cnt_pnts.copy()
                self.selectedShape.points = bng_box.copy()
                self.selectedShape.contourEdited = True
            else:
                mmshape.points = bng_box.copy()
                mmshape.contour_points = cnt_pnts.copy()
                mmshape.close()
                self.shapes.append(mmshape)
            self.parent().window().saveFile()
            self.deactivateMarkingMode()
        self.last_x = None
        self.last_y = None
        self.points.clear()

    def mouseMoveEvent(self, ev):
        """Update line with last point and current coordinates."""
        pos = self.transformPos(ev.pos())
        self.globalMousePos = pos
        # Update coordinates in status bar if image is opened
        window = self.parent().window()
        if window.filePath is not None:
            self.parent().window().labelCoordinates.setText(
                'X: %d; Y: %d' % (pos.x(), pos.y()))

        if self.manualMarkingMode and self.enabledDrawing:
            painter = QPainter(self.pixmap)
            p = painter.pen()
            p.setWidth(self.pen_width)
            p.setColor(self.pen_color)
            painter.setPen(p)
            if self.last_x is not None or self.last_y is not None:
                painter.drawLine(int(self.last_x), int(self.last_y), int(pos.x()), int(pos.y()))
                last_list_pos = self.points.__len__() - 1    # get the index for the last mouse position
                offset = 10
                if self.points[last_list_pos].x() > (self.points[0].x() - offset) \
                    and self.points[last_list_pos].x() < (self.points[0].x() + offset) \
                    and self.points[last_list_pos].y() > (self.points[0].y() - offset) \
                    and self.points[last_list_pos].y() < (self.points[0].y() + offset) \
                        and self.points.__len__() > 20:  # minimal 20 points in the manualMark
                    self.startEndEqual = True
                    p.setColor(Qt.green)
                    painter.setPen(p)
                    painter.drawEllipse(QPoint(int(pos.x()), int(pos.y())), 5, 5)
                    self.enabledDrawing = False
                painter.end()
                self.update()
                self.points.append(QPoint(int(pos.x()), int(pos.y())))
                self.last_x = int(pos.x())
                self.last_y = int(pos.y())
                if self.startEndEqual:
                    self.endManualMark()

        if self.drawing() or self.manualMarkingMode:
            self.overrideCursor(CURSOR_DRAW)
            if self.current:
                color = self.drawingLineColor
                if self.outOfPixmap(pos):
                    pos = self.intersectionPoint(self.current[-1], pos)
                elif len(self.current) > 1 and self.closeEnough(pos, self.current[0]):
                    pos = self.current[0]
                    color = self.current.line_color
                    self.overrideCursor(CURSOR_POINT)
                    self.current.highlightVertex(0, Shape.NEAR_VERTEX)

                self.line[1] = pos
                self.line.line_color = color
                self.prevPoint = QPoint()
                self.current.highlightClear()
            else:
                self.prevPoint = pos
            self.repaint()
            return

        # Polygon copy moving.
        if not self.contourMode:
            if Qt.RightButton & ev.buttons():
                if self.selectedShapeCopy and self.prevPoint:
                    self.overrideCursor(CURSOR_MOVE)
                    self.boundedMoveShape(self.selectedShapeCopy, pos)
                    self.repaint()
                elif self.selectedShape:
                    self.selectedShapeCopy = self.selectedShape.copy()
                    self.repaint()
                return

        if not self.contourMode:
            if Qt.LeftButton & ev.buttons():
                if self.selectedVertex():
                    self.boundedMoveVertex(pos)
                    self.shapeMoved.emit()
                    self.repaint()
                elif self.selectedShape and self.prevPoint:
                    self.overrideCursor(CURSOR_MOVE)
                    self.boundedMoveShape(self.selectedShape, pos)
                    self.shapeMoved.emit()
                    # self.selectedShape.contour_points = list()
                    self.repaint()
                return
        if self.contourMode and self.selectedShape:
            if Qt.LeftButton & ev.buttons():
                self.overrideCursor(CURSOR_MOVE)
                if self.cntOldidx is not None:
                    shapeOrigin = self.selectedShape.points[0]
                    try:
                        cntOld = self.selectedShape.contour_points[self.cntOldidx]
                    except IndexError:
                        return
                    cntNew = int(pos.y() - shapeOrigin.y()), int(pos.x() - shapeOrigin.x())
                    delta_y, delta_x = cntNew[0] - cntOld[0], cntNew[1] - cntOld[1]
                    mods = ev.modifiers()
                    if Qt.KeyboardModifier.ControlModifier == mods:
                        for i, p in enumerate(self.selectedShape.contour_points):
                            self.selectedShape.contour_points[i] = (p[0] + delta_y, p[1] + delta_x)
                    else:
                        for i in range(self.cntOldidx - 3, self.cntOldidx + 4, 1):
                            i %= len(self.selectedShape.contour_points)
                            p = self.selectedShape.contour_points[i]
                            d = np.sqrt((p[0] - cntOld[0]) ** 2 + (p[1] - cntOld[1]) ** 2)
                            f = 1 / (1 + 1.8 * d)
                            self.selectedShape.contour_points[i] = (p[0] + delta_y * f, p[1] + delta_x * f)
            self.repaint()
            return
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            index = shape.nearestVertex(pos, self.epsilon)
            if index is not None:
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = index, shape
                shape.highlightVertex(index, shape.MOVE_VERTEX)
                self.overrideCursor(CURSOR_POINT)
                self.update()
                break
            elif shape.containsPoint(pos):
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = None, shape
                self.overrideCursor(CURSOR_GRAB)
                self.update()
                break
        else:  # Nothing found, clear highlights, reset state.
            if self.hShape:
                self.hShape.highlightClear()
                self.update()
            self.hVertex, self.hShape = None, None
            self.overrideCursor(CURSOR_DEFAULT)

    def mousePressEvent(self, ev):
        pos = self.transformPos(ev.pos())

        if ev.button() == Qt.LeftButton:

            if self.manualMarkingMode:
                if self.last_x is None and not self.outOfPixmap(pos):
                    self.last_x = pos.x()
                    self.last_y = pos.y()
                    self.points.append(QPoint(pos.x(), pos.y()))  # insert the first coordination of mouse
                    self.enabledDrawing = True
                    self.startEndEqual = False
                    return

            if self.drawing():
                self.handleDrawing(pos)
            elif self.contourMode and self.showContourOverlay:
                self.unHighlight()
                xmin, ymin = int(self.selectedShape.points[0].x()), int(self.selectedShape.points[0].y())
                pointcloud = list()
                begin = pos.y() - ymin, pos.x() - xmin
                d_s = list()
                for p in self.selectedShape.contour_points:
                    d = np.sqrt((p[0] - begin[0])**2 + (p[1] - begin[1])**2)
                    # print(d)
                    if d < 10:
                        pointcloud.append(p)
                        d_s.append(d)
                try:
                    nearest = pointcloud[np.argmin(d_s)]
                    self.cntOldidx = self.selectedShape.contour_points.index(nearest)
                except Exception:
                    self.cntOldidx = None
            else:
                self.selectShapePoint(pos)
                self.prevPoint = pos
                self.repaint()
        elif ev.button() == Qt.RightButton and self.editing():
            self.selectShapePoint(pos)
            self.prevPoint = pos
            self.repaint()

    def mouseReleaseEvent(self, ev):
        pos = self.transformPos(ev.pos())
        if ev.button() == Qt.RightButton:
            menu = self.menus[bool(self.selectedShapeCopy)]
            self.restoreCursor()
            if not menu.exec_(self.mapToGlobal(ev.pos()))\
               and self.selectedShapeCopy:
                self.selectedShapeCopy = None
                self.repaint()

        elif ev.button() == Qt.LeftButton and self.selectedShape:
            if self.contourMode and self.showContourOverlay and not self.manualMarkingMode:
                if self.cntOldidx is not None:
                    shapeOrigin = self.selectedShape.points[0]
                    try:
                        cntOld = self.selectedShape.contour_points[self.cntOldidx]
                        cntNew = int(pos.y() - shapeOrigin.y()), int(pos.x() - shapeOrigin.x())
                        delta_y, delta_x = cntNew[0] - cntOld[0], cntNew[1] - cntOld[1]
                        for i in range(self.cntOldidx - 3, self.cntOldidx + 4, 1):  # points around that index get modified, too
                            i %= len(self.selectedShape.contour_points)
                            p = self.selectedShape.contour_points[i]
                            d = np.sqrt((p[0] - cntOld[0]) ** 2 + (p[1] - cntOld[1]) ** 2)
                            f = 1 / (1 + 1.4 * d)
                            self.selectedShape.contour_points[i] = (int(p[0] + delta_y * f), int(p[1] + delta_x * f))
                    except IndexError:
                        print(self.contourMode, self.showContourOverlay, self.manualMarkingMode, self.cntOldidx)
            self.repaint()
            if self.selectedVertex():
                self.overrideCursor(CURSOR_POINT)
            else:
                self.overrideCursor(CURSOR_GRAB)
        elif ev.button() == Qt.LeftButton:
            pos = self.transformPos(ev.pos())
            if self.drawing():
                self.handleDrawing(pos)

    def endMove(self, copy=False):
        assert self.selectedShape and self.selectedShapeCopy
        shape = self.selectedShapeCopy
        if copy:
            self.shapes.append(shape)
            self.selectedShape.selected = False
            self.selectedShape = shape
            self.repaint()
        else:
            self.selectedShape.points = [p for p in shape.points]
        self.selectedShapeCopy = None

    def hideBackroundShapes(self, value):
        self.hideBackround = value
        if self.selectedShape:
            self.setHiding(True)
            self.repaint()

    def handleDrawing(self, pos):
        if self.current and self.current.reachMaxPoints() is False:
            initPos = self.current[0]
            minX = initPos.x()
            minY = initPos.y()
            targetPos = self.line[1]
            maxX = targetPos.x()
            maxY = targetPos.y()
            self.current.addPoint(QPoint(maxX, minY))
            self.current.addPoint(targetPos)
            self.current.addPoint(QPoint(minX, maxY))
            self.finalise()
        elif not self.outOfPixmap(pos):
            self.current = Shape()
            self.current.addPoint(pos)
            self.line.points = [pos, pos]
            self.setHiding()
            self.drawingPolygon.emit(True)
            self.update()

    def setHiding(self, enable=True):
        self._hideBackround = self.hideBackround if enable else False

    def canCloseShape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        if self.canCloseShape() and len(self.current) > 3:
            self.current.popPoint()
            self.finalise()

    def selectShape(self, shape):
        self.deSelectShape()
        shape.selected = True
        self.selectedShape = shape
        self.setHiding()
        self.selectionChanged.emit(True)
        self.update()

    def selectShapePoint(self, point):
        """Select the first shape created which contains this point."""
        self.deSelectShape()
        if self.selectedVertex():  # A vertex is marked for selection.
            index, shape = self.hVertex, self.hShape
            shape.highlightVertex(index, shape.MOVE_VERTEX)
            self.selectShape(shape)
            return
        for shape in reversed(self.shapes):
            if self.isVisible(shape) and shape.containsPoint(point):
                self.selectShape(shape)
                self.calculateOffsets(shape, point)
                return

    def calculateOffsets(self, shape, point):
        rect = shape.boundingRect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPoint(x1, y1), QPoint(x2, y2)

    def boundedMoveVertex(self, pos):
        index, shape = self.hVertex, self.hShape
        point = shape[index]
        if self.outOfPixmap(pos):
            pos = self.intersectionPoint(point, pos)
        shiftPos = pos - point
        shape.moveVertexBy(index, shiftPos)

        lindex = (index + 1) % 4
        rindex = (index + 3) % 4
        lshift = None
        rshift = None
        if index % 2 == 0:
            rshift = QPoint(shiftPos.x(), 0)
            lshift = QPoint(0, shiftPos.y())
        else:
            lshift = QPoint(shiftPos.x(), 0)
            rshift = QPoint(0, shiftPos.y())
        shape.moveVertexBy(rindex, rshift)
        shape.moveVertexBy(lindex, lshift)

    def boundedMoveShape(self, shape, pos):
        if self.outOfPixmap(pos):
            return False
        o1 = pos + self.offsets[0]
        if self.outOfPixmap(o1):
            pos -= QPoint(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.outOfPixmap(o2):
            pos += QPoint(min(0, self.pixmap.width() - o2.x()), min(0, self.pixmap.height() - o2.y()))
        dp = pos - self.prevPoint
        if dp:
            shape.moveBy(dp)
            self.prevPoint = pos
            return True
        return False

    def deSelectShape(self):
        if self.selectedShape and not self.contourMode:
            self.selectedShape.selected = False
            self.selectedShape = None
            self.setHiding(False)
            self.selectionChanged.emit(False)
            self.update()

    def deleteSelected(self):
        if self.selectedShape and not self.contourMode:
            shape = self.selectedShape
            if self.selectedShape in self.shapes:
                print('Box wurde gelöscht')
                self.shapes.remove(self.selectedShape)
            else:
                print('Zu löschen Box wurde nicht gefunden')
            self.selectedShape = None
            self.update()
            return shape

    def copySelectedShape(self):
        if self.selectedShape:
            shape = self.selectedShape.copy()
            self.deSelectShape()
            self.shapes.append(shape)
            shape.selected = True
            self.selectedShape = shape
            self.boundedShiftShape(shape)
            return shape

    def boundedShiftShape(self, shape):
        point = shape[0]
        offset = QPoint(2.0, 2.0)
        self.calculateOffsets(shape, point)
        self.prevPoint = point
        if not self.boundedMoveShape(shape, point - offset):
            self.boundedMoveShape(shape, point + offset)

    def paintEvent(self, event):
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)
        p = self._painter
        p.begin(self)
        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter())

        p.drawPixmap(0, 0, self.pixmap)
        Shape.scale = self.scale
        for shape in self.shapes:
            if (shape.selected or not self._hideBackround) and self.isVisible(shape):
                shape.fill = shape.selected or shape == self.hShape
                shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selectedShapeCopy:
            self.selectedShapeCopy.paint(p)

        if self.current is not None and len(self.line) == 2:
            leftTop = self.line[0]
            rightBottom = self.line[1]
            rectWidth = rightBottom.x() - leftTop.x()
            rectHeight = rightBottom.y() - leftTop.y()
            p.setPen(self.drawingRectColor)
            brush = QBrush(Qt.BDiagPattern)
            p.setBrush(brush)
            p.drawRect(leftTop.x(), leftTop.y(), rectWidth, rectHeight)

        if self.drawing() and not self.prevPoint.isNull() and not self.outOfPixmap(self.prevPoint):
            p.setPen(QColor(0, 0, 0))
            p.drawLine(self.prevPoint.x(), 0, self.prevPoint.x(), self.pixmap.height())
            p.drawLine(0, self.prevPoint.y(), self.pixmap.width(), self.prevPoint.y())

        self.setAutoFillBackground(True)
        if self.verified:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(184, 239, 38, 128))
            self.setPalette(pal)
        else:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(232, 232, 232, 255))
            self.setPalette(pal)

        if self.showContourOverlay:
            # print('showing contour with Qt')
            p.setPen(self.drawingContourColor)
            brush = QBrush(QColor('transparent'))
            p.setBrush(brush)
            for shape in self.shapes:
                p.drawPolygon(self.createPoly(shape))
            if self.contourMode and self.selectedShape:
                pen = QPen(QColor('black'))
                pen.setWidth(3)
                p.setPen(pen)
                xmin, ymin = int(self.selectedShape.points[0].x()), int(self.selectedShape.points[0].y())
                for i in self.selectedShape.contour_points:
                    p.drawPoint(QPoint(i[1] + xmin, i[0] + ymin))  # numpy format y,x coordinates

        p.end()

    def createPoly(self, shape):
        polygon = QPolygonF()
        xmin, ymin = int(shape.points[0].x()), int(shape.points[0].y())
        for p in shape.contour_points:
            polygon.append(QPoint(p[1] + xmin, p[0] + ymin))
        return polygon

    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return point / self.scale - self.offsetToCenter()

    def offsetToCenter(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPoint(x, y)

    def outOfPixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    def finalise(self):
        assert self.current
        if self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return

        self.current.close()
        self.shapes.append(self.current)
        self.current = None
        self.setHiding(False)
        self.newShape.emit()
        self.update()

    def closeEnough(self, p1, p2):
        return distance(p1 - p2) < self.epsilon

    def intersectionPoint(self, p1, p2):
        size = self.pixmap.size()
        points = [(0, 0),
                  (size.width(), 0),
                  (size.width(), size.height()),
                  (0, size.height())]
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        d, i, (x, y) = min(self.intersectingEdges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        if (x, y) == (x1, y1):
            if x3 == x4:
                return QPoint(x3, min(max(0, y2), max(y3, y4)))
            else:  # y3 == y4
                return QPoint(min(max(0, x2), max(x3, x4)), y3)
        return QPoint(x, y)

    def intersectingEdges(self, x1y1, x2y2, points):
        """For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen."""
        x1, y1 = x1y1
        x2, y2 = x2y2
        for i in range(4):
            x3, y3 = points[i]
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QPoint((x3 + x4) / 2, (y3 + y4) / 2)
                d = distance(m - QPoint(x2, y2))
                yield d, i, (x, y)

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        delta = ev.angleDelta()
        h_delta = delta.x()
        v_delta = delta.y()

        mods = ev.modifiers()
        if ((mods == Qt.KeyboardModifier.ControlModifier) or (mods == Qt.KeyboardModifier.MetaModifier)) and v_delta:
            self.zoomRequest.emit(v_delta)
        else:
            v_delta and self.scrollRequest.emit(v_delta, Qt.Vertical)
            h_delta and self.scrollRequest.emit(h_delta, Qt.Horizontal)
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if key == Qt.Key_Escape and self.current:
            print('ESC press')
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key_Return and self.canCloseShape():
            self.finalise()
        elif key == Qt.Key_Left and self.selectedShape:
            self.moveOnePixel('Left')
        elif key == Qt.Key_Right and self.selectedShape:
            self.moveOnePixel('Right')
        elif key == Qt.Key_Up and self.selectedShape:
            self.moveOnePixel('Up')
        elif key == Qt.Key_Down and self.selectedShape:
            self.moveOnePixel('Down')
        elif key == Qt.Key_S and self.selectedShape:
            if not self.selectedShape.contourEdited:
                self.selectedShape.contourEdited = True
                self.deSelectShape()
                self.update()
        elif key == Qt.Key_E and self.selectedShape and self.showContourOverlay:
            self.contourMode = True
            self.unHighlight()
        elif key == Qt.Key_Q and self.selectedShape and self.contourMode:
            if self.manualMarkingMode:
                self.startEndEqual = True
                self.endManualMark()
            self.contourMode = False
            self.selectedShape.contourEdited = True
            self.deSelectShape()
            self.saveFileSignal.emit()
        elif key == Qt.Key_N and self.selectedShape and self.contourMode:
            if not self.selectedShape.contour_points:
                self.selectedShape.contour_points = self.genContourInShape(self.selectedShape)
                self.update()
        elif key == Qt.Key_R and self.selectedShape and self.contourMode:
            self.selectedShape.contour_points = list()
            self.update()
        elif key == Qt.Key_F and not self.contourMode:
            pos = self.globalMousePos
            shapesIdx = list()
            for s in self.shapes:
                if s.containsPoint(pos):
                    shapesIdx.append(self.shapes.index(s))
            if len(shapesIdx) >= 2:
                if sorted(self.memIdx) != sorted(shapesIdx):
                    self.memIdx = shapesIdx
                    self.currentIdx = 0
                else:
                    self.currentIdx += 1
                i = self.memIdx[self.currentIdx % len(self.memIdx)]
                if self.selectedShape != self.shapes[i]:
                    self.deSelectShape()
                    self.selectShape(self.shapes[i])
                    self.update()
        elif key == Qt.Key_M and self.showContourOverlay:
            self.manualMarkingMode = not self.manualMarkingMode
            print("Manual marking mode: ", self.manualMarkingMode)
        return

    def genContourInShape(self, shape):
        genContour = list()
        xmin, xmax, ymin, ymax = shape.points[0].x(), shape.points[2].x(), shape.points[0].y(), shape.points[2].y()
        height = xmax - xmin
        width = ymax - ymin
        r = (xmax - xmin) // 2
        w = 360 / 16
        for i in range(16):
            t = w * i
            x = r * math.cos(math.radians(t))
            y = r * math.sin(math.radians(t))
            genContour.append((width / 2 + x, height / 2 + y))
        return genContour

    def moveOnePixel(self, direction):
        if direction == 'Left' and not self.moveOutOfBound(QPoint(-1.0, 0)):
            self.selectedShape.points[0] += QPoint(-1.0, 0)
            self.selectedShape.points[1] += QPoint(-1.0, 0)
            self.selectedShape.points[2] += QPoint(-1.0, 0)
            self.selectedShape.points[3] += QPoint(-1.0, 0)
        elif direction == 'Right' and not self.moveOutOfBound(QPoint(1.0, 0)):
            self.selectedShape.points[0] += QPoint(1.0, 0)
            self.selectedShape.points[1] += QPoint(1.0, 0)
            self.selectedShape.points[2] += QPoint(1.0, 0)
            self.selectedShape.points[3] += QPoint(1.0, 0)
        elif direction == 'Up' and not self.moveOutOfBound(QPoint(0, -1.0)):
            self.selectedShape.points[0] += QPoint(0, -1.0)
            self.selectedShape.points[1] += QPoint(0, -1.0)
            self.selectedShape.points[2] += QPoint(0, -1.0)
            self.selectedShape.points[3] += QPoint(0, -1.0)
        elif direction == 'Down' and not self.moveOutOfBound(QPoint(0, 1.0)):
            self.selectedShape.points[0] += QPoint(0, 1.0)
            self.selectedShape.points[1] += QPoint(0, 1.0)
            self.selectedShape.points[2] += QPoint(0, 1.0)
            self.selectedShape.points[3] += QPoint(0, 1.0)
        self.shapeMoved.emit()
        self.repaint()

    def moveOutOfBound(self, step):
        points = [p1 + p2 for p1, p2 in zip(self.selectedShape.points, [step] * 4)]
        return True in map(self.outOfPixmap, points)

    def setLastLabel(self, text, line_color=None, fill_color=None):
        assert text
        self.shapes[-1].label = text
        if line_color:
            self.shapes[-1].line_color = line_color
        if fill_color:
            self.shapes[-1].fill_color = fill_color
        return self.shapes[-1]

    def undoLastLine(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def resetAllLines(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def loadPixmap(self, pixmap):
        self.pixmap = pixmap
        self.pixmapCopy = QPixmap.copy(pixmap)
        self.shapes = []
        self.repaint()

    def loadShapes(self, shapes):
        self.shapes = list(shapes)
        self.current = None
        self.repaint()

    def setShapeVisible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def currentCursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def overrideCursor(self, cursor):
        self._cursor = cursor
        if self.currentCursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restoreCursor(self):
        QApplication.restoreOverrideCursor()

    def resetState(self):
        self.restoreCursor()
        self.pixmap = None
        self.memIdx = list()
        self.currentIdx = 0
        self.update()

    def deactivateMarkingMode(self):
        if self.manualMarkingMode:
            self.manualMarkingMode = False
            self.overrideCursor(CURSOR_DEFAULT)
            self.last_x, self.last_y = None, None
            self.pen_color = QColor('#000000')
            self.pen_width = 3
            self.points.clear()
