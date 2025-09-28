from __future__ import annotations

import logging
from typing import Optional

from .ports import Notifier

logger = logging.getLogger(__name__)

try:
    from desktop_notifier import DesktopNotifier  # type: ignore
except Exception:  # pragma: no cover
    DesktopNotifier = None  # type: ignore


class LinuxNotifier(Notifier):
    def __init__(self, app_name: str = "tts-reader"):
        self._app_name = app_name
        self._notifier = None
        try:
            if DesktopNotifier is not None:
                self._notifier = DesktopNotifier(app_name=app_name)
            else:
                logger.warning("desktop-notifier not available; notifications disabled")
        except Exception:
            logger.warning("Failed to initialize DesktopNotifier; notifications disabled", exc_info=True)
            self._notifier = None

    def notify(self, title: str, message: str, *, subtitle: Optional[str] = None) -> None:
        if self._notifier is None:
            return
        try:
            # Use synchronous API to avoid dealing with event loops
            self._notifier.send_sync(title if title else self._app_name, message)
        except Exception:
            # Never let notifications break app flow
            logger.error("Notification send failed", exc_info=True)

