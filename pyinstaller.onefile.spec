# -*- mode: python -*-
from distutils.version import StrictVersion

import sys
sys.path.append(os.getcwd())
import wizard

v = StrictVersion(wizard.ArchiveWizard.version)
major, minor, patch = v.version
assert patch == 0
name = 'ArchiveCD-{major}.{minor:03d}.exe'.format(major=major, minor=minor)

a = Analysis(['wizard.py'],
             pathex=['y:\\archivecd'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)

onefile_binaries = a.binaries + [('discid.dll', 'discid.dll', 'BINARY'),
                         ('qt4_plugins/imageformats/qjpeg4.dll', 'imageformats/qjpeg4.dll', 'BINARY'),
                        ]
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          Tree('images', prefix='images'),
          onefile_binaries,
          a.zipfiles,
          a.datas,
          name=name,
          debug=False,
          strip=None,
          upx=True,
          console=True )
