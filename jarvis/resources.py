"""Resolve bundled assets without depending on the process working directory."""

from __future__ import annotations

from pathlib import Path
import sys


def runtime_root() -> Path:
    """Return the source root or PyInstaller's unpacked application root."""
    bundled_root = getattr(sys, "_MEIPASS", None)
    return Path(bundled_root) if bundled_root else Path.cwd()


def runtime_path(relative: str | Path) -> Path:
    """Resolve a project-relative runtime asset in source or bundled mode."""
    path = Path(relative)
    if path.is_absolute():
        return path
    return runtime_root() / path
