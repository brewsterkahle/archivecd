# -*- mode: python -*-
a = Analysis(['wizard.py'],
             pathex=['y:\\archivecd'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)

onedir_binaries = a.binaries + [('discid.dll', 'discid.dll', 'BINARY'),
                         ('imageformats/qjpeg4.dll', 'imageformats/qjpeg4.dll', 'BINARY'),
                        ]

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='wizard.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True )
coll = COLLECT(exe,
               Tree('images', prefix='images'),
               onedir_binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='wizard')
