from tts import TTS
import logging
import config
import time
import shutil
import threading
import signal
import subprocess
import queue
from locked import Locked

logger = logging.getLogger(__name__)


class Piper(TTS):
    def __init__(self, parsed):
        TTS.__init__(self)
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
        self.gen_thread = threading.Thread(target=self.run_gen_thread, daemon=True)
        self.play_thread = threading.Thread(target=self.run_play_thread, daemon=True)

        self.gen_thread.start()
        self.play_thread.start()

    def run_play_thread(self):
        while True:
            audio = self.play_queue.get()
            if self.reset_issued.get():
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
                            f"atempo={self.parsed.playback_speed},volume={self.parsed.volume}",
                            "-f",
                            "s16le",
                            "-ar",
                            f"{self.parsed.playback_sample_rate}",
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
                self.play_queue_size.set(self.play_queue_size.get() - len(audio))
                self.play_queue_size.set(max(0, self.play_queue_size.get()))

    def run_gen_thread(self):
        while True:
            text = self.gen_queue.get()
            if self.reset_issued.get():
                continue

            try:
                self.gen_process.set(
                    subprocess.Popen(
                        [
                            self.piper_path,
                            "--output_raw",
                            "--sentence_silence",
                            f"{self.parsed.sentence_silence}",
                            "--model",
                            self.parsed.model,
                            "--config",
                            self.parsed.model_config,
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                    )
                )
                out, _ = self.gen_process.get().communicate(input=text.encode())
            finally:
                self.gen_process.set(None)
                self.gen_queue.task_done()
                self.gen_queue_size.set(self.gen_queue_size.get() - len(text))
                self.gen_queue_size.set(max(0, self.gen_queue_size.get()))

            if len(out) > 0:
                self.play_queue.put(out)
                self.play_queue_size.set(self.play_queue_size.get() + len(out))

    def speak(self, text):
        if len(text) > 0:
            self.reset_issued.set(False)
            self.gen_queue.put(text)
            self.gen_queue_size.set(self.gen_queue_size.get() + len(text))

    def is_speaking(self):
        pass

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

        self.paused = False

        while self.gen_queue.qsize() > 0:
            self.gen_queue.get()
            self.gen_queue.task_done()
        while self.play_queue.qsize() > 0:
            self.play_queue.get()
            self.play_queue.task_done()

        self.gen_queue_size.set(0)
        self.play_queue_size.set(0)

        self.stop_gen_process()
        self.stop_play_process()

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
