from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_local_file(path: str) -> tuple[bool, str]:
    """Open a file with the OS default application (e.g. Excel for .xlsx)."""
    p = Path(path)
    if not p.is_file():
        return False, f"File not found:\n{p}"
    try:
        resolved = str(p.resolve())
        if sys.platform == "win32":
            os.startfile(resolved)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", resolved], check=False)
        else:
            subprocess.run(["xdg-open", resolved], check=False)
        return True, ""
    except OSError as e:
        return False, str(e)
