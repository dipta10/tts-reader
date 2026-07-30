from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Union


class ReaderController(ABC):
    @abstractmethod
    def read_text(self, text: str, getaudio: bool) -> Union[bytes, str]:
        ...

    @abstractmethod
    def read_clipboard(self, getaudio: bool) -> Union[bytes, str]:
        ...

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def toggle(self) -> None:
        ...

    @abstractmethod
    def play(self) -> None:
        ...

    @abstractmethod
    def pause(self) -> None:
        ...

    @abstractmethod
    def reset(self) -> None:
        ...

    @abstractmethod
    def skip(self) -> None:
        ...

    @abstractmethod
    def set_speed(self, value: float) -> None:
        ...

    @abstractmethod
    def set_volume(self, value: float) -> None:
        ...

