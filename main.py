import os
import subprocess
import threading
import time
from subprocess import Popen
from typing import List
from plyer import notification
import signal
import uuid
from unidecode import unidecode

from flask import Flask

app = Flask(__name__)

# it is recommended to use dqueue I think
# https://stackoverflow.com/questions/71290441/how-to-run-a-thread-endlessly-in-python
queue: List = []
script_process = None
play_process = None
audio_file_path = '/tmp'
tokens = []

'''
Todo:
    - write logs to a file
    - implement stop signal
    - implement a logger
'''


def _process_read_text():
    global script_process
    global play_process
    while True:
        if len(queue) != 0:
            print('found something in the queue...')
            file_name = queue.pop(0)
            try:
                script_process = None
                print('about to play...')
                # play_cmd = 'ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.4" ~/Desktop/welcome.wav'.split(' ')
                # https://stackoverflow.com/questions/23228650/python-cannot-kill-process-using-process-terminate
                play_process = Popen(['./play_script.sh', file_name], start_new_session=True)
                print(play_process)

                play_process.wait()
                play_process = None
                print('done playing.')
            except Exception as e:
                print(e)
                notify('TTS-Reader: error playing text :(')
                print(f'error reading text: {file_name}')
            finally:
                os.remove(os.path.join(audio_file_path, file_name))
        else:
            sleep_time = 0.5
            time.sleep(sleep_time)


readThread = threading.Thread(target=_process_read_text, daemon=True)
readThread.start()


@app.route('/read')
def read():
    print(f'queue length: {len(queue)}')
    add_text()
    return 'none'


def sanitizeText(text: str):
    # 𝗟𝗮𝘁𝗲𝗻𝗰𝘆 -> Latency
    text = unidecode(text)
    # for example in pdf " better perfor‐\nmance"
    text = text.replace('‐\n', '')
    text = text.replace('‐ ', '')
    return text


def add_text():
    global tokens
    try:
        out_binary = subprocess.check_output(['xclip', '-o', '-selection primary'])
        text: str = out_binary.decode('utf-8')
    except Exception as e:
        print(e)
        notify('Unable to get selected text')
        return
    tokens = text.split('. ')
    try:
        while tokens:
            text = ' '.join(tokens[:1])
            tokens = tokens[1:]
            text = sanitizeText(text)
            file_name = f'{uuid.uuid4()}.wav'
            process = Popen(['./script.sh', f'{file_name}', f'"{text}"'])
            process.wait()
            queue.append(file_name)
    except Exception as e:
        print(e)
        notify('TTS-Reader: something went wrong when creating audio output :(')

    print(queue)


def read_text():
    p = Popen(['./script.sh', '"hello"'])
    p.wait()
    print('done reading.')


@app.route('/stop')
def stop():
    print(f'clearing queue')
    global tokens
    queue.clear()
    try:
        if script_process is not None:
            print(f'pscript_process id: {script_process.pid}')
            os.kill(script_process.pid, signal.SIGKILL)
        if play_process is not None:
            print(f'play_process pid: {play_process.pid}')
            # os.kill(play_process.pid, signal.SIGKILL)
            os.killpg(play_process.pid, signal.SIGTERM)
            tokens = []
            # os.kill(play_process.pid, signal.SIGQUIT)
            print(f'play_process pid: {play_process} KILLED')
    except Exception as e:
        print('error stopping player')
        print(e)
        notify('error stopping tts :(')
    return 'queue cleared..'


def notify(msg: str):
    notification.notify(
        title='tts-reader',
        message=msg,
        app_icon=None,
        timeout=2,
    )

app.run(host="0.0.0.0", port=5000)
