from __future__ import annotations

import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import Optional


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


# ----------------------------
# Windows: ffplay-based player
# ----------------------------
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
        # Write PCM to temp file and append 500ms of silence to avoid tail cutoff
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
            f.write(pcm)
            silence_bytes = b"\x00\x00" * int(rate * 0.5)  # 500ms of mono s16le
            f.write(silence_bytes)
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


# ---------------------------------------
# Linux: ffmpeg filter -> aplay sink
# ---------------------------------------
class _AplayHandle(PlaybackHandle):
    def __init__(self, ffmpeg: subprocess.Popen, aplay: subprocess.Popen):
        self._ffmpeg = ffmpeg
        self._aplay = aplay

    def wait(self) -> int:
        self._aplay.wait()
        return self._ffmpeg.wait()

    def terminate(self) -> None:
        for p in (self._aplay, self._ffmpeg):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass

    def is_running(self) -> bool:
        return (self._aplay.poll() is None) or (self._ffmpeg.poll() is None)


class AplayAudio(AudioPlayback):
    def __init__(self, aplay_path: str = "aplay"):
        self.aplay_path = aplay_path

    def play(self, pcm: bytes, *, rate: int, speed: float, volume: float) -> PlaybackHandle:
        ffmpeg = subprocess.Popen(
            [
                "ffmpeg",
                "-f", "s16le",
                "-ar", str(rate),
                "-ac", "1",
                "-i", "-",
                "-af", f"atempo={speed},volume={volume}",
                "-f", "s16le",
                "-ar", str(rate),
                "-ac", "1",
                "-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        aplay = subprocess.Popen(
            [self.aplay_path, "-f", "S16_LE", "-c", "1", "-r", str(rate)],
            stdin=ffmpeg.stdout,
            stdout=subprocess.PIPE,
        )
        # Feed and close input upfront (single buffer playback)
        if ffmpeg.stdin is not None:
            try:
                ffmpeg.stdin.write(pcm)
            finally:
                ffmpeg.stdin.close()
        return _AplayHandle(ffmpeg, aplay)

