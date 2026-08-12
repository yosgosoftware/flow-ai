import queue
import threading
import time
import winsound


START = ((523, 70), (784, 100))
STOP = ((659, 80), (494, 90))
SUCCESS = ((784, 70), (1046, 130))
FAILURE = ((196, 140), (147, 180))


class AudioCues:
    def __init__(self):
        self._enabled = True
        self._queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="FlowAI-AudioCues",
        )
        self._thread.start()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)

    def on_status(self, state, *args):
        if state == "listening":
            self._play(START)
        elif state == "transcribing":
            self._play(STOP)

    def on_success(self, *args):
        self._play(SUCCESS)

    def on_error(self, *args):
        self._play(FAILURE)

    def _play(self, sequence):
        if not self._enabled:
            return
        self._queue.put(sequence)

    def _run(self):
        while True:
            sequence = self._queue.get()
            for freq, ms in sequence:
                try:
                    winsound.Beep(freq, ms)
                except Exception:
                    pass
                time.sleep(0.02)