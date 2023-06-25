import os
import subprocess
import threading
import time
from subprocess import Popen
from typing import List
import signal

from flask import Flask

app = Flask(__name__)

cnt = 0
# it is recommended to use dqueue I think
# https://stackoverflow.com/questions/71290441/how-to-run-a-thread-endlessly-in-python
queue: List = []
script_process = None
play_process = None


'''
Todo:
    - add notifications
    - write logs to a file
    - implement a queue
    - implement stop signal
'''


def _process_read_text():
    global script_process
    global play_process
    while True:
        if len(queue) != 0:
            print('found someting in the queue...')
            text = queue.pop(0)
            try:
                script_process = Popen(['./script.sh', f'"{text}"'])
                script_process.wait()
                script_process = None
                print('done reading...')

                print('about to play...')
                # play_cmd = 'ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.4" ~/Desktop/welcome.wav'.split(' ')
                # https://stackoverflow.com/questions/23228650/python-cannot-kill-process-using-process-terminate
                play_process = Popen('./play_script.sh', start_new_session=True)
                print(play_process)
                play_process.wait()
                play_process = None
                print('done playing.')
            except Exception as e:
                print(e)
                print(f'error reading text: {text}')
        else:
            sleep_time = 0.5
            # print(f'found nothing in the queue, going to sleep for {sleep_time}s')
            time.sleep(sleep_time)


readThread = threading.Thread(target=_process_read_text, daemon=True)
readThread.start()

@app.route('/read')
def read():
    print(f'queue length: {len(queue)}')
    add_text()
    return 'none'


def add_text():
    out_binary = subprocess.check_output(['xclip', '-o', '-selection primary'])
    out: str = out_binary.decode('utf-8')
    # todo: if there's an error, find a way to show a notification
    queue.append(out)
    print(queue)


def read_text():
    p = Popen(['./script.sh', '"hello"'])
    p.wait()
    print('done reading.')


@app.route('/stop')
def stop():
    print(f'clearing queue')
    queue.clear()
    if script_process is not None:
        print(f'pscript_process id: {script_process.pid}')
        os.kill(script_process.pid, signal.SIGKILL)
    if play_process is not None:
        print(f'play_process pid: {play_process.pid}')
        # os.kill(play_process.pid, signal.SIGKILL)
        os.killpg(play_process.pid, signal.SIGTERM)
        # os.kill(play_process.pid, signal.SIGQUIT)
        print(f'play_process pid: {play_process} KILLED')
    return 'queue cleared..'


@app.route('/')
def hello():
    global cnt
    cnt += 1
    print(cnt)

    return 'hola'
