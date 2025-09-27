from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from .ports import Clipboard


class LinuxClipboard(Clipboard):
    def __init__(self, wayland: bool):
        self._wayland = wayland
        if self._wayland:
            self._wl_paste = shutil.which("wl-paste")
            if not self._wl_paste:
                raise RuntimeError("Couldn't find the wl-paste binary")
        else:
            self._xclip = shutil.which("xclip")
            if not self._xclip:
                raise RuntimeError("Couldn't find the xclip binary")

    def read_text(self) -> Optional[str]:
        cmd = [self._wl_paste, "-p"] if self._wayland else [self._xclip, "-o", "-selection", "primary"]
        out = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        return out.decode("utf-8")

