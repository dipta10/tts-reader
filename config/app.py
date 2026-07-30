from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application-level configuration for the HTTP server."""

    ip: str = "127.0.0.1"
    port: int = 5000
    debug: bool = False
    log_level: str = "INFO"
