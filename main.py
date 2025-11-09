import argparse
import logging
import platform

import uvicorn

from config import AppConfig, PiperConfig, TextConfig
from piper_backend import Piper
from speechd_backend import Speechd
from services.clipboard import build_clipboard
from services.reader import DefaultReaderController
from web.app import create_app
from services.notify import build_notifier


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
        help="Enable debug mode (developmental purposes)",
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

    app_config = AppConfig(
        ip=parsed.ip,
        port=parsed.port,
        debug=parsed.debug,
        log_level=parsed.log_level,
    )

    piper_config = PiperConfig(
        model=parsed.piper_model,
        model_config=parsed.piper_model_config,
        rate=parsed.piper_rate,
        sentence_silence=parsed.piper_sentence_silence,
        one_sentence=parsed.piper_one_sentence,
        volume=parsed.volume,
        speed=parsed.speed,
    )

    text_config = TextConfig(
        ignore_chars=parsed.ignore_chars,
        ignore_newline=parsed.ignore_newline,
    )

    # Build dependencies via factories
    clipboard = build_clipboard(parsed)
    if platform.system() == "Windows" and clipboard is None:
        logger.warning(
            "pyperclip not available. GET requests for clipboard reading will not work on Windows."
        )

    # Note: Speechd still receives parsed for now (can be refactored later)
    tts = Speechd(parsed) if parsed.speechd else Piper(piper_config)

    notifier = build_notifier()

    if not tts.inited:
        raise SystemExit("Failed to initialize the TTS backend")

    controller = DefaultReaderController(
        text_config=text_config,
        piper_config=piper_config,
        tts=tts,
        clipboard=clipboard,
        notifier=notifier,
    )
    app = create_app(controller)

    uvicorn.run(
        app,
        host=app_config.ip,
        port=app_config.port,
        log_level="debug" if app_config.debug else "info",
        access_log=app_config.debug,
    )
