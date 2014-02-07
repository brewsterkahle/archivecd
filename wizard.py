#!/usr/bin/env python

from PyQt4 import QtCore, QtGui
import sys
import json
import urllib
import webbrowser


# ArchiveWizard
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QWizard):
    Page_Intro, Page_Scan_Drives, Page_Read_TOC, Page_Lookup_CD, Page_Mark_Added, Page_EAC, Page_Select_EAC, Page_Verify_EAC, Page_Upload, Page_Verify_Upload= range(10)

    def __init__(self, parent=None):
        QtGui.QWizard.__init__(self, parent)

        self.intro_page         = IntroPage(self)
        self.scan_drives_page   = ScanDrivesPage(self)
        self.read_toc_page      = ReadTOCPage(self)
        self.lookup_cd_page     = LookupCDPage(self)
        self.mark_added_page    = MarkAddedPage(self)
        self.eac_page           = EACPage(self)
        self.select_eac_page    = SelectEACPage(self)
        self.verify_eac_page    = VerifyEACPage(self)
        self.upload_page        = UploadPage(self)
        self.verify_upload_page = VerifyUploadPage(self)

        self.setPage(self.Page_Intro,         self.intro_page)
        self.setPage(self.Page_Scan_Drives,   self.scan_drives_page)
        self.setPage(self.Page_Read_TOC,      self.read_toc_page)
        self.setPage(self.Page_Lookup_CD,     self.lookup_cd_page)
        self.setPage(self.Page_Mark_Added,    self.mark_added_page)
        self.setPage(self.Page_EAC,           self.eac_page)
        self.setPage(self.Page_Select_EAC,    self.select_eac_page)
        self.setPage(self.Page_Verify_EAC,    self.verify_eac_page)
        self.setPage(self.Page_Upload,        self.upload_page)
        self.setPage(self.Page_Verify_Upload, self.verify_upload_page)


    def done(self, x):
        if x == 1:
            self.restart()
        else:
            QtGui.QApplication.quit()


# WizardPage
#_________________________________________________________________________________________
class WizardPage(QtGui.QWizardPage):
    def __init__(self, parent=None):
        QtGui.QWizardPage.__init__(self, parent)
        self.wizard = parent


# IntroPage
#_________________________________________________________________________________________
class IntroPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Introduction')

        #Check to ensure we are on Windows
        if sys.platform != 'win32':
            error_str = 'This program must be run on a Windows computer.'
            self.setSubTitle(error_str)
            return

        self.setSubTitle('Please enter a CD and click the Next button')


    def isComplete(self):
        return (sys.platform == 'win32')


# ScanDrivesPage
#_________________________________________________________________________________________
class ScanDrivesPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Checking for CD Drives')
        
        layout = QtGui.QVBoxLayout()
        self.combo = QtGui.QComboBox()
        self.combo.addItems(['(Choose CD Drive)'])
        self.connect(self.combo, QtCore.SIGNAL("currentIndexChanged(const QString&)"),
                     self, QtCore.SIGNAL("completeChanged()"))


        layout.addWidget(self.combo)
        self.setLayout(layout)


    def initializePage(self):
        #based on picard/util/cdrom.py
        from ctypes import windll
        GetLogicalDrives = windll.kernel32.GetLogicalDrives
        GetDriveType = windll.kernel32.GetDriveTypeA
        DRIVE_CDROM = 5
        cd_drives = []
        mask = GetLogicalDrives()
        for i in range(26):
            if mask >> i & 1:
                drive = chr(i + ord("A")) + ":"
                if GetDriveType(drive) == DRIVE_CDROM:
                    cd_drives.append(drive)
        self.combo.addItems(cd_drives)



    def isComplete(self):
        print self.combo.currentIndex()
        return (self.combo.currentIndex() != 0)



# ReadTOCPage
#_________________________________________________________________________________________
class ReadTOCPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Reading CD Table of Contents')

        self.toc_label = QtGui.QLabel('checking...')
        self.toc_string = None
        self.disc_id    = None
        self.is_complete = False

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.toc_label)

        self.setLayout(layout)


    def isComplete(self):
        return self.is_complete


    def initializePage(self):
        cd_drive = self.wizard.scan_drives_page.combo.currentText()
        print cd_drive
        self.toc_label.setText('reading ' + cd_drive)
        import discid
        try:
            disc = discid.read(str(cd_drive))
        except discid.disc.DiscError:
            self.toc_label.setText('Unable to read disc')
            return


        self.toc_string = disc.toc_string
        self.disc_id    = disc.id
        print self.toc_string
        self.toc_label.setText(self.toc_string + '\n\nPress Next to check the archive.org database')
        self.is_complete = True


