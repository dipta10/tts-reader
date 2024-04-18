import threading

class Locked:
    def __init__(self, data=None):
        self.data = data
        self.lock = threading.Lock()

    def set(self, data):
        with self.lock:
            self.data = data

    def get(self):
        with self.lock:
            return self.data
