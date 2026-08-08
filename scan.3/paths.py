"""Where QuickScan keeps the data it accumulates.

Not beside the program. The packaged application lives in a folder that gets
replaced wholesale on every rebuild or reinstall, so anything written there is
one update away from being deleted, and it would go without warning: the app
would simply start again from an empty history and look like it was working.

The signal log behind the calibration warnings represents months of recorded
outcomes and cannot be regenerated, which is what makes this worth doing
properly rather than leaving as it was.
"""
from __future__ import annotations

import os
import shutil
import sys
from typing import Optional


def resource_dir() -> str:
    """Where read-only bundled assets live.

    PyInstaller unpacks --add-data into _MEIPASS; running from source it is
    simply the project folder.
    """
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    """The per-user directory for logs, created if it is missing."""
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    path = os.path.join(base, 'QuickScan')
    os.makedirs(path, exist_ok=True)
    return path


def legacy_dir() -> str:
    """Where these files used to live: next to the source modules."""
    return os.path.dirname(os.path.abspath(__file__))


def migrate(filename: str, destination: Optional[str] = None) -> Optional[str]:
    """Move a data file out of the program folder, once.

    Copies rather than moves, and leaves the original behind renamed. A failed
    migration that loses the only copy of an unrepeatable log would be far
    worse than one that leaves a stray file, so the safe direction is the one
    that keeps two copies until the user is satisfied.

    Returns the path it was recovered from, or None if there was nothing to do.
    """
    target_dir = destination or data_dir()
    target = os.path.join(target_dir, filename)
    if os.path.exists(target):
        return None                     # already migrated, or already in use

    source = os.path.join(legacy_dir(), filename)
    if not os.path.isfile(source) or os.path.samefile(legacy_dir(), target_dir):
        return None

    shutil.copy2(source, target)
    if os.path.getsize(target) != os.path.getsize(source):
        os.remove(target)               # partial copy: better to have not tried
        raise OSError(f'copying {filename} to {target_dir} was incomplete')
    try:
        os.replace(source, source + '.migrated')
    except OSError:
        pass                            # the copy is what matters
    return source
