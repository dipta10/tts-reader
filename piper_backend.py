from tts import TTS
import importlib
import logging
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import platform
import tempfile
import os
from locked import Locked

logger = logging.getLogger(__name__)


class Piper(TTS):
    def __init__(self, parsed):
        super().__init__()
        self.parsed = parsed
        self.paused = False
        self.reset_issued = Locked(False)
        self.play_queue = queue.Queue()
        self.gen_queue = queue.Queue()
        self.get_queue = queue.Queue()
        self.get_queue_lock = threading.Lock()
        self.gen_process = Locked(None)
        self.play_process = Locked(None)
        self.ffmpeg_process = Locked(None)

        self.is_windows = platform.system() == "Windows"
        self.ffplay_path = shutil.which("ffplay")

        self.piper_path = shutil.which("piper-tts")
        if self.piper_path is None and not self.parsed.piper_python:
            logger.warning("The piper C++ executable was not found")

        self.is_piper_python = self.piper_path is None or self.parsed.piper_python
        if self.is_piper_python:
            if importlib.util.find_spec("piper") is None:
                logger.critical("The piper python module was not found")
                self.inited = False
                return

        self.gen_thread = threading.Thread(target=self.run_gen_thread, daemon=True)
        self.play_thread = threading.Thread(target=self.run_play_thread, daemon=True)

        self.gen_thread.start()
        self.play_thread.start()
        self.inited = True

    def run_play_thread(self):
        while True:
            if self.get_queue_lock.locked():
                # None of our business. User is downloading audio
                time.sleep(0.5)
                continue

            audio = self.play_queue.get()
            if self.reset_issued.get():
                self.play_queue.task_done()
                continue

            try:
                if self.is_windows:
                    # On Windows, use a temporary file approach for more reliable playback
                    # First check if we have audio data
                    if len(audio) == 0:
                        logger.warning("No audio data to play")
                        self.play_queue.task_done()
                        continue

                    # Write audio to a temporary file with padding to prevent cutoff
                    with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as temp_file:
                        temp_file.write(audio)
                        # Add 500ms of silence at the end to prevent cutoff
                        silence_samples = int(self.parsed.piper_rate * 0.5)  # 500ms of silence
                        silence_bytes = b'\x00\x00' * silence_samples  # 2 bytes per sample for s16le
                        temp_file.write(silence_bytes)
                        temp_filename = temp_file.name

                    try:
                        ffplay_cmd = [
                            "ffplay",
                            "-f", "s16le",
                            "-ar", str(self.parsed.piper_rate),
                            temp_filename,  # Remove channel specification, let ffplay auto-detect
                            "-af", f"atempo={self.parsed.speed},volume={self.parsed.volume}",  # Normal volume
                            "-nodisp",  # No video display
                            "-autoexit",  # Exit when playback finishes
                            "-loglevel", "error"  # Only show errors to reduce noise
                        ]
                        logger.debug(f"Running ffplay command: {' '.join(ffplay_cmd)}")
                        logger.debug(f"Temp file size: {os.path.getsize(temp_filename)} bytes")

                        play_proc = subprocess.Popen(
                            ffplay_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        self.play_process.set(play_proc)
                        stdout, stderr = play_proc.communicate()

                        if play_proc.returncode != 0:
                            logger.error(f"ffplay failed with return code {play_proc.returncode}")
                            logger.error(f"ffplay stderr: {stderr.decode('utf-8', errors='ignore')}")
                        else:
                            logger.debug("ffplay completed successfully")
                            if stderr:
                                logger.debug(f"ffplay stderr: {stderr.decode('utf-8', errors='ignore')}")
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(temp_filename)
                        except Exception as e:
                            logger.error("Error deleting temporary file: %s", repr(e))
                else:
                    # On Linux, use ffmpeg + aplay pipeline
                    ffmpeg_proc = subprocess.Popen(
                        [
                            "ffmpeg",
                            "-f", "s16le",
                            "-ar", str(self.parsed.piper_rate),
                            "-ac", "1",
                            "-i", "-",
                            "-af", f"atempo={self.parsed.speed},volume={self.parsed.volume}",
                            "-f", "s16le",
                            "-ar", str(self.parsed.piper_rate),
                            "-ac", "1",
                            "-",
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                    )

                    aplay_proc = subprocess.Popen(
                        ["aplay", "-f", "S16_LE", "-c", "1", "-r", str(self.parsed.piper_rate)],
                        stdin=ffmpeg_proc.stdout,
                        stdout=subprocess.PIPE,
                    )
                    self.ffmpeg_process.set(ffmpeg_proc)
                    self.play_process.set(aplay_proc)

                    try:
                        ffmpeg_proc.stdin.write(audio)
                    except BrokenPipeError as e:
                        logger.error("ffmpeg stdin closed (BrokenPipeError), likely due to reset/termination.", exc_info=True)
                    except Exception as e:
                        logger.error("Error writing to ffmpeg stdin: %s", repr(e), exc_info=True)
                    finally:
                        try:
                            ffmpeg_proc.stdin.close()
                        except Exception as e:
                            logger.error("Error closing ffmpeg stdin: %s", repr(e), exc_info=True)

                    aplay_proc.wait()
                    ffmpeg_proc.wait()
            except Exception as e:
                logger.error("Error while playing audio: %s", repr(e), exc_info=True)
            finally:
                self.ffmpeg_process.set(None)
                self.play_process.set(None)
                self.play_queue.task_done()

    def run_gen_thread(self):
        while True:
            text, getaudio = self.gen_queue.get()
            if self.reset_issued.get():
                self.gen_queue.task_done()
                continue

            try:
                prefix = [self.piper_path]
                if self.is_piper_python:
                    prefix = [sys.executable, "-m", "piper"]

                self.gen_process.set(
                    subprocess.Popen(
                        prefix
                        + [
                            "--output_raw",
                            "--sentence_silence",
                            f"{self.parsed.piper_sentence_silence}",
                            "--model",
                            self.parsed.piper_model,
                            "--config",
                            self.parsed.piper_model_config,
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                    )
                )
                out, _ = self.gen_process.get().communicate(input=text.encode())
                logger.debug(f"Generated audio data: {len(out)} bytes for text: '{text[:50]}...'")
            finally:
                self.gen_process.set(None)
                self.gen_queue.task_done()

            if getaudio:
                self.get_queue.put(b"" if len(out) == 0 else out)
            elif len(out) > 0:
                self.play_queue.put(out)
            else:
                logger.warning(f"No audio generated for text: '{text[:50]}...'")

    def speak(self, text, getaudio):
        tokens = [text]
        audio = b""

        done = lambda: audio if getaudio else None

        if self.parsed.piper_one_sentence:
            tokens = text.split(".")
            for i in range(len(tokens)):
                tokens[i] = tokens[i].strip() + "."

        self.reset_issued.set(False)

        # This lock is important because if another request arrives, results
        # could possibly get mixed up get()ing from multiple places simultaneously
        # A better solution could be a separate thread for getaudio
        with self.get_queue_lock:
            for text in tokens:
                if self.reset_issued.get():
                    return done()
                self.gen_queue.put((text, getaudio))

            if getaudio:
                for i in range(len(tokens)):
                    if self.reset_issued.get():
                        audio = b""
                        return done()
                    audio += self.get_queue.get()
                    self.get_queue.task_done()

        return done()

    def play(self):
        self.reset_issued.set(False)
        self.paused = False
        with self.play_process.lock:
            if self.play_process.data is not None and not self.is_windows:
                # Signal handling only works on Unix-like systems
                self.play_process.data.send_signal(signal.SIGCONT)

    def pause(self):
        with self.play_process.lock:
            if self.play_process.data is not None and not self.is_windows:
                # Signal handling only works on Unix-like systems
                self.play_process.data.send_signal(signal.SIGSTOP)
                self.paused = True

    def toggle(self):
        if self.paused:
            self.play()
        else:
            self.pause()

    def skip(self):
        self.play()
        with self.play_process.lock:
            if self.play_process.data is not None:
                self.play_process.data.terminate()

    def reset(self):
        # Make sure more commands aren't enqueued
        self.reset_issued.set(True)
        time.sleep(0.25)

        self.stop_gen_process()
        self.stop_play_process()

        self.paused = False

        while self.gen_queue.qsize() > 0:
            self.gen_queue.get()
            self.gen_queue.task_done()
        while self.play_queue.qsize() > 0:
            self.play_queue.get()
            self.play_queue.task_done()
        while self.get_queue.qsize() > 0:
            self.get_queue.get()
            self.get_queue.task_done()

    def stop_play_process(self):
        with self.play_process.lock:
            if self.play_process.data is not None:
                self.play_process.data.terminate()
                if not self.is_windows:
                    # SIGKILL only works on Unix-like systems
                    self.play_process.data.send_signal(signal.SIGKILL)

        with self.ffmpeg_process.lock:
            if self.ffmpeg_process.data is not None:
                self.ffmpeg_process.data.terminate()
                if not self.is_windows:
                    # SIGKILL only works on Unix-like systems
                    self.ffmpeg_process.data.send_signal(signal.SIGKILL)

    def stop_gen_process(self):
        with self.gen_process.lock:
            if self.gen_process.data is not None:
                self.gen_process.data.terminate()

    def status(self):
        return {
            "paused": self.paused,
            "reset_issued.get()": self.reset_issued.get(),
            "gen_queue.qsize()": self.gen_queue.qsize(),
            "play_queue.qsize()": self.play_queue.qsize(),
            "get_queue.qsize()": self.get_queue.qsize(),
            "gen_process.get().pid?": None
            if self.gen_process.get() is None
            else self.gen_process.get().pid,
            "play_process.get().pid?": None
            if self.play_process.get() is None
            else self.play_process.get().pid,
            "gen_thread.is_alive()": self.gen_thread.is_alive(),
            "play_thread.is_alive()": self.play_thread.is_alive(),
        }
