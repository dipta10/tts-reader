from __future__ import annotations

import os
import subprocess
import tempfile

from .ports import AudioPlayback, PlaybackHandle


class _FFplayHandle(PlaybackHandle):
    def __init__(self, proc: subprocess.Popen, temp_path: str):
        self._proc = proc
        self._temp = temp_path

    def wait(self) -> int:
        try:
            stdout, stderr = self._proc.communicate()
        finally:
            self._cleanup()
        return self._proc.returncode or 0

    def terminate(self) -> None:
        try:
            if self.is_running():
                self._proc.terminate()
        finally:
            self._cleanup()

    def is_running(self) -> bool:
        return self._proc.poll() is None

    def _cleanup(self) -> None:
        if self._temp and os.path.exists(self._temp):
            try:
                os.unlink(self._temp)
            except Exception:
                pass
            finally:
                self._temp = ""


class FFplayAudio(AudioPlayback):
    def __init__(self, ffplay_path: str = "ffplay"):
        self.ffplay_path = ffplay_path

    def play(self, pcm: bytes, *, rate: int, speed: float, volume: float) -> PlaybackHandle:
        # Write PCM to temp file
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
            f.write(pcm)
            temp_path = f.name

        cmd = [
            self.ffplay_path,
            "-f", "s16le",
            "-ar", str(rate),
            temp_path,
            "-af", f"atempo={speed},volume={volume}",
            "-nodisp",
            "-autoexit",
            "-loglevel", "error",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return _FFplayHandle(proc, temp_path)