# LookupCDPage
#_________________________________________________________________________________________
class LookupCDPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Looking up CD in archive.org database')

        self.status_label = QtGui.QLabel('checking...')
        self.status_label.setWordWrap(True)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.status_label)

        self.setLayout(self.layout)

        self.scroll_area = QtGui.QScrollArea()
        self.layout.addWidget(self.scroll_area)

        self.is_complete = False
        self.radio_buttons = []


    def initializePage(self):
        url = 'http://dowewantit0.us.archive.org:5000/lookupCD?'
        url += urllib.urlencode({'sectors':   self.wizard.read_toc_page.toc_string,
                                 'mb_discid': self.wizard.read_toc_page.disc_id})
        #test_toc = '1 10 211995 182 22295 46610 71440 94720 108852 132800 155972 183515 200210'
        #url += urllib.urlencode({'sectors': test_toc})
        print url

        f = urllib.urlopen(url)
        c = f.read()
        self.status_label.setText('server returned:\n\n' + c)
        
        print c
        obj = json.loads(c)
        if len(obj) > 0:
            self.show_result(obj)
        else:
            self.status_label.setText('No match was found in the archive.org database. Please press the Next button to add your CD to your Music Locker.')
            self.is_complete = True


    def get_cover_image(self, metadata):
        img = None
        for f in metadata['files']:
            #print f
            if f['name'].endswith('_thumb.jpg'):
                img = f['name']
                break
            #todo: set image if itemimage.jpg not found
        return img


    def fetch_ia_metadata(self, itemid):
        url = 'https://archive.org/metadata/'+itemid
        metadata = json.load(urllib.urlopen(url))
        #print metadata
        md = {'img':     self.get_cover_image(metadata),
              'title':   metadata['metadata'].get('title'),
              'creator': metadata['metadata'].get('creator'),
              'date':    metadata['metadata'].get('date')
             }
        return md

        
    def show_result(self, obj):
        widget = QtGui.QWidget()        
        vbox = QtGui.QVBoxLayout(widget)
        self.radio_buttons = []

        s = es = ''
        if len(obj) > 1:
            s = 's'; es = 'es'

        self.status_label.setText('{n} match{es} for this CD was found in our database'.format(n=len(obj), es=es))
        for item in obj:
            item_id = item[0]
            md = self.fetch_ia_metadata(item_id)
            button = QtGui.QRadioButton("{t}\n{c}\n{d}".format(t=md['title'], c=md['creator'], d=md['date']))
            if md['img'] is not None:
                img_label = QtGui.QLabel()
                img_url = "https://archive.org/download/{id}/{img}".format(id=item_id, img=md['img'])
                #print img_url
                data = urllib.urlopen(img_url).read()
                img = QtGui.QImage()
                img.loadFromData(data)
                #img_label.setPixmap(QtGui.QPixmap(img).scaledToWidth(100))
                #self.layout.addWidget(img_label)
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(img))
                button.setIcon(icon)
                #button.setChecked(True)
                button.setStyleSheet('QRadioButton {icon-size: 100px;}')
            vbox.addWidget(button)
            self.radio_buttons.append(button)

        no_button  = QtGui.QRadioButton("My CD is different from the one{s} shown above".format(s=s))
        vbox.addWidget(no_button)
        self.radio_buttons.append(no_button)
        self.scroll_area.setWidget(widget)
        self.is_complete = True


    def isComplete(self):
        return self.is_complete


    def nextId(self):
        i = -1
        for i, radio in enumerate(self.radio_buttons):
            if radio.isChecked():
                break

        if (i == len(self.radio_buttons)-1) or (i == -1):
            return self.wizard.Page_EAC
        else:
            return self.wizard.Page_Mark_Added


# MarkAddedPage
#_________________________________________________________________________________________
class MarkAddedPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('CD Added to Locker')
        self.setSubTitle('This CD was added to your Music Locker')
        self.setFinalPage(True)
        self.setButtonText(QtGui.QWizard.FinishButton, "Scan Another CD")


    def nextId(self):
        return -1



# EACPage
#_________________________________________________________________________________________
class EACPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('EAC')
        self.setSubTitle('Please open Exact Audio Copy and copy the CD to your hard drive.')



# SelectEACPage
#_________________________________________________________________________________________
class SelectEACPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('EAC')
        self.setSubTitle('Please select the folder containing the CD data copied using EAC.')
        self.path = None
        #self.setButtonText(QtGui.QWizard.FinishButton, "Scan Another CD")
        layout = QtGui.QVBoxLayout()

        def handle_button():
            self.path = QtGui.QFileDialog.getExistingDirectory(None, 'Select EAC data folder', "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}", QtGui.QFileDialog.ShowDirsOnly)
            print self.path
            self.emit(QtCore.SIGNAL("completeChanged()"))
            self.label.setText("EAC Data dir = {p}\n\nClick Next to verify the data was copied by EAC correctly".format(p=self.path))

        button = QtGui.QPushButton('Click to select EAC data folder')
        button.clicked.connect(handle_button)
        layout.addWidget(button)
        self.label = QtGui.QLabel("")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.setLayout(layout)



    def isComplete(self):
        return self.path is not None


# VerifyEACPage
#_________________________________________________________________________________________
class VerifyEACPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Verifying EAC data')
        self.setSubTitle('The data was copied correctly. Click next to upload data to the Internet Archive')


# UploadPage
#_________________________________________________________________________________________
class UploadPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Upload EAC data')
        self.setSubTitle('Click the Open Web Browser button to launch the Internet Archive uploader. When the upload is complete, press the Next button.')

        def handle_button():
            webbrowser.open('https://archive.org/upload')
            self.button_clicked = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        button = QtGui.QPushButton('Open Web Browser')
        button.clicked.connect(handle_button)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(button)
        self.setLayout(layout)
        self.button_clicked = False

    def isComplete(self):
        return self.button_clicked


# VerifyUploadPage
#_________________________________________________________________________________________
class VerifyUploadPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Verifying Upload')
        self.setSubTitle('The upload was successful. You may now scan another CD or quit the application.')
        self.setButtonText(QtGui.QWizard.FinishButton, "Scan Another CD")
        self.setButtonText(QtGui.QWizard.CancelButton, "Quit")


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wizard = ArchiveWizard()
    sys.exit(wizard.exec_())

