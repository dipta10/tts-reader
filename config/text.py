from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TextConfig:
    """Configuration for text processing and sanitization."""

    ignore_chars: List[str] = field(default_factory=list)
    ignore_newline: bool = False
