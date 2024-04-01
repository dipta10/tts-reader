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
parser.add_argument("-i", "--ip", type=str, default="127.0.0.1", help="IP address")
parser.add_argument("-p", "--port", type=int, default=5000, help="Port")
parser.add_argument(
    "-s", "--playback_speed", type=float, default=1.2, help="Playback speed"
)
parser.add_argument("-v", "--volume", type=float, default=1.0, help="Volume [0-1]")
parser.add_argument(
    "-r",
    "--play_sample_rate",
    type=int,
    default=22050,
    help="Playback sample rate. More info at https://github.com/rhasspy/piper/blob/master/TRAINING.md",
)
parser.add_argument(
    "-f",
    "--full_selection",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="Process the whole selectation at a time instead of chunking and reading by individual sentences",
)
parser.add_argument(
    "-w",
    "--wayland",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="Assume running under Wayland",
)
parser.add_argument("-m", "--model", type=str, default=None, help="Path to the model")
parser.add_argument(
    "-c",
    "--model_config",
    type=str,
    default=None,
    help="Path to the model configuration",
)
parser.add_argument(
    "-d",
    "--debug",
    default=False,
    action=argparse.BooleanOptionalAction,
    help="Enable flask debug mode (developmental purposes)",
)

parsed = None
pass_queue = Queue()
gen_process = None
play_process = None
stop_playing = False

app = Flask("tts-reader")


def thread_play():
    global play_process
    global parsed

    ffplay_path = shutil.which("ffplay")
    if ffplay_path == None:
        print("ffplay not found in PATH")
        notify("ffplay not found in PATH")
        fatal_exit()

    while True:
        audio = pass_queue.get()
        try:
            if not stop_playing:
                play_process = Popen(
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
                        f"{parsed.play_sample_rate}",
                        "-ac",
                        "1",
                        "-",
                    ],
                    stdin=subprocess.PIPE,
                    start_new_session=True,
                )
                play_process.communicate(input=audio)
                play_process = None

        except Exception as e:
            print(e)
            notify("Failed to play")

        finally:
            pass


play_thread = threading.Thread(target=thread_play, daemon=True)
play_thread.start()


@app.route("/read")
def read():
    global stop_playing
    stop_playing = False

    num_chars = 0

    try:
        out = subprocess.check_output(
            ["wl-paste", "-p"]
            if parsed.wayland
            else ["xclip", "-o", "-selection primary"]
        )
        text = out.decode("utf-8")
        num_chars = len(text)

    except Exception as e:
        print(e)
        notify("Failed to get selected text")
        return

    try:
        if not parsed.full_selection:
            tokens = text.split(". ")
            while tokens:
                text = tokens[0].strip() + "."
                tokens = tokens[1:]
                text = sanitize_text(text)

                out = generate_audio(text)
                if out != None:
                    pass_queue.put(out)
        else:
            out = generate_audio(text)
            if out != None:
                pass_queue.put(out)

    except Exception as e:
        print(e)
        notify("Failed while organizing/generating text")
        fatal_exit()

    return f"Generated and queued {num_chars} characters for playback"


def generate_audio(text):
    global gen_process

    gen_process = Popen(
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
    out, _ = gen_process.communicate(input=text.encode())
    gen_process = None

    return out


def sanitize_text(text: str):
    text = unidecode(text)
    text = text.replace("‐\n", "")
    text = text.replace("‐ ", "")
    return text


@app.route("/stop")
def stop():
    global gen_process
    global play_process
    global stop_playing
    global pass_queue

    num_queue = pass_queue.qsize()

    stop_playing = True
    while pass_queue.qsize() > 0:
        pass_queue.get()

    try:
        if gen_process is not None:
            print(f"Killing gen_process {gen_process.pid}")
            os.killpg(gen_process.pid, signal.SIGTERM)

        if play_process is not None:
            print(f"Killing play_process {play_process.pid}")
            os.killpg(play_process.pid, signal.SIGTERM)

    except Exception as e:
        print(e)
        notify("Failed to stop TTS")

    return f"Queue cleared of pending {num_queue} items. Killed the generate and play processes if running"


def notify(msg):
    notification.notify(
        title="tts-reader",
        message=msg,
        app_icon=None,
        timeout=2,
    )


def fatal_exit():
    os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    parsed = parser.parse_args()

    if parsed.model == None or parsed.model_config == None:
        print("Please provide both the --model and --model_config arguments")
        sys.exit(1)

    app.run(host=parsed.ip, port=parsed.port, debug=parsed.debug)
