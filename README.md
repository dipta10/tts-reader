# TTS Reader
Select and read aloud text from anywhere 🎧

### Requirements
- curl (or anything else to issue http requests)
- ffmpeg
- wl-clipboard (if you're on Wayland)
- xclip (if you're on X11)

### Steps to run
1. Download voice models and their respective configurations in the `models` directory. See [here](https://github.com/rhasspy/piper/blob/master/VOICES.md)
2. Install requirements and run the application:
    ```bash
    pip install -r requirements.txt 
    python main.py --port 5000 --playback_speed=1.0 --volume_level=.8 --model models/yourmodel.onnx --model_config models/yourmodel.onnx.json --wayland
    ```
3. Select any text from your browser, terminal, etc
4. Run the following command to read aloud the selected text:
    ```bash
    curl --url http://localhost:5000/read
    ```
5. You can also tell it to read random text using the POST request:
    ```bash
    echo Hope you are having a lovely day, sir. | curl -X POST --data-binary @- -H 'Content-Type: application/octet-stream' localhost:5000/read
    ```
5. If you want to interrupt reading, use:
    ```bash
    curl --url http://localhost:5000/stop
    ```
6. Check status of the program using:
    ```bash
    curl --url http://localhost:5000/status
    ```
7. Change volume and playback speed at runtime like:
    ```bash
    curl --url http://localhost:5000/speed/1.25
    curl --url http://localhost:5000/volume/0.7
    ```
    
### Let's set a keybind
You can set keybindings in your DE or window manager of choice for practial usage. For example, if you're running i3wm, add the following to your i3 config, `~/.config/i3/config`.
```shell
set $alt Mod1
bindsym $alt+3 exec "curl --url http://localhost:5000/read"
bindsym $alt+shift+3 exec "curl --url http://localhost:5000/stop"
```

### Available options
```
usage: tts-reader [-h] [-i IP] [-p PORT] [-s PLAYBACK_SPEED] [-v VOLUME]
                  [-r PLAYBACK_SAMPLE_RATE] [-l SENTENCE_SILENCE]
                  [-o | --one_sentence | --no-one_sentence]
                  [-w | --wayland | --no-wayland] [-m MODEL] [-c MODEL_CONFIG]
                  [-d | --debug | --no-debug]

options:
  -h, --help            show this help message and exit
  -i IP, --ip IP        IP address
  -p PORT, --port PORT  Port
  -s PLAYBACK_SPEED, --playback_speed PLAYBACK_SPEED
                        Playback speed
  -v VOLUME, --volume VOLUME
                        Volume [0-1]
  -r PLAYBACK_SAMPLE_RATE, --playback_sample_rate PLAYBACK_SAMPLE_RATE
                        Playback sample rate. More info at https://github.com/
                        rhasspy/piper/blob/master/TRAINING.md
  -l SENTENCE_SILENCE, --sentence_silence SENTENCE_SILENCE
                        Seconds of silence after each sentence. Passed to
                        piper
  -o, --one_sentence, --no-one_sentence
                        Process one sentence at a time, instead of the default
                        whole selection
  -w, --wayland, --no-wayland
                        Assume running under Wayland
  -m MODEL, --model MODEL
                        Path to the model
  -c MODEL_CONFIG, --model_config MODEL_CONFIG
                        Path to the model configuration
  -d, --debug, --no-debug
                        Enable flask debug mode (developmental purposes)
```

### Disclaimer
This is my pet project. I switched from Windows to Ubuntu, mainly for i3wm and because my potato laptop works way faster here.
I was looking for an alternative for TTS reader where with a keybind I can make the app read the selected text aloud.

Since I didn't find a standalone application that can do it or perform as well as TTS Readers available on Windows, I decided to create one for myself using [Piper](https://github.com/rhasspy/piper) as a side project.

### Todo
- [x] Use Piper python library and remove lib from repo
