"""PyQT Window Classes."""

import platform
import os.path
import sys

import codecs
import glob
from functools import partial
from PIL import Image, ImageFont, ImageDraw
import numpy as np

import logging

# from skimage import io
# from skimage.color import rgb2gray
import cv2
from shapely.geometry import Polygon
from libs.canvas import Canvas
from libs.colorDialog import ColorDialog
# from libs.constants import SETTING_ADVANCE_MODE
from libs.labelDialog import LabelDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.lib import addActions, generateColorByText, newAction
from libs.pascal_voc_io import PascalVocReader, PascalVocWriter, XML_EXT
from libs.settings import Settings
from libs.shape import DEFAULT_FILL_COLOR, DEFAULT_LINE_COLOR, Shape
from libs.toolBar import ToolBar
from libs.zoomWidget import ZoomWidget
from libs.detection import ADPKDDetector, ADPKDSegmenter
from libs.excelExport import cellTableGenerator, scaleDialog
from libs.ui.widget import HashableQListWidgetItem
from libs.ui.adpkd_tool_design_ui import Ui_MainWindow
from libs.ui.QPenWidth_ui import Ui_Dialog
from PySide6.QtWidgets import QMenuBar, QMainWindow, QVBoxLayout, QCheckBox, QLineEdit, QHBoxLayout, QWidget, QToolButton, QScrollArea, QDockWidget, QLabel, QDialog, QColorDialog, QMessageBox, QProgressDialog, QFileDialog, QListWidgetItem
from PySide6.QtCore import Qt, QSize, QByteArray, QTimer, QPoint, QProcess, QThread
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QCursor, QImageReader, QIcon
from libs.rpath import resource_path


