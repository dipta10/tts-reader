from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .ports import TTS
from .piper import Piper
from .speechd import Speechd

if TYPE_CHECKING:
    from config import PiperConfig

logger = logging.getLogger(__name__)


def build_tts(config: PiperConfig, use_speechd: bool = False) -> TTS:
    """Factory function to build TTS backend.

    Args:
        config: PiperConfig with TTS settings (used by Piper backend)
        use_speechd: If True, use speech-dispatcher backend (currently unimplemented)

    Returns:
        TTS implementation instance (Piper or Speechd)

    Note:
        Speechd backend is currently unimplemented and will always return inited=False.
        The factory will create it but it won't be usable.
    """
    if use_speechd:
        # Note: Speechd still uses old interface, needs refactoring
        # For now, pass a dummy object to satisfy its __init__
        logger.warning("Speech-dispatcher backend is currently unimplemented")
        return Speechd(None)  # Will set inited=False immediately

    return Piper(config)
