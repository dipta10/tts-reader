# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TTS Reader is a text-to-speech service that reads selected text from anywhere on the system. It runs as a FastAPI HTTP server that accepts requests to read text from the clipboard or via POST request body. The service uses Piper TTS for speech synthesis and supports both Linux and Windows platforms.

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

### Configuration System

The application uses typed configuration dataclasses for type safety and explicit dependencies:

**config/app.py** - AppConfig
- Server-level configuration: IP, port, debug mode, log level
- Used by main.py to configure uvicorn server

**config/piper.py** - PiperConfig
- TTS-specific settings: model paths, rate, speed, volume, sentence silence
- **Shared mutable pattern**: Single instance shared between Controller and Piper backend
- Controller mutates speed/volume at runtime; Piper reads fresh values on next playback
- Includes validation in `__post_init__`: volume [0-1], speed [0-10]

**config/text.py** - TextConfig
- Text processing settings: ignore_chars list, ignore_newline flag
- Used by Controller for text sanitization

### Factory Pattern

All platform-specific services use the factory pattern for consistent instantiation:

**services/tts/factory.py** - `build_tts(config: PiperConfig, use_speechd: bool) -> TTS`
- Selects TTS backend (Piper vs Speechd)
- Injects PiperConfig into backend

**services/clipboard/factory.py** - `build_clipboard(use_wayland: bool) -> Optional[Clipboard]`
- Returns WindowsClipboard (pyperclip) on Windows
- Returns LinuxClipboard (wl-paste or xclip) on Linux

**services/audio/factory.py** - `build_audio_player() -> AudioPlayback`
- Returns FFplayAudio on Windows
- Returns AplayAudio on Linux
- Note: Piper currently uses inline subprocess code instead of this factory

**services/notify/factory.py** - `build_notifier(app_name: str) -> Optional[Notifier]`
- Returns WindowsNotifier (winotify) on Windows
- Returns LinuxNotifier (desktop-notifier) on Linux/macOS

**services/platform.py** - Platform utility
- Centralized platform detection: `Platform.is_windows()`, `Platform.is_linux()`, `Platform.is_macos()`
- Caches result for performance
- Used by all factories for consistent platform checks

### Core Components

**TTS Backend (services/tts/ports.py)**
- Abstract base class `TTS` defines the interface for all TTS backends
- Concrete implementations: `Piper` (services/tts/piper.py) and `Speechd` (services/tts/speechd.py, incomplete)
- Methods: `speak()`, `play()`, `pause()`, `toggle()`, `skip()`, `reset()`, `status()`

**Piper Backend (services/tts/piper.py)**
- Primary TTS implementation using Piper Python API
- Receives `PiperConfig` in constructor (shared with Controller for runtime mutations)
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
- Receives typed config objects: `TextConfig`, `PiperConfig` (shared with Piper)
- Runtime parameter adjustment: `set_speed()` and `set_volume()` mutate shared `PiperConfig`
- Text sanitization: removes ignored characters, normalizes unicode, collapses newlines
- Integrates with notification service to provide user feedback
- Parameter clamping: volume [0-1], speed [0-10]

**Web Layer (web/app.py)**
- FastAPI app with HTTP endpoints mapping to controller operations
- Routes: `/read`, `/status`, `/toggle`, `/play`, `/pause`, `/reset`, `/skip`, `/volume/<float>`, `/speed/<float>`
- `/read` accepts both GET (clipboard) and POST (request body) methods
- Query parameter `?getaudio` returns audio bytes instead of playing
- All handlers are async for better concurrency

**Platform Services (services/)**
- **tts/**: TTS implementations and factory (Piper, Speechd, ports, factory)
- **clipboard/**: Platform-specific clipboard access (LinuxClipboard, WindowsClipboard, factory)
  - Linux: Uses `wl-paste` (Wayland) or `xclip` (X11)
  - Windows: Uses `pyperclip` library
- **audio/**: Audio playback abstractions (FFplayAudio for Windows, AplayAudio for Linux, factory)
- **notify/**: Desktop notifications (LinuxNotifier, WindowsNotifier, factory)
  - Linux: Uses `desktop-notifier` package
  - Windows: Uses `winotify` package
- **reader/**: Application controller (DefaultReaderController, ports)
- **platform.py**: Centralized platform detection utility

**Thread Synchronization (locked.py)**
- `Locked` class: Thread-safe wrapper providing atomic get/set operations with internal lock

### Data Flow

1. HTTP request arrives at FastAPI endpoint (`/read`)
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

**Entry Point and Configuration**
- `main.py`: Entry point, argument parsing, config creation, dependency injection via factories
- `config/app.py`: AppConfig dataclass for server settings
- `config/piper.py`: PiperConfig dataclass for TTS settings with validation
- `config/text.py`: TextConfig dataclass for text processing settings

**Core Application**
- `services/reader/controller.py`: DefaultReaderController orchestrating text processing and TTS
- `web/app.py`: FastAPI application with HTTP endpoints
- `locked.py`: Thread-safe Locked wrapper class

**TTS Backend**
- `services/tts/ports.py`: TTS abstract base class interface
- `services/tts/piper.py`: Piper TTS implementation with threading and audio streaming
- `services/tts/speechd.py`: Speech-dispatcher backend (unimplemented)
- `services/tts/factory.py`: build_tts() factory function

**Platform Services**
- `services/platform.py`: Centralized Platform detection utility
- `services/clipboard/factory.py`: build_clipboard() factory
- `services/audio/factory.py`: build_audio_player() factory
- `services/notify/factory.py`: build_notifier() factory

**Service Structure** (each follows ports & adapters pattern)
- `services/{service}/ports.py`: Abstract interface
- `services/{service}/{impl}.py`: Concrete implementations (linux.py, windows.py, piper.py, etc.)
- `services/{service}/factory.py`: Factory function for platform-specific selection

### Dependency Injection Pattern

The application uses constructor-based dependency injection in `main.py`:

```python
# 1. Parse command-line arguments
parsed = parser.parse_args()

# 2. Create typed configuration objects
app_config = AppConfig(ip=parsed.ip, port=parsed.port, ...)
piper_config = PiperConfig(model=parsed.piper_model, speed=parsed.speed, ...)
text_config = TextConfig(ignore_chars=parsed.ignore_chars, ...)

# 3. Build dependencies using factory functions
clipboard = build_clipboard(use_wayland=parsed.wayland)
tts = build_tts(piper_config, use_speechd=parsed.speechd)
notifier = build_notifier(app_name="tts-reader")

# 4. Inject dependencies into controller
controller = DefaultReaderController(
    text_config=text_config,
    piper_config=piper_config,  # Shared with TTS backend
    tts=tts,
    clipboard=clipboard,
    notifier=notifier,
)

# 5. Create FastAPI app with controller
app = create_app(controller)

# 6. Run server with app config
uvicorn.run(app, host=app_config.ip, port=app_config.port)
```

**Benefits:**
- Clear dependency graph and initialization order
- Type-safe configuration objects
- Easy to test (can inject mocks)
- Single responsibility per component
- Explicit rather than implicit dependencies

## Important Notes

- The `speechd` backend is currently unimplemented (always returns `inited = False`)
- Piper models must be downloaded separately from https://github.com/rhasspy/piper/blob/master/VOICES.md
- The application assumes `ffmpeg`, `aplay` (Linux), or `ffplay` (Windows) are available in PATH
- Thread safety is critical: `reset_issued` flag is checked throughout to allow cancellation
- The `get_queue_lock` prevents mixing results when multiple download requests arrive simultaneously
