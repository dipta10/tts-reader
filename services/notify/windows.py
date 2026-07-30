from __future__ import annotations

import logging
from typing import Optional

from .ports import Notifier

logger = logging.getLogger(__name__)

try:
    from winotify import Notification  # type: ignore
    WINOTIFY_AVAILABLE = True
except Exception:  # pragma: no cover
    WINOTIFY_AVAILABLE = False


class WindowsNotifier(Notifier):
    """Windows notifier using winotify library.

    Uses Windows toast notifications via winotify, which is compatible with Python 3.13+.
    """

    def __init__(self, app_name: str = "tts-reader"):
        self._app_name = app_name
        self._available = WINOTIFY_AVAILABLE

        if not self._available:
            logger.warning("winotify not available; notifications disabled")
        else:
            logger.info("Windows notifications initialized with winotify")

    def notify(self, title: str, message: str, *, subtitle: Optional[str] = None) -> None:
        if not self._available:
            return

        try:
            # Create notification
            notif_title = title if title else self._app_name

            toast = Notification(
                app_id=self._app_name,
                title=notif_title,
                msg=message,
                duration="short"  # "short" or "long"
            )

            # Show the notification
            toast.show()

        except Exception:
            # Never let notifications break app flow
            logger.error("Notification send failed", exc_info=True)

