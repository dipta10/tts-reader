from subprocess import Popen
from queue import Queue
import argparse
import os
import signal
import subprocess
import sys
import shutil
import threading
import time

from flask import Flask
from plyer import notification
from unidecode import unidecode

parser = argparse.ArgumentParser(
    prog="tts-reader",
)
parser.add_argument(
    "-i", "--ip", type=str, default="127.0.0.1", help="ip address to host on"
)
parser.add_argument("-p", "--port", type=int, default=5000, help="port number")
parser.add_argument(
    "-s", "--playback_speed", type=float, default=1.2, help="playback speed"
)
parser.add_argument("--volume", type=float, default=1.0, help="volume between 0 and 1")
parser.add_argument(
    "--one_sentence",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="read one sentence at a time instead of the default full selection",
)
parser.add_argument(
    "--wayland",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="assume wayland instead",
)
parser.add_argument("--model", type=str, default=None, help="path to the model")
parser.add_argument(
    "--model_config", type=str, default=None, help="path to the model config"
)
parser.add_argument(
    "--debug",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="enable flask debug mode (for developmental purposes)",
)

parsed = None
text_queue = Queue()
current_process = None
stop_playing = False

app = Flask("tts-reader")


def thread_generate_play():
    global current_process
    global parsed

    ffplay_path = shutil.which("ffplay")
    if ffplay_path == None:
        print("ffplay not found in PATH")
        sys.exit(1)

    while True:
        text = text_queue.get()
        try:
            out = None
            current_process = None

            if not stop_playing:
                process = Popen(
                    [
                        sys.executable,
                        "-m",
                        "piper",
                        "--output-raw",
                        "--model",
                        parsed.model,
                        "--config",
                        parsed.model_config,
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    start_new_session=True,
                )
                current_process = process
                out, _ = process.communicate(input=text.encode())
                current_process = None

            if not stop_playing:
                ffplay_process = Popen(
                    [
                        ffplay_path,
                        "-hide_banner",
                        "-loglevel",
                        "panic",
                        "-nostats",
                        "-autoexit",
                        "-nodisp",
                        "-af",
                        f"atempo={parsed.playback_speed},volume={parsed.volume}",
                        "-f",
                        "s16le",
                        "-ar",
                        "22050",
                        "-ac",
                        "1",
                        "-",
                    ],
                    stdin=subprocess.PIPE,
                    start_new_session=True,
                )
                current_process = ffplay_process
                ffplay_process.communicate(input=out)
                current_process = None

        except Exception as e:
            print(e)
            notify("Failed to generate/play")

        finally:
            pass


read_thread = threading.Thread(target=thread_generate_play, daemon=True)
read_thread.start()


@app.route("/read")
def read():
    global stop_playing
    stop_playing = False

    try:
        out = subprocess.check_output(
            ["wl-paste", "-p"]
            if parsed.wayland
            else ["xclip", "-o", "-selection primary"]
        )
        text = out.decode("utf-8")

    except Exception as e:
        print(e)
        notify("Failed to get selected text")
        return

    tokens = text.split(". ")
    try:
        if parsed.one_sentence:
            while tokens:
                text = tokens[0].strip() + "."
                tokens = tokens[1:]
                text = sanitizeText(text)
                text_queue.put(text)
        else:
            text_queue.put(text)

    except Exception as e:
        print(e)
        notify("Failed while organizing text for TTS")

    return ""


def sanitizeText(text: str):
    text = unidecode(text)
    text = text.replace("‐\n", "")
    text = text.replace("‐ ", "")
    return text


@app.route("/stop")
def stop():
    global stop_playing
    global text_queue

    stop_playing = True
    while text_queue.qsize() > 0:
        text_queue.get()

    try:
        if current_process is not None:
            print(f"Killing current_process {current_process.pid}")
            os.killpg(current_process.pid, signal.SIGTERM)

    except Exception as e:
        print(e)
        notify("Failed to stop TTS")

    return "Queue cleared"


def notify(msg: str):
    notification.notify(
        title="tts-reader",
        message=msg,
        app_icon=None,
        timeout=2,
    )


if __name__ == "__main__":
    parsed = parser.parse_args()

    if parsed.model == None or parsed.model_config == None:
        print("Please provide both the --model and --model_config arguments")
        sys.exit(1)

    app.run(host=parsed.ip, port=parsed.port, debug=parsed.debug)
