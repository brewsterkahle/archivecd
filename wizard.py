#!/usr/bin/env python

from PyQt4 import QtCore, QtGui
import ctypes
import sys
import json
import urllib
import webbrowser

import discid
import musicbrainzngs


# ArchiveWizard
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QWizard):
    Page_Intro, Page_Scan_Drives, Page_Lookup_CD, Page_Mark_Added, Page_MusicBrainz, Page_EAC, Page_Select_EAC, Page_Verify_EAC, Page_Upload, Page_Verify_Upload = range(10)

    useragent = 'Internet Archive Music Locker'
    version   = '0.1'
    url       = 'https://archive.org'

    def __init__(self, parent=None):
        QtGui.QWizard.__init__(self, parent)

        self.reset()

        self.intro_page         = IntroPage(self)
        self.scan_drives_page   = ScanDrivesPage(self)
        self.lookup_cd_page     = LookupCDPage(self)
        self.mark_added_page    = MarkAddedPage(self)
        self.musicbrainz_page   = MusicBrainzPage(self)
        self.eac_page           = EACPage(self)

        self.setPage(self.Page_Intro,         self.intro_page)
        self.setPage(self.Page_Scan_Drives,   self.scan_drives_page)
        self.setPage(self.Page_Lookup_CD,     self.lookup_cd_page)
        self.setPage(self.Page_Mark_Added,    self.mark_added_page)
        self.setPage(self.Page_MusicBrainz,   self.musicbrainz_page)
        self.setPage(self.Page_EAC,           self.eac_page)


    def done(self, x):
        if x == 1:
            self.restart()
        else:
            QtGui.QApplication.quit()


    def reset(self):
        self.toc_string    = None
        self.disc_id       = None
        self.freedb_discid = None
        self.ia_result     = None
        self.mb_result     = None
        self.freedb_result = None
        self.ia_chosen     = None
        self.mb_chosen     = None


    def create_metadata_widget(self, page, metadata, is_ia=False, is_mb=False):
        '''Create a widget with albums from the given metadata array. Return both the
        widget and a list of radio buttons. Wire the radio button toggle event to the
        "radio_clicked" method of the given page.'''

        widget = QtGui.QWidget()
        vbox = QtGui.QVBoxLayout(widget)
        radio_buttons = []

        for md in metadata:
            item_id = md['id']
            button = QtGui.QRadioButton("{t}\n{a}\n{d} {c}".format(t=md['title'], a=md['creator'], d=md['date'], c=md.get('country', '')))
            button.toggled.connect(page.radio_clicked)

            if md['qimg'] is not None:
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(md['qimg']))
                button.setIcon(icon)
                button.setStyleSheet('QRadioButton {icon-size: 100px;}')

            #vbox.addWidget(button)
            hbox = QtGui.QHBoxLayout()
            hbox.addWidget(button)
            if is_ia:
                label = QtGui.QLabel('<a href="https://archive.org/details/{id}"><img src="ia_logo.jpg"></a>'.format(id=item_id))
                label.setOpenExternalLinks(True)
                hbox.addWidget(label)
            elif is_mb:
                label = QtGui.QLabel('<a href="http://musicbrainz.org/release/{id}"><img src="mb_logo.png"></a>'.format(id=item_id))
                label.setOpenExternalLinks(True)
                hbox.addWidget(label)
            vbox.addLayout(hbox)

            radio_buttons.append(button)

        if len(metadata) > 0:
            no_button  = QtGui.QRadioButton("My CD is not shown above")
            no_button.toggled.connect(page.radio_clicked)
            vbox.addWidget(no_button)
            radio_buttons.append(no_button)

        return widget, radio_buttons


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

        layout = QtGui.QVBoxLayout()
        pixmap = QtGui.QPixmap('logo.jpg')
        img_label = QtGui.QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(img_label)

        line1 = self.make_field('archive.org username:')
        line2 = self.make_field('password:', echo_mode=QtGui.QLineEdit.Password)
        layout.addLayout(line1)
        layout.addLayout(line2)

        self.setLayout(layout)


    def make_field(self, label_text, echo_mode=QtGui.QLineEdit.Normal):
        hbox = QtGui.QHBoxLayout()
        label = QtGui.QLabel(label_text)
        label.setFixedWidth(200)
        label.setAlignment(QtCore.Qt.AlignRight)

        field = QtGui.QLineEdit()
        field.setFixedWidth(200)
        field.setEchoMode(echo_mode)

        hbox.addStretch(1)
        hbox.addWidget(label)
        hbox.addWidget(field)
        hbox.addStretch(1)
        return hbox


    def isComplete(self):
        return (sys.platform == 'win32')


