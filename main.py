from flask import Flask, request
from unidecode import unidecode
from piper_backend import Piper
from speechd_backend import Speechd
import argparse
import logging
import time
import datetime
import subprocess
import platform
from services.clipboard import build_clipboard
from services.reader import DefaultReaderController


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class App:
    def __init__(self, parsed):
        self.parsed = parsed
        self.parsed.volume = max(0.0, min(self.parsed.volume, 1.0))
        self.parsed.speed = max(0.0, min(self.parsed.speed, 10.0))

        self.begin_time = time.time()
        # self.notifier = DesktopNotifier()
        self.notifier = None

        self.flask = Flask("tts-reader")
        self.flask.add_url_rule(
            "/read", "read", view_func=self.read, methods=["GET", "POST"]
        )
        self.flask.add_url_rule("/play", "play", view_func=self.play)
        self.flask.add_url_rule("/pause", "pause", view_func=self.pause)
        self.flask.add_url_rule("/toggle", "toggle", view_func=self.toggle)
        self.flask.add_url_rule("/reset", "reset", view_func=self.reset)
        self.flask.add_url_rule("/skip", "skip", view_func=self.skip)
        self.flask.add_url_rule("/volume/<float:data>", "volume", view_func=self.volume)
        self.flask.add_url_rule("/speed/<float:data>", "speed", view_func=self.speed)
        self.flask.add_url_rule("/status", "status", view_func=self.status)

        self.clipboard = build_clipboard(self.parsed)
        if platform.system() == "Windows" and self.clipboard is None:
            logger.warning("pyperclip not available. GET requests for clipboard reading will not work on Windows.")

        self.tts = Speechd(self.parsed) if self.parsed.speechd else Piper(self.parsed)
        if not self.tts.inited:
            raise Exception("Failed to initialize the TTS backend")
        # Application-level controller
        self.controller = DefaultReaderController(parsed=self.parsed, tts=self.tts, clipboard=self.clipboard)

    def read(self):
        getaudio = request.args.get("getaudio", None) is not None
        if request.method == "POST":
            if not request.data:
                s = "Failed to get the POSTed data"
                logger.error(
                    "%s: Empty post request maybe because the content type header (%s) is wrong",
                    s,
                    request.content_type,
                )
                self.notify(s)
                return s
            try:
                text = request.data.decode("utf-8")
            except UnicodeError as e:
                s = "Failed to decode the POSTed data as UTF-8"
                logger.error("%s: %s", s, repr(e))
                self.notify(s)
                return s
            return self.controller.read_text(text, getaudio)
        else:
            return self.controller.read_clipboard(getaudio)

    def status(self):
        return self.controller.status()

    def toggle(self):
        self.controller.toggle()
        return ""

    def play(self):
        self.controller.play()
        return ""

    def pause(self):
        self.controller.pause()
        return ""

    def reset(self):
        self.controller.reset()
        return ""

    def skip(self):
        self.controller.skip()
        return ""

    def speed(self, data):
        self.controller.set_speed(max(0.0, min(data, 10.0)))
        return ""

    def volume(self, data):
        self.controller.set_volume(max(0.0, min(data, 1.0)))
        return ""

    def uptime(self):
        diff = time.time() - self.begin_time
        return str(datetime.timedelta(seconds=int(diff)))

    def run(self):
        self.flask.run(
            host=self.parsed.ip, port=self.parsed.port, debug=self.parsed.debug
        )

    def notify(self, msg):
        # right now skipping it for windows
        pass
        # self.notifier.send_sync(title="TTS Reader", message=msg, timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="tts-reader",
    )
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address")
    parser.add_argument("--port", type=int, default=5000, help="Port")
    parser.add_argument(
        "--wayland",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Assume running under Wayland",
    )
    parser.add_argument(
        "--piper-python",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Attempt to use the piper python module. Has no effect if a different backend is selected",
    )
    parser.add_argument(
        "--speechd",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Use speechd instead of piper. Incomplete",
    )
    parser.add_argument("--volume", type=float, default=1.0, help="Volume [0-1]")
    parser.add_argument(
        "--speed", type=float, default=1.0, help="Playback speed [0-10]"
    )
    parser.add_argument(
        "--piper-rate",
        type=int,
        default=22050,
        help="Piper: Playback sample rate. More info at https://github.com/rhasspy/piper/blob/master/TRAINING.md",
    )
    parser.add_argument(
        "--piper-sentence-silence",
        type=float,
        default=0.8,
        help="Piper: Seconds of silence after each sentence",
    )
    parser.add_argument(
        "--piper-one-sentence",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Piper: Process one sentence at a time, instead of the default whole selection",
    )
    parser.add_argument(
        "--piper-model", type=str, default=None, help="Piper: Path to the model"
    )
    parser.add_argument(
        "--piper-model-config",
        type=str,
        default=None,
        help="Piper: Path to the model configuration",
    )
    parser.add_argument(
        "--debug",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enable flask debug mode (developmental purposes)",
    )
    parser.add_argument(
        '--ignore_chars',
        nargs='*',
        default=[],
        help='List of characters to ignore'
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )

    parser.add_argument(
        "--ignore_newline",
        action="store_true",
        help="Ignore newline characters",
    )

    parsed = parser.parse_args()

    try:
        if parsed.log_level:
            logging.getLogger().setLevel(parsed.log_level)
    except Exception as e:
        logger.error("Error setting log level")

    logging.basicConfig(
        encoding="utf-8", level=logging.DEBUG if parsed.debug else logging.INFO
    )

    app = App(parsed)
    app.run()
