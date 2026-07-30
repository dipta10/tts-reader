from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Notifier(ABC):
    """Technology-agnostic interface for sending desktop notifications."""

    @abstractmethod
    def notify(self, title: str, message: str, *, subtitle: Optional[str] = None) -> None:
        """Send a notification. Implementations should best-effort and never raise."""
        ...

