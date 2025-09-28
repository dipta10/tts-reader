from tts import TTS
import logging
import queue
import shutil
import signal
import subprocess
import threading
import time
import platform
from locked import Locked
from services.audio import FFplayAudio

logger = logging.getLogger(__name__)

# Sentinels for streaming playback over the play_queue
STREAM_START = object()
STREAM_END = object()


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

        # Choose audio playback service (Windows first). Linux path kept inline for now.
        self.player = FFplayAudio() if self.is_windows else None
        self.play_handle = Locked(None)

        try:
            # Use Piper Python API directly
            from piper.voice import PiperVoice  # type: ignore
        except Exception:
            logger.critical("The piper python module was not found", exc_info=True)
            self.inited = False
            return
        try:
            self.piper_voice = PiperVoice.load(
                self.parsed.piper_model,
                config_path=self.parsed.piper_model_config,
                use_cuda=getattr(self.parsed, "piper_cuda", False),
            )
            model_rate = getattr(self.piper_voice.config, "sample_rate", None)
            if model_rate and getattr(self.parsed, "piper_rate", None) and self.parsed.piper_rate != model_rate:
                logger.warning(
                    "Configured piper_rate (%s) differs from model sample rate (%s); playback will use configured rate",
                    self.parsed.piper_rate,
                    model_rate,
                )
        except Exception:
            logger.critical("Failed to initialize PiperVoice from Python API", exc_info=True)
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

            item = self.play_queue.get()
            if self.reset_issued.get():
                self.play_queue.task_done()
                continue

            try:
                if item is STREAM_START:
                    # Start streaming session
                    if self.is_windows:
                        # Windows path: accumulate chunks and then play as one buffer (still reduces gen latency a bit)
                        chunks = bytearray()
                        # Gather chunks until end or reset
                        while True:
                            next_item = self.play_queue.get()
                            if next_item is STREAM_END or self.reset_issued.get():
                                self.play_queue.task_done()
                                break
                            if isinstance(next_item, (bytes, bytearray)):
                                chunks.extend(next_item)
                            self.play_queue.task_done()
                        # If reset, drop accumulated audio silently
                        if self.reset_issued.get() or len(chunks) == 0:
                            continue
                        # Delegate to AudioPlayback service as before
                        try:
                            handle = self.player.play(
                                bytes(chunks),
                                rate=self.parsed.piper_rate,
                                speed=self.parsed.speed,
                                volume=self.parsed.volume,
                            )
                            self.play_handle.set(handle)
                            while handle.is_running() and not self.reset_issued.get():
                                time.sleep(0.05)
                            if self.reset_issued.get():
                                try:
                                    handle.terminate()
                                    try:
                                        handle.wait()
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            else:
                                rc = handle.wait()
                                if rc != 0:
                                    logger.error(f"Audio playback failed with return code {rc}")
                        finally:
                            self.play_handle.set(None)
                    else:
                        # Linux path: stream into ffmpeg + aplay as chunks arrive
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
                            # Consume chunks until STREAM_END or reset
                            while True:
                                next_item = self.play_queue.get()
                                if next_item is STREAM_END or self.reset_issued.get():
                                    self.play_queue.task_done()
                                    break
                                if isinstance(next_item, (bytes, bytearray)):
                                    try:
                                        ffmpeg_proc.stdin.write(next_item)
                                    except BrokenPipeError:
                                        logger.error("ffmpeg stdin closed (BrokenPipeError), likely due to reset/termination.", exc_info=True)
                                        break
                                    except Exception as e:
                                        logger.error("Error writing to ffmpeg stdin: %s", repr(e), exc_info=True)
                                        break
                                self.play_queue.task_done()
                        finally:
                            try:
                                if ffmpeg_proc.stdin:
                                    ffmpeg_proc.stdin.close()
                            except Exception as e:
                                logger.error("Error closing ffmpeg stdin: %s", repr(e), exc_info=True)

                            aplay_proc.wait()
                            ffmpeg_proc.wait()
                else:
                    # Non-streaming single buffer (backward compatibility)
                    audio = item
                    if self.is_windows:
                        if len(audio) == 0:
                            logger.warning("No audio data to play")
                            continue
                        try:
                            handle = self.player.play(
                                audio,
                                rate=self.parsed.piper_rate,
                                speed=self.parsed.speed,
                                volume=self.parsed.volume,
                            )
                            self.play_handle.set(handle)
                            while handle.is_running() and not self.reset_issued.get():
                                time.sleep(0.05)
                            if self.reset_issued.get():
                                try:
                                    handle.terminate()
                                    try:
                                        handle.wait()
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            else:
                                rc = handle.wait()
                                if rc != 0:
                                    logger.error(f"Audio playback failed with return code {rc}")
                        finally:
                            self.play_handle.set(None)
                    else:
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
                        except BrokenPipeError:
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

            produced_any = False
            try:
                if getaudio:
                    # Accumulate for HTTP response
                    out_bytes = bytearray()
                    try:
                        for audio_bytes in self.piper_voice.synthesize_stream_raw(
                            text,
                            sentence_silence=self.parsed.piper_sentence_silence,
                        ):
                            if self.reset_issued.get():
                                break
                            if audio_bytes:
                                produced_any = True
                                out_bytes.extend(audio_bytes)
                    except Exception as e:
                        logger.error("Piper Python synthesis failed: %s", repr(e), exc_info=True)
                    out = bytes(out_bytes)
                    logger.debug(
                        f"Generated audio data: {len(out)} bytes for text: '{text[:50]}...'"
                    )
                else:
                    # Stream directly to play thread in chunks
                    try:
                        self.play_queue.put(STREAM_START)
                        for audio_bytes in self.piper_voice.synthesize_stream_raw(
                            text,
                            sentence_silence=self.parsed.piper_sentence_silence,
                        ):
                            if self.reset_issued.get():
                                break
                            if audio_bytes:
                                produced_any = True
                                self.play_queue.put(audio_bytes)
                    except Exception as e:
                        logger.error("Piper Python synthesis failed: %s", repr(e), exc_info=True)
                    finally:
                        # Always signal end-of-stream so player can close gracefully
                        self.play_queue.put(STREAM_END)
                        out = b""
            finally:
                self.gen_process.set(None)
                self.gen_queue.task_done()

            if getaudio:
                self.get_queue.put(b"" if len(out) == 0 else out)
            else:
                if not produced_any:
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
        # Prefer handle termination (Windows path)
        with self.play_handle.lock:
            if self.play_handle.data is not None:
                try:
                    self.play_handle.data.terminate()
                except Exception:
                    pass
                finally:
                    self.play_handle.set(None)
        # Fallback to raw process (Linux path)
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
        # First try via AudioPlayback handle (Windows path)
        with self.play_handle.lock:
            if self.play_handle.data is not None:
                try:
                    self.play_handle.data.terminate()
                except Exception:
                    pass
                finally:
                    self.play_handle.set(None)

        # Fallback to raw processes (primarily Linux path)
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
