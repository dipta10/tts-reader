  1. You have Ports & Adapters for the WRONG layer

  You've abstracted platform-specific stuff (clipboard, notifications), which is fine.
  But look at piper_backend.py - it's 600+ lines doing:
  - TTS synthesis
  - Audio pipeline management
  - Thread orchestration
  - Queue management
  - Platform detection for audio playback
  - Streaming logic

  This violates Single Responsibility Principle massively. The "Piper" backend is not
  just a TTS adapter - it's your entire audio pipeline engine.

  2. Missing the Core Domain Layer

  Where is your business logic? You have:
  - Infrastructure (clipboard, audio, TTS libraries)
  - Presentation (Flask HTTP endpoints)
  - A thin controller that mostly delegates

  But no domain model. Questions like "what is a speech request?", "what are the rules
  for text sanitization?", "what states can playback be in?" - these aren't explicitly
  modeled.

  3. Concurrency Model is Primitive

  You're using manual threads + queues in 2025. This is error-prone:
  - No graceful shutdown protocol
  - Hard to test
  - The Locked class reinvents threading.Lock()
  - Thread lifecycle is unclear

  For production, you should be using asyncio with FastAPI, not Flask + threads.

  What Architecture SHOULD You Use?

  Given that this is a concurrent, I/O-bound application with background processing,
  here's what I'd recommend:

  Clean Architecture + Event-Driven Design

  ┌─────────────────────────────────────────┐
  │         Presentation Layer              │
  │  (FastAPI routes, WebSocket for status) │
  └─────────────────┬───────────────────────┘
                    │
  ┌─────────────────▼───────────────────────┐
  │        Application Layer                │
  │  (Use Cases / Command Handlers)         │
  │  - ReadTextUseCase                      │
  │  - ControlPlaybackUseCase               │
  │  - GetStatusUseCase                     │
  └─────────────────┬───────────────────────┘
                    │
  ┌─────────────────▼───────────────────────┐
  │          Domain Layer                   │
  │  (Business Logic - Pure Python)         │
  │  - TextDocument (entity)                │
  │  - PlaybackSession (aggregate)          │
  │  - TextSanitizer (domain service)       │
  │  - PlaybackState (state machine)        │
  └─────────────────┬───────────────────────┘
                    │
  ┌─────────────────▼───────────────────────┐
  │      Infrastructure Layer               │
  │  (Ports & Adapters live here)           │
  │  - TTS adapters (Piper, Speech-d)       │
  │  - Audio adapters (FFmpeg, etc)         │
  │  - Clipboard adapters                   │
  │  - Notification adapters                │
  └─────────────────────────────────────────┘

  Critical Missing Components

  1. State Machine for Playback
  # domain/playback_state.py
  class PlaybackState(Enum):
      IDLE = "idle"
      SYNTHESIZING = "synthesizing"
      PLAYING = "playing"
      PAUSED = "paused"

  class PlaybackStateMachine:
      # Defines valid state transitions
      # This is DOMAIN LOGIC, not infrastructure
  2. Audio Pipeline as First-Class Service
  # application/audio_pipeline.py
  class AudioPipeline:
      """Orchestrates synthesis → streaming → playback"""
      # Currently buried in piper_backend.py
  3. Event Bus for Decoupling
  # Events:
  class TextCaptured(Event)
  class SynthesisStarted(Event)
  class AudioChunkGenerated(Event)
  class PlaybackStateChanged(Event)

  # Handlers subscribe to events
  # No direct coupling between components
  4. Proper Dependency Injection
  # Use dependency-injector library
  # Not manual wiring in main.py
  5. Async/Await Instead of Threads
  # Use asyncio queues, not threading.Queue
  # Use aiohttp or FastAPI, not Flask
  # Background tasks with asyncio.create_task()

  Specific Problems in Current Design

  Let me point out actual issues:

  Problem 1: TTS Backend is Too Fat

  piper_backend.py should be:
  class PiperTTSAdapter(TTS):
      """Just wraps Piper library - nothing else"""
      async def synthesize(self, text: str) -> AsyncIterator[bytes]:
          # Only TTS synthesis, no playback logic

  But currently it also manages the entire audio pipeline. Wrong layer.

  Problem 2: No Separation of Audio Streaming from Playback

  You have:
  Text → TTS → [gen_queue → gen_thread → play_queue → play_thread] → Audio

  This should be:
  Text → SynthesisService → AudioPipeline → PlaybackService
        (domain)           (application)    (infrastructure)

  Problem 3: ReaderController Violates SRP

  class DefaultReaderController(ReaderController):
      def read_clipboard(self, getaudio: bool):
          text = self.clipboard.read_text()  # Infrastructure
          text = sanitize_text(text)          # Domain logic
          self.tts.speak(text, getaudio)     # Application orchestration

  This mixes 3 different concerns. Should be:

  class ReadTextUseCase:
      def __init__(self, clipboard: ClipboardPort,
                   sanitizer: TextSanitizer,
                   audio_pipeline: AudioPipeline):
          # Clear dependencies

      async def execute(self, request: ReadTextRequest) -> ReadTextResponse:
          # Pure orchestration

  Problem 4: No Error Handling Strategy

  Where are your custom exceptions? Where's retry logic? Circuit breakers for external
  dependencies?

  # Should have:
  class TTSynthesisError(Exception): pass
  class ClipboardAccessError(Exception): pass
  class AudioPlaybackError(Exception): pass

  # With retry decorators, circuit breakers, etc.

  Problem 5: No Observability

  Production apps need:
  - Structured logging (JSON logs)
  - Metrics (Prometheus): synthesis_duration, queue_depth, error_rate
  - Distributed tracing (OpenTelemetry)
  - Health checks (/health, /ready endpoints)

  What You Should Do

  If learning enterprise architecture (your goal):

  1. Refactor to Clean Architecture:
    - Extract domain layer (entities, value objects, domain services)
    - Create application layer (use cases)
    - Move current code to infrastructure layer
    - Add proper DI container
  2. Add Missing Patterns:
    - State Machine for playback states
    - Strategy Pattern for different TTS backends
    - Observer Pattern or Event Bus for status updates
    - Repository Pattern if you add persistence (logs, history)
  3. Migrate to Async:
    - Replace Flask → FastAPI
    - Replace threading.Queue → asyncio.Queue
    - Replace threads → asyncio.create_task()
    - Replace subprocess pipes → asyncio subprocess
  4. Add Production Concerns:
    - Structured logging everywhere
    - Prometheus metrics
    - Health check endpoints
    - Graceful shutdown handling
    - Configuration management (12-factor)
  5. Add Proper Testing:
    - Unit tests for domain layer (pure functions)
    - Integration tests for adapters
    - End-to-end tests for use cases
    - Property-based testing for text sanitization

  The Bigger Picture

  Your current architecture is Ports & Adapters applied superficially. You have the
  pattern for platform abstractions, but:
  - No clear layering (domain vs application vs infrastructure)
  - No domain model
  - Wrong concurrency model for 2025
  - Missing observability, error handling, testing strategy

  For a real production app, you need:
  - Architectural LAYERS (macro structure)
  - Design PATTERNS (micro structure)
  - Cross-cutting CONCERNS (logging, metrics, errors)
  - Modern CONCURRENCY (async/await)
  - TESTABILITY (DI, pure functions, isolation)

  Want me to help refactor this toward proper Clean Architecture + async/await +
  event-driven design?