# ScanDrivesPage
#_________________________________________________________________________________________
class ScanDrivesPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Insert CD and choose your CD Drive from the list below')

        layout = QtGui.QVBoxLayout()
        self.combo = QtGui.QComboBox()
        self.combo.addItems(['(Choose CD Drive)'])
        self.connect(self.combo, QtCore.SIGNAL("currentIndexChanged(const QString&)"),
                     self, QtCore.SIGNAL("completeChanged()"))

        layout.addWidget(self.combo)
        self.setLayout(layout)
        self.scanned_drives = False

    def initializePage(self):
        #After the first CD is scanned, this page becomes the first page of the wizard
        self.wizard.reset()

        if self.scanned_drives:
            #If we have already scanned the drives, then we have already processed a
            #CD. Eject the current CD so the user can easily insert a new one, and
            #do not scan the cd drives again.
            cd_drive = self.wizard.scan_drives_page.combo.currentText()
            ctypes.windll.WINMM.mciSendStringW(u"open {drive} type cdaudio alias cdrom".format(drive=cd_drive), None, 0, None)
            ctypes.windll.WINMM.mciSendStringW(u"set cdrom door open", None, 0, None)
            return

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

        if 2 == self.combo.count():
            #only one drive, just select it
            self.combo.setCurrentIndex(1)

        #Once we have finished logging in, do not ask users to log in again.
        #Make this page the new first page of the wizard.
        self.wizard.setStartId(self.wizard.Page_Scan_Drives)
        self.scanned_drives = True


    def isComplete(self):
        return (self.combo.currentIndex() != 0)


