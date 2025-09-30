from __future__ import annotations

import logging
import platform
from typing import Optional

from .ports import Notifier
from .linux import LinuxNotifier
from .windows import WindowsNotifier

logger = logging.getLogger(__name__)


def build_notifier(app_name: str = "tts-reader") -> Optional[Notifier]:
    """Return a best-effort Notifier for the current platform, or None if unavailable.

    Args:
        app_name: The application name to display in notifications.
    """
    system = platform.system()
    try:
        if system == "Windows":
            return WindowsNotifier(app_name=app_name)
        # Default to Linux for everything else (Linux, Darwin with XDG portals, etc.)
        return LinuxNotifier(app_name=app_name)
    except Exception:
        logger.warning("Failed to initialize notifier; continuing without notifications", exc_info=True)
        return None

