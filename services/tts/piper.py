from .ports import TTS
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
from config import PiperConfig

logger = logging.getLogger(__name__)

# Sentinels for streaming playback over the play_queue
STREAM_START = object()
STREAM_END = object()
RESET = object()


class Piper(TTS):
    def __init__(self, config: PiperConfig):
        super().__init__()
        self.config = config
        self.paused = False
        self.reset_issued = Locked(False)
        self.reset_epoch = Locked(0)
        self.play_queue = queue.Queue()
        self.gen_queue = queue.Queue()
        self.get_queue = queue.Queue()
        self.get_queue_lock = threading.Lock()
        self.gen_process = Locked(None)
        self.play_process = Locked(None)
        self.ffmpeg_process = Locked(None)
        self.active_play_handles = Locked([])

        self.is_windows = platform.system() == "Windows"
        self.ffplay_path = shutil.which("ffplay")

        # Choose audio playback service (Windows first). Linux path kept inline for now.
        self.player = FFplayAudio() if self.is_windows else None
        self.play_handle = Locked((None, None))

        try:
            # Use Piper Python API directly
            from piper.voice import PiperVoice  # type: ignore
        except Exception:
            logger.critical("The piper python module was not found", exc_info=True)
            self.inited = False
            return
        try:
            self.piper_voice = PiperVoice.load(
                self.config.model,
                config_path=self.config.model_config,
                use_cuda=False,  # CUDA support can be added to PiperConfig if needed
            )
            model_rate = getattr(self.piper_voice.config, "sample_rate", None)
            if model_rate and self.config.rate and self.config.rate != model_rate:
                logger.warning(
                    "Configured rate (%s) differs from model sample rate (%s); playback will use configured rate",
                    self.config.rate,
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

    def _drain_queue(self, q: queue.Queue) -> int:
        drained = 0
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break
            else:
                q.task_done()
                drained += 1
        return drained

    def _take_play_handle(self):
        with self.play_handle.lock:
            _, handle = self.play_handle.data
            self.play_handle.data = (None, None)
            return handle

    def _set_play_handle(self, epoch, handle):
        with self.play_handle.lock:
            self.play_handle.data = (epoch, handle)

    def _clear_play_handle(self, epoch):
        with self.play_handle.lock:
            current_epoch, _ = self.play_handle.data
            if current_epoch == epoch:
                self.play_handle.data = (None, None)

    def _next_reset_epoch(self) -> int:
        with self.reset_epoch.lock:
            self.reset_epoch.data += 1
            return self.reset_epoch.data

    def _current_reset_epoch(self) -> int:
        return self.reset_epoch.get()

    def _register_play_handle(self, epoch, handle) -> None:
        with self.active_play_handles.lock:
            handles = list(self.active_play_handles.data)
            handles.append((epoch, handle))
            self.active_play_handles.data = handles

    def _unregister_play_handle(self, handle) -> None:
        with self.active_play_handles.lock:
            handles = [entry for entry in self.active_play_handles.data if entry[1] is not handle]
            self.active_play_handles.data = handles

    def _terminate_all_play_handles(self, *, reason: str) -> int:
        with self.active_play_handles.lock:
            handles = list(self.active_play_handles.data)
            self.active_play_handles.data = []

        terminated = 0
        for epoch, handle in handles:
            try:
                logger.info("Terminating playback handle: reason=%s epoch=%s", reason, epoch)
                handle.terminate()
                terminated += 1
            except Exception:
                logger.warning("Failed to terminate playback handle: reason=%s epoch=%s", reason, epoch, exc_info=True)

        return terminated

    def run_play_thread(self):
        while True:
            if self.get_queue_lock.locked():
                # None of our business. User is downloading audio
                time.sleep(0.5)
                continue

            item_epoch, item = self.play_queue.get()
            current_epoch = self._current_reset_epoch()
            if item_epoch != current_epoch:
                logger.debug(
                    "Dropping stale play item: item_epoch=%s current_epoch=%s item_type=%s",
                    item_epoch,
                    current_epoch,
                    type(item).__name__,
                )
                self.play_queue.task_done()
                continue

            if self.reset_issued.get():
                self.play_queue.task_done()
                continue

            try:
                if item is RESET:
                    logger.debug("Play thread received RESET sentinel")
                    continue

                if item is STREAM_START:
                    # Start streaming session
                    logger.debug("Play thread started streaming playback session for epoch=%s", item_epoch)
                    if self.is_windows:
                        # Windows path: accumulate chunks and then play as one buffer (still reduces gen latency a bit)
                        chunks = bytearray()
                        # Gather chunks until end or reset
                        while True:
                            next_epoch, next_item = self.play_queue.get()
                            if (
                                next_item is RESET
                                or next_item is STREAM_END
                                or self.reset_issued.get()
                                or next_epoch != item_epoch
                                or item_epoch != self._current_reset_epoch()
                            ):
                                self.play_queue.task_done()
                                break
                            if isinstance(next_item, (bytes, bytearray)):
                                chunks.extend(next_item)
                            self.play_queue.task_done()
                        # If reset, drop accumulated audio silently
                        if item_epoch != self._current_reset_epoch() or self.reset_issued.get() or len(chunks) == 0:
                            continue
                        # Delegate to AudioPlayback service as before
                        handle = None
                        handle_epoch = None
                        try:
                            handle = self.player.play(
                                bytes(chunks),
                                rate=self.config.rate,
                                speed=self.config.speed,
                                volume=self.config.volume,
                            )
                            handle_epoch = self._current_reset_epoch()
                            self._set_play_handle(handle_epoch, handle)
                            self._register_play_handle(handle_epoch, handle)
                            logger.debug(
                                "Started Windows playback: bytes=%s rate=%s speed=%s volume=%s",
                                len(chunks),
                                self.config.rate,
                                self.config.speed,
                                self.config.volume,
                            )
                            while handle.is_running() and handle_epoch == self._current_reset_epoch() and not self.reset_issued.get():
                                time.sleep(0.05)
                            if handle_epoch != self._current_reset_epoch() or self.reset_issued.get():
                                logger.debug(
                                    "Stopping Windows playback for stale/reset epoch=%s current_epoch=%s",
                                    handle_epoch,
                                    self._current_reset_epoch(),
                                )
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
                            if handle is not None:
                                self._unregister_play_handle(handle)
                            if handle_epoch is not None:
                                self._clear_play_handle(handle_epoch)
                    else:
                        # Linux path: stream into ffmpeg + aplay as chunks arrive
                        ffmpeg_proc = subprocess.Popen(
                            [
                                "ffmpeg",
                                "-f", "s16le",
                                "-ar", str(self.config.rate),
                                "-ac", "1",
                                "-i", "-",
                                "-af", f"atempo={self.config.speed},volume={self.config.volume}",
                                "-f", "s16le",
                                "-ar", str(self.config.rate),
                                "-ac", "1",
                                "-",
                            ],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                        )
                        aplay_proc = subprocess.Popen(
                            ["aplay", "-f", "S16_LE", "-c", "1", "-r", str(self.config.rate)],
                            stdin=ffmpeg_proc.stdout,
                            stdout=subprocess.PIPE,
                        )
                        self.ffmpeg_process.set(ffmpeg_proc)
                        self.play_process.set(aplay_proc)

                        try:
                            # Consume chunks until STREAM_END or reset
                            while True:
                                next_epoch, next_item = self.play_queue.get()
                                if (
                                    next_item is RESET
                                    or next_item is STREAM_END
                                    or self.reset_issued.get()
                                    or next_epoch != item_epoch
                                    or item_epoch != self._current_reset_epoch()
                                ):
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
                    if item is STREAM_END:
                        logger.warning("Dropping unexpected STREAM_END with no matching STREAM_START")
                        continue

                    # Non-streaming single buffer (backward compatibility)
                    audio = item
                    if self.is_windows:
                        if len(audio) == 0:
                            logger.warning("No audio data to play")
                            continue
                        handle = None
                        handle_epoch = None
                        try:
                            handle = self.player.play(
                                audio,
                                rate=self.config.rate,
                                speed=self.config.speed,
                                volume=self.config.volume,
                            )
                            handle_epoch = self._current_reset_epoch()
                            self._set_play_handle(handle_epoch, handle)
                            self._register_play_handle(handle_epoch, handle)
                            while handle.is_running() and handle_epoch == self._current_reset_epoch() and not self.reset_issued.get():
                                time.sleep(0.05)
                            if handle_epoch != self._current_reset_epoch() or self.reset_issued.get():
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
                            if handle is not None:
                                self._unregister_play_handle(handle)
                            if handle_epoch is not None:
                                self._clear_play_handle(handle_epoch)
                    else:
                        ffmpeg_proc = subprocess.Popen(
                            [
                                "ffmpeg",
                                "-f", "s16le",
                                "-ar", str(self.config.rate),
                                "-ac", "1",
                                "-i", "-",
                                "-af", f"atempo={self.config.speed},volume={self.config.volume}",
                                "-f", "s16le",
                                "-ar", str(self.config.rate),
                                "-ac", "1",
                                "-",
                            ],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                        )

                        aplay_proc = subprocess.Popen(
                            ["aplay", "-f", "S16_LE", "-c", "1", "-r", str(self.config.rate)],
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
            epoch, text, getaudio = self.gen_queue.get()
            if self.reset_issued.get() or epoch != self._current_reset_epoch():
                logger.debug(
                    "Dropping stale generation task: epoch=%s current_epoch=%s chars=%s",
                    epoch,
                    self._current_reset_epoch(),
                    len(text),
                )
                self.gen_queue.task_done()
                continue

            produced_any = False
            try:
                logger.debug(
                    "Generator picked up text: chars=%s getaudio=%s one_sentence=%s",
                    len(text),
                    getaudio,
                    self.config.one_sentence,
                )
                if getaudio:
                    # Accumulate for HTTP response
                    out_bytes = bytearray()
                    try:
                        for audio_bytes in self.piper_voice.synthesize_stream_raw(
                            text,
                            sentence_silence=self.config.sentence_silence,
                        ):
                            if self.reset_issued.get() or epoch != self._current_reset_epoch():
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
                        self.play_queue.put((epoch, STREAM_START))
                        for audio_bytes in self.piper_voice.synthesize_stream_raw(
                            text,
                            sentence_silence=self.config.sentence_silence,
                        ):
                            if self.reset_issued.get() or epoch != self._current_reset_epoch():
                                break
                            if audio_bytes:
                                produced_any = True
                                self.play_queue.put((epoch, audio_bytes))
                    except Exception as e:
                        logger.error("Piper Python synthesis failed: %s", repr(e), exc_info=True)
                    finally:
                        # Always signal end-of-stream so player can close gracefully
                        self.play_queue.put((epoch, STREAM_END))
                        out = b""
            finally:
                self.gen_process.set(None)
                self.gen_queue.task_done()

            if getaudio:
                self.get_queue.put(b"" if len(out) == 0 else out)
            else:
                if not produced_any:
                    logger.warning(f"No audio generated for text: '{text[:50]}...'")
                else:
                    logger.debug("Generator finished streaming audio for chars=%s", len(text))

    def speak(self, text, getaudio):
        tokens = [text]
        audio = b""

        done = lambda: audio if getaudio else None

        if self.config.one_sentence:
            tokens = text.split(".")
            for i in range(len(tokens)):
                tokens[i] = tokens[i].strip() + "."

        self.reset_issued.set(False)
        request_epoch = self._current_reset_epoch()
        logger.debug(
            "Queueing speech request: epoch=%s tokens=%s getaudio=%s gen_queue=%s play_queue=%s",
            request_epoch,
            len(tokens),
            getaudio,
            self.gen_queue.qsize(),
            self.play_queue.qsize(),
        )

        # This lock is important because if another request arrives, results
        # could possibly get mixed up get()ing from multiple places simultaneously
        # A better solution could be a separate thread for getaudio
        with self.get_queue_lock:
            for text in tokens:
                if self.reset_issued.get() or request_epoch != self._current_reset_epoch():
                    return done()
                self.gen_queue.put((request_epoch, text, getaudio))

            if getaudio:
                for i in range(len(tokens)):
                    if self.reset_issued.get() or request_epoch != self._current_reset_epoch():
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
        handle = self._take_play_handle()
        if handle is not None:
            logger.info("Skip requested; terminating current playback handle")
            try:
                handle.terminate()
            except Exception:
                logger.warning("Failed to terminate current playback handle during skip", exc_info=True)
            finally:
                self._unregister_play_handle(handle)
        # Fallback to raw process (Linux path)
        with self.play_process.lock:
            if self.play_process.data is not None:
                self.play_process.data.terminate()

    def reset(self):
        # Make sure more commands aren't enqueued
        logger.info(
            "Reset requested: gen_queue=%s play_queue=%s get_queue=%s paused=%s",
            self.gen_queue.qsize(),
            self.play_queue.qsize(),
            self.get_queue.qsize(),
            self.paused,
        )
        new_epoch = self._next_reset_epoch()
        self.reset_issued.set(True)

        self.stop_play_process()
        self.stop_gen_process()
        time.sleep(0.05)

        self.paused = False

        drained_gen = self._drain_queue(self.gen_queue)
        drained_play = self._drain_queue(self.play_queue)
        drained_get = self._drain_queue(self.get_queue)
        self.play_queue.put((new_epoch, RESET))
        logger.info(
            "Reset finished: epoch=%s drained gen=%s play=%s get=%s; threads alive gen=%s play=%s active_handles=%s",
            new_epoch,
            drained_gen,
            drained_play,
            drained_get,
            self.gen_thread.is_alive(),
            self.play_thread.is_alive(),
            len(self.active_play_handles.get()),
        )

    def stop_play_process(self):
        # First try via AudioPlayback handle (Windows path)
        handle = self._take_play_handle()
        if handle is not None:
            logger.debug("Stopping active playback handle")
            try:
                handle.terminate()
            except Exception:
                logger.warning("Failed to terminate active playback handle", exc_info=True)
            finally:
                self._unregister_play_handle(handle)

        terminated_handles = self._terminate_all_play_handles(reason="reset_or_stop")
        if terminated_handles:
            logger.info("Terminated %s additional playback handle(s)", terminated_handles)

        if self.is_windows and self.player is not None:
            try:
                self.player.terminate_all()
            except Exception:
                logger.warning("Failed to force-stop ffplay processes", exc_info=True)

        # Fallback to raw processes (primarily Linux path)
        with self.play_process.lock:
            if self.play_process.data is not None:
                logger.debug("Stopping raw play process pid=%s", self.play_process.data.pid)
                self.play_process.data.terminate()
                if not self.is_windows:
                    # SIGKILL only works on Unix-like systems
                    self.play_process.data.send_signal(signal.SIGKILL)

        with self.ffmpeg_process.lock:
            if self.ffmpeg_process.data is not None:
                logger.debug("Stopping ffmpeg process pid=%s", self.ffmpeg_process.data.pid)
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
            "play_handle.active": self.play_handle.get()[1] is not None,
            "active_play_handles.count": len(self.active_play_handles.get()),
            "reset_epoch.get()": self._current_reset_epoch(),
            "gen_thread.is_alive()": self.gen_thread.is_alive(),
            "play_thread.is_alive()": self.play_thread.is_alive(),
        }
