from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from .ports import Clipboard


class LinuxClipboard(Clipboard):
    def __init__(self, wayland: bool):
        self._wayland = wayland
        self._wl_paste = shutil.which("wl-paste")
        if self._wayland and not self._wl_paste:
            raise RuntimeError("Couldn't find the wl-paste binary")

        self._xclip = shutil.which("xclip")
        if not self._wayland and not self._xclip:
            raise RuntimeError("Couldn't find the xclip binary")

        self.commands = [
            [self._wl_paste, "-p"],
            [self._xclip, "-o", "-selection", "primary"]
        ]

    def read_text(self) -> Optional[str]:
        for cmd in self.commands:
            try:
                out = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
                return out.decode("utf-8")
            except subprocess.CalledProcessError:
                pass

        raise RuntimeError("Failed to read clipboard with both wl-paste and xclip")
