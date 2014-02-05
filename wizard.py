#!/usr/bin/env python

from PyQt4 import QtCore, QtGui
import sys
import json
import urllib


# ArchiveWizard
#_________________________________________________________________________________________
class ArchiveWizard(QtGui.QWizard):
    def __init__(self, parent=None):
        QtGui.QWizard.__init__(self, parent)

        self.intro_page        = IntroPage(self)
        self.scan_drives_page  = ScanDrivesPage(self)
        self.read_toc_page     = ReadTOCPage(self)
        self.lookup_cd_page    = LookupCDPage(self)

        self.addPage(self.intro_page)
        self.addPage(self.scan_drives_page)
        self.addPage(self.read_toc_page)
        self.addPage(self.lookup_cd_page)


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

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.status_label)

        self.setLayout(self.layout)
        self.is_complete = False


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
        if len(obj) == 1:
            self.show_single_result(obj)


    def get_cover_image(self, metadata):
        img = None
        for f in metadata['files']:
            print f
            if f['name'].endswith('_thumb.jpg'):
                img = f['name']
                break
            #todo: set image if itemimage.jpg not found
        return img


    def fetch_ia_metadata(self, itemid):
        url = 'https://archive.org/metadata/'+itemid
        metadata = json.load(urllib.urlopen(url))
        #print metadata
        md = {'img': self.get_cover_image(metadata),
              'title': metadata['metadata']['title'],
              'creator': metadata['metadata']['creator'],
             }
        return md

        
    def show_single_result(self, obj):
        self.status_label.setText('A match for this CD was found in our database')
        item_id = obj[0][0]
        md = self.fetch_ia_metadata(item_id)
        if md['img'] is not None:
            img_label = QtGui.QLabel()
            img_url = "https://archive.org/download/{id}/{img}".format(id=item_id, img=md['img'])
            print img_url
            data = urllib.urlopen(img_url).read()
            img = QtGui.QImage()
            img.loadFromData(data)
            img_label.setPixmap(QtGui.QPixmap(img).scaledToWidth(100))
            self.layout.addWidget(img_label)

        title_label = QtGui.QLabel(md['title'])
        creator_label = QtGui.QLabel(md['creator'])

        self.layout.addWidget(title_label)
        self.layout.addWidget(creator_label)

        yes_button = QtGui.QRadioButton("This is my CD")
        no_button  = QtGui.QRadioButton("My CD is different from the one shown above")
        self.layout.addWidget(yes_button)
        self.layout.addWidget(no_button)
        yes_button.setChecked(True)



    def isComplete(self):
        return self.is_complete


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wizard = ArchiveWizard()
    sys.exit(wizard.exec_())

