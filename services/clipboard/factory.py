from __future__ import annotations

import logging
import platform
from typing import Optional

from .ports import Clipboard
from .windows import WindowsClipboard
from .linux import LinuxClipboard

logger = logging.getLogger(__name__)


def build_clipboard(parsed) -> Optional[Clipboard]:
    system = platform.system()
    if system == "Windows":
        try:
            import pyperclip  # type: ignore[import]
        except Exception:
            logger.warning("pyperclip not available. GET requests for clipboard reading will not work on Windows.")
            return None
        return WindowsClipboard(pyperclip)

    return LinuxClipboard(bool(getattr(parsed, "wayland", False)))

