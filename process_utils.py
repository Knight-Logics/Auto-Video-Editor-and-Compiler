"""
Windows-safe subprocess helpers (no console flash).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Optional

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_SW_HIDE = 0


def hidden_creationflags(extra: int = 0) -> int:
    """Creation flags that prevent a visible console on Windows."""
    if os.name != "nt":
        return extra
    flags = extra
    if _CREATE_NO_WINDOW:
        flags |= _CREATE_NO_WINDOW
    return flags


def hidden_startupinfo() -> Optional[subprocess.STARTUPINFO]:
    """STARTUPINFO that keeps child processes off the taskbar/console."""
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = _SW_HIDE
    return info


def _apply_hidden_defaults(kwargs: dict) -> None:
    if os.name != "nt":
        return
    existing = int(kwargs.get("creationflags") or 0)
    kwargs["creationflags"] = hidden_creationflags(existing)
    if kwargs.get("startupinfo") is None:
        kwargs["startupinfo"] = hidden_startupinfo()


def popen_hidden(args, **kwargs: Any) -> subprocess.Popen:
    """subprocess.Popen without a visible CMD window on Windows."""
    _apply_hidden_defaults(kwargs)
    return subprocess.Popen(args, **kwargs)


def run_hidden(args, **kwargs: Any) -> subprocess.CompletedProcess:
    """subprocess.run without a visible CMD window on Windows."""
    _apply_hidden_defaults(kwargs)
    return subprocess.run(args, **kwargs)
