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
        self.play_queue_size = Locked(0)
        self.gen_queue_size = Locked(0)
        self.gen_process = Locked(None)
        self.play_process = Locked(None)

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
            audio = self.play_queue.get()
            if self.reset_issued.get():
                self.play_queue.task_done()
                continue

            try:
                self.play_process.set(
                    subprocess.Popen(
                        [
                            self.ffplay_path,
                            "-hide_banner",
                            "-loglevel",
                            "panic",
                            "-nostats",
                            "-autoexit",
                            "-nodisp",
                            "-af",
                            f"atempo={self.parsed.speed},volume={self.parsed.volume}",
                            "-f",
                            "s16le",
                            "-ar",
                            f"{self.parsed.piper_rate}",
                            "-ac",
                            "1",
                            "-",
                        ],
                        stdin=subprocess.PIPE,
                    )
                )
                self.play_process.get().communicate(input=audio)
            finally:
                self.play_process.set(None)
                self.play_queue.task_done()
                with self.play_queue_size.lock:
                    self.play_queue_size.data = self.play_queue_size.data - len(audio)
                    self.play_queue_size.data = max(0, self.play_queue_size.data)

    def run_gen_thread(self):
        while True:
            text = self.gen_queue.get()
            if self.reset_issued.get():
                self.gen_queue.task_done()
                continue

            try:
                prefix = (
                    [sys.executable, "-m", "piper"]
                    if self.is_piper_python
                    else [self.piper_path]
                )
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
            finally:
                self.gen_process.set(None)
                self.gen_queue.task_done()
                with self.gen_queue_size.lock:
                    self.gen_queue_size.data = self.gen_queue_size.data - len(audio)
                    self.gen_queue_size.data = max(0, self.gen_queue_size.data)

            if len(out) > 0:
                self.play_queue.put(out)
                with self.play_queue_size.lock:
                    self.play_queue_size.data += len(out)

    def speak(self, text):
        if len(text) > 0:
            self.reset_issued.set(False)
            self.gen_queue.put(text)
            with self.gen_queue_size.lock:
                self.gen_queue_size.data += len(text)

    def play(self):
        self.reset_issued.set(False)
        self.paused = False
        with self.play_process.lock:
            if self.play_process.data is not None:
                self.play_process.data.send_signal(signal.SIGCONT)

    def pause(self):
        with self.play_process.lock:
            if self.play_process.data is not None:
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
        self.stop_gen_process()
        self.stop_play_process()

        self.paused = False

        while self.gen_queue.qsize() > 0:
            self.gen_queue.get()
            self.gen_queue.task_done()
        while self.play_queue.qsize() > 0:
            self.play_queue.get()
            self.play_queue.task_done()

        self.gen_queue_size.set(0)
        self.play_queue_size.set(0)

    def stop_play_process(self):
        with self.play_process.lock:
            if self.play_process.data is not None:
                self.play_process.data.terminate()

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
            "gen_queue_size.get() / 1024**2": self.gen_queue_size.get() / 1024**2,
            "play_queue_size.get() / 1024**2": self.play_queue_size.get() / 1024**2,
            "gen_process.get().pid?": None
            if self.gen_process.get() is None
            else self.gen_process.get().pid,
            "play_process.get().pid?": None
            if self.play_process.get() is None
            else self.play_process.get().pid,
            "gen_thread.is_alive()": self.gen_thread.is_alive(),
            "play_thread.is_alive()": self.play_thread.is_alive(),
        }
