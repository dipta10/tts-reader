from tts import TTS
import logging

logger = logging.getLogger(__name__)

has_speechd = True
try:
    import speechd
except ImportError:
    has_speechd = False


class Spd(TTS):
    def __init__(self):
        TTS.__init__(self)
        if not has_speechd:
            raise Exception(
                "The speechd python module is unavailable. Please check if you have speech-dispatcher installed and/or you've enabled --system-site-packages for the virtualenv"
            )
        self.sdclient = speechd.SSIPClient("tts-reader" + __name__)

    def __del__(self):
        pass

    def speak(self, text):
        pass

    def play(self):
        pass

    def pause(self):
        pass
