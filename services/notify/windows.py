from __future__ import annotations

import logging

from .ports import Notifier

logger = logging.getLogger(__name__)


class WindowsNotifier(Notifier):
    """Placeholder Windows notifier.

    TODO: Implement using WinRT or a library like win10toast if/when Windows support is needed.
    """

    def __init__(self):
        pass

    def notify(self, title: str, message: str, *, subtitle: str | None = None) -> None:  # pragma: no cover - stub
        try:
            # No-op for now
            logger.debug("WindowsNotifier.notify: %s - %s", title, message)
        except Exception:
            # Never propagate from notifier
            logger.debug("Windows notification failed", exc_info=True)

