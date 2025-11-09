# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TTS Reader is a text-to-speech service that reads selected text from anywhere on the system. It runs as a Flask HTTP server that accepts requests to read text from the clipboard or via POST request body. The service uses Piper TTS for speech synthesis and supports both Linux and Windows platforms.

## Development Setup

### Initial Setup

1. Create virtual environment with system-site-packages:
   ```bash
   python -m venv venv --system-site-packages
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. For Piper TTS Python module compatibility, use Python v3.10.12 or install specific dependencies:
   ```bash
   pip install --no-deps -r piper.requirements.txt
   ```

### Running the Application

Basic command:
```bash
python main.py --port 5000 --speed=1.0 --volume=.8 --piper-model yourmodel.onnx --piper-model-config yourmodel.onnx.json --wayland
```

Example from run_app.sh:
```bash
python main.py --port 5012 --speed=1.2 --piper-one-sentence --piper-sentence-silence=0.1 --volume=1 --piper-model models/new-models/en_US-hfc_male-medium.onnx --piper-model-config models/new-models/en_US-hfc_male-medium.onnx.json --wayland --ignore_chars "*" "\n" --ignore_newline
```

### Testing the API

```bash
# Read selected text from clipboard
curl http://localhost:5000/read

# Read custom text via POST
echo "Hello world" | curl -X POST -H 'Content-Type: application/octet-stream' --data-binary @- localhost:5000/read

# Download audio instead of playing
curl 'http://localhost:5000/read?getaudio'

# Control playback
curl http://localhost:5000/reset
curl http://localhost:5000/toggle
curl http://localhost:5000/pause
curl http://localhost:5000/play
curl http://localhost:5000/skip

# Get status
curl http://localhost:5000/status

# Adjust parameters
curl http://localhost:5000/speed/1.25
curl http://localhost:5000/volume/0.7
```

## Architecture

### Core Components

**TTS Backend (tts.py)**
- Abstract base class `TTS` defines the interface for all TTS backends
- Concrete implementations: `Piper` (piper_backend.py) and `Speechd` (speechd_backend.py, incomplete)
- Methods: `speak()`, `play()`, `pause()`, `toggle()`, `skip()`, `reset()`, `status()`

**Piper Backend (piper_backend.py)**
- Primary TTS implementation using Piper Python API
- Uses **three queues** for pipeline processing:
  - `gen_queue`: Queues text for TTS synthesis
  - `play_queue`: Queues audio chunks for playback
  - `get_queue`: Returns generated audio for download requests
- Two worker threads:
  - `gen_thread`: Runs `run_gen_thread()` to synthesize speech from text
  - `play_thread`: Runs `run_play_thread()` to play audio chunks
- Platform-specific audio handling:
  - **Linux**: Streams audio through `ffmpeg` → `aplay` pipeline
  - **Windows**: Uses `FFplayAudio` service (services/audio/ffplay.py)
- Supports streaming playback via `STREAM_START`/`STREAM_END` sentinels
- Thread-safe state management via `Locked` wrapper class

**Reader Controller (services/reader/controller.py)**
- `DefaultReaderController` orchestrates clipboard reading, text sanitization, and TTS
- Text sanitization: removes ignored characters, normalizes unicode, collapses newlines
- Integrates with notification service to provide user feedback
- Parameter clamping: volume [0-1], speed [0-10]

**Web Layer (web/app.py)**
- Flask app with HTTP endpoints mapping to controller operations
- Routes: `/read`, `/status`, `/toggle`, `/play`, `/pause`, `/reset`, `/skip`, `/volume/<float>`, `/speed/<float>`
- `/read` accepts both GET (clipboard) and POST (request body) methods
- Query parameter `?getaudio` returns audio bytes instead of playing

**Platform Services (services/)**
- **clipboard/**: Platform-specific clipboard access (LinuxClipboard, WindowsClipboard)
  - Linux: Uses `wl-paste` (Wayland) or `xclip` (X11)
  - Windows: Uses `pyperclip` library
- **audio/**: Audio playback abstractions (FFplayAudio for Windows)
- **notify/**: Desktop notifications (LinuxNotifier, WindowsNotifier)
  - Linux: Uses `desktop-notifier` package
  - Windows: Uses `winotify` package

**Thread Synchronization (locked.py)**
- `Locked` class: Thread-safe wrapper providing atomic get/set operations with internal lock

### Data Flow

1. HTTP request arrives at Flask endpoint (`/read`)
2. `ReaderController.read_clipboard()` or `read_text()` is called
3. Text is sanitized (character removal, unicode normalization)
4. Text is queued to `gen_queue`
5. `gen_thread` synthesizes speech using Piper, produces audio chunks
6. For playback: chunks go to `play_queue` → `play_thread` → platform audio (ffmpeg+aplay or FFplay)
7. For download: chunks accumulate in `get_queue` and are returned as HTTP response
8. Desktop notification is sent to user

### Platform Differences

**Linux**:
- Streams audio through subprocess pipeline: `ffmpeg` (effects) → `aplay` (playback)
- Uses POSIX signals (SIGCONT, SIGSTOP, SIGKILL) for process control
- Clipboard access via `wl-paste`/`xclip` command-line tools

**Windows**:
- Uses `FFplayAudio` service which writes PCM to temp file and plays via `ffplay`
- Cannot use signal-based pause/resume (signals not supported)
- Clipboard access via `pyperclip` library
- Requires `ffplay` executable in PATH

### Key Files

- `main.py`: Entry point, argument parsing, dependency injection
- `piper_backend.py`: Core TTS implementation with threading and audio streaming
- `services/reader/controller.py`: Application logic and text processing
- `web/app.py`: HTTP API layer
- `locked.py`: Thread synchronization primitive
- `services/clipboard/factory.py`: Platform detection and clipboard provider selection
- `services/notify/factory.py`: Platform detection and notification provider selection

## Important Notes

- The `speechd` backend is currently unimplemented (always returns `inited = False`)
- Piper models must be downloaded separately from https://github.com/rhasspy/piper/blob/master/VOICES.md
- The application assumes `ffmpeg`, `aplay` (Linux), or `ffplay` (Windows) are available in PATH
- Thread safety is critical: `reset_issued` flag is checked throughout to allow cancellation
- The `get_queue_lock` prevents mixing results when multiple download requests arrive simultaneously
