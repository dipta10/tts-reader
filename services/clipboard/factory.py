from __future__ import annotations

import logging
import platform
from typing import Optional

from .ports import Clipboard
from .windows import WindowsClipboard
from .linux import LinuxClipboard

logger = logging.getLogger(__name__)


def build_clipboard(use_wayland: bool = False) -> Optional[Clipboard]:
    """Factory function to build platform-specific clipboard implementation.

    Args:
        use_wayland: If True, use wl-paste on Linux (Wayland). If False, use xclip (X11).
                     Ignored on Windows.

    Returns:
        Clipboard implementation appropriate for the current platform, or None if unavailable.
        - Windows: WindowsClipboard (requires pyperclip)
        - Linux: LinuxClipboard (requires wl-paste or xclip binaries)
    """
    system = platform.system()
    if system == "Windows":
        try:
            import pyperclip  # type: ignore[import]
        except Exception:
            logger.warning("pyperclip not available. GET requests for clipboard reading will not work on Windows.")
            return None
        return WindowsClipboard(pyperclip)

    return LinuxClipboard(use_wayland)

