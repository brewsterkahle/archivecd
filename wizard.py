#!/usr/bin/env python

from PyQt4 import QtCore, QtGui
import sys
import json
import urllib
import webbrowser

import discid
import musicbrainzngs


# ArchiveWizard
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QWizard):
    Page_Intro, Page_Scan_Drives, Page_Read_TOC, Page_Lookup_CD, Page_Mark_Added, Page_MusicBrainz, Page_EAC, Page_Select_EAC, Page_Verify_EAC, Page_Upload, Page_Verify_Upload = range(11)

    useragent = 'Internet Archive Music Locker'
    version   = '0.1'
    url       = 'https://archive.org'

    def __init__(self, parent=None):
        QtGui.QWizard.__init__(self, parent)

        self.intro_page         = IntroPage(self)
        self.scan_drives_page   = ScanDrivesPage(self)
        self.read_toc_page      = ReadTOCPage(self)
        self.lookup_cd_page     = LookupCDPage(self)
        self.mark_added_page    = MarkAddedPage(self)
        self.musicbrainz_page   = MusicBrainzPage(self)
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
        self.setPage(self.Page_MusicBrainz,   self.musicbrainz_page)
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
        self.freedb_discid = None
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
        try:
            disc = discid.read(str(cd_drive))
        except discid.disc.DiscError:
            self.toc_label.setText('Unable to read disc')
            return


        self.toc_string = disc.toc_string
        self.disc_id    = disc.id
        self.freedb_discid  = disc.freedb_id
        print self.toc_string
        self.toc_label.setText(self.toc_string + '\n\nPress Next to check the archive.org database')
        self.is_complete = True



# NetworkThread
#_________________________________________________________________________________________
class NetworkThread(QtCore.QThread):
    taskFinished = QtCore.pyqtSignal()

    def __init__(self, toc_string, disc_id, freedb_discid):
        QtCore.QThread.__init__(self)

        self.toc_string = toc_string
        self.disc_id    = disc_id
        self.freedb_discid = freedb_discid
        self.obj        = None
        self.metadata   = {}


    def run(self):
        url = 'http://dowewantit0.us.archive.org:5000/lookupCD?'
        url += urllib.urlencode({'sectors':   self.toc_string,
                                 'mb_discid': self.disc_id,
                                 'freedb_discid': self.freedb_discid})
        #test_toc = '1 10 211995 182 22295 46610 71440 94720 108852 132800 155972 183515 200210'
        #url += urllib.urlencode({'sectors': test_toc})
        print 'fetching ', url
        sys.stdout.flush()

        f = urllib.urlopen(url)
        c = f.read()
        print c
        sys.stdout.flush()
        self.obj = json.loads(c)

        for item in self.obj:
            item_id = item[0]
            self.metadata[item_id] = self.fetch_ia_metadata(item_id)

        self.taskFinished.emit()


    def fetch_ia_metadata(self, item_id):
        url = 'https://archive.org/metadata/'+item_id
        print 'fetching ', url
        sys.stdout.flush()
        metadata = json.load(urllib.urlopen(url))
        #print metadata
        md = {'qimg':    self.get_cover_qimg(item_id, metadata),
              'title':   metadata['metadata'].get('title'),
              'creator': metadata['metadata'].get('creator'),
              'date':    metadata['metadata'].get('date')
             }
        return md


    def get_cover_qimg(self, item_id, metadata):
        img = None
        for f in metadata['files']:
            #print f
            if f['name'].endswith('_thumb.jpg'):
                img = f['name']
                break
            #todo: set image if itemimage.jpg not found

        qimg = None
        if img is not None:
            img_url = "https://archive.org/download/{id}/{img}".format(id=item_id, img=img)
            print 'loading image from ', img_url
            sys.stdout.flush()
            data = urllib.urlopen(img_url).read()
            qimg = QtGui.QImage()
            qimg.loadFromData(data)
            #icon = QtGui.QIcon()
            #icon.addPixmap(QtGui.QPixmap(qimg))
        return qimg


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

        self.progress_bar = QtGui.QProgressBar(self)
        self.progress_bar.setRange(0,0)
        self.layout.addWidget(self.progress_bar)

        self.setLayout(self.layout)

        self.scroll_area = QtGui.QScrollArea()
        self.layout.addWidget(self.scroll_area)

        self.is_complete = False
        self.radio_buttons = []


    def initializePage(self):
        self.is_complete = False
        self.network_lookup = NetworkThread(self.wizard.read_toc_page.toc_string, self.wizard.read_toc_page.disc_id, self.wizard.read_toc_page.freedb_discid)
        self.network_lookup.taskFinished.connect(self.task_finished)
        self.network_lookup.start()


    def task_finished(self):
        print 'network task done'
        sys.stdout.flush()
        self.progress_bar.hide()
        self.show_result(self.network_lookup.obj, self.network_lookup.metadata)


    def show_result(self, obj, metadata):
        widget = QtGui.QWidget()
        vbox = QtGui.QVBoxLayout(widget)
        self.radio_buttons = []

        s = es = ''
        if len(obj) > 1:
            s = 's'; es = 'es'

        if len(obj) == 0:
            self.status_label.setText('No match was found in the archive.org database. Please press the Next button to add your CD to your Music Locker.')
        else:
            self.status_label.setText('{n} match{es} for this CD was found in our database'.format(n=len(obj), es=es))

        for item in obj:
            item_id = item[0]
            #md = self.fetch_ia_metadata(item_id)
            md = metadata[item_id]

            button = QtGui.QRadioButton("{t}\n{c}\n{d}".format(t=md['title'], c=md['creator'], d=md['date']))
            button.toggled.connect(self.radio_clicked)

            if md['qimg'] is not None:
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(md['qimg']))
                button.setIcon(icon)
                button.setStyleSheet('QRadioButton {icon-size: 100px;}')

            vbox.addWidget(button)
            self.radio_buttons.append(button)

        if len(obj) > 0:
            no_button  = QtGui.QRadioButton("My CD is different from the one{s} shown above".format(s=s))
            no_button.toggled.connect(self.radio_clicked)
            vbox.addWidget(no_button)
            self.radio_buttons.append(no_button)
        else:
            self.is_complete = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        self.scroll_area.setWidget(widget)


    def radio_clicked(self, enabled):
        self.is_complete = True
        self.emit(QtCore.SIGNAL("completeChanged()"))


    def isComplete(self):
        return self.is_complete


    def nextId(self):
        i = -1
        for i, radio in enumerate(self.radio_buttons):
            if radio.isChecked():
                break

        if (i == len(self.radio_buttons)-1) or (i == -1):
            return self.wizard.Page_MusicBrainz
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


