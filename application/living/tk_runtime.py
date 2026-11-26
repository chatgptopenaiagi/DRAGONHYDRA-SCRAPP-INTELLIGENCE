"""Locate the base Python installation's Tcl and Tk data for a Windows source venv."""
import os
from pathlib import Path
import sys


def configure():
    if os.name != 'nt' or getattr(sys, 'frozen', False):
        return
    import _tkinter
    base = Path(sys.base_prefix) / 'tcl'
    for key, folder in [('TCL_LIBRARY', 'tcl' + _tkinter.TCL_VERSION),
                        ('TK_LIBRARY', 'tk' + _tkinter.TK_VERSION)]:
        library = base / folder
        if library.is_dir():
            os.environ.setdefault(key, str(library))
