from subprocess import Popen
from typing import List
import argparse
import os
import signal
import subprocess
import sys
import shutil
import threading
import time
import uuid

from flask import Flask
from plyer import notification
from unidecode import unidecode

app = Flask(__name__)

parser = argparse.ArgumentParser(
    prog="tts-reader",
)
parser.add_argument(
    "-i", "--ip", type=str, default="127.0.0.1", help="ip address to host on"
)
parser.add_argument("-p", "--port", type=int, default=5000, help="port number")
parser.add_argument("--playback_speed", type=float, default=1.2, help="playback speed")
parser.add_argument("--volume_level", type=float, default=1.0, help="volume level")
parser.add_argument(
    "--wayland",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="assume wayland instead",
)
parser.add_argument(
    "--debug",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="debug (for developmental purposes)",
)
parser.add_argument("--model", type=str, default=None, help="path to the model")
parser.add_argument(
    "--model_config", type=str, default=None, help="path to the model config"
)

# it is recommended to use dqueue I think
# https://stackoverflow.com/questions/71290441/how-to-run-a-thread-endlessly-in-python
queue: List = []
current_process = None
audio_file_path = "/tmp"
tokens = []
stop_playing = False


def _process_read_text():
    global current_process

    ffplay_path = shutil.which("ffplay")
    if ffplay_path == None:
        print("ffplay not found in PATH")
        sys.exit(1)

    pa = parser.parse_args()
    playback_speed = str(pa.playback_speed)
    volume_level = str(pa.volume_level)

    while True:
        if len(queue) == 0:
            sleep_time = 0.5
            time.sleep(sleep_time)
            continue

        text = queue.pop(0)
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
                        pa.model,
                        "--config",
                        pa.model_config,
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
                        f"atempo={pa.playback_speed},volume={pa.volume_level}",
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
            print("error", e)
            notify("TTS-Reader: error playing text :(")
        finally:
            pass
            # os.remove(os.path.join(audio_file_path, file_name))


readThread = threading.Thread(target=_process_read_text, daemon=True)
readThread.start()


@app.route("/read")
def read():
    global stop_playing
    stop_playing = False
    add_text()
    return ""


def sanitizeText(text: str):
    """
    This function sanitizes the input text by removing non-ASCII characters and hyphenation artifacts. Example:
    - 𝗟𝗮𝘁𝗲𝗻𝗰𝘆 -> Latency
    - in pdf files " better perfor‐\nmance"

    Parameters:
    text (str): The input string to be sanitized.

    Returns:
    str: The sanitized text.
    """
    text = unidecode(text)
    text = text.replace("‐\n", "")
    text = text.replace("‐ ", "")
    return text


def add_text():
    global tokens
    pa = parser.parse_args()

    try:
        is_wayland = bool(pa.wayland)
        if is_wayland:
            out_binary = subprocess.check_output(["wl-paste", "-p"])
        else:
            out_binary = subprocess.check_output(["xclip", "-o", "-selection primary"])
        text = out_binary.decode("utf-8")

    except Exception as e:
        print(e)
        notify("Failed to get selected text")
        return

    tokens = text.split(". ")

    try:
        while tokens:
            text = tokens[0].strip() + "."
            tokens = tokens[1:]
            text = sanitizeText(text)
            queue.append(text)

    except Exception as e:
        print(e)
        notify("TTS-Reader: something went wrong when creating audio output :(")


def read_text():
    p = Popen(["./script.sh", '"hello"'])
    p.wait()


@app.route("/stop")
def stop():
    global tokens
    global stop_playing
    stop_playing = True
    queue.clear()
    try:
        if current_process is not None:
            print(f"current_process pid: {current_process.pid}")
            os.killpg(current_process.pid, signal.SIGTERM)
            tokens = []
            print(f"current_process pid: {current_process} KILLED")
    except Exception as e:
        print(e)
        notify("error stopping tts :(")
    return "queue cleared.."


def notify(msg: str):
    notification.notify(
        title="tts-reader",
        message=msg,
        app_icon=None,
        timeout=2,
    )


if __name__ == "__main__":
    pa = parser.parse_args()

    if pa.model == None or pa.model_config == None:
        print("Please provide both the --model and --model_config arguments")
        sys.exit(1)

    app.run(host=pa.ip, port=pa.port, debug=pa.debug)
