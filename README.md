# Installation for developing on Windows

## Install Python and PyQT

- Download the 32-bit Python 2.7 installer from http://www.python.org/download/releases/2.7.6/. The link will be labeled '[Windows x86 MSI Installer](http://www.python.org/ftp/python/2.7.6/python-2.7.6.msi)'.
- Download the 32-bit PyQT4 installer for Python 2.7 from http://www.riverbankcomputing.com/software/pyqt/download. The link will be labeled '[PyQt4-4.10.3-gpl-Py2.7-Qt4.8.5-x32.exe](http://sourceforge.net/projects/pyqt/files/PyQt4/PyQt-4.10.3/PyQt4-4.10.3-gpl-Py2.7-Qt4.8.5-x32.exe)'.
- Download the source code from https://github.com/brewsterkahle/archivecd, either using the [Download ZIP](https://github.com/brewsterkahle/archivecd/archive/master.zip) link for using `git`.
- In the windows `cmd.exe` console, you should be able to run `wizard.py`. If you want to run from a cygwin terminal, you can type ` /cygdrive/c/Python27/python.exe  wizard.py`

## Install PyInstaller for making .exe files

- Follow the instructions at http://pythonhosted.org/PyInstaller/#installing-pyinstaller
- Install the 32-bit version of [PyWin32](http://sourceforge.net/projects/pywin32/files/pywin32/) for Python 2.7 first. The link should be labeled '[ywin32-218.win32-py2.7.exe](http://sourceforge.net/projects/pywin32/files/pywin32/Build%20218/pywin32-218.win32-py2.7.exe/download)'.
- Install [pip-win](https://sites.google.com/site/pydatalog/python/pip-for-windows) next
- Launch `pip-win` and type run `pip install PyInstaller`
- In the `cmd.exe` console, run `C:\Python27\Scripts\pyinstaller.exe pyinstaller.onefile.spec`