from distutils.core import setup
import py2exe

import sys
import os
import glob

def find_data_files(source,target,patterns):
    """Locates the specified data-files and returns the matches
    in a data_files compatible format.

    source is the root of the source data tree.
        Use '' or '.' for current directory.
    target is the root of the target data tree.
        Use '' or '.' for the distribution directory.
    patterns is a sequence of glob-patterns for the
        files you want to copy.
    """
    if glob.has_magic(source) or glob.has_magic(target):
        raise ValueError("Magic not allowed in src, target")
    ret = {}
    for pattern in patterns:
        pattern = os.path.join(source,pattern)
        for filename in glob.glob(pattern):
            if os.path.isfile(filename):
                targetpath = os.path.join(target,os.path.relpath(filename,source))
                path = os.path.dirname(targetpath)
                ret.setdefault(path,[]).append(filename)
    return sorted(ret.items())


setup(
    version = "0.1",
    description = "Internet Archive Music Locker",
    name = "ArchiveCD",

    data_files = find_data_files('.', '', ["discid.dll", "ia_logo.jpg", "logo.jpg", "mb_logo.png", "imageformats/*"]),
    options = {"py2exe": {"includes": ["sip"],        # something loaded dynamically by qt.
                          "excludes": ["_scproxy"],   # an OS X thing it tried to import
#                          "bundle_files": 1,
                         }
              },
#    zipfile = None,
    
    windows = ["wizard.py"],
    )
