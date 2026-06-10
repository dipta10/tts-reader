from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from .ports import AudioPlayback, PlaybackHandle

logger = logging.getLogger(__name__)


class _FFplayHandle(PlaybackHandle):
    def __init__(self, proc: subprocess.Popen, temp_path: str):
        self._proc = proc
        self._temp = temp_path

    def wait(self) -> int:
        try:
            self._proc.wait()
        finally:
            self._cleanup()
        return self._proc.returncode or 0

    def terminate(self) -> None:
        try:
            if self._proc.poll() is None:
                logger.info("Force-stopping ffplay pid=%s", self._proc.pid)
                self._proc.kill()

                try:
                    self._proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass

            if self._proc.poll() is None:
                logger.info("Force-stopping ffplay process tree pid=%s", self._proc.pid)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    timeout=2,
                    check=False,
                )
                try:
                    self._proc.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    logger.warning("ffplay pid=%s still running after taskkill", self._proc.pid)
        except Exception as e:
            logger.warning("Terminate error for ffplay pid=%s: %s", self._proc.pid, repr(e), exc_info=True)
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

    def terminate_all(self) -> None:
        exe_name = os.path.basename(self.ffplay_path) or "ffplay"
        if not exe_name.lower().endswith(".exe"):
            exe_name = f"{exe_name}.exe"

        logger.info("Force-stopping all %s processes", exe_name)
        subprocess.run(
            ["taskkill", "/F", "/T", "/IM", exe_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            timeout=2,
            check=False,
        )

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
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        logger.debug("Started ffplay pid=%s temp=%s bytes=%s", proc.pid, temp_path, len(pcm))
        return _FFplayHandle(proc, temp_path)

