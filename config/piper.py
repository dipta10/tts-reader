from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PiperConfig:
    """Configuration for Piper TTS backend."""

    model: Optional[str] = None
    model_config: Optional[str] = None
    rate: int = 22050
    sentence_silence: float = 0.8
    one_sentence: bool = False
    volume: float = 1.0
    speed: float = 1.0

    def __post_init__(self):
        """Validate and clamp configuration values."""
        # Clamp volume to [0, 1]
        self.volume = max(0.0, min(self.volume, 1.0))
        # Clamp speed to [0, 10]
        self.speed = max(0.0, min(self.speed, 10.0))
