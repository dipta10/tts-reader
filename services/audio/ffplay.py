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
        # TODO: LLM Generated code, yet to review this code.
        try:
            # 1. Try the polite way first (send 'q' to ffplay stdin)
            if self._proc.stdin and self._proc.poll() is None:
                try:
                    self._proc.stdin.write(b'q')
                    self._proc.stdin.flush()
                except:
                    pass

            # 2. Get the PID
            pid = self._proc.pid

            # 3. Use the Windows "Force" command
            # /F = Force, /T = Task Tree (kills children)
            import subprocess
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"Terminate error: {e}")
        finally:
            # Always run cleanup to delete the temp file
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

