from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Dict, Optional, Union

from unidecode import unidecode

from services.clipboard import Clipboard
from tts import TTS
from .ports import ReaderController

logger = logging.getLogger(__name__)


class DefaultReaderController(ReaderController):
    """Application-level controller orchestrating clipboard, sanitization, and TTS.

    Keeps HTTP-independent logic here; web layer provides only decoded text and flags.
    """

    def __init__(self, *, parsed, tts: TTS, clipboard: Optional[Clipboard]):
        self.parsed = parsed
        self.tts = tts
        self.clipboard = clipboard
        self.begin_time = time.time()

        # Clamp initial values defensively
        self.parsed.volume = max(0.0, min(self.parsed.volume, 1.0))
        self.parsed.speed = max(0.0, min(self.parsed.speed, 10.0))

    # -----------------
    # Public operations
    # -----------------
    def read_text(self, text: str, getaudio: bool) -> Union[bytes, str]:
        text = self._sanitize_text(text)
        if not text:
            s = "Skipped processing empty text"
            self._notify(s)
            return s

        s = f"Queued text of {len(text)} characters for the TTS"
        self._notify(s)
        audio = self.tts.speak(text, getaudio)
        return audio if getaudio else s

    def read_clipboard(self, getaudio: bool) -> Union[bytes, str]:
        if self.clipboard is None:
            s = "Clipboard not available. Cannot read clipboard on this platform."
            logger.error(s)
            self._notify(s)
            return s

        try:
            raw = self.clipboard.read_text() or ""
            return self.read_text(raw, getaudio)
        except Exception as e:
            s = "Failed to get the clipboard contents"
            logger.error("%s: %s", s, repr(e))
            self._notify(s)
            return s

    def status(self) -> Dict[str, Any]:
        return {
            "self": {
                "uptime()": self._uptime(),
                "parsed": self.parsed.__dict__,
            },
            "self.tts": self.tts.status(),
        }

    def toggle(self) -> None:
        self.tts.toggle()

    def play(self) -> None:
        self.tts.play()

    def pause(self) -> None:
        self.tts.pause()

    def reset(self) -> None:
        self.tts.reset()

    def skip(self) -> None:
        self.tts.skip()

    def set_speed(self, value: float) -> None:
        self.parsed.speed = max(0.0, min(value, 10.0))

    def set_volume(self, value: float) -> None:
        self.parsed.volume = max(0.0, min(value, 1.0))

    # -----------------
    # Internal helpers
    # -----------------
    def _sanitize_text(self, text: str) -> str:
        # Remove ignored chars
        for ch in getattr(self.parsed, "ignore_chars", []) or []:
            text = text.replace(ch, "")
        # Collapse newlines if requested
        if getattr(self.parsed, "ignore_newline", False):
            text = text.replace("\n", " ").replace("\r", " ")
        # Normalize unicode and hyphen artifacts
        text = unidecode(text.strip()).replace("‐\n", "").replace("‐ ", "")
        return text

    def _uptime(self) -> str:
        diff = time.time() - self.begin_time
        return str(datetime.timedelta(seconds=int(diff)))

    def _notify(self, msg: str) -> None:
        # Placeholder for a notifier service; currently a no-op
        pass