# MusicBrainzPage
#_________________________________________________________________________________________
class MusicBrainzPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Please help us find the MusicBrainz identifier for this CD by choosing a release from the list below')

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
        self.is_complete = False
        disc_id = self.wizard.read_toc_page.disc_id
        #disc_id = '203b2nNoBhUpSWCAejk5rojPuOU-' #testing
        #disc_id = 'OnYoxOJ8mAwXzTJcq42vROwOKSM-' #test cdstub
        musicbrainzngs.set_useragent(self.wizard.useragent, self.wizard.version, self.wizard.url)
        mb = musicbrainzngs.get_releases_by_discid(disc_id, includes=["artists"])
        self.show_result(mb)


    def isComplete(self):
        return self.is_complete


    def show_result(self, mb):
        widget = QtGui.QWidget()
        vbox = QtGui.QVBoxLayout(widget)
        self.radio_buttons = []

        if 'disc' in mb:
            releases = mb['disc']['release-list']
        elif 'cdstub' in mb:
            releases = [mb['cdstub']]

        #num_releases = disc['release-count']
        num_releases = len(releases)

        s = es = ''
        if num_releases > 1:
            s = 's'; es = 'es'

        if num_releases == 0:
            self.status_label.setText('No match was found in the archive.org database. Please press the Next button to add your CD to your Music Locker.')
        else:
            self.status_label.setText('{n} match{es} for this CD was found in our database'.format(n=num_releases, es=es))

        for release in releases:
            title   = release.get('title', '')
            artist  = release.get('artist-credit-phrase', '')
            if artist == '':
                artist = release.get('artist', '') #support cdstubs
            country = release.get('country', '')
            date    = release.get('date', '')

            button = QtGui.QRadioButton("{t}\n{a}\n{d} {c}".format(t=title, a=artist, d=date, c=country))
            button.toggled.connect(self.radio_clicked)

            #if md['icon'] is not None:
            #    button.setIcon(md['icon'])
            #    button.setStyleSheet('QRadioButton {icon-size: 100px;}')

            vbox.addWidget(button)
            self.radio_buttons.append(button)

        if num_releases > 0:
            no_button  = QtGui.QRadioButton("My CD is different from the one{s} shown above".format(s=s))
            no_button.toggled.connect(self.radio_clicked)
            vbox.addWidget(no_button)
            self.radio_buttons.append(no_button)
        else:
            self.is_complete = True

        self.scroll_area.setWidget(widget)


    def radio_clicked(self, enabled):
        self.is_complete = True
        self.emit(QtCore.SIGNAL("completeChanged()"))



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

