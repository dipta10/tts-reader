import argparse
import os
import signal
import subprocess
import threading
import time
import uuid
import sys
from subprocess import Popen
from typing import List

from flask import Flask
from plyer import notification
from unidecode import unidecode

app = Flask(__name__)

parser = argparse.ArgumentParser(
    prog="tts-reader",
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
parser.add_argument("--model", type=str, default=None, help="path to the model")
parser.add_argument(
    "--model_config", type=str, default=None, help="path to the model config"
)

# it is recommended to use dqueue I think
# https://stackoverflow.com/questions/71290441/how-to-run-a-thread-endlessly-in-python
queue: List = []
script_process = None
play_process = None
audio_file_path = "/tmp"
tokens = []

"""
Todo:
    - write logs to a file
    - implement stop signal
    - implement a logger
"""


def _process_read_text():
    global script_process
    global play_process

    playback_speed = str(parser.parse_args().playback_speed)
    volume_level = str(parser.parse_args().volume_level)
    while True:
        if len(queue) == 0:
            sleep_time = 0.5
            time.sleep(sleep_time)
            continue

        file_name = queue.pop(0)
        try:
            script_process = None
            # play_cmd = 'ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.4" ~/Desktop/welcome.wav'.split(' ')
            # https://stackoverflow.com/questions/23228650/python-cannot-kill-process-using-process-terminate
            play_process = Popen(
                ["./play_script.sh", file_name, playback_speed, volume_level],
                start_new_session=True,
            )

            play_process.wait()
            play_process = None
        except Exception as e:
            print("error", e)
            notify("TTS-Reader: error playing text :(")
        finally:
            os.remove(os.path.join(audio_file_path, file_name))


readThread = threading.Thread(target=_process_read_text, daemon=True)
readThread.start()


@app.route("/read")
def read():
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
    try:
        is_wayland = bool(parser.parse_args().wayland)
        if is_wayland:
            out_binary = subprocess.check_output(["wl-paste", "-p"])
        else:
            out_binary = subprocess.check_output(["xclip", "-o", "-selection primary"])
        text: str = out_binary.decode("utf-8")
    except Exception as e:
        print(e)
        notify("Unable to get selected text")
        return
    tokens = text.split(". ")
    try:
        while tokens:
            text = " ".join(tokens[:1])
            tokens = tokens[1:]
            text = sanitizeText(text)
            file_name = f"{uuid.uuid4()}.wav"
            process = Popen(
                [
                    "./script.sh",
                    f"{file_name}",
                    f'"{text}"',
                    parser.parse_args().model,
                    parser.parse_args().model_config,
                ]
            )
            process.wait()
            queue.append(file_name)
    except Exception as e:
        print(e)
        notify("TTS-Reader: something went wrong when creating audio output :(")


def read_text():
    p = Popen(["./script.sh", '"hello"'])
    p.wait()


@app.route("/stop")
def stop():
    global tokens
    queue.clear()
    try:
        if script_process is not None:
            print(f"pscript_process id: {script_process.pid}")
            os.kill(script_process.pid, signal.SIGKILL)
        if play_process is not None:
            print(f"play_process pid: {play_process.pid}")
            os.killpg(play_process.pid, signal.SIGTERM)
            tokens = []
            print(f"play_process pid: {play_process} KILLED")
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
    if parser.parse_args().model == None or parser.parse_args().model_config == None:
        print("Please provide both the --model and --model_config arguments")
        sys.exit(1)

    app.run(host="0.0.0.0", port=parser.parse_args().port)
