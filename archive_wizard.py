#!/usr/bin/env python

from PyQt4 import QtCore, QtGui
import sys

# ArchiveWizard
# copied from PySide/dialogs/ComplexWizard example
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)

        #store history for supporting back button
        self.history = []

        self.cancelButton = QtGui.QPushButton(self.tr("Cancel"))
        self.backButton = QtGui.QPushButton(self.tr("< &Back"))
        self.nextButton = QtGui.QPushButton(self.tr("Next >"))
        self.finishButton = QtGui.QPushButton(self.tr("&Finish"))

        self.connect(self.cancelButton, QtCore.SIGNAL("clicked()"), self.reject)
        self.connect(self.backButton, QtCore.SIGNAL("clicked()"), self.backButtonClicked)
        self.connect(self.nextButton, QtCore.SIGNAL("clicked()"), self.nextButtonClicked)
        self.connect(self.finishButton, QtCore.SIGNAL("clicked()"), self.accept)

        buttonLayout = QtGui.QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(self.cancelButton)
        buttonLayout.addWidget(self.backButton)
        buttonLayout.addWidget(self.nextButton)
        buttonLayout.addWidget(self.finishButton)

        self.mainLayout = QtGui.QVBoxLayout()
        self.mainLayout.addLayout(buttonLayout)
        self.setLayout(self.mainLayout)

        self.resize(640, 480)

        self.intro_page    = IntroPage(self)
        self.read_toc_page = ReadTOCPage(self) 
        self.setFirstPage(self.intro_page)


    def historyPages(self):
        return self.history

    def setFirstPage(self, page):
        page.resetPage()
        self.history.append(page)
        self.switchPage(None)

    def backButtonClicked(self):
        oldpage = self.history.pop()
        oldpage.resetPage()
        self.switchPage(oldpage)

    def nextButtonClicked(self):
        oldpage = self.history[-1]
        newpage = oldpage.nextPage()
        newpage.resetPage()
        self.history.append(newpage)
        self.switchPage(oldpage)

    def completeStateChanged(self):
        currentpage = self.history[-1]
        if currentpage.isLastPage():
            self.finishButton.setEnabled(currentpage.isComplete())
        else:
            self.nextButton.setEnabled(currentpage.isComplete())

    def switchPage(self, oldPage):
        if oldPage is not None:
            oldPage.hide()
            self.mainLayout.removeWidget(oldPage)
            self.disconnect(oldPage, QtCore.SIGNAL("completeStateChanged())"),
                            self.completeStateChanged)

        newpage = self.history[-1]
        self.mainLayout.insertWidget(0, newpage)
        newpage.show()
        newpage.setFocus()
        self.connect(newpage, QtCore.SIGNAL("completeStateChanged()"),
                     self.completeStateChanged)

        self.backButton.setEnabled(len(self.history) != 1)
        if newpage.isLastPage():
            self.nextButton.setEnabled(False)
            self.finishButton.setDefault(True)
        else:
            self.nextButton.setDefault(True)
            self.finishButton.setEnabled(False)

        self.completeStateChanged()


# WizardPage
#_________________________________________________________________________________________
class WizardPage(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.wizard = parent
        self.hide()

    def resetPage(self):
        pass

    def nextPage(self):
        return None

    def isLastPage(self):
        return False

    def isComplete(self):
        return True


# IntroPage
#_________________________________________________________________________________________
class IntroPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)

        title_label = QtGui.QLabel(self.tr('<font size="5"><b>Introduction</b></font>'))

        layout = QtGui.QVBoxLayout()
        layout.addWidget(title_label)
        layout.addSpacing(10)

        #Check to ensure we are on Windows
        if sys.platform != 'win32':
            error_label = QtGui.QLabel(self.tr('''<font size="6">This program must be run on a Windows computer.</font>'''))
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            self.setLayout(layout)
            return

        label = QtGui.QLabel(self.tr(
                             '''<font size="3">This wizard will help you archive your CDs in your Personal Music Locker.
                             Please insert a CD and choose your CD drive below</font>'''))
        label.setWordWrap(True)
        layout.addWidget(label)

        #based on picard/util/cdrom.py
        from ctypes import windll
        GetLogicalDrives = windll.kernel32.GetLogicalDrives
        GetDriveType = windll.kernel32.GetDriveTypeA
        DRIVE_CDROM = 5
        cd_drives = ['(Choose CD Drive)']
        mask = GetLogicalDrives()
        for i in range(26):
            if mask >> i & 1:
                drive = chr(i + ord("A")) + ":"
                if GetDriveType(drive) == DRIVE_CDROM:
                    cd_drives.append(drive)

        self.combo = QtGui.QComboBox()
        self.combo.addItems(cd_drives)
        self.connect(self.combo, QtCore.SIGNAL("currentIndexChanged(const QString&)"),
                     self, QtCore.SIGNAL("completeStateChanged()"))

        layout.addWidget(self.combo)

        self.setLayout(layout)

    def isComplete(self):
        print self.combo.currentIndex()
        return ((sys.platform == 'win32') and (self.combo.currentIndex() != 0))


    def nextPage(self):
        return self.wizard.read_toc_page


# ReadTOCPage
#_________________________________________________________________________________________
class ReadTOCPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)

        print self.wizard.intro_page.combo.currentText()


# TitlePage
#_________________________________________________________________________________________
class TitlePage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)

        self.topLabel = QtGui.QLabel(self.tr(
                            "<center><font color=\"blue\" size=\"5\"><b><i>"
                            "Super Product One</i></b></font></center>"))

        self.registerRadioButton = QtGui.QRadioButton(self.tr("&Register your copy"))
        self.evaluateRadioButton = QtGui.QRadioButton(self.tr("&Evaluate our product"))
        self.setFocusProxy(self.registerRadioButton)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.topLabel)
        layout.addSpacing(10)
        layout.addWidget(self.registerRadioButton)
        layout.addWidget(self.evaluateRadioButton)
        layout.addStretch(1)
        self.setLayout(layout)

    def resetPage(self):
        self.registerRadioButton.setChecked(True)

    def nextPage(self):
        if self.evaluateRadioButton.isChecked():
            return self.wizard.evaluatePage
        else:
            return self.wizard.registerPage


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wizard = ArchiveWizard()
    sys.exit(wizard.exec_())
