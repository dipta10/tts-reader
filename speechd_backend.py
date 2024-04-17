from tts import TTS
import logging
import time

logger = logging.getLogger(__name__)

has_speechd = True
try:
    import speechd
except ImportError:
    has_speechd = False


class Speechd(TTS):
    def __init__(self, parsed):
        super().__init__()
        if not has_speechd:
            raise Exception(
                "The speechd python module is unavailable. Please check if you have speech-dispatcher installed and/or you've enabled --system-site-packages for the virtualenv"
            )
        self.parsed = parsed
        self.sdclient = speechd.SSIPClient(f"tts-reader_{__name__}_{time.time()}")
        self.inited = True

    def __del__(self):
        self.sdclient.close()

    def speak(self, text):
        self.sdclient.speak(text)

    def play(self):
        pass

    def pause(self):
        pass

    def toggle(self):
        pass

    def skip(self):
        pass

    def reset(self):
        pass

    def status(self):
        pass