# BackgroundThread
#_________________________________________________________________________________________
class BackgroundThread(QtCore.QThread):
    taskFinished = QtCore.pyqtSignal()

    def __init__(self, wizard, status_label):
        QtCore.QThread.__init__(self)

        self.wizard       = wizard
        self.status_label = status_label
        self.obj          = None
        self.metadata     = {}

    def run(self):
        if self.wizard.toc_string is None:
            #called the first time, check archive.org db
            self.run_ia()
        else:
            #called the second time, check MusicBrainz db
            self.run_mb()

    def run_ia(self):
        status_label = self.status_label

        disc = self.read_cd()
        if disc is None:
            self.taskFinished.emit()
            return

        self.wizard.toc_string = disc.toc_string
        self.wizard.disc_id    = disc.id
        self.wizard.freedb_discid  = disc.freedb_id

        obj, metadata = self.lookup_ia()
        self.obj = obj
        self.metadata = metadata
        self.wizard.ia_result = metadata

        #if len(self.wizard.ia_result) == 0:
        print 'checking musicbrainz'
        sys.stdout.flush()
        self.wizard.mb_result = self.lookup_mb()
        print self.wizard.mb_result

        self.taskFinished.emit()


    def run_mb(self):
        status_label = self.status_label

        print 'IA result not found, checking musicbrainz'
        sys.stdout.flush()
        self.wizard.mb_result = self.lookup_mb()
        print self.wizard.mb_result

        self.taskFinished.emit()


    def read_cd(self):
        cd_drive = self.wizard.scan_drives_page.combo.currentText()
        self.status_label.setText('Reading CD drive ' + cd_drive)
        try:
            disc = discid.read(str(cd_drive))
        except discid.disc.DiscError:
            self.status_label.setText('Unable to read disc')
            return None
        return disc


    def lookup_ia(self):
        status_label = self.status_label
        status_label.setText('Checking the archive.org database')

        url = 'http://dowewantit0.us.archive.org:5000/lookupCD?'
        url += urllib.urlencode({'sectors':   self.wizard.toc_string,
                                 'mb_discid': self.wizard.disc_id,
                                 'freedb_discid': self.wizard.freedb_discid,
                                 'version': 2})
        #test_toc = '1 10 211995 182 22295 46610 71440 94720 108852 132800 155972 183515 200210'
        #url += urllib.urlencode({'sectors': test_toc})
        print 'fetching ', url
        sys.stdout.flush()

        f = urllib.urlopen(url)
        c = f.read()
        print c
        sys.stdout.flush()
        obj = json.loads(c)
        metadata   = []
        for item in obj['archive.org']['releases']:
            item_id = item['id']
            metadata.append(self.fetch_ia_metadata(item_id))
        return obj, metadata


    def fetch_ia_metadata(self, item_id):
        url = 'https://archive.org/metadata/'+item_id
        print 'fetching ', url
        sys.stdout.flush()
        metadata = json.load(urllib.urlopen(url))
        #print metadata
        md = {'id':      item_id,
              'qimg':    self.get_cover_qimg(item_id, metadata),
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


    def lookup_mb(self):
        status_label = self.status_label
        status_label.setText('Checking the MusicBrainz database')

        disc_id = self.wizard.disc_id
        #disc_id = '203b2nNoBhUpSWCAejk5rojPuOU-' #testing
        #disc_id = 'OnYoxOJ8mAwXzTJcq42vROwOKSM-' #test cdstub
        #disc_id  = 'CvLoGpzPT2GKm1hx8vGEpP0lBwc-' #test 404

        musicbrainzngs.set_useragent(self.wizard.useragent, self.wizard.version, self.wizard.url)
        try:
            mb = musicbrainzngs.get_releases_by_discid(disc_id, includes=["artists", "recordings"])
        except:
            mb = {}
        print mb

        if 'disc' in mb:
            releases = mb['disc']['release-list']
        elif 'cdstub' in mb:
            releases = [mb['cdstub']]
        else:
            releases = [] #404 case

        metadata = []
        for release in releases:
            id      = release.get('id')
            title   = release.get('title', '')
            artist  = release.get('artist-credit-phrase', '')
            if artist == '':
                artist = release.get('artist', '') #support cdstubs
            country = release.get('country', '')
            date    = release.get('date', '')

            md_obj = {'id':      id,
                      'qimg':    None,
                      'title':   title,
                      'creator': artist,
                      'date':    date,
                      'country': country,
                     }

            description = self.get_mb_track_list(release)
            if description:
                md_obj['description'] = description

            metadata.append(md_obj)

        return metadata


    def get_mb_track_list(self, release):
        description = ''
        medium_list = release.get('medium-list')
        if not (medium_list and medium_list[0]):
            return None

        track_list = medium_list[0].get('track-list')
        if not track_list:
            return None

        for track in track_list:
            recording = track.get('recording')
            if recording:
                milliseconds = recording.get('length')
                seconds = float(milliseconds)/1000.0
                length = '{m}:{s:02d}'.format(m=int(seconds/60), s=int(seconds%60))
                description += '{n}. {t} {l}<br/>'.format(n=track.get('number'), t=recording.get('title'), l=length)

        return description



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

        self.scroll_area = None
        #self.scroll_area = QtGui.QScrollArea()
        #self.layout.addWidget(self.scroll_area)

        self.is_complete = False
        self.radio_buttons = []


    def initializePage(self):
        self.is_complete           = False
        self.wizard.toc_string     = None
        self.wizard.disc_id        = None
        self.wizard.freedb_discid  = None

        self.wizard.ia_result      = None
        self.wizard.mb_result      = None
        self.wizard.freedb_result  = None

        self.progress_bar.show()

        if self.scroll_area:
            self.scroll_area.setParent(None)

        self.radio_buttons = []
        self.scroll_area = QtGui.QScrollArea()
        self.layout.addWidget(self.scroll_area)

        self.background_thread = BackgroundThread(self.wizard, self.status_label)
        self.background_thread.taskFinished.connect(self.task_finished)
        self.background_thread.start()


    def task_finished(self):
        print 'background task done'
        sys.stdout.flush()
        self.progress_bar.hide()
        if self.wizard.toc_string is not None:
            self.show_result()


    def show_result(self):
        self.is_ia = False
        self.is_mb = False
        if self.wizard.ia_result:
            print self.wizard.ia_result
            self.status_label.setText('A match was found in the archive.org database. Please choose the correct match below.')
            metadata = self.wizard.ia_result
            self.is_ia = True
        elif self.wizard.mb_result is not None:
            self.status_label.setText('This CD was not found in the archive.org database, so we will add it. First, please choose a match from the MusicBrainz database below.')
            metadata = self.wizard.mb_result
            self.is_mb = True

        widget, self.radio_buttons = self.wizard.create_metadata_widget(self, metadata, is_ia=self.is_ia, is_mb=self.is_mb)

        if len(metadata) == 0:
            self.is_complete = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        self.scroll_area.setWidget(widget)


    def radio_clicked(self, enabled):
        i = -1
        for i, radio in enumerate(self.radio_buttons):
            if radio.isChecked():
                break

        if (i != len(self.radio_buttons)-1) and (i != -1):
            if self.is_ia:
                self.wizard.ia_chosen = i
            elif self.is_mb:
                self.wizard.mb_chosen = i
        else:
            if self.is_ia:
                self.wizard.ia_chosen = None
            elif self.is_mb:
                self.wizard.mb_chosen = None

        self.is_complete = True
        self.emit(QtCore.SIGNAL("completeChanged()"))


    def isComplete(self):
        return self.is_complete


    def nextId(self):
        i = -1
        for i, radio in enumerate(self.radio_buttons):
            if radio.isChecked():
                break

        if self.wizard.ia_result:
            #We have a match from the archive.org db. If the user said that the match
            #was correct, mark the disc as added to their Music Locker. Otherwise,
            #if there was an match from the MusicBrainz db, show MB results to the user.
            #If there were no MB matches, go directly to the EAC page.
            if (i == len(self.radio_buttons)-1) or (i == -1):
                if self.wizard.mb_result:
                    return self.wizard.Page_MusicBrainz
                else:
                    return self.wizard.Page_EAC
            else:
                return self.wizard.Page_Mark_Added
        else:
            return self.wizard.Page_EAC



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
        self.setTitle('Please choose a match from the MusicBrainz database')

        self.status_label = QtGui.QLabel('This will help us fill out the metadata for your CD automatically')
        self.status_label.setWordWrap(True)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.status_label)

        #self.progress_bar = QtGui.QProgressBar(self)
        #self.progress_bar.setRange(0,0)
        #self.layout.addWidget(self.progress_bar)

        self.setLayout(self.layout)

        self.scroll_area = QtGui.QScrollArea()
        self.layout.addWidget(self.scroll_area)

        self.is_complete = False
        self.radio_buttons = []


    def initializePage(self):
        metadata = self.wizard.mb_result
        widget, self.radio_buttons = self.wizard.create_metadata_widget(self, metadata, is_mb=True)

        self.is_complete = False
        if len(metadata) == 0:
            self.is_complete = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        self.scroll_area.setWidget(widget)


    def radio_clicked(self, enabled):
        i = -1
        for i, radio in enumerate(self.radio_buttons):
            if radio.isChecked():
                break

        if (i != len(self.radio_buttons)-1) and (i != -1):
            self.wizard.mb_chosen = i
        else:
            self.wizard.mb_chosen = None

        self.is_complete = True
        self.emit(QtCore.SIGNAL("completeChanged()"))


    def isComplete(self):
        return self.is_complete


