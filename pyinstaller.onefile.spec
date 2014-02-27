# -*- mode: python -*-
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
          name='wizard.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True )
