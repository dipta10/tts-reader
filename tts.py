from abc import ABC, abstractmethod


class TTS(ABC):
    def __init__(self):
        self.inited = False
        pass

    def __del__(self):
        pass

    @abstractmethod
    def speak(self, text):
        pass

    @abstractmethod
    def play(self):
        pass

    @abstractmethod
    def pause(self):
        pass

    @abstractmethod
    def toggle(self):
        pass

    @abstractmethod
    def skip(self):
        pass

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def status(self):
        pass
