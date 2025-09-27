from __future__ import annotations

import platform
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Clipboard(ABC):
    """Interface to read text from the clipboard/selection."""

    @abstractmethod
    def read_text(self) -> Optional[str]:
        raise NotImplementedError


class WindowsClipboard(Clipboard):
    def __init__(self, pyperclip_module):
        self._pyperclip = pyperclip_module

    def read_text(self) -> Optional[str]:
        # pyperclip.paste() returns str or raises; normalize None to empty string
        text = self._pyperclip.paste()
        return text or ""


class LinuxClipboard(Clipboard):
    def __init__(self, wayland: bool, wl_paste_path: Optional[str], xclip_path: Optional[str]):
        self._wayland = wayland
        self._wl_paste = wl_paste_path
        self._xclip = xclip_path
        if self._wayland:
            if not self._wl_paste:
                raise RuntimeError("Couldn't find the wl-paste binary")
        else:
            if not self._xclip:
                raise RuntimeError("Couldn't find the xclip binary")

    def read_text(self) -> Optional[str]:
        cmd = [self._wl_paste, "-p"] if self._wayland else [self._xclip, "-o", "-selection", "primary"]
        out = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        return out.decode("utf-8")


def build_clipboard(parsed) -> Optional[Clipboard]:
    """
    Return a Clipboard implementation for the current platform or None on Windows if pyperclip is missing.
    """
    system = platform.system()
    if system == "Windows":
        try:
            import pyperclip  # type: ignore
        except Exception:
            logger.warning("pyperclip not available. GET requests for clipboard reading will not work on Windows.")
            return None
        return WindowsClipboard(pyperclip)

    wl_paste = shutil.which("wl-paste")
    xclip = shutil.which("xclip")
    return LinuxClipboard(bool(getattr(parsed, "wayland", False)), wl_paste, xclip)

