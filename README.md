# TTS Reader
Select and read aloud text from anywhere 🔊

### Requirements
- ffmpeg
- wl-clipboard (Wayland only)
- xclip (X11 only)
- piper (https://github.com/rhasspy/piper/releases)
- anything to send requests

### Working
1. Download the models and their respective configurations in a directory. See [here](https://github.com/rhasspy/piper/blob/master/VOICES.md)
2. Create a virtual environment, install requirements and run:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt 
    python main.py --port 5000 --playback_speed=1.0 --volume_level=.8 --model yourmodel.onnx --model_config yourmodel.onnx.json --wayland
    ```
3. Select any text in any application
4. To read aloud:
    ```bash
    curl http://localhost:5000/read
    ```
5. To read aloud random text, send a POST request:
    ```bash
    echo Hope you are having a lovely day, sir. | curl -X POST -H 'Content-Type: application/octet-stream' --data-binary @- localhost:5000/read
    ```
6. To just download the generated audio:
    ```bash
    curl 'http://localhost:5000/read?sendaudio'
    ```
6. To interrupt the reading:
    ```bash
    curl http://localhost:5000/stop
    ```
7. To get basic runtime stats:
    ```bash
    curl http://localhost:5000/status
    ```
8. You can dynamically alter the speed and volume using:
    ```bash
    curl http://localhost:5000/speed/1.25
    curl http://localhost:5000/volume/0.7
    ```
9. Pause, play, toggle and skip with:
    ```bash
    curl http://localhost:5000/pause
    curl http://localhost:5000/play
    curl http://localhost:5000/toggle
    curl http://localhost:5000/skip
    ```
    
### Let's set keybinds
For practical usage, you can set keybindings in your DE or window manager. Say, if you're running sway, add the following to your config `~/.config/sway/config`.
```shell
bindsym $mod+t exec "curl http://localhost:5000/read"
bindsym $mod+shift+t exec "curl http://localhost:5000/stop"
bindsym Shift+XF86AudioPlay exec "curl http://localhost:5000/toggle"
bindsym Shift+XF86AudioNext exec "curl http://localhost:5000/skip"
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
