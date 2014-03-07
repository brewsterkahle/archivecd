#!/usr/bin/env python

import os
import sys

#fix for loading discid.dll
if getattr(sys, 'frozen', None):
     BASE_DIR = sys._MEIPASS
else:
     BASE_DIR = os.getcwd()
os.environ['PATH'] = BASE_DIR + '\;' + os.environ.get('PATH', '')
import discid

from PyQt4 import QtCore, QtGui
import ctypes
import distutils.version
import json
import re
import urllib
import webbrowser
import musicbrainzngs


# ArchiveWizard
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QWizard):
    Page_Intro, Page_Scan_Drives, Page_Lookup_CD, Page_Mark_Added, Page_MusicBrainz, Page_EAC, Page_Select_EAC, Page_Verify_EAC, Page_Upload, Page_Verify_Upload = range(10)

    useragent = 'Internet Archive Music Locker'
    version   = '0.109'
    url       = 'https://archive.org'
    metadata_services = ['musicbrainz.org', 'freedb.org', 'gracenote.com']
    service_logos = {
        'archive.org': {
            'image':    'ia_logo.jpg',
            'template': '<a href="https://archive.org/details/{id}"><img src="{img}"></a>',
        },
        'musicbrainz.org': {
            'image':    'mb_logo.png',
            'template': '<a href="http://musicbrainz.org/release/{id}"><img src="{img}"></a>',
        },
        'freedb.org': {
            'image':    'freedb_logo.jpg',
            'template': '<a href="http://freedb.freedb.org/~cddb/cddb.cgi?cmd=cddb+read+{id}&hello=joe+my.host.com+xmcd+2.1&proto=6"><img src="{img}"></a>',
        },
        'gracenote.com': {
            'image':    'gracenote_logo.png',
            'template': '<img src="{img}">',
        },
    }


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
        self.metadata      = None
        self.ia_chosen     = None
        self.mb_chosen     = None


    def img_path(self, img):
        return os.path.join(BASE_DIR, 'images', img)


    def display_metadata(self, page, keys):
        widget = QtGui.QWidget()
        vbox = QtGui.QVBoxLayout(widget)
        radio_buttons = []
        releases = []
        for key in keys:
            try:
                r = self.metadata[key]['releases']
                for release in r:
                    release['type'] = key
                releases += r
            except LookupError:
                pass

        #print 'releases', releases
        sys.stdout.flush()

        for md in releases:
            item_id = md['id']

            button = QtGui.QRadioButton("{t}\n{a}\n{d} {c}".format(t=md.get('title', ''), a=', '.join(md.get('artists', '')), d=md.get('date', ''), c=md.get('country', '')))
            button.toggled.connect(page.radio_clicked)

            if md.get('qimg') is not None:
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(md['qimg']))
                button.setIcon(icon)
                button.setStyleSheet('QRadioButton {icon-size: 100px;}')

            hbox = QtGui.QHBoxLayout()
            hbox.addWidget(button)

            if md['type'] in self.service_logos:
                service_logo = self.service_logos[md['type']]
                template = service_logo['template']
                image = service_logo['image']
                label = QtGui.QLabel(template.format(id=item_id, img=self.img_path(image)))
                label.setOpenExternalLinks(True)
                hbox.addWidget(label)

            vbox.addLayout(hbox)
            radio_buttons.append(button)

        if len(releases) > 0:
            no_button  = QtGui.QRadioButton("My CD is not shown above")
            no_button.toggled.connect(page.radio_clicked)
            vbox.addWidget(no_button)
            radio_buttons.append(no_button)

        return widget, radio_buttons, releases


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
        self.is_complete = (sys.platform == 'win32')


    def initializePage(self):
        #Check to ensure we are on Windows
        if sys.platform != 'win32':
            error_str = 'This program must be run on a Windows computer.'
            self.setSubTitle(error_str)
            return

        self.setSubTitle('Please enter a CD and click the Next button')

        self.layout = QtGui.QVBoxLayout()
        pixmap = QtGui.QPixmap(self.wizard.img_path('logo.jpg'))
        img_label = QtGui.QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(img_label)

        line1 = self.make_field('archive.org username:')
        line2 = self.make_field('password:', echo_mode=QtGui.QLineEdit.Password)
        self.layout.addLayout(line1)
        self.layout.addLayout(line2)

        version_label = QtGui.QLabel('version ' + str(self.wizard.version))
        self.layout.addWidget(version_label)
        self.check_for_update()

        self.setLayout(self.layout)


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


    def check_for_update(self):
        self.update_label = QtGui.QLabel('Checking for update...')
        self.layout.addWidget(self.update_label)

        try:
            current_version = distutils.version.StrictVersion(self.wizard.version)
            self.newest_version = current_version
            ml = urllib.urlopen('https://archive.org/metadata/archivecd/files')
            files = json.load(ml)
            for file in files['result']:
                name = file['name']
                match = re.search('ArchiveCD-([\d\.]+)\.exe', name)
                if match:
                    v = distutils.version.StrictVersion(match.group(1))
                    if v > current_version:
                        self.newest_version = v
            if self.newest_version > current_version:
                self.update_label.setText('A new version ({v}) was found'.format(v=v))
                self.update_button = QtGui.QPushButton('Download and launch update')
                self.update_button.clicked.connect(self.download_launch_update)
                self.layout.addWidget(self.update_button)
            else:
                self.update_label.setText('ArchiveCD is up to date')
        except Exception:
            self.update_label.setText('Could not check for an update')


    def download_launch_update(self):
        self.update_button.setParent(None) #remove update_button
        self.is_complete = False
        self.emit(QtCore.SIGNAL("completeChanged()"))
        app.processEvents()

        new_file = 'ArchiveCD-{v}.exe'.format(v=self.newest_version)
        path = os.path.join(os.getcwd(), new_file)

        if not os.path.exists(path):
            try:
                url = 'https://archive.org/download/archivecd/{f}'.format(f=new_file)
                print 'Downloading {url} to {p}'.format(url=url, p=path)
                sys.stdout.flush()
                self.update_label.setText('Downloading {f}...'.format(f=new_file))
                app.processEvents()
                urllib.urlretrieve(url, path)
            except Exception:
                self.update_label.setText('Could not download update')
                app.processEvents()
                return

        print 'Launching {f}'.format(f=new_file)
        sys.stdout.flush()
        self.update_label.setText('Launching {f}...'.format(f=new_file))
        app.processEvents()
        os.execlp(path, new_file)


    def isComplete(self):
        return self.is_complete


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
        #self.metadata     = {}

    def run(self):
        status_label = self.status_label

        disc = self.read_cd()
        if disc is None:
            self.taskFinished.emit()
            return

        self.wizard.toc_string = disc.toc_string
        self.wizard.disc_id    = disc.id
        self.wizard.freedb_discid  = disc.freedb_id

        obj = self.lookup_ia()
        self.obj = obj
        #self.metadata = metadata
        #self.wizard.ia_result = metadata
        self.wizard.metadata = obj

        if ('freedb.org' in obj) and (obj['freedb.org']['status'] == 'ok'):
            self.wizard.freedb_result = obj['freedb.org']['releases']

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

        #test results from coverartarchive:
        #url = 'http://dowewantit0.us.archive.org:5000/lookupCD?mb_discid=4kclzDTxSO_3SOzXlmxxjDCsTPw-&freedb_discid=c90a6e10&version=2&sectors=1+16+200447+150+1795+22335+38900+42357+54407+69417+90770+93927+104780+120090+122705+130822+146112+162935+180952'

        print 'fetching ', url
        sys.stdout.flush()

        f = urllib.urlopen(url)
        c = f.read()
        obj = json.loads(c)
        print json.dumps(obj, indent=4)
        sys.stdout.flush()

        for item in obj['archive.org']['releases']:
            item_id = item['id']
            ia_md = self.fetch_ia_metadata(item_id)
            item.update(ia_md)

        for key in obj:
            if key == 'archive.org':
                continue
            service = obj[key]
            if 'releases' not in service:
                continue
            for release in service['releases']:
                cover_url = release.get('cover_url')
                if cover_url:
                    status_label.setText('Fetching cover image from ' + key)
                    qimg = self.get_cover_qimg(cover_url)
                    if qimg:
                        release['qimg'] = qimg
                #print 'RELEASE', release

        status_label.setText('Finished querying database')

        return obj


    def fetch_ia_metadata(self, item_id):
        url = 'https://archive.org/metadata/'+item_id
        print 'fetching ', url
        sys.stdout.flush()
        metadata = json.load(urllib.urlopen(url))

        #print 'METADATA API:', metadata
        #sys.stdout.flush()

        md = {'id':      item_id,
              'qimg':    self.get_cover_ia(item_id, metadata),
              'title':   metadata['metadata'].get('title'),
              'artists': metadata['metadata'].get('creator'),
              'date':    metadata['metadata'].get('date'),
              'collection': metadata['metadata'].get('collection'),
             }
        if isinstance(md['artists'], basestring):
            md['artists'] = [md['artists']]
        return md


    def get_cover_ia(self, item_id, metadata):
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
            qimg = self.get_cover_qimg(img_url)
            #print 'loading image from ', img_url
            #sys.stdout.flush()
            #data = urllib.urlopen(img_url).read()
            #qimg = QtGui.QImage()
            #qimg.loadFromData(data)
        return qimg


    def get_cover_qimg(self, img_url):
        try:
            print 'loading image from ', img_url
            sys.stdout.flush()
            data = urllib.urlopen(img_url).read()
            qimg = QtGui.QImage()
            qimg.loadFromData(data)
            return qimg
        except Exception:
            return None


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
        except Exception:
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
        self.metadata              = []
        self.show_ia               = False
        self.show_md               = False
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
        self.show_ia = self.got_md('archive.org')
        self.show_md = self.show_ia
        for key in self.wizard.metadata_services:
            self.show_md |= self.got_md(key)

        print 'ia', self.show_ia, ' md', self.show_md
        sys.stdout.flush()

        if self.show_ia:
            widget, self.radio_buttons, self.wizard.ia_result = self.wizard.display_metadata(self, ['archive.org'])
        elif self.show_md:
            widget, self.radio_buttons, self.wizard.mb_result = self.wizard.display_metadata(self, self.wizard.metadata_services)
        else:
            widget = QtGui.QLabel('Your album was not found in our database. Please press the Next button to continue.')
            self.is_complete = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        self.scroll_area.setWidget(widget)


    def got_md(self, key):
        try:
            md = self.wizard.metadata[key]
            if (md['status'] == 'ok') and md['releases']:
                return True
        except LookupError:
            pass
        return False


    def radio_clicked(self, enabled):
        i = -1
        for i, radio in enumerate(self.radio_buttons):
            if radio.isChecked():
                break

        if (i != len(self.radio_buttons)-1) and (i != -1):
            if self.show_ia:
                self.wizard.ia_chosen = i
            elif self.show_md:
                self.wizard.mb_chosen = i
        else:
            if self.show_ia:
                self.wizard.ia_chosen = None
            elif self.show_md:
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

        if self.show_md:
            if self.show_ia:
                #We have a match from the archive.org db. If the user said that the match
                #was correct, mark the disc as added to their Music Locker. Otherwise,
                #if there was an match from the MusicBrainz db, show MB results to the user.
                #If there were no MB matches, go directly to the EAC page.
                if (i == len(self.radio_buttons)-1) or (i == -1):
                    return self.wizard.Page_MusicBrainz
                else:
                    return self.wizard.Page_Mark_Added
            else:
                return self.wizard.Page_EAC
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
        self.is_complete = False
        widget, self.radio_buttons, self.wizard.mb_result = self.wizard.display_metadata(self, self.wizard.metadata_services)
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
        args = {'collection':   'acdc',
                'source':       'CD',
                'releasetype':  'album',
                'toc':          self.wizard.toc_string,
                'test_item':    1,
               }

        if self.wizard.mb_chosen is not None:
            md = self.wizard.mb_result[self.wizard.mb_chosen]
            for key in ['title', 'artists', 'date', 'description']:
                if key in md:
                    val = md[key]
                    if key == 'description':
                        if isinstance(val, list):
                            val = val[0]
                        val = val.replace('\n', '<br/>')
                    if key == 'artists':
                        key = 'creator[]'
                    args[key] = val
            if md['type'] == 'musicbrainz.org':
                args['external-identifier[]'] = ['urn:mb_release_id:'+md['id']]

        freedb_id = self.get_freedb_external_id()
        gracenote_id, gracenote_genre = self.get_gracenote_metadata()
        for id in (freedb_id, gracenote_id):
            if id:
                external_ids = args.get('external-identifier[]', [])
                args['external-identifier[]'] = external_ids + [id]

        if gracenote_genre:
            args['subject'] = gracenote_genre

        id = self.make_identifier(args)
        if id:
            args['suggested_identifier'] = id

        print 'args', json.dumps(args, indent=4)
        sys.stdout.flush()

        self.url += '?' + urllib.urlencode(args, True)


    def get_freedb_external_id(self):
        try:
            freedb = self.wizard.metadata['freedb.org']['releases']
            freedb_genre = freedb[0]['genre']
            freedb_id = freedb[0]['id']
            return 'urn:freedb_id:{id}'.format(id=freedb_id)
        except (LookupError, TypeError):
            return None


    def get_gracenote_metadata(self):
        try:
            gracenote = self.wizard.metadata['gracenote.com']['releases']
            gracenote_id = gracenote[0]['id']
            gracenote_genre = gracenote[0].get('genre')
            return 'urn:gracenote_id:{id}'.format(id=gracenote_id), gracenote_genre
        except (LookupError, TypeError):
            return None, None


    def make_identifier(self, args):
        id = None
        try:
            regex  = re.compile('[^a-zA-Z0-9\.\-_]+')
            artist = regex.sub('', args['creator[]'][0].lower().replace(' ', '-'))
            title  = regex.sub('', args['title'].lower().replace(' ', '-'))
            if artist and title:
                id     = 'cd_{title}_{artist}'.format(artist=artist, title=title)
        except Exception:
            pass
        return id


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

