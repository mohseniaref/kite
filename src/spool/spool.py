#!/usr/bin/python
from PySide import QtGui, QtCore
from .tab_scene import QKiteScene
from .tab_quadtree import QKiteQuadtree  # noqa
from .tab_covariance import QKiteCovariance  # noqa
from .utils_qt import loadUi
from ..meta import Subject
from ..scene import Scene

from os import path
import os
import sys
import time  # noqa
import logging
import pyqtgraph as pg


def validateFilename(filename):
    filedir = path.dirname(filename)
    if filename == '' or filedir == '':
        return False
    if path.isdir(filename) or not os.access(filedir, os.W_OK):
        QtGui.QMessageBox.critical(None, 'Path Error',
                                   'Could not access file <b>%s</b>'
                                   % filename)
        return False
    return True


class Spool(QtGui.QApplication):
    def __init__(self, scene=None, filename=None):
        QtGui.QApplication.__init__(self, ['KiteSpool'])
        # self.setStyle('plastique')
        splash_img = QtGui.QPixmap(
            path.join(path.dirname(path.realpath(__file__)),
                      'ui/boxkite-sketch.jpg'))\
            .scaled(QtCore.QSize(400, 250), QtCore.Qt.KeepAspectRatio)
        splash = QtGui.QSplashScreen(splash_img,
                                     QtCore.Qt.WindowStaysOnTopHint)
        splash.show()
        self.processEvents()

        def updateSplashMessage(msg=''):
            splash.showMessage("Loading kite.%s ..." % msg.title(),
                               QtCore.Qt.AlignBottom)

        updateSplashMessage('Scene')

        self.spool_win = SpoolMainWindow()
        self.spool_win.loadingModule.subscribe(updateSplashMessage)

        self.spool_win.actionExit.triggered.connect(self.exit)
        self.aboutToQuit.connect(self.deleteLater)

        if scene is not None:
            self.addScene(scene)
        if filename is not None:
            self.importScene(filename)

        splash.finish(self.spool_win)
        self.spool_win.show()
        sys.exit(self.exec_())

    def addScene(self, scene):
        self.spool_win.addScene(scene)

    def importScene(self, filename):
        self.spool_win.scene_proxy.importFile(filename)

    def __del__(self):
        pass


class SpoolMainWindow(QtGui.QMainWindow):
    sigExportCovariance = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        QtGui.QMainWindow.__init__(self, *args, **kwargs)
        self.views = [QKiteScene, QKiteQuadtree, QKiteCovariance]
        self.loadUi()

        self.scene_thread = QtCore.QThread()
        self.scene_thread.scene_proxy = QSceneProxy()
        self.scene_thread.scene_proxy.moveToThread(self.scene_thread)
        self.scene_proxy.sigSceneModelChanged.connect(self.buildViews)
        self.scene_thread.start()

        self.sigExportCovariance.connect(self.scene_proxy.exportCovariance)

        self.ptree = QKiteParameterTree(showHeader=True)
        self.ptree.resize(100, 100)
        self.splitter.insertWidget(0, self.ptree)

        self.log_model = SceneLogModel(self)
        self.log = SceneLog(self)

        self.actionSave_config.triggered.connect(
            self.onSaveConfig)
        self.actionSave_scene.triggered.connect(
            self.onSaveData)
        self.actionLoad_config.triggered.connect(
            self.onLoadConfig)
        self.actionLoad_scene.triggered.connect(
            self.onOpenScene)

        self.actionImport_scene.triggered.connect(
            self.onImportScene)
        self.actionExport_quadtree.triggered.connect(
            self.onExportQuadtree)
        self.actionExport_covariance_weights.triggered.connect(
            self.onExportCovarianceWeight)

        self.actionAbout_Spool.triggered.connect(
            self.about.show)
        self.actionHelp.triggered.connect(
            lambda: QtGui.QDesktopServices.openUrl('http://pyrocko.org'))
        self.actionLog.triggered.connect(
            self.log.show)

        self.loadingModule = Subject()

    @property
    def scene_proxy(self):
        return self.scene_thread.scene_proxy

    @property
    def about(self):
        about = QtGui.QDialog()
        about_ui = path.join(path.dirname(path.realpath(__file__)),
                             'ui/about.ui')
        loadUi(about_ui, baseinstance=about)
        return about

    def loadUi(self):
        ui_file = path.join(path.dirname(path.realpath(__file__)),
                            'ui/spool.ui')
        loadUi(ui_file, baseinstance=self)
        return

    def addScene(self, scene):
        self.scene_proxy.setScene(scene)
        self.buildViews()

    def buildViews(self):
        if self.scene_proxy.scene is None:
            return
        for v in self.views:
            self.addView(v)

    def addView(self, view):
        view = view(self)
        self.loadingModule.notify(view.title)
        self.tabs.addTab(view, view.title)

        if hasattr(view, 'parameters'):
            for parameter in view.parameters:
                self.ptree.addParameters(parameter)

    def onSaveConfig(self):
        filename, _ = QtGui.QFileDialog.getSaveFileName(
            filter='YAML file *.yml (*.yml)', caption='Save scene YAML config')
        if not validateFilename(filename):
            return
        self.scene_proxy.scene.save_config(filename)

    def onSaveData(self):
        filename, _ = QtGui.QFileDialog.getSaveFileName(
            filter='YAML *.yml and NumPy container *.npz (*.yml *.npz)',
            caption='Save scene')
        if not validateFilename(filename):
            return
        self.scene_proxy.scene.save(filename)

    def onLoadConfig(self):
        filename, _ = QtGui.QFileDialog.getOpenFileName(
            filter='YAML file *.yml (*.yml)', caption='Load scene YAML config')
        if not validateFilename(filename):
            return
        self.scene_proxy.scene.load_config(filename)

    def onOpenScene(self):
        filename, _ = QtGui.QFileDialog.getOpenFileName(
            filter='YAML *.yml and NumPy container *.npz (*.yml *.npz)',
            caption='Load kite scene')
        if not validateFilename(filename):
            return
        self.scene_proxy.setScene(Scene.load(filename))

    def onImportScene(self):
        filename, _ = QtGui.QFileDialog.getOpenFileName(
            self,
            filter='GMT5SAR Scene *.grd (*.grd);;'
                   'ISCE Scene *unw* (*unw*);;Gamma Scene *.geo (*.geo);;'
                   'Matlab Container *.mat (*.mat);;Any File (*)',
            caption='Import scene to spool')
        if not validateFilename(filename):
            return
        self.scene_proxy.setScene(Scene.import_data(filename))

    def onExportQuadtree(self):
        filename, _ = QtGui.QFileDialog.getSaveFileName(
            filter='CSV File *.csv (*.csv)', caption='Export Quadtree CSV')
        if not validateFilename(filename):
            return
        self.scene_proxy.quadtree.export(filename)

    def onExportCovarianceWeight(self):
        filename, _ = QtGui.QFileDialog.getSaveFileName(
            filter='Text File *.txt (*.txt)',
            caption='Export Covariance Weights',)
        if not validateFilename(filename):
            return

        p = QtGui.QProgressDialog(
            'Caluclating full <span style="font-family: monospace">'
            'Covariance.weight_matrix</span>, this can take a few minutes...',
            '', 0, 0)
        p.setCancelButtonText(None)
        p.closeEvent = lambda e: e.ignore()
        p.setValue(0)
        p.show()

        self.sigExportCovariance.emit(filename)
        self.scene_proxy.sigOperationFinished.connect(p.reset)
        self.progress = p

    def exit(self):
        pass


