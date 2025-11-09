 Comprehensive Architecture Refactoring Plan

 Phase 1: Create Configuration Classes

 Goal: Replace monolithic parsed argparse object with typed configuration classes

 1. Create config/ directory with typed configuration dataclasses:
   - AppConfig: IP, port, debug settings
   - PiperConfig: All piper-specific settings (model, rate, sentence silence, etc.)
   - TextConfig: Character ignore settings, newline handling
   - Extract configurations from parsed in main.py

 2. Update services to accept specific config objects instead of parsed:
   - DefaultReaderController receives TextConfig
   - Piper receives PiperConfig
   - Factories receive only required parameters

 Benefits: Type safety, explicit dependencies, easier testing, cleaner interfaces

 ---
 Phase 2: Add Missing Factories

 Goal: Standardize factory pattern across all services

 3. Create services/tts/factory.py:
   - build_tts(config: PiperConfig, use_speechd: bool) -> TTS
   - Centralizes TTS backend selection logic
   - Keeps Speechd option but handles "unimplemented" gracefully
 4. Create services/audio/factory.py:
   - build_audio_player() -> AudioPlayback
   - Returns FFplayAudio() on Windows, AplayAudio() on Linux
   - Centralizes audio backend selection
   - Note: Won't modify Piper to use it yet (respecting your choice)

 Benefits: Consistent pattern across all services, easier to test and extend

 ---
 Phase 3: Centralize Platform Detection

 Goal: Single source of truth for platform checks

 5. Create services/platform.py:
   - Platform.is_windows(), Platform.is_linux() static methods
   - Update all factories to use this instead of platform.system()

 Benefits: Testability (can mock platform), consistency, DRY principle

 ---
 Phase 4: Standardize Factory Signatures

 Goal: Make all factories consistent and minimal

 6. Update clipboard factory:
   - Change build_clipboard(parsed) → build_clipboard(use_wayland: bool)
   - Extract parsed.wayland in main.py before calling
 7. Update notifier factory:
   - Already clean (build_notifier(app_name: str))
   - No changes needed

 Benefits: Cleaner interfaces, less coupling, easier to understand

 ---
 Phase 5: Update main.py Orchestration

 Goal: Clean dependency construction with new factories

 8. Refactor main.py:
   - Parse arguments into configuration objects
   - Use all factory functions consistently
   - Clean dependency injection into controller
   - Example structure:
   # Parse configs
 app_config = AppConfig(ip=parsed.ip, port=parsed.port, ...)
 piper_config = PiperConfig(model=parsed.piper_model, ...)
 text_config = TextConfig(ignore_chars=parsed.ignore_chars, ...)

 # Build dependencies via factories
 clipboard = build_clipboard(use_wayland=parsed.wayland)
 notifier = build_notifier(app_name="tts-reader")
 tts = build_tts(config=piper_config, use_speechd=parsed.speechd)

 # Inject into controller
 controller = DefaultReaderController(
     config=text_config,
     tts=tts,
     clipboard=clipboard,
     notifier=notifier
 )

 Benefits: Clear dependency graph, single responsibility, easier to understand

 ---
 Phase 6: Update CLAUDE.md

 Goal: Document the new architecture

 9. Update CLAUDE.md to reflect:
   - New configuration classes structure
   - Factory pattern usage across all services
   - Centralized platform detection
   - Improved dependency injection pattern

 ---
 What We're NOT Changing (Per Your Request):

 - ❌ Not refactoring Piper to use AplayAudio (keeping inline code)
 - ❌ Not implementing or removing Speechd backend
 - ❌ Not modifying the FastAPI web layer (already clean)
 - ❌ Not changing the threading/queue architecture in Piper

 Estimated Impact:

 - New files: 6 (config dataclasses, 2 factories, platform utility)
 - Modified files: 5 (main.py, clipboard/notify factories, controller, CLAUDE.md)
 - Deleted files: 0
 - Breaking changes: None (internal refactoring only)
 - External API: Unchanged (all curl commands still work)

 Testing Strategy:

 After each phase, verify the server starts and all endpoints work:
 - Start server with same arguments as before
 - Test all curl commands from README
 - Ensure audio playback still works
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