from distutils.core import setup
import py2exe

setup(
    version = "0.0.0",
    description = "Internet Archive audio cd tool thing-y",
    name = "ArchiveCD",

    data_files = [(".", ["discid.dll"])],             # dynamically loaded by us
    options = {"py2exe": {"includes": ["sip"],        # something loaded dynamically by qt.
                          "excludes": ["_scproxy"],   # an OS X thing it tried to import
                          "bundle_files": 1,
# Uncomment these lines if we want to halve the size of the exacutable.
#                          "optimize": 2,
#                          "compressed": True,
                      }},
    zipfile = None,
    
    windows = ["wizard.py"],
    )