class QSceneProxy(QtCore.QObject):
    ''' Proxy for :class:`kite.Scene` so we can change the scene
    '''
    sigSceneModelChanged = QtCore.Signal()

    sigSceneChanged = QtCore.Signal()
    sigConfigChanged = QtCore.Signal()

    sigFrameChanged = QtCore.Signal()
    sigQuadtreeChanged = QtCore.Signal()
    sigQuadtreeConfigChanged = QtCore.Signal()
    sigCovarianceChanged = QtCore.Signal()
    sigCovarianceConfigChanged = QtCore.Signal()

    sigOperationFinished = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.scene = None
        self.frame = None
        self.quadtree = None
        self.covariance = None

    def setScene(self, scene):
        self.disconnectSlots()

        self.scene = scene
        self.frame = scene.frame
        self.quadtree = scene.quadtree
        self.covariance = scene.covariance

        self.connectSlots()
        self.sigSceneModelChanged.emit()

    def disconnectSlots(self):
        if self.scene is None:
            return

        self.scene.evChanged.unsubscribe(
            self.sigSceneChanged.emit)
        self.scene.evConfigChanged.unsubscribe(
            self.sigConfigChanged.emit)

        self.scene.frame.evChanged.unsubscribe(
            self.sigFrameChanged.emit)

        self.quadtree.evChanged.unsubscribe(
            self.sigQuadtreeChanged.emit)
        self.quadtree.evConfigChanged.unsubscribe(
            self.sigQuadtreeConfigChanged.emit)

        self.covariance.evChanged.unsubscribe(
            self.sigCovarianceChanged.emit)
        self.covariance.evConfigChanged.unsubscribe(
            self.sigCovarianceConfigChanged.emit)

    def connectSlots(self):
        self.scene.evChanged.subscribe(
            self.sigSceneChanged.emit)
        self.scene.evConfigChanged.subscribe(
            self.sigConfigChanged.emit)

        self.scene.frame.evChanged.subscribe(
            self.sigFrameChanged.emit)

        self.quadtree.evChanged.subscribe(
            self.sigQuadtreeChanged.emit)
        self.quadtree.evConfigChanged.subscribe(
            self.sigQuadtreeConfigChanged.emit)

        self.covariance.evChanged.subscribe(
            self.sigCovarianceChanged.emit)
        self.covariance.evConfigChanged.subscribe(
            self.sigCovarianceConfigChanged.emit)

    @QtCore.Slot(str)
    def exportCovariance(self, filename):
        self.scene.covariance.export_weight_matrix(filename)
        self.sigOperationFinished.emit()

    @QtCore.Slot(str)
    def importFile(self, filename):
        self.setScene(Scene.import_data(filename))
        self.sigOperationFinished.emit()

    @QtCore.Slot(str)
    def loadFile(self, filename):
        self.setScene(Scene.load(filename))
        self.sigOperationFinished.emit()

    @QtCore.Slot(str)
    def loadConfig(self, filename):
        self.scene.load_config(filename)
        self.sigOperationFinished.emit()

    @QtCore.Slot(float)
    def setQuadtreeNanFraction(self, value):
        self.quadtree.nan_fraction = value

    @QtCore.Slot(float)
    def setQuadtreeEpsilon(self, value):
        self.quadtree.epsilon = value


