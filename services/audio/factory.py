from __future__ import annotations

import logging

from services.platform import Platform
from .ports import AudioPlayback
from .ffplay import FFplayAudio
from .aplay import AplayAudio

logger = logging.getLogger(__name__)


def build_audio_player() -> AudioPlayback:
    """Factory function to build platform-specific audio playback backend.

    Returns:
        AudioPlayback implementation appropriate for the current platform.
        - Windows: FFplayAudio (uses ffplay via temp file)
        - Linux: AplayAudio (uses ffmpeg → aplay pipeline)

    Note:
        Currently, the Piper backend uses inline subprocess code for Linux
        instead of AplayAudio. This factory is provided for future refactoring
        and consistency with other service factories.
    """
    if Platform.is_windows():
        logger.debug("Using FFplayAudio for Windows")
        return FFplayAudio()

    logger.debug("Using AplayAudio for Linux")
    return AplayAudio()
