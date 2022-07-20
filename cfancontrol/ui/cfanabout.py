# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'cfanabout.ui'
#
# Created by: PyQt5 UI code generator 5.14.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_AboutDialog(object):
    def setupUi(self, AboutDialog):
        AboutDialog.setObjectName("AboutDialog")
        AboutDialog.resize(454, 228)
        AboutDialog.setModal(True)
        self.verticalLayout = QtWidgets.QVBoxLayout(AboutDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.lblAppIcon = QtWidgets.QLabel(AboutDialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lblAppIcon.sizePolicy().hasHeightForWidth())
        self.lblAppIcon.setSizePolicy(sizePolicy)
        self.lblAppIcon.setObjectName("lblAppIcon")
        self.horizontalLayout_2.addWidget(self.lblAppIcon)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.lblAbout = QtWidgets.QLabel(AboutDialog)
        self.lblAbout.setWordWrap(True)
        self.lblAbout.setOpenExternalLinks(True)
        self.lblAbout.setObjectName("lblAbout")
        self.verticalLayout_2.addWidget(self.lblAbout)
        self.horizontalLayout_2.addLayout(self.verticalLayout_2)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.btnClose = QtWidgets.QPushButton(AboutDialog)
        self.btnClose.setObjectName("btnClose")
        self.horizontalLayout.addWidget(self.btnClose)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(AboutDialog)
        QtCore.QMetaObject.connectSlotsByName(AboutDialog)

    def retranslateUi(self, AboutDialog):
        _translate = QtCore.QCoreApplication.translate
        AboutDialog.setWindowTitle(_translate("AboutDialog", "Dialog"))
        self.lblAppIcon.setText(_translate("AboutDialog", "<html><head/><body><p>&nbsp;&nbsp;&nbsp;<img src=\":/icons/commander_icon.png\"/>&nbsp;&nbsp;&nbsp;</p></body></html>"))
        self.lblAbout.setText(_translate("AboutDialog", "<html><head/><body><p>GUI for managing the Corsair Commander Pro under Linux. Using the QT framework and implemented in Pyrthon.</p><p>Source code and documentation: <a href=\"https://github.com/maclarsson/cfancontrol\">cfancontrol on github</a></p><p>Copyright (C) 2021-2022 maclarsson, licensed under the GPLv3</p></body></html>"))
        self.btnClose.setText(_translate("AboutDialog", "Close"))
from . import resources_rc
