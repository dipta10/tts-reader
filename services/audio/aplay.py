from __future__ import annotations

import subprocess

from .ports import AudioPlayback, PlaybackHandle


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

