from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Clipboard(ABC):
    """Technology-agnostic interface to read text from the clipboard/selection."""

    @abstractmethod
    def read_text(self) -> Optional[str]:
        """Return clipboard text or empty string; may raise on OS/command errors."""
        raise NotImplementedError

