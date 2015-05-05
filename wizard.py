#!/usr/bin/env python

''' Copyright 2014 Internet Archive

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

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
import codecs
import eac_log_to_musicbrainz_discid


# ArchiveWizard
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QWizard):
    Page_Intro, Page_Scan_Drives, Page_Lookup_CD, Page_Mark_Added, Page_MusicBrainz, Page_EAC, Page_Select_EAC, Page_Verify_EAC, Page_Upload, Page_Verify_Upload = range(10)

    useragent = 'Internet Archive Music Locker'
    version   = '0.122'
    url       = 'https://archive.org'
    archivecd_server = 'dowewantit0.us.archive.org'
    archivecd_port   = '5000'
    metadata_services = ['musicbrainz.org', 'freedb.org', 'gracenote.com']
    service_logos = {
        'archive.org': {
            'image':    u'ia_logo.jpg',
            'template': u'<a href="https://archive.org/details/{id}"><img src="{img}"></a>',
        },
        'musicbrainz.org': {
            'image':    u'mb_logo.png',
            'template': u'<a href="http://musicbrainz.org/release/{id}"><img src="{img}"></a>',
        },
        'freedb.org': {
            'image':    u'freedb_logo.jpg',
            'template': u'<a href="http://freedb.freedb.org/~cddb/cddb.cgi?cmd=cddb+read+{id}&hello=joe+my.host.com+xmcd+2.1&proto=6"><img src="{img}"></a>',
        },
        'gracenote.com': {
            'image':    u'gracenote_logo.png',
            'template': u'<img src="{img}">',
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
        self.eac_log_file  = None
        self.barcode       = None


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

            #protect against md api returning None for title or artist
            title = md.get('title', '')
            if title is None:
                title = u''
            if md.get('artists', '') is not None:
                artists = u', '.join(md.get('artists', ''))
            else:
                artists = u''

            button_txt = u"{t}\n{a}".format(t=title, a=artists)
            if md.get('date') or md.get('country'):
                button_txt += u"\n{d} {c}".format(d=md.get('date', ''), c=md.get('country', ''))
            if md['type'] != 'archive.org':
                button_txt += u"\nMetadata provider: {p}".format(p=md['type'])
                if md['type'] == 'musicbrainz.org':
                    button_txt += u" (preferred)"

            button = QtGui.QRadioButton(button_txt)
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
            vbox.addSpacing(10)
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
        self.setTitle('Archive your CDs in the Archive.org Music Locker')
        self.is_complete = (sys.platform == 'win32')
        self.setButtonText(QtGui.QWizard.NextButton, "Login")


    def initializePage(self):
        #Check to ensure we are on Windows
        if sys.platform != 'win32':
            error_str = 'This program must be run on a Windows computer.'
            self.setSubTitle(error_str)
            return

        self.layout = QtGui.QVBoxLayout()
        about_txt = '''<qt>
            Please help the Internet Archive build the Audiophile CD Collection, a world class joint collection for researchers and preservation.
            <br/><br/>
            <a href="http://blog.archive.org/?p=8051&preview=true">Help</a></qt>
        '''
        about_label = QtGui.QLabel(about_txt)
        about_label.setWordWrap(True)
        about_label.setOpenExternalLinks(True)
        self.layout.addWidget(about_label)

        grid_layout = QtGui.QGridLayout()
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(2, 1)

        pixmap = QtGui.QPixmap(self.wizard.img_path('logo.jpg'))
        img_label = QtGui.QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(QtCore.Qt.AlignCenter)

        #self.layout.addWidget(img_label)
        grid_layout.addWidget(img_label, 0, 1)

        login_label = QtGui.QLabel('Login to archive.org')
        login_label.setAlignment(QtCore.Qt.AlignCenter)
        grid_layout.addWidget(login_label, 1, 1)

        username_label = QtGui.QLabel('username:')
        username_label.setAlignment(QtCore.Qt.AlignRight)
        grid_layout.addWidget(username_label, 2, 0)
        username_field = QtGui.QLineEdit()
        username_field.setFixedWidth(230)
        username_field.setPlaceholderText('you@example.com')
        grid_layout.addWidget(username_field, 2, 1, alignment=QtCore.Qt.AlignCenter)

        password_label = QtGui.QLabel('password:')
        password_label.setAlignment(QtCore.Qt.AlignRight)
        grid_layout.addWidget(password_label, 3, 0)
        password_field = QtGui.QLineEdit(self) #set self as parent so we can set focus later
        password_field.setEchoMode(QtGui.QLineEdit.Password)
        password_field.setFixedWidth(230)
        grid_layout.addWidget(password_field, 3, 1, alignment=QtCore.Qt.AlignCenter)

        #The username_field placeholder text won't show unless the focus is set elsewhere.
        #Unfortunately, it seems like we can only put focus in another text field, so
        #set focus in the password field
        password_field.setFocus()

        forgot_txt = '''<a href="https://archive.org/account/login.createaccount.php">Join Us</a>
                        &nbsp;&nbsp;-&nbsp;&nbsp;
                        <a href="https://archive.org/account/login.forgotpw.php">Forgot Password</a>
                     '''
        forgot_label = QtGui.QLabel(forgot_txt)
        forgot_label.setOpenExternalLinks(True)
        grid_layout.addWidget(forgot_label, 4, 1, alignment=QtCore.Qt.AlignCenter)

        self.layout.addLayout(grid_layout)

        port_layout = QtGui.QHBoxLayout()
        combo_label = QtGui.QLabel('Server port:')
        self.port_combo = QtGui.QComboBox()
        self.port_combo.addItems(['5000', '4999'])
        self.connect(self.port_combo, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.change_port)

        port_layout.addWidget(combo_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addStretch()
        self.layout.addLayout(port_layout)

        version_label = QtGui.QLabel('version ' + str(self.wizard.version))
        self.layout.addWidget(version_label)
        self.check_for_update()

        self.setLayout(self.layout)\


    def change_port(self):
        self.wizard.archivecd_port = self.port_combo.currentText()


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
                self.update_label.setText(u'A new version ({v}) was found'.format(v=v))
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

        new_file = u'ArchiveCD-{v}.exe'.format(v=self.newest_version)
        path = os.path.join(os.getcwd(), new_file)

        if not os.path.exists(path):
            try:
                url = u'https://archive.org/download/archivecd/{f}'.format(f=new_file)
                print u'Downloading {url} to {p}'.format(url=url, p=path)
                sys.stdout.flush()
                self.update_label.setText(u'Downloading {f}...'.format(f=new_file))
                app.processEvents()
                urllib.urlretrieve(url, path)
            except Exception:
                self.update_label.setText('Could not download update')
                app.processEvents()
                return

        print 'Launching {f}'.format(f=new_file)
        sys.stdout.flush()
        self.update_label.setText(u'Launching {f}...'.format(f=new_file))
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

        def handle_button_eac_log():
            self.barcode_field.clear()
            log_file = unicode(QtGui.QFileDialog.getOpenFileName(self, "Select Directory of Audio Files", ".", '*.log'))
            print u'Chose EAC log file', log_file
            sys.stdout.flush()
            if log_file != '':
                self.wizard.eac_log_file = log_file
                self.emit(QtCore.SIGNAL("completeChanged()"))
                self.wizard.next()

        def handle_barcode_field(string):
            self.wizard.barcode = string
            self.emit(QtCore.SIGNAL("completeChanged()"))

        layout = QtGui.QVBoxLayout()
        self.combo = QtGui.QComboBox()
        self.combo.addItems(['(Choose CD Drive)'])
        self.connect(self.combo, QtCore.SIGNAL("currentIndexChanged(const QString&)"),
                     self, QtCore.SIGNAL("completeChanged()"))

        or_label = QtGui.QLabel('or')
        or_label.setAlignment(QtCore.Qt.AlignCenter)
        self.button_eac_log = QtGui.QPushButton('Choose EAC Log File')
        self.button_eac_log.clicked.connect(handle_button_eac_log)

        or_label2 = QtGui.QLabel('or')
        or_label2.setAlignment(QtCore.Qt.AlignCenter)
        self.barcode_field = QtGui.QLineEdit()
        self.barcode_field.setAlignment(QtCore.Qt.AlignCenter)
        self.barcode_field.setPlaceholderText('scan barcode')
        self.barcode_field.textChanged.connect(handle_barcode_field)

        layout.addWidget(self.combo)
        layout.addWidget(or_label)
        layout.addWidget(self.button_eac_log)
        layout.addWidget(or_label2)
        layout.addWidget(self.barcode_field)

        self.setLayout(layout)
        self.scanned_drives = False


    def initializePage(self):
        #After the first CD is scanned, this page becomes the first page of the wizard
        self.wizard.reset()
        self.barcode_field.clear()

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
        return ((self.combo.currentIndex() != 0) or (self.wizard.eac_log_file is not None) or (self.barcode_field.text() != ""))


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

        if not self.wizard.barcode:
            if self.wizard.eac_log_file is not None:
                disc = self.read_eac_log()
            else:
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


    def read_eac_log(self):
        try:
            fh = codecs.open(self.wizard.eac_log_file, encoding='utf-16-le').readlines()
            toc = eac_log_to_musicbrainz_discid.calculate_mb_toc_numbers(eac_log_to_musicbrainz_discid.filter_toc_entries(iter(fh)))
            disc = discid.put(toc[0], toc[1], toc[2], toc[3:])
        except:
            self.status_label.setText('Unable to parse EAC log file')
            return None
        return disc


    def lookup_ia(self):
        status_label = self.status_label
        status_label.setText('Checking the archive.org database')

        url = 'http://{s}:{p}/lookupCD?'.format(s=self.wizard.archivecd_server,
                                                p=self.wizard.archivecd_port)

        if self.wizard.barcode:
            url += urllib.urlencode({'barcode': self.wizard.barcode,
                                     'version': 2})
        else:
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

        #cover_limit = 10
        for i, item in enumerate(obj['archive.org']['releases']):
            item_id = item['id']
            #fetch_cover = (i < cover_limit)
            fetch_cover = True
            ia_md = self.fetch_ia_metadata(item_id, fetch_cover)
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


    def fetch_ia_metadata(self, item_id, fetch_cover):
        url = 'https://archive.org/metadata/'+item_id
        print 'fetching ', url
        sys.stdout.flush()
        metadata = json.load(urllib.urlopen(url))

        #print 'METADATA API:', metadata
        #sys.stdout.flush()

        md = {'id':      item_id,
              'title':   metadata['metadata'].get('title'),
              'artists': metadata['metadata'].get('creator'),
              'date':    metadata['metadata'].get('date'),
              'collection': metadata['metadata'].get('collection'),
             }

        if fetch_cover:
            md['qimg'] = self.get_cover_ia(item_id, metadata)

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
            img_url = u"https://archive.org/download/{id}/{img}".format(id=item_id, img=img)
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
                length = u'{m}:{s:02d}'.format(m=int(seconds/60), s=int(seconds%60))
                description += u'{n}. {t} {l}<br/>'.format(n=track.get('number'), t=recording.get('title'), l=length)

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
            self.status_label.setText('A possible match for this CD was found in the Archive.org database. Please select your CD below.')
            widget, self.radio_buttons, self.wizard.ia_result = self.wizard.display_metadata(self, ['archive.org'])
        elif self.show_md:
            self.status_label.setText('The CD was not in Archive.org, so please upload it. Select metadata that matches your CD below.')
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
        self.setSubTitle('This CD was added to your Music Locker on Archive.org')
        self.setFinalPage(True)
        self.setButtonText(QtGui.QWizard.FinishButton, "Scan Another CD")


    def initializePage(self):
        print 'ia chosen', self.wizard.ia_chosen
        sys.stdout.flush()

        layout = QtGui.QVBoxLayout()

        try:
            md = self.wizard.metadata['archive.org']['releases'][self.wizard.ia_chosen]
            if md.get('qimg') is not None:
                label = QtGui.QLabel()
                label.setPixmap(QtGui.QPixmap(md['qimg']))
                layout.addWidget(label)
        except Exception:
            pass

        goto_label = QtGui.QLabel('<a href="http://archive.org/MusicLocker">Go to your Music Locker</a>')
        goto_label.setOpenExternalLinks(True)
        layout.addWidget(goto_label)

        self.setLayout(layout)


    def nextId(self):
        return -1


# MusicBrainzPage
#_________________________________________________________________________________________
class MusicBrainzPage(WizardPage):
    def __init__(self, wizard):
        WizardPage.__init__(self, wizard)
        self.setTitle('Add metadata and upload CD.')

        self.status_label = QtGui.QLabel('The CD was not in Archive.org, so please upload it. Select metadata that matches your CD below.')
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
        self.setSubTitle('Please open Exact Audio Copy and copy the CD to your hard drive. When you are finished with EAC, please click one of the two buttons below:')
        self.url = 'https://archive.org/upload'
        self.args = {}

        def handle_button_upload():
            webbrowser.open(self.url)
            self.button_clicked = True
            self.emit(QtCore.SIGNAL("completeChanged()"))

        def handle_button_later():
            audio_dir = unicode(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory of Audio Files"))

            extra_meta = {}
            for key in self.args:
                if key in [u'suggested_identifier', u'collection']:
                    continue
                new_key = re.sub(r'\[\]$', '', key)
                extra_meta[new_key] = self.args[key]
            meta_path = os.path.join(audio_dir, u'ia_extrameta.json')
            print u'writing metadata to ', meta_path.encode('utf-8')
            sys.stdout.flush()
            fh = open(meta_path, 'wb')
            json.dump(extra_meta, fh, indent=4)
            self.button_clicked = True
            self.emit(QtCore.SIGNAL("completeChanged()"))


        self.button = QtGui.QPushButton('Open Web Browser to Upload to Music Locker')
        self.button.clicked.connect(handle_button_upload)
        or_label = QtGui.QLabel('or')
        or_label.setAlignment(QtCore.Qt.AlignCenter)
        self.button_later = QtGui.QPushButton('Write Information to the Hard Drive for later uploading')
        self.button_later.clicked.connect(handle_button_later)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(or_label)
        layout.addWidget(self.button_later)
        self.setLayout(layout)
        self.button_clicked = False
        self.setButtonText(QtGui.QWizard.FinishButton, "Scan Another CD")


    def initializePage(self):
        self.button_clicked = False

        print 'chosen ia=', self.wizard.ia_chosen, ' mb=', self.wizard.mb_chosen
        sys.stdout.flush()

        self.url = 'https://archive.org/upload'
        self.args = {u'collection[]': [u'acdc'],
                     u'source':       u'CD',
                     u'releasetype':  u'album',
                     u'toc':          self.wizard.toc_string,
                    }

        if self.wizard.mb_chosen is not None:
            md = self.wizard.mb_result[self.wizard.mb_chosen]
            for key in [u'title', u'artists', u'date', u'description']:
                if key in md:
                    val = md[key]
                    if key == u'description':
                        if isinstance(val, list):
                            val = val[0]
                        val = val.replace('\n', '<br/>')
                    if key == u'artists':
                        key = u'creator[]'
                    self.args[key] = val
            if md['type'] == 'musicbrainz.org':
                self.args[u'external-identifier[]'] = [u'urn:mb_release_id:'+md['id']]

        freedb_id = self.get_freedb_external_id()
        gracenote_id, gracenote_genre = self.get_gracenote_metadata()
        for id in (freedb_id, gracenote_id):
            if id:
                external_ids = self.args.get(u'external-identifier[]', [])
                self.args[u'external-identifier[]'] = external_ids + [id]

        if gracenote_genre:
            self.args[u'subject'] = gracenote_genre

        id = self.make_identifier(self.args)
        if id:
            self.args[u'suggested_identifier'] = id

        if self.wizard.eac_log_file is not None:
            m = re.search(r'/(\d{2}-\d{4}\d*)/', self.wizard.eac_log_file)
            if m:
                external_ids = self.args.get(u'external-identifier[]', [])
                self.args[u'external-identifier[]'] = external_ids + [u'urn:arcmusic:'+m.group(1)]
                collections = self.args.get(u'collection[]', [])
                self.args[u'collection[]'] = collections + [u'archiveofcontemporarymusic']

        print 'args', json.dumps(self.args, indent=4)

        #urlencode does not work with unicode data
        str_args = self.utf8_encode(self.args)
        print urllib.urlencode(str_args, True)
        sys.stdout.flush()

        self.url += '?' + urllib.urlencode(str_args, True)


    def get_freedb_external_id(self):
        try:
            freedb = self.wizard.metadata['freedb.org']['releases']
            freedb_genre = freedb[0]['genre']
            freedb_id = freedb[0]['id']
            return u'urn:freedb_id:{id}'.format(id=freedb_id)
        except (LookupError, TypeError):
            return None


    def get_gracenote_metadata(self):
        try:
            gracenote = self.wizard.metadata['gracenote.com']['releases']
            gracenote_id = gracenote[0]['id']
            gracenote_genre = gracenote[0].get('genre')
            return u'urn:gracenote_id:{id}'.format(id=gracenote_id), gracenote_genre
        except (LookupError, TypeError):
            return None, None


    def make_identifier(self, args):
        id = None
        try:
            regex  = re.compile('[^a-zA-Z0-9\.\-_]+')
            artist = regex.sub('', args['creator[]'][0].lower().replace(' ', '-'))
            title  = regex.sub('', args['title'].lower().replace(' ', '-'))
            if artist and title:
                id     = u'cd_{title}_{artist}'.format(artist=artist, title=title)
        except Exception:
            pass
        return id


    def utf8_encode(self, args):
        str_args = {}
        for k, v in args.iteritems():
            if isinstance(v, unicode):
                str_args[k] = v.encode('utf-8')
            elif isinstance(v, list):
                l = []
                for item in v:
                    if isinstance(item, unicode):
                        l.append(item.encode('utf-8'))
                    else:
                        l.append(item)
                str_args[k] = l
            else:
                str_args[k] = v
        return str_args


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