# EACPage
#_________________________________________________________________________________________
class EACPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('EAC')
        self.setSubTitle('Please open Exact Audio Copy and copy the CD to your hard drive. When you are finished, please click the Upload button to add your CD to your Music Locker.')
        self.url = 'https://archive.org/upload'

        def handle_button():
            webbrowser.open(self.url)
            self.button_clicked = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        self.button = QtGui.QPushButton('Open Web Browser to Upload to Music Locker')
        self.button.clicked.connect(handle_button)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)
        self.button_clicked = False
        self.setButtonText(QtGui.QWizard.FinishButton, "Scan Another CD")


    def initializePage(self):
        self.button_clicked = False

        print 'chosen ia=', self.wizard.ia_chosen, ' mb=', self.wizard.mb_chosen
        sys.stdout.flush()

        self.url = 'https://archive.org/upload'
        args = {'collection':          'acdc',
                'source':              'CD',
                'test_item':           1,
               }

        if self.wizard.mb_chosen is not None:
            md = self.wizard.mb_result[self.wizard.mb_chosen]
            for key in ['title', 'creator', 'date', 'description']:
                if key in md:
                    args[key] = md[key]
            args['external-identifier'] = 'urn:mb_release_id:'+md['id']

        self.url += '?' + urllib.urlencode(args)


    def nextId(self):
        return -1


    def isComplete(self):
        return self.button_clicked


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

