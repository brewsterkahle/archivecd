#!/usr/bin/env python

"""Wizard to guide user to:
 - insert cd
 - please rip with eac
 - check for a good rip
 - upload with metadata (freedb, musicmind)
"""

from PyQt4 import QtGui


def createIntroPage():
    page = QtGui.QWizardPage()
    page.setTitle("Introduction")

    page.setSubTitle("This wizard will help you archive your CDs in your Personal Music Locker")

    label = QtGui.QLabel("Please insert a CD")
    label.setWordWrap(True)

    layout = QtGui.QVBoxLayout()
    layout.addWidget(label)
    page.setLayout(layout)

    return page


def choose_cd():
    page = QtGui.QWizardPage()
    page.setTitle("Choose CD Drive")

    file_dialog = QtGui.QFileDialog()
    file_dialog.setFileMode(QtGui.QFileDialog.Directory)
    file_dialog.setOptions(QtGui.QFileDialog.ShowDirsOnly)
    file_dialog.setDirectory('/')

    layout = QtGui.QVBoxLayout()
    layout.addWidget(file_dialog)
    page.setLayout(layout)

    return page


def createConclusionPage():
    page = QtGui.QWizardPage()
    page.setTitle("Conclusion")

    label = QtGui.QLabel("You are now added this CD to your locker!")
    label.setWordWrap(True)

    layout = QtGui.QVBoxLayout()
    layout.addWidget(label)
    page.setLayout(layout)

    return page


if __name__ == '__main__':

    import sys

    app = QtGui.QApplication(sys.argv)

    wizard = QtGui.QWizard()
    wizard.addPage(createIntroPage())
    wizard.addPage(choose_cd())
    wizard.addPage(createConclusionPage())
    wizard.setWindowTitle("Music Locker Uploader")
    wizard.show()

    sys.exit(wizard.exec_())