class QKiteParameterTree(pg.parametertree.ParameterTree):
    pass


class SceneLogModel(QtCore.QAbstractTableModel, logging.Handler):
    log_records = []

    def __init__(self, spool, *args, **kwargs):
        QtCore.QAbstractTableModel.__init__(self, *args, **kwargs)
        logging.Handler.__init__(self)

        self.spool = spool
        getPixmap = spool.style().standardPixmap
        qstyle = QtGui.QStyle

        self.levels = {
            50: [getPixmap(qstyle.SP_MessageBoxCritical), 'Critical'],
            40: [getPixmap(qstyle.SP_MessageBoxCritical), 'Error'],
            30: [getPixmap(qstyle.SP_MessageBoxWarning), 'Warning'],
            20: [getPixmap(qstyle.SP_MessageBoxInformation), 'Info'],
            10: [getPixmap(qstyle.SP_FileIcon), 'Debug'],
        }

        for i in self.levels.itervalues():
            i[0] = i[0].scaledToHeight(20)

        self.spool.scene_proxy.sigSceneModelChanged.connect(
            lambda: self.attachScene(self.spool.scene_proxy.scene))

    def attachScene(self, scene):
        self.scene = scene
        self.scene._log.addHandler(self)

    def detachScene(self, scene):
        self.scene._log.removeHandler(self)
        self.scene = None

    def data(self, idx, role):
        rec = self.log_records[idx.row()]

        if role == QtCore.Qt.DisplayRole:
            if idx.column() == 0:
                return int(rec.levelno)
            elif idx.column() == 1:
                return '%s:%s' % (rec.levelname, rec.name)
            elif idx.column() == 2:
                return rec.getMessage()

        elif role == QtCore.Qt.ItemDataRole:
            return idx.data()

        elif role == QtCore.Qt.DecorationRole:
            if idx.column() != 0:
                return
            log_lvl = self.levels[int(idx.data())]
            return log_lvl[0]

        elif role == QtCore.Qt.ToolTipRole:
            if idx.column() == 0:
                return rec.levelname
            elif idx.column() == 1:
                return '%s.%s' % (rec.module, rec.funcName)
            elif idx.column() == 2:
                return 'Line %d' % rec.lineno

    def rowCount(self, idx):
        return len(self.log_records)

    def columnCount(self, idx):
        return 3

    def emit(self, record):
        self.log_records.append(record)
        self.beginInsertRows(QtCore.QModelIndex(),
                             0, 0)
        self.endInsertRows()
        self.spool.log.tableView.scrollToBottom()
        if record.levelno >= 30 and self.spool.log.autoBox.isChecked():
            self.spool.log.show()


class SceneLog(QtGui.QDialog):

    class LogFilter(QtGui.QSortFilterProxyModel):
        def __init__(self, *args, **kwargs):
            QtGui.QSortFilterProxyModel.__init__(self, *args, **kwargs)
            self.level = 0

        def setLevel(self, level):
            self.level = level
            self.setFilterRegExp('%s' % self.level)

    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)

        log_ui = path.join(path.dirname(path.realpath(__file__)),
                           'ui/logging.ui')
        loadUi(log_ui, baseinstance=self)

        self.closeButton.setIcon(self.style().standardPixmap(
                                 QtGui.QStyle.SP_DialogCloseButton))

        self.table_filter = self.LogFilter()
        self.table_filter.setFilterKeyColumn(0)
        self.table_filter.setDynamicSortFilter(True)
        self.table_filter.setSourceModel(parent.log_model)

        self.tableView.setModel(self.table_filter)

        self.tableView.setColumnWidth(0, 30)
        self.tableView.setColumnWidth(1, 200)

        self.filterBox.addItems(
            [l[1] for l in parent.log_model.levels.values()] + ['All'])
        self.filterBox.setCurrentIndex(0)

        def changeFilter():
            for k, v in parent.log_model.levels.iteritems():
                if v[1] == self.filterBox.currentText():
                    self.table_filter.setLevel(k)
                    return

            self.table_filter.setLevel(0)

        self.filterBox.currentIndexChanged.connect(changeFilter)


__all__ = ['Spool']

if __name__ == '__main__':
    from kite.scene import SceneSynTest
    if len(sys.argv) > 1:
        sc = Scene.load(sys.argv[1])
    else:
        sc = SceneSynTest.createGauss()

    Spool(scene=sc)