class WindowMixin(object):

    def menu(self, title, actions=None):
        if platform.uname().system.startswith('Darw'):
            self._menu_bar = QMenuBar()
        else:
            self._menu_bar = self.menuBar()
        menu = self._menu_bar.addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        # self.addToolBar(Qt.LeftToolBarArea, toolbar)
        # self.addToolBar(TopToolBarArea, toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, appname, scriptPath, defaultFilename=None, defaultPrefdefClassFile=None):
        super(MainWindow, self).__init__()
        self.appname = appname
        self.script_path = scriptPath
        self.setWindowTitle(appname)

        self.mask_model_weights = None
        self.unet_model_weights = None

        self.__init_ui()
        self.__init_settings(defaultPrefdefClassFile)
        self.__init_widgets(defaultFilename)

    def __init_ui(self):
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        icons = [
            (self.ui.actionOpenDirDialog, "icons/folder-open.svg"),
            (self.ui.actionOpenNextImg, "icons/arrow-forward-circle-outline.svg"),
            (self.ui.actionOpenPrevImg, "icons/arrow-back-circle-outline.svg"),
            (self.ui.actionCreateMode, "icons/crop-sharp.svg"),
            (self.ui.actionCellDetectionDir, "icons/images.svg"),
            (self.ui.actionCellDetection, "icons/image.svg"),
            (self.ui.actionSave, "icons/save-sharp.svg"),
            (self.ui.actionReload_Img, "icons/reload-outline.svg"),
            (self.ui.actionSetEditMode, "icons/edit.png"),
            (self.ui.actionDeleteSelectedShape, "icons/cut.svg"), 
            (self.ui.actionGenOutput, "icons/bar-chart-sharp.svg"),
            (self.ui.actionResetImg, "icons/trash-bin.svg"),
            (self.ui.actionResetAll, "icons/resetall.png"),
            (self.ui.actionZoomIn, "icons/zoom-in.png"),
            (self.ui.actionZoomOut, "/icons/zoom-out.png"),
            (self.ui.actionOriginalSize, "icons/undo.png"),
            (self.ui.actionFitWidth, "icons/fit-width.png"),
            (self.ui.actionOpenWeightsMask, "icons/file.png"),
            (self.ui.actionContourmode, "icons/scan.svg")
        ]
        for elem, path in icons:
            icon = QIcon(resource_path(path))
            elem.setIcon(icon)

        # print(resource_path("icons\\folder-open.svg"))
        # icon = QIcon(resource_path("icons\\folder-open.svg"))
        # self.ui.actionOpenDirDialog.setIcon(icon)

        # connect actions to functions
        # open_dir_dialog
        self.ui.actionOpenDirDialog.triggered.connect(self.openDirDialog)
        self.fileListWidget = self.ui.listWidget
        # open mask rcnn weights
        self.ui.actionOpenWeightsMask.triggered.connect(self.openMaskWeights)
        # open mask unet weights
        self.ui.actionOpenWeightsUnet.triggered.connect(self.openUnetWeights)
        # open_prev_img
        self.ui.actionOpenPrevImg.triggered.connect(self.openPrevImg)
        # open_next_img
        self.ui.actionOpenNextImg.triggered.connect(self.openNextImg)
        # create_mode
        self.ui.actionCreateMode.triggered.connect(self.setCreateMode)
        self.createMode = self.ui.actionCreateMode
        # cell_detection_dir
        self.ui.actionCellDetectionDir.triggered.connect(self.cellDetectionDir)
        # cell_detection
        self.ui.actionCellDetection.triggered.connect(self.cellDetection)
        # save
        self.ui.actionSave.triggered.connect(self.saveFile)
        self.save = self.ui.actionSave
        # reload_img
        self.ui.actionReload_Img.triggered.connect(self.reloadImg)
        # set_edit_mode
        self.ui.actionSetEditMode.triggered.connect(self.setEditMode)
        self.editMode = self.ui.actionSetEditMode
        # delete_selected_shape
        self.ui.actionDeleteSelectedShape.triggered.connect(self.deleteSelectedShape)
        self.delete = self.ui.actionDeleteSelectedShape
        # gen_output
        self.ui.actionGenOutput.triggered.connect(self.genOutput)
        # reset_img
        self.ui.actionResetImg.triggered.connect(self.resetImg)
        # reset_all
        self.ui.actionResetAll.triggered.connect(self.resetAll)
        # Konturmodus
        self.ui.actionContourmode.triggered.connect(self.toggleContourOverlay)
        self.contourOverlay = self.ui.actionContourmode
        # UNet verwenden
        # self.ui.actionUNet_verwenden.triggered.connect(self.toggleUnet)
        self.ui.actionNN_Verzeichnis_2.clicked.connect(self.changeModelPathDialog)
        # Zoom in
        self.ui.actionZoomIn.triggered.connect(partial(self.addZoom, 10))
        self.zoomIn = self.ui.actionZoomIn
        # Zoom out
        self.ui.actionZoomOut.triggered.connect(partial(self.addZoom, -10))
        self.zoomOut = self.ui.actionZoomOut
        # Original Size
        self.ui.actionOriginalSize.triggered.connect(partial(self.setZoom, 100))
        self.zoomOrg = self.ui.actionOriginalSize
        # Fit Window
        self.ui.actionFitWindow.triggered.connect(self.setFitWindow)
        self.fitWindow = self.ui.actionFitWindow
        # Fit Width
        self.ui.actionFitWidth.triggered.connect(self.setFitWidth)
        self.fitWidth = self.ui.actionFitWidth
        # Change color for manual marking
        self.ui.actionChangePenColor.clicked.connect(self.changePenColor)
        # Change pen width for manual marking
        self.ui.actionChangePenWidth.clicked.connect(self.changePenWidth)

    def __init_settings(self, defaultPrefdefClassFile):
        # Load setting in the main thread
        self.settings = Settings()
        if self.settings.load():
            self.mask_model_weights = self.settings.get('mask_model_dir', None)
            self.unet_model_weights = self.settings.get('unet_dir', None)
        else:
            self.changeModelPathDialog()
        if self.mask_model_weights is None or self.unet_model_weights is None:
            self.changeModelPathDialog()
        self.ui.nn_path_label.setText('{0}'.format(self.mask_model_weights.rsplit('/', 1)[0]))
        # Save as Pascal voc xml
        self.defaultSaveDir = None
        self.usingPascalVocFormat = True
        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False
        self._noSelectionSlot = False
        self.autoSaving = True
        self.singleClassMode = True
        self.lastLabel = None

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)

    def __init_widgets(self, defaultFilename):
        settings = self.settings
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)
        self.itemsToShapes = {}
        self.shapesToItems = {}
        self.prevLabelText = ''
        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)
        self.useDefaultLabelCheckbox = QCheckBox(u'Use default label')
        self.useDefaultLabelCheckbox.setChecked(False)
        self.defaultLabelTextLine = QLineEdit()
        useDefaultLabelQHBoxLayout = QHBoxLayout()
        useDefaultLabelQHBoxLayout.addWidget(self.useDefaultLabelCheckbox)
        useDefaultLabelQHBoxLayout.addWidget(self.defaultLabelTextLine)
        useDefaultLabelContainer = QWidget()
        useDefaultLabelContainer.setLayout(useDefaultLabelQHBoxLayout)
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        listLayout.addWidget(useDefaultLabelContainer)
        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)
        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        # self.scrollBars = {
        #     Qt.Vertical: scroll.verticalScrollBar(),
        #     Qt.Horizontal: scroll.horizontalScrollBar()
        # }
        self.scrollBars = [scroll.verticalScrollBar(), scroll.horizontalScrollBar()]
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)
        self.canvas.saveFileSignal.connect(self.saveFile)
        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)
        # TODO: change for mdetectiongPolygon.connect(self.toggleDrawingSensitive)
        self.setCentralWidget(scroll)
        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable

        self.detector = ADPKDDetector(self.mask_model_weights)
        self.detector_thread = QThread()
        self.detector.moveToThread(self.detector_thread)
        self.detector_thread.start()
        self.unet_seg = ADPKDSegmenter(self.unet_model_weights)
        self.segmenter_thread = QThread()
        self.unet_seg.moveToThread(self.segmenter_thread)
        self.segmenter_thread.start()
        
        # Actions
        action = partial(newAction, self)
        close = action('&Schließen', self.closeFile, 'Ctrl+W', 'icons/close.png', u'Aktuelle Datei schließen')
        self.zoomActions = (self.zoomWidget, self.zoomIn, self.zoomOut, self.zoomOrg, self.fitWindow, self.fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }
        self.onLoadActive = (close, self.createMode, self.editMode)

        self.image = QImage()
        # self.filePath = ustr(defaultFilename)
        self.filePath = defaultFilename
        self.recentFiles = []
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        self.resize(QSize(1200, 900))
        self.move(QPoint(0, 0))
        self.restoreState(QByteArray())
        Shape.line_color = self.lineColor = DEFAULT_LINE_COLOR
        Shape.fill_color = self.fillColor = DEFAULT_FILL_COLOR
        self.canvas.setDrawingColor(self.lineColor)

        self.pixel_scale = settings.get('pixel_scaling', 0)
        self.ui.scalingInput.setText(u'%f' % self.pixel_scale)
        self.unet_usage = settings.get('unet_usage', True)
        # self.lastOpenDir = ustr(settings.get('last_open_dir', None))
        self.lastOpenDir = settings.get('last_open_dir', None)

        # def xbool(x):
        #     if isinstance(x, QVariant):
        #         return x.toBool()
        #     return bool(x)

        # if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
        #     pass

        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        self.zoomWidget.valueChanged.connect(self.paintCanvas)
        self.populateModeActions()
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)
        if self.filePath and os.path.isdir(self.filePath):
            pass

    # change Penwidth
    def changePenWidth(self):

        """
            Change the thickness of the drawing pen with with the measure from dialog file.

            Attributes
            ----------
            QDialog_PenwWidth : QtWidgets.QDialog()
                Dialog
            rsp : Boolean
                Answer of the Dialog
            pen_width : int
                Width of pen.

        """

        pen_width = self.canvas.getPenWidth()
        QDialog_PenWidth = QDialog()
        self.dialog = Ui_Dialog()
        self.dialog.setupUi(QDialog_PenWidth)
        self.dialog.horizontalSlider.setValue(int(pen_width))
        self.dialog.horizontalSlider.setTickPosition(pen_width)
        self.drawDialogLine(pen_width)
        self.dialog.horizontalSlider.valueChanged.connect(self.horizontalSliderChange)
        QDialog_PenWidth.show()
        rsp = QDialog_PenWidth.exec_()

        if rsp == QDialog.Accepted:
            self.canvas.setPenWidth(self.dialog.horizontalSlider.value())
        else:
            print('Cancel Button pressed')

    def horizontalSliderChange(self, e):
        self.drawDialogLine(e)

    def drawDialogLine(self, w):

        """
        This method updates the content of the dialog box. This means the thicknes of the drawn line and the
        text is updated on the value.

        Parameter
        ---------
        e : int
            Value from the slider,

        Attributes
        ----------
        dialogPixmap : QPixmap
            Drawing board
        dialogPainter : QPainter
            Painter for the drawing board.
        dialogPen : QPen
            Pen
        """
        self.dialog.label_2.setText("Pen width: %s" % w)
        dialogPixmap = QPixmap(461, 131)
        dialogPixmap.fill(Qt.white)
        self.dialog.label.setPixmap(dialogPixmap)
        dialogPainter = QPainter(self.dialog.label.pixmap())
        dialogPen = dialogPainter.pen()
        dialogPen.setWidth(w)
        dialogPen.setColor(self.canvas.getPenColor())
        dialogPainter.setPen(dialogPen)
        dialogPainter.drawLine(80, 65, 400, 65)
        dialogPainter.end()

    def changePenColor(self):
        """
            This method changes the color of the drawing pen with the selected color from the QColorDialog.

            Attribute
            ---------
            col : QtGui.QColor
                Selected color from the dialog.

        """
        col = QColorDialog.getColor()

        if col.isValid():
            self.canvas.setPenColor(col.name())

    def noShapes(self):
        return not self.itemsToShapes

    def populateModeActions(self):
        menu = (self.delete, self.contourOverlay)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)

    def setDirty(self):
        self.dirty = True
        self.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.save.setEnabled(False)

    def toggleActions(self, value=True):
        for z in self.zoomActions:
            z.setEnabled(value)
        for action in self.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.contourOverlay.setChecked(self.canvas.showContourOverlay)
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()

    # def currentItem(self):
    #     # TODO what items?
    #     if items:
    #         return items[0]
    #     return None

    def createShape(self):
        self.canvas.setEditing(False)

    def resetOverlays(self):
        self.contourOverlay.setChecked(self.canvas.showContourOverlay)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.editMode.setEnabled(not drawing)
        self.delete.setEnabled(not drawing)
        if not drawing:  # and self.beginner():
            # Cancel creation.
            self.statusBar().showMessage('Drawing stopped')
            self.statusBar().show()
            self.canvas.setEditing(True)
            self.editMode.setEnabled(False)
            self.delete.setEnabled(False)
            self.createMode.setEnabled(True)
            self.canvas.restoreCursor()

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.createMode.setEnabled(edit)

    def setCreateMode(self):
        if self.filePath is None:
            return
        self.toggleDrawMode(False)
        self.delete.setEnabled(False)
        self.editMode.setEnabled(True)

    def setEditMode(self):
        if self.filePath is None:
            return
        self.toggleDrawMode(True)
        self.delete.setEnabled(True)
        self.editMode.setEnabled(False)

    def toggleContourOverlay(self, show=False):
        # print('clicked contour toggle')
        if show:
            self.calcContours()
        self.canvas.showContourOverlay = show
        self.canvas.deactivateMarkingMode()
        self.canvas.update()

    # def toggleUnet(self, show=True):
    #     self.unet_usage = show

    def fileitemDoubleClicked(self, item=None):
        # currIndex = self.mImgList.index(ustr(item.text()))
        currIndex = self.mImgList.index(item.text())
        if currIndex < len(self.mImgList):
            filename = self.mImgList[currIndex]
            if filename:
                self.loadFile(filename)

    def btnstate(self, item=None):
        if not self.canvas.editing():
            return
        try:
            shape = self.itemsToShapes[item]
        except Exception:
            pass
        try:
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
        except Exception as e:
            print(e)
            pass

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                try:
                    self.shapesToItems[shape].setSelected(True)
                    # print(shape)
                except KeyError:
                    print('Shape key {0} is unknown'.format(shape))
                    logging.error('Shape key {0} is unknown'.format(shape))
                    self.shapesToItems[self.canvas.shapes[0]].setSelected(True)
        self.delete.setEnabled(selected)

    def addLabel(self, shape):
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item

    def remLabel(self, shape):
        if shape is None:
            return
        item = self.shapesToItems[shape]
        del self.shapesToItems[shape]
        del self.itemsToShapes[item]

    def loadLabels(self, shapes):
        s = []
        for label, points, line_color, fill_color, contour_points, confidence, contourEdited in shapes:
            shape = Shape(label=label)
            for x, y in points:
                shape.addPoint(QPoint(x, y))
            if contour_points:
                for x, y in contour_points:
                    shape.addContourPoint((x, y))
            shape.confidence = confidence
            shape.contourEdited = contourEdited
            shape.close()
            s.append(shape)
            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)
            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)
            self.addLabel(shape)
        self.canvas.loadShapes(s)

    def saveLabels(self, annotationFilePath):
        # annotationFilePath = ustr(annotationFilePath)
        if self.labelFile is None:
            self.labelFile = LabelFile()
            self.labelFile.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                        contour_points=s.contour_points,
                        confidence=s.confidence,
                        contourEdited=s.contourEdited)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        try:
            if self.usingPascalVocFormat is True:
                logging.info('Img: ' + self.filePath + ' -> Its xml: ' + annotationFilePath)
                self.labelFile.savePascalVocFormat(annotationFilePath, shapes, self.filePath, self.imageData, self.lineColor.getRgb(), self.fillColor.getRgb())
            else:
                self.labelFile.save(annotationFilePath, shapes, self.filePath, self.imageData, self.lineColor.getRgb(), self.fillColor.getRgb())
            return True
        except LabelFileError as e:
            self.errorMessage(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def labelSelectionChanged(self):
        item = self.currentItem()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapes[item])
            # shape = self.itemsToShapes[item]

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    def newShape(self):
        text = 'cell'
        if text is not None:
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color)
            self.addLabel(shape)
            self.editMode.setEnabled(True)
            self.delete.setEnabled(False)
            self.setDirty()
        else:
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        # print(f'Scroll Request emitted with {delta}, {orientation}')
        units = - delta / (8 * 10)
        bar = self.scrollBars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def setZoom(self, value):
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(int(value))

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # print(f'Zoom Request emitted with {delta}')
        # h_bar = self.scrollBars[Qt.Horizontal]
        # v_bar = self.scrollBars[Qt.Vertical]
        h_bar = self.scrollBars[1]
        v_bar = self.scrollBars[0]
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        cursor = QCursor()
        pos = cursor.pos()
        # relative_pos = QWidget.mapFromGlobal(self, pos)
        # cursor_x = relative_pos.x()
        # cursor_y = relative_pos.y()
        cursor_x = pos.x()
        cursor_y = pos.y()
        w = self.scrollArea.width()
        h = self.scrollArea.height()
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)
        units = delta / (8 * 5)
        scale = 2
        self.addZoom(scale * units)
        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max
        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max
        h_bar.setValue(int(new_h_bar_value))
        v_bar.setValue(int(new_v_bar_value))

    def setFitWindow(self, value=True):
        if value:
            self.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None, overlays=None):
        self.resetState()
        self.canvas.setEnabled(False)
        # if filePath is None:
        #     filePath = self.settings.get(SETTING_FILENAME)
        filePath = str(filePath)
        # unicodeFilePath = ustr(filePath)
        unicodeFilePath = filePath
        if unicodeFilePath and self.fileListWidget.count() > 0:
            # file = filePath.split('/')[-1]
            index = self.mImgList.index(unicodeFilePath)
            fileWidgetItem = self.fileListWidget.item(index)
            fileWidgetItem.setSelected(True)
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            img = cv2.cvtColor(cv2.imread(unicodeFilePath, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
            # img = read_img(unicodeFilePath, None)
            height, width, channel = img.shape
            bytesPerLine = 3 * width
            image = QImage(img.data, width, height, bytesPerLine, QImage.Format_RGB888)
            self.labelFile = None
            if image.isNull():
                self.errorMessage(u'Error opening the image', u"<p>Invalid format: <i>%s</i>" % unicodeFilePath)
                self.status("Error opening image: %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.filePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))
            if self.labelFile:
                self.loadLabels(self.labelFile.shapes)
            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.toggleActions(True)
            if self.usingPascalVocFormat is True:
                if self.defaultSaveDir is not None:
                    basename = os.path.basename(os.path.splitext(self.filePath)[0]) + XML_EXT
                    xmlPath = os.path.join(self.defaultSaveDir, basename)
                    self.loadPascalXMLByFilename(xmlPath)
                else:
                    xmlPath = os.path.splitext(filePath)[0] + XML_EXT
                    if os.path.isfile(xmlPath):
                        self.loadPascalXMLByFilename(xmlPath)
            self.setWindowTitle(self.appname + ' ' + filePath)
            self.canvas.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            return True
        return False

    # TODO: seee if this is usefull
    # def resizeEvent(self, event):
    #     if self.canvas and not self.image.isNull()\
    #        and self.zoomMode != self.MANUAL_ZOOM:
    #         self.adjustScale()
    #     super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def saveSettings(self):
        # self.settings.data['pixel_scaling'] = self.pixel_scale
        self.settings.data['pixel_scaling'] = float(self.ui.scalingInput.text())
        # self.settings.data['unet_usage'] = self.unet_usage
        self.settings.data['mask_model_dir'] = self.mask_model_weights
        self.settings.data['unet_dir'] = self.unet_model_weights
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            self.settings.data['last_open_dir'] = self.lastOpenDir
        else:
            self.settings.data['last_open_dir'] = ""
        self.settings.save()

    def closeEvent(self, event):
        if self.dirty:
            self.saveFile()
        self.saveSettings()

    def reloadImg(self):
        if not self.mayContinue():
            return
        logging.info('Reload image')
        self.canvas.pixmap = None
        self.loadFile(self.filePath)

    def resetImg(self):
        if self.filePath is not None:
            anno_file = self.filePath.split('.')[0] + '.xml'
            if not os.path.exists(anno_file):
                self.noAnnotationFileDialog()
                return
        if not self.deleteAnnotationsDialog():
            return
        os.remove(anno_file)
        logging.info('Reset image')
        self.reloadImg()

    def cellDetection(self):
        if not self.mayContinue():
            return
        if self.filePath is None:
            return
        logging.info(self.filePath)
        currentPath = self.filePath
        localPath = self.filePath.split(os.path.basename(currentPath))[0]
        imgFileName = os.path.basename(currentPath)
        # currentImg = io.imread(currentPath)
        currentImg = cv2.cvtColor(cv2.imread(currentPath, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        if self.detector is not None:
            # print(type(currentImg), currentImg.shape)
            boxes = self.detector.predict(currentImg, img_size=currentImg.shape[:2])
            height, width, depth = currentImg.shape
            filename = currentPath.split('.')[0] + '.xml'
            writer = PascalVocWriter('{0}'.format(localPath), imgFileName, [height, width, depth], localImgPath=currentPath)
            writer.verified = False
            # print('Writing data to disk')
            for box in boxes:
                xmin = box.xmin
                xmax = box.xmax
                ymin = box.ymin
                ymax = box.ymax
                # print(xmin, ymin, xmax, ymax)
                contour = box.contour
                # print(contour)
                confidence = box.confidence
                writer.addBndBox(xmin, ymin, xmax, ymax, 'cell', contour, confidence, False)
        writer.save(targetFile=filename)
        self.loadRecent(currentPath, True)

    def cellDetectionDir(self):
        if self.filePath is None:
            return
        progress = QProgressDialog('Detection cells {0}/{1}'.format(0, len(self.mImgList)), None, 0, 0, self)
        progress.setWindowTitle('Please wait')
        progress.setWindowModality(Qt.WindowModal)
        progress.setRange(0, len(self.mImgList))
        progress.setValue(0)
        progress.forceShow()
        for p in self.mImgList:
            progress.setLabelText('Detecting cells {0}/{1}'.format(progress.value() + 1, len(self.mImgList)))
            progress.forceShow()
            self.filePath = p
            self.cellDetection()
            progress.setValue(int(progress.value() + 1))
        progress.close()
        progress = QMessageBox.information(self, u'Information', 'Cell detection done')

    def calcContours(self):
        rendered = False
        if not self.canvas.shapes:
            return
        else:
            # fullImg = io.imread(self.filePath)
            fullImg = cv2.cvtColor(cv2.imread(self.filePath, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
            if fullImg is not None:
                for i, s in enumerate(self.canvas.shapes):
                    if self.canvas.shapes[i].contour_points:
                        continue
                    else:
                        xmin, ymin = int(s.points[0].x()), int(s.points[0].y())
                        xmax, ymax = int(s.points[2].x()), int(s.points[2].y())
                        img = fullImg[ymin:ymax + 1, xmin:xmax + 1, :]
                        rendered = True
                        # img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                        try:
                            if img.shape[0] <= 1 or img.shape[1] <= 1:
                                raise ValueError('bounding box is a line not a box')
                        except ValueError as e:
                            logging.error('Not all contours could be calculated:{}{}{}{}{}{}'.format(e, img, xmin, xmax, ymin, ymax))
                            self.statusBar().showMessage('Not all contours could be calculated:{}{}{}{}{}{}'.format(e, img, xmin, xmax, ymin, ymax))
                            self.statusBar().show()
                            continue
                        logging.info('Calling Unet')
                        if self.unet_seg is not None:
                            points = self.unet_seg.predict(img, img.shape[:2])
                            if len(points) < 5:
                                self.canvas.shapes[i].contour_points = list()
                            else:
                                self.canvas.shapes[i].contour_points = points.copy()
            else:
                logging.error('No image loaded: {0}'.format(self.filePath))
            if rendered:
                self.saveFile()

    def genOutput(self):   # TODO move to libs
        if self.dirname is None:
            return
        number_anno_files = len(glob.glob(self.dirname + '/' + '*.xml'))
        # currentImg = io.imread(self.filePath)
        currentImg = cv2.cvtColor(cv2.imread(self.filePath, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        width, height = currentImg.shape[0], currentImg.shape[1]
        del currentImg
        dialog = scaleDialog(parent=self, width=width, height=height, scaling=self.pixel_scale)
        dialog.exec()
        self.pixel_scale = dialog.pixel_scale
        self.ui.scalingInput.setText(u'%f' % self.pixel_scale)
        excel_filename = dialog.filename
        dialog.close()
        if dialog.gen:
            tableGenerator = cellTableGenerator(self.dirname + '/' + excel_filename + '.xlsx')
            progress = QProgressDialog('Calculating {0}/{1}'.format(0, number_anno_files), None, 0, 0, self)
            progress.setWindowTitle('Please wait')
            progress.setWindowModality(Qt.WindowModal)
            progress.setRange(0, number_anno_files)
            progress.setValue(0)
            progress.forceShow()
            for p in self.mImgList:
                # marked_img_list = list()
                anno_file = p.split('.')[0] + '.xml'
                if not os.path.exists(anno_file):
                    continue
                else:
                    progress.setLabelText('Generating results {0}/{1}'.format(progress.value() + 1, number_anno_files))
                    progress.forceShow()
                    self.filePath = p
                    self.loadFile(self.filePath)
                    draw_file = Image.open(self.filePath)
                    draw = ImageDraw.Draw(draw_file)
                    font = ImageFont.load_default()
                    image_filename = self.filePath.split('/')[-1]
                    tableGenerator.add_cellcount(image_filename, len(self.canvas.shapes))
                    for i, s in enumerate(self.canvas.shapes):
                        xmin, xmax, ymin, ymax = s.points[0].x(), s.points[2].x(), s.points[0].y(), s.points[2].y()
                        if not s.contour_points:
                            continue
                        else:
                            if len(s.contour_points) < 2:
                                continue
                            polygon_points = [(int(x + xmin), int(y + ymin)) for y, x in s.contour_points]
                            polygon = Polygon([(int(y), int(x)) for y, x in s.contour_points])
                            perimeter = polygon.length * self.pixel_scale  # polygon.length is defined as perimeter of polygon shape
                            r = perimeter / (2 * np.pi)
                            V = (4 / 3) * np.pi * (r**3)
                            tableGenerator.add_cell(i + 1, image_filename, polygon.area * (self.pixel_scale ** 2), perimeter, r, V)
                            draw.text((int(xmax - ((xmax - xmin) // 2)), int(ymax - ((ymax - ymin) // 2))), "{:.3f}".format(polygon.area * (self.pixel_scale**2)), fill=(0, 0, 0, 255), font=font)
                            draw.text((int(xmin), int(ymin)), "{}".format(i + 1), fill=(0, 0, 0, 255), font=font)
                            draw.polygon(polygon_points, outline=(255, 255, 0, 255))
                    draw.text((10, 10), str(len(self.canvas.shapes)), fill=(0, 0, 0, 255), font=font)
                    draw_file.save(self.filePath.split('.')[0] + '_done' + '.jpg')
                    progress.setValue(int(progress.value() + 1))
            progress.close()
            tableGenerator.close()
            # info = QMessageBox.information(self, u'Information', 'Result stored in {0}.xlsx'.format(excel_filename))
        del dialog

    def loadRecent(self, filename, cellDetection=False):
        if not cellDetection:
            if self.dirty:
                self.saveFile()
        self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.jpeg', '.jpg', '.png', '.bmp']
        images = []
        for root, _, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    # path = ustr(os.path.abspath(relativePath))
                    path = os.path.abspath(relativePath)
                    images.append(path)
        images.sort(key=lambda x: x.lower())
        return images

    def openDirDialog(self, _value=False, dirpath=None):
        if self.dirty:
            self.saveFile()
        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'
        # targetDirPath = ustr(QFileDialog.getExistingDirectory(self, '%s - Open path' % self.appname, defaultOpenDirPath, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        targetDirPath = QFileDialog.getExistingDirectory(self, '%s - Open path' % self.appname, defaultOpenDirPath, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        self.importDirImages(targetDirPath)

    def changeModelPathDialog(self):
        self.noModelsFoundInformationDialog(msg='No model path configured')
        # modelPath = ustr(QFileDialog.getExistingDirectory(self, '%s - Open path' % self.appname, self.settings.home, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        modelPath = QFileDialog.getExistingDirectory(self, '%s - Open path' % self.appname, self.settings.home, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if os.path.exists(modelPath):
            mask_model_weights = modelPath + '/MaskRCNN_30_epochs.ckpt'
            unet_model_weights = modelPath + '/ADPKDUnet_10_epochs_2.ckpt'
            if os.path.exists(mask_model_weights):
                self.mask_model_weights = mask_model_weights
                self.unet_model_weights = unet_model_weights
            else:
                self.noModelsFoundInformationDialog(msg='No models found, tool closes')
                sys.exit(0)

    def importDirImages(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return
        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None
        self.fileListWidget.clear()
        self.mImgList = self.scanAllImages(dirpath)
        self.openNextImg()
        for imgPath in self.mImgList:
            file = imgPath.split('/')[-1]
            item = QListWidgetItem(file)
            self.fileListWidget.addItem(item)

    def openMaskWeights(self):
        print('Opening weights')
        return None
        # self.model_weights = QFileDialog.getOpenFileName(self, 'Choose MMDetection weights', os.getcwd(), '(*.pth*)')[0]
        # del self.detector
        # # self.detector = MaskRCNNDetector(self.mask_model_weights)
        # self.detector = mmdetectionDetector(self.model_weights)

    def openUnetWeights(self):
        print('Opening weights')
        return None
        # self.unet_model_weights = QFileDialog.getOpenFileName(self, 'Chosse U-Net weights', os.getcwd(), '(*.hdf5*)')[0]
        # del self.unet_seg
        # self.unet_seg = UNetSegmentation(self.unet_model_weights)

    def openPrevImg(self, _value=False):
        if self.autoSaving:
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
        if self.dirty:
            self.saveFile()
        if len(self.mImgList) <= 0:
            return
        if self.filePath is None:
            return
        currIndex = self.mImgList.index(self.filePath)
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            if filename:
                self.resetOverlays()
                self.loadFile(filename)
                if self.canvas.showContourOverlay:
                    self.calcContours()

    def openNextImg(self, _value=False):
        if self.autoSaving:
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
        if self.dirty:
            self.saveFile()
        if len(self.mImgList) <= 0:
            return
        filename = None
        if self.filePath is None:
            filename = self.mImgList[0]
        else:
            currIndex = self.mImgList.index(self.filePath)
            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]
        if filename:
            self.resetOverlays()
            self.loadFile(filename)
            if self.canvas.showContourOverlay:
                self.calcContours()

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        # path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        path = os.path.dirname(self.filePath) if self.filePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Images (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Select image' % self.appname, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)

    def saveFile(self, _value=False):
        if self.filePath is None:
            return
        imgFileDir = os.path.dirname(self.filePath)
        imgFileName = os.path.basename(self.filePath)
        savedFileName = os.path.splitext(imgFileName)[0] + XML_EXT
        savedPath = os.path.join(imgFileDir, savedFileName)
        self._saveFile(savedPath)

    def _saveFile(self, annotationFilePath):
        if annotationFilePath and self.saveLabels(annotationFilePath):
            self.setClean()

    def closeFile(self, _value=False):
        if self.dirty:
            self.saveFile()
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(self.script_path))

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def noModelsFoundInformationDialog(self, msg):
        ok = QMessageBox.Ok
        msg = u'{}'.format(msg)
        return QMessageBox.information(self, u'No models found', msg, ok)

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'Discard unsaved changes ? '
        return yes == QMessageBox.warning(self, u'Unsaved changes', msg, yes | no)

    def noAnnotationFileDialog(self):
        ok = QMessageBox.Ok
        msg = u'No annotations found'
        return QMessageBox.information(self, u'No annotations found', msg, ok)

    def deleteAnnotationsDialog(self, fileName=None):
        if self.filePath is None:
            return
        yes, no = QMessageBox.Yes, QMessageBox.No
        if fileName is None:
            fileName = (self.filePath.split('/')[-1]).split('.')[0] + XML_EXT
        msg = u'Delete all saved annotations of {0} ?'.format(fileName)
        return yes == QMessageBox.warning(self, u'Löschen', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title, '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def deleteSelectedShape(self):
        if self.filePath is None:
            return
        self.toggleDrawMode(True)
        self.remLabel(self.canvas.deleteSelected())
        self.saveFile()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return
        tVocParseReader = PascalVocReader(xmlPath)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified
