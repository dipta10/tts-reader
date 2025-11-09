# TTS Reader

Select and read aloud text from anywhere 🔊

## Quick Setup

**Prerequisites:**
- Python 3.9 or higher
- `ffmpeg` and `aplay` (Linux) installed on your system

Run the automated setup script:
```bash
chmod +x setup.sh
./setup.sh
```

This script will:
- Create a virtual environment
- Install all Python dependencies (including Piper TTS)
- Download a default voice model (en_US-hfc_male-medium)

Then start the server:
```bash
source venv/bin/activate
python main.py --port 5000 --piper-model models/en_US-hfc_male-medium.onnx --piper-model-config models/en_US-hfc_male-medium.onnx.json
```

## Manual Setup

If you prefer to set up manually or need a different voice model, follow these steps (these are the same steps automated in `setup.sh`):

### Requirements

- Python 3.9 or higher (Python 3.10.12+ recommended for Piper compatibility)
- ffmpeg
- aplay (Linux) / working audio output (Windows)
- wl-clipboard (Wayland only) or xclip (X11 only)

### Steps

1. Create a virtual environment with system-site-packages:
   ```bash
   python -m venv venv --system-site-packages
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install --no-deps -r piper.requirements.txt
   ```

   > **Note:** The `--no-deps` flag for piper.requirements.txt is needed due to [this compatibility issue](https://github.com/rhasspy/piper/issues/509).

3. Download voice models from [Piper Voices](https://github.com/rhasspy/piper/blob/master/VOICES.md) and place them in a `models/` directory.

4. Run the server:
   ```bash
   python main.py --port 5000 --speed=1.0 --volume=.8 --piper-model yourmodel.onnx --piper-model-config yourmodel.onnx.json --wayland
   ```

## Usage

### Reading Text

1. To read selected text from clipboard:
   ```bash
   curl http://localhost:5000/read
   ```
2. To read custom text via POST request:
   ```bash
   echo Hope you are having a lovely day, sir. | curl -X POST -H 'Content-Type: application/octet-stream' --data-binary @- localhost:5000/read
   ```
3. To download the generated audio instead of playing it:
   ```bash
   curl 'http://localhost:5000/read?getaudio'
   ```

### Playback Control

```bash
curl http://localhost:5000/reset    # Stop and clear current reading
curl http://localhost:5000/pause    # Pause playback
curl http://localhost:5000/play     # Resume playback
curl http://localhost:5000/toggle   # Toggle pause/play
curl http://localhost:5000/skip     # Skip to next sentence
curl http://localhost:5000/status   # Get playback status
```

### Adjusting Settings

Dynamically change speed and volume:
```bash
curl http://localhost:5000/speed/1.25
curl http://localhost:5000/volume/0.7
```

Ignore certain characters when reading (set at startup):
```bash
python main.py --ignore_chars '*' '-'
```

## Setting Up Keybindings

For practical usage, you can set up keyboard shortcuts in your desktop environment or window manager:

#### Linux (Sway)
If you're running sway, add the following to your config `~/.config/sway/config`:

```shell
bindsym $mod+t exec "curl http://localhost:5000/read"
bindsym $mod+shift+t exec "curl http://localhost:5000/reset"
bindsym Shift+XF86AudioPlay exec "curl http://localhost:5000/toggle"
bindsym Shift+XF86AudioNext exec "curl http://localhost:5000/skip"
```

#### Windows (AutoHotkey)
If you're using Windows, you can use [AutoHotkey](https://www.autohotkey.com/) to set up keybinds. Create an `.ahk` script with:

```autohotkey
; Alt+T to read selected text from clipboard
!t::
	Send ^c
	Sleep 50
    Run, curl.exe http://localhost:5012/read, , Hide
return

; Alt+Shift+T to stop/reset reading
!+t::
    Run, curl.exe http://localhost:5012/reset, , Hide
return
```

## Command-Line Options

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
                  [--ignore_chars [IGNORE_CHARS ...]]
                  [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

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
  --ignore_chars [IGNORE_CHARS ...]
                        List of characters to ignore
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the logging level
```
