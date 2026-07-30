"""Platform detection utilities for cross-platform service selection."""

from __future__ import annotations

import platform
from typing import Literal


PlatformName = Literal["Windows", "Linux", "Darwin", "Unknown"]


class Platform:
    """Centralized platform detection for consistent behavior across factories."""

    _cached_system: PlatformName | None = None

    @classmethod
    def system(cls) -> PlatformName:
        """Get the current platform name (cached for performance).

        Returns:
            One of: "Windows", "Linux", "Darwin", or "Unknown"
        """
        if cls._cached_system is None:
            system = platform.system()
            if system in ("Windows", "Linux", "Darwin"):
                cls._cached_system = system  # type: ignore
            else:
                cls._cached_system = "Unknown"
        return cls._cached_system

    @classmethod
    def is_windows(cls) -> bool:
        """Check if running on Windows."""
        return cls.system() == "Windows"

    @classmethod
    def is_linux(cls) -> bool:
        """Check if running on Linux."""
        return cls.system() == "Linux"

    @classmethod
    def is_macos(cls) -> bool:
        """Check if running on macOS."""
        return cls.system() == "Darwin"
