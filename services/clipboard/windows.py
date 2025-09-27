from __future__ import annotations

from typing import Optional

from .ports import Clipboard


class WindowsClipboard(Clipboard):
    def __init__(self, pyperclip_module):
        self._pyperclip = pyperclip_module

    def read_text(self) -> Optional[str]:
        text = self._pyperclip.paste()
        return text or ""

