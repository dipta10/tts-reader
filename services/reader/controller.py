from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Dict, Optional, Union

from unidecode import unidecode

from services.clipboard import Clipboard
from tts import TTS
from .ports import ReaderController
from services.notify import Notifier


logger = logging.getLogger(__name__)


class DefaultReaderController(ReaderController):
    """Application-level controller orchestrating clipboard, sanitization, and TTS.

    Keeps HTTP-independent logic here; web layer provides only decoded text and flags.
    """

    def __init__(self, *, parsed, tts: TTS, clipboard: Optional[Clipboard], notifier: Optional[Notifier] = None):
        self.parsed = parsed
        self.tts = tts
        self.clipboard = clipboard
        self.notifier = notifier
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
        self._notify("Playback toggled")

    def play(self) -> None:
        self.tts.play()
        self._notify("Playback resumed")

    def pause(self) -> None:
        self.tts.pause()
        self._notify("Playback paused")

    def reset(self) -> None:
        self.tts.reset()
        self._notify("Reset issued")

    def skip(self) -> None:
        self.tts.skip()
        self._notify("Skipped current item")

    def set_speed(self, value: float) -> None:
        self.parsed.speed = max(0.0, min(value, 10.0))
        self._notify(f"Speed set to {self.parsed.speed:.2f}x")

    def set_volume(self, value: float) -> None:
        self.parsed.volume = max(0.0, min(value, 1.0))
        self._notify(f"Volume set to {self.parsed.volume:.2f}")

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
        try:
            if getattr(self, "notifier", None) is not None:
                self.notifier.notify("TTS Reader", msg)
        except Exception:
            logger.debug("Notifier failed", exc_info=True)

