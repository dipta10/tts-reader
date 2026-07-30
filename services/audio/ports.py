from __future__ import annotations

from abc import ABC, abstractmethod


class PlaybackHandle(ABC):
    @abstractmethod
    def wait(self) -> int:
        """Block until playback completes and return the process return code."""
        ...

    @abstractmethod
    def terminate(self) -> None:
        """Stop playback as quickly and safely as possible."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        ...


class AudioPlayback(ABC):
    @abstractmethod
    def play(self, pcm: bytes, *, rate: int, speed: float, volume: float) -> PlaybackHandle:
        """Start playing the given PCM buffer and return a handle to control it."""
        ...

