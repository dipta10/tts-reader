# TTS Reader

Select and read aloud text from anywhere 🔊

### Requirements

- ffmpeg
- wl-clipboard (Wayland only)
- xclip (X11 only)
- piper C++ (https://github.com/rhasspy/piper/releases), or piper python (https://pypi.org/project/piper-tts/)
- anything to send requests

### Working

1. Install piper in your $PATH if using the original C++ variant, or `pip install piper-tts` if using the Python wrapper
2. Download the models and their respective configurations in a directory. See [here](https://github.com/rhasspy/piper/blob/master/VOICES.md)
3. Create a virtual environment, install requirements and run:
   ```bash
   python -m venv venv --system-site-packages
   source venv/bin/activate
   pip install -r requirements.txt
   python main.py --port 5000 --speed=1.0 --volume=.8 --piper-model yourmodel.onnx --piper-model-config yourmodel.onnx.json --wayland
   ```
4. Select any text in any application 4. To read aloud:
   ```bash
   curl http://localhost:5000/read
   ```
5. To read aloud random text, send a POST request:
   ```bash
   echo Hope you are having a lovely day, sir. | curl -X POST -H 'Content-Type: application/octet-stream' --data-binary @- localhost:5000/read
   ```
6. To just download the generated audio, instead of playing it:
   ```bash
   curl 'http://localhost:5000/read?getaudio'
   ```
7. To interrupt the reading:
   ```bash
   curl http://localhost:5000/reset
   ```
8. To get basic runtime stats:
   ```bash
   curl http://localhost:5000/status
   ```
9. You can dynamically alter the speed and volume using:
   ```bash
   curl http://localhost:5000/speed/1.25
   curl http://localhost:5000/volume/0.7
   ```
10. Pause, play, toggle and skip with:
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
bindsym $mod+shift+t exec "curl http://localhost:5000/reset"
bindsym Shift+XF86AudioPlay exec "curl http://localhost:5000/toggle"
bindsym Shift+XF86AudioNext exec "curl http://localhost:5000/skip"
```

### Available options

```
usage: tts-reader [-h] [--ip IP] [--port PORT] [--wayland | --no-wayland]
                  [--piper-python | --no-piper-python]
                  [--speechd | --no-speechd] [--volume VOLUME] [--speed SPEED]
                  [--piper-rate PIPER_RATE]
                  [--piper-sentence-silence PIPER_SENTENCE_SILENCE]
                  [--piper-one-sentence | --no-piper-one-sentence]
                  [--piper-model PIPER_MODEL]
                  [--piper-model-config PIPER_MODEL_CONFIG]
                  [--debug | --no-debug]

options:
  -h, --help            show this help message and exit
  --ip IP               IP address
  --port PORT           Port
  --wayland, --no-wayland
                        Assume running under Wayland
  --piper-python, --no-piper-python
                        Attempt to use the piper python module. Has no effect
                        if a different backend is selected
  --speechd, --no-speechd
                        Use speechd instead of piper. Incomplete
  --volume VOLUME       Volume [0-1]
  --speed SPEED         Playback speed [0-10]
  --piper-rate PIPER_RATE
                        Piper: Playback sample rate. More info at https://gith
                        ub.com/rhasspy/piper/blob/master/TRAINING.md
  --piper-sentence-silence PIPER_SENTENCE_SILENCE
                        Piper: Seconds of silence after each sentence
  --piper-one-sentence, --no-piper-one-sentence
                        Piper: Process one sentence at a time, instead of the
                        default whole selection
  --piper-model PIPER_MODEL
                        Piper: Path to the model
  --piper-model-config PIPER_MODEL_CONFIG
                        Piper: Path to the model configuration
  --debug, --no-debug   Enable flask debug mode (developmental purposes)
```
