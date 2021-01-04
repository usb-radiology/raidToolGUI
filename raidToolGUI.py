#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 10 12:27:50 2020

@author: francesco
"""

MOCK = False

import argparse
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
import shelve
import datetime
import re
import time
import os,os.path
import functools

import miniAgoraDialog, agoraDialog
from loadConfig import initFromConfig

from raidTool import RaidTool, RaidError

try:
    os.mkdir('shelves')
except:
    pass

MINIDIALOG_SIZE=32
RETRIEVEDCOLOR = (255,255,127)
RETRIEVED_SHELF_FILENAME = os.path.join('shelves', 'retrieved.db')
TRANSFERREDCOLOR = (127,255,127)
TRANSFERRED_SHELF_FILENAME = os.path.join('shelves', 'transferred.db')
IGNORECOLOR = (127, 127, 127)
IGNORED_SHELF_FILENAME = os.path.join('shelves', 'ignored.db')
ERRORCOLOR = (255,127,127)

HISTORY_TTL = datetime.timedelta(weeks=1)

# Generic worker wrapper object to call any function from a separate thread
class Worker(QtCore.QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and 
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @QtCore.pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        self.fn(*self.args, **self.kwargs)

def purgeOldShelf(shelf):
    now = datetime.datetime.now()
    for key, value in shelf.items():
        if value < now - HISTORY_TTL:
            del shelf[key]
            print(key, 'deleted from shelf')
        

class SmallWindow(QtWidgets.QDialog, miniAgoraDialog.Ui_MiniDialog):
    
    NormalIcon = 'icons/agoraIcon.png'
    AlertIcon = 'icons/agoraIcon_alert.png'
    RetrieveIcon = 'icons/agoraIcon_retrieve.png'
    UploadIcon = 'icons/agoraIcon_upload.png'
    
    def __init__(self, mainWindow):
        QtWidgets.QDialog.__init__(self)
        self.setupUi(self)
        self.mainWindow = mainWindow
        self.rightClick = False
        self.originPos = None

    @QtCore.pyqtSlot(str)
    def setIcon(self, icon):
        if not icon:
            icon = self.AlertIcon if self.mainWindow.isNewDataAvailable() else self.NormalIcon
        self.setStyleSheet("background-image: url(\"" + icon + "\");\n"
            "background-repeat: no-repeat;\n"
            "background-attachment: fixed;\n"
            "background-position: center; \n"
            "background-color: #101010;")

    def mouseMoveEvent(self, event):
        super(SmallWindow, self).mouseMoveEvent(event)
        if self.rightClick == True:
            self.move(event.globalPos() - self.originPos)

    def mousePressEvent(self, event):
        super(SmallWindow, self).mousePressEvent(event)
        if event.button() == QtCore.Qt.RightButton:
            self.rightClick = True
            self.setCursor(QtCore.Qt.SizeAllCursor)
            self.originPos = event.pos()
        elif event.button() == QtCore.Qt.LeftButton:
            self.restoreMainWindow()

    def mouseDoubleClickEvent(self, event):
        self.mainWindow.quit()

    def mouseReleaseEvent(self, event):
        super(SmallWindow, self).mouseReleaseEvent(event)
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.rightClick = False
        
    def restoreMainWindow(self):
        self.mainWindow.show()
        self.mainWindow.setWindowState(QtCore.Qt.WindowActive)
        self.hide()
        
# Decorator to disable controls before a function and reanable them afterwards
def enableDisableDecorator(func):
    functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        self.enableControls(False)
        func(self, *args, **kwargs)
        self.enableControls(True)
    return wrapper
        
class WindowClass(QtWidgets.QDialog, agoraDialog.Ui_AgoraDialog):
    
    UpdateRowColorSignal = QtCore.pyqtSignal(int, tuple)
    
    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        
        ## UI Initialization
        self.setupUi(self)
        #self.setFixedSize(self.size())
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowCloseButtonHint)
        self.minime = SmallWindow(self)
        self.refreshButton.clicked.connect(self.refreshRaid_clicked)
        self.retrieveButton.clicked.connect(self.retrieve_clicked)
        self.transferButton.clicked.connect(self.transfer_clicked)
        self.ignoreButton.clicked.connect(self.ignore_clicked)
        self.checkAllButton.clicked.connect(lambda: self.checkAll(True))
        self.uncheckAllButton.clicked.connect(lambda: self.checkAll(False))
        self.clearStatusButton.clicked.connect(self.clearStatus)
        self.UpdateRowColorSignal.connect(self.setRowColor)
        self.quitButton.clicked.connect(self.quit)
        self.dataTable.setColumnWidth(0, 70)
        self.dataTable.setColumnWidth(1, 70) 
        self.dataTable.setColumnWidth(2, int(self.width()/3))
        self.dataTable.setColumnWidth(3, int(self.width()/3))
        self.threadpool = QtCore.QThreadPool()
        
        ## Configuration
        self.reloadConfig()

        self.busy = False
        
        self.backgroundCheckTimer = None
        if self.globalConfig['BackgroundCheckInterval'] > 0:
            self.backgroundCheckTimer = QtCore.QTimer(self)
            self.backgroundCheckTimer.setInterval(self.globalConfig['BackgroundCheckInterval'] * 1000)
            self.backgroundCheckTimer.timeout.connect(self.backgroundRefresh)
            self.backgroundCheckTimer.start()
        
        self.retrievedShelf = shelve.open(RETRIEVED_SHELF_FILENAME)
        purgeOldShelf(self.retrievedShelf)
        self.transferredShelf = shelve.open(TRANSFERRED_SHELF_FILENAME)
        purgeOldShelf(self.transferredShelf)
        self.ignoredShelf = shelve.open(IGNORED_SHELF_FILENAME)
        purgeOldShelf(self.ignoredShelf)
        self.dataList = []
        
        self.skipTempDict = {}
    
    def reloadConfig(self):
        self.raid, self.targets, self.rules, self.globalConfig = initFromConfig()
        
    # finds the target names according to the rules
    def findTargetNames(self, protName, patName):
        target = []
        for ignoreRegex in self.globalConfig['GlobalIgnoreRegex']:
            protMatch = re.match('^' + ignoreRegex + '$', protName)
            if protMatch: return None
        
        for rule in self.rules:
            protMatch = False
            patMatch = False
            if 'ProtRegex' in rule:
                protMatch = re.match('^' + rule['ProtRegex'] + '$', protName)
            else: # if there is not protRegex, assume true
                protMatch = True
            if 'PatRegex' in rule:
                patMatch = re.match('^' + rule['PatRegex'] + '$', patName)
            else: # same as above
                patMatch = True
            if protMatch and patMatch: target.append(rule['Target'])
        return target
    
    def isMinified(self):
        return self.minime.isVisible()
       
    def isNewDataAvailable(self):
        newData = False
        for d in self.dataList:
            if (d[0]['FileID'] not in self.retrievedShelf and
               d[0]['FileID'] not in self.transferredShelf and
               d[0]['FileID'] not in self.ignoredShelf):
                newData = True
                break
        return newData
        
    @QtCore.pyqtSlot(bool)
    def enableControls(self, enable = True):
        self.refreshButton.setEnabled(enable)
        self.retrieveButton.setEnabled(enable)
        self.transferButton.setEnabled(enable)
        self.checkAllButton.setEnabled(enable)
        self.uncheckAllButton.setEnabled(enable)
        
    def clearStatus(self):
        ans = QtWidgets.QMessageBox.warning(self,
            'Clear status',
            'Warning! This operation will clear the retrieved/transferred status of the selected items!',
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Ok)
        
        if ans == QtWidgets.QMessageBox.Ok:
            for row in range(self.dataTable.rowCount()):
                fileID = self.dataList[row][0]['FileID']
                if self.isRowChecked(row):
                    try:
                        del self.retrievedShelf[fileID]
                    except:
                        pass
                    try:
                        del self.transferredShelf[fileID]
                    except:
                        pass
                    try:
                        del self.ignoredShelf[fileID]
                    except:
                        pass
                    self.setRowColor(row, None)
        
    def checkAll(self, status):
        for row in range(self.dataTable.rowCount()):
            self.dataTable.cellWidget(row, 0).setChecked(status)

    @QtCore.pyqtSlot(int, tuple)
    def setRowColor(self, row, color):        
        for c in range(1,5):
            try:
                if color:
                    self.dataTable.item(row, c).setBackground(QtGui.QColor(*color))
                else: # default background
                    self.dataTable.item(row, c).setBackground(QtGui.QBrush())
            except:
                pass
    
    def isRowChecked(self, row):
        checkbox = self.dataTable.cellWidget(row,0)
        return checkbox.isChecked()
        
    def backgroundRefresh(self):
        if not self.isMinified(): return
        print("Background refresh")
        try:
            self.doRefreshRaid()
        except RaidError:
            print("Raid error. Retrying in 10 seconds")
            self.backgroundCheckTimer.setInterval(10 * 1000)
        else:
            self.backgroundCheckTimer.setInterval(self.globalConfig['BackgroundCheckInterval'] * 1000)        
    
    def refreshRaid_clicked(self, *args, **kwargs):
        try:
            self.doRefreshRaid()
        except RaidError:
            QtWidgets.QMessageBox.critical(self,
                'Error',
                'Error Retrieving RAID data',
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Ok)
        
    @enableDisableDecorator
    def doRefreshRaid(self, *args, **kwargs):
        self.reloadConfig()
        data = self.raid.loadList()
        self.dataTable.setRowCount(0)
        self.dataList = []
        for d in data:
            # filter the data
            nextRow = self.dataTable.rowCount()
            target = self.findTargetNames(d['Prot'], d['Pat'])
            if not target: continue
            self.dataTable.insertRow(nextRow)
            checkbox = QtWidgets.QCheckBox('')
            checkbox.setChecked(True)
            self.dataTable.setCellWidget(nextRow, 0, checkbox)
            self.dataTable.setItem(nextRow, 1, QtWidgets.QTableWidgetItem(str(d['MeasID'])))
            self.dataTable.setItem(nextRow, 2, QtWidgets.QTableWidgetItem(d['Prot']))
            self.dataTable.setItem(nextRow, 3, QtWidgets.QTableWidgetItem(d['Pat']))
            self.dataTable.setItem(nextRow, 4, QtWidgets.QTableWidgetItem(", ".join(target)))
            # store datastructure/target pairs
            self.dataList.append( (d, target) )
            skipTemp = all([self.targets[t].skipTemp() for t in target]) # skip temp directory if all the targets wish to skip temp
            self.skipTempDict[d['FileID']] = skipTemp

            if d['FileID'] in self.ignoredShelf:
                self.UpdateRowColorSignal.emit(nextRow, IGNORECOLOR)
            elif d['FileID'] in self.transferredShelf:
                #self.setRowColor(nextRow, TRANSFERREDCOLOR)
                self.UpdateRowColorSignal.emit(nextRow, TRANSFERREDCOLOR)
            elif d['FileID'] in self.retrievedShelf or skipTemp: # if skipTemp, make the file appear as retrieved. Not added to the shelf because it might change with a change in config
                #self.setRowColor(nextRow, RETRIEVEDCOLOR)
                self.UpdateRowColorSignal.emit(nextRow, RETRIEVEDCOLOR)
                

        if not self.busy: self.minime.setIcon(None) # set default busy/nonbusy icon if the app is not busy (in which case we want the busy icon)
    
    @enableDisableDecorator        
    def doRetrieve(self):
        self.minime.setIcon(SmallWindow.RetrieveIcon)
        self.busy = True
        for row in range(self.dataTable.rowCount()):
            fileID = self.dataList[row][0]['FileID']
            if fileID in self.retrievedShelf or fileID in self.ignoredShelf: continue
            if self.isRowChecked(row):            
                self.statusLabel.setText(f'Status: Retrieving {fileID} - Scanning might be affected!')
                QtWidgets.QApplication.processEvents()
                # do the retrieval if not skipTemp
                if self.skipTempDict[fileID]:
                    retrieveSuccess = True
                else:
                    retrieveSuccess = self.raid.retrieve(fileID)
                if retrieveSuccess:
                    #self.setRowColor(row, RETRIEVEDCOLOR)
                    self.UpdateRowColorSignal.emit(row, RETRIEVEDCOLOR) # thread safety
                    self.retrievedShelf[fileID] = self.dataList[row][0]['CreateTime']
                else:
                    #self.setRowColor(row, ERRORCOLOR)
                    self.UpdateRowColorSignal.emit(row, ERRORCOLOR) # thread safety
                self.statusLabel.setText(f'Status: Idle')
                
        self.minime.setIcon(None)
        self.busy = False
    
    def retrieve_clicked(self, *args, **kwargs):
        ans = QtWidgets.QMessageBox.question(self,
            'Start retrieval',
            'Start object retrieval? Scanning might be affected during this time!',
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Ok)
        
        if ans == QtWidgets.QMessageBox.Ok:
            self.threadpool.start(Worker(self.doRetrieve))
        
    @enableDisableDecorator            
    def doTransfer(self):
        self.minime.setIcon(SmallWindow.UploadIcon)
        self.busy = True
        for row in range(self.dataTable.rowCount()):
            fileID = self.dataList[row][0]['FileID']
            allTargetNames = self.dataList[row][1]
            if fileID in self.transferredShelf or fileID in self.ignoredShelf: continue
            if fileID not in self.retrievedShelf: continue
            if not self.isRowChecked(row): continue

            # row is checked, and file is to be transferred
            self.statusLabel.setText(f'Status: Transferring {fileID}')

            success = True

            for targetIndex, targetName in enumerate(allTargetNames):
                uploader = self.targets[targetName]
                # do the transfer
                deleteOriginal = (targetIndex == len(allTargetNames)-1) # delete cached file if the current target is the last one in the list
                success &= uploader.uploadData(self.raid, fileID, deleteOriginal = deleteOriginal, dataStructure = self.dataList[row][0])

            if success:
                self.UpdateRowColorSignal.emit(row, TRANSFERREDCOLOR) # thread safety
                self.transferredShelf[fileID] = self.dataList[row][0]['CreateTime']
            else:
                self.UpdateRowColorSignal.emit(row, ERRORCOLOR) # thread safety

            self.statusLabel.setText(f'Status: Idle')
        
        # don't leave any target open
        for target in self.targets.values():
            target.close()
            
        self.minime.setIcon(None)
        self.busy = False
    
    def transfer_clicked(self, *args, **kwargs):
        # move this to another thread?
        ans = QtWidgets.QMessageBox.question(self,
            'Start transfer',
            'Start transfer? Scanning is still possible.',
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Ok)
        
        if ans == QtWidgets.QMessageBox.Ok:
            self.threadpool.start(Worker(self.doTransfer))
           
    @enableDisableDecorator
    def ignore_clicked(self, *args, **kwargs):
        for row in range(self.dataTable.rowCount()):
            fileID = self.dataList[row][0]['FileID']
            if self.isRowChecked(row):
                self.UpdateRowColorSignal.emit(row, IGNORECOLOR) # thread safety
                self.ignoredShelf[fileID] = self.dataList[row][0]['CreateTime']
        if not self.busy: self.minime.setIcon(None) # set default busy/nonbusy icon if the app is not busy (in which case we want the busy icon)
           
    @QtCore.pyqtSlot()
    def quit(self):
        ans = QtWidgets.QMessageBox.question(self,
            'AgoraGUI',
            'Really quit?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        
        if ans != QtWidgets.QMessageBox.Yes: return
        
        if self.backgroundCheckTimer: self.backgroundCheckTimer.stop()
        
        self.retrievedShelf.close()
        self.transferredShelf.close()
        self.ignoredShelf.close()
        self.close()
        self.minime.close()
        #QtCore.QCoreApplication.quit()
        
    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.windowState() & QtCore.Qt.WindowMinimized:
                self.minify()
        
    def closeEvent(self, evt):
        evt.ignore()
        self.minify()
        
    def minify(self):
        self.minime.setWindowFlags(QtCore.Qt.FramelessWindowHint) # | QtCore.Qt.WindowStaysOnTopHint)
        self.minime.resize(MINIDIALOG_SIZE,MINIDIALOG_SIZE)
        self.minime.show()
        self.hide()
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    Window = WindowClass()
    parser = argparse.ArgumentParser(description="Idea GUI")
    parser.add_argument("-m", "--start-minified", action="store_true", help="start app minified")
    parser.add_argument("-p", "--position", help="starting position in the form x,y")
    args = parser.parse_args()
    
    if args.position is not None:
        x,y = args.position.split(',')
        if args.start_minified:
            Window.minime.move(int(x), int(y))
        else:
            Window.move(int(x), int(y))
    
    Window.show()
    
    if args.start_minified:
        Window.minify()
    app.exec_()