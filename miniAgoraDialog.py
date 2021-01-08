# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'miniAgoraDialog.ui'
#
# Created by: PyQt5 UI code generator 5.14.2
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MiniDialog(object):
    def setupUi(self, MiniDialog):
        MiniDialog.setObjectName("MiniDialog")
        MiniDialog.resize(104, 32)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MiniDialog.sizePolicy().hasHeightForWidth())
        MiniDialog.setSizePolicy(sizePolicy)
        MiniDialog.setStyleSheet("background-image: url(\"icons/agoraIcon.png\");\n"
"background-repeat: no-repeat;\n"
"background-attachment: fixed;\n"
"background-position: center; \n"
"background-color: #101010;")

        self.retranslateUi(MiniDialog)
        QtCore.QMetaObject.connectSlotsByName(MiniDialog)

    def retranslateUi(self, MiniDialog):
        _translate = QtCore.QCoreApplication.translate
        MiniDialog.setWindowTitle(_translate("MiniDialog", "MiniDialog"))
        MiniDialog.setToolTip(_translate("MiniDialog", "<html><head/><body><p><span style=\" font-weight:600;\">Click</span>: Open RAID Control</p><p><span style=\" font-weight:600;\">Right-Click</span>: Move widget</p></body></html>"))
