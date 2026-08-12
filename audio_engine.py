import math
import os
import tempfile
import threading
import uuid
import wave

import numpy as np

try:
    import pyaudio
except ImportError:
    import pyaudiowpatch as pyaudio

RATE_PREFERENCES = (16000, 48000, 44100)
CHUNK = 256


class AudioEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._pa = None
        self._stream = None
        self._recording = False
        self._buffer = []
        self._last_db = -60.0
        self._samplerate = 0
        self._device_name = None

    def _get_pa(self):
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        return self._pa

    def list_devices(self):
        try:
            pa = self._get_pa()
            devices = []
            seen = set()
            for index in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(index)
                if int(info.get("maxInputChannels") or 0) > 0:
                    name = str(info.get("name") or "Device %d" % index).strip()
                    if name and name not in seen:
                        seen.add(name)
                        devices.append(
                            {
                                "index": index,
                                "name": name,
                                "channels": int(info["maxInputChannels"]),
                                "rate": int(info.get("defaultSampleRate") or 0),
                            }
                        )
            return devices
        except Exception:
            return []

    def default_device_name(self):
        try:
            info = self._get_pa().get_default_input_device_info()
            return str(info.get("name") or "").strip() or None
        except Exception:
            return None

    def find_device(self, name):
        for device in self.list_devices():
            if device["name"] == name:
                return device
        return None

    @property
    def samplerate(self):
        with self._lock:
            return self._samplerate

    @property
    def device(self):
        with self._lock:
            return self._device_name

    def open(self, device_name=None):
        self.close()
        if device_name is None:
            device_name = self.default_device_name()
        device = self.find_device(device_name)
        if device is None:
            device_name = self.default_device_name()
            device = self.find_device(device_name)
        if device is None:
            return False
        pa = self._get_pa()
        rates = [RATE_PREFERENCES[0]] + list(RATE_PREFERENCES[1:])
        for rate in rates:
            try:
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=int(rate),
                    input=True,
                    input_device_index=int(device["index"]),
                    frames_per_buffer=CHUNK,
                    stream_callback=self._callback,
                )
                stream.start_stream()
            except Exception:
                continue
            with self._lock:
                self._stream = stream
                self._samplerate = int(rate)
                self._device_name = device["name"]
            return True
        return False

    def close(self):
        with self._lock:
            stream = self._stream
            self._stream = None
            self._recording = False
            self._buffer = []
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def current_db(self):
        with self._lock:
            return self._last_db

    def start_recording(self):
        with self._lock:
            self._recording = True
            self._buffer = []

    def cancel_recording(self):
        with self._lock:
            self._recording = False
            self._buffer = []

    def finish_recording(self):
        with self._lock:
            self._recording = False
            chunks = self._buffer
            self._buffer = []
            samplerate = self._samplerate
        if not chunks:
            return None
        samples = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        if samples.size < max(1, samplerate // 10):
            return None
        path = os.path.join(tempfile.gettempdir(), "flowai_%s.wav" % uuid.uuid4().hex)
        try:
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(samplerate)
                wav_file.writeframes(samples.tobytes())
        except OSError:
            return None
        return path

    def _callback(self, in_data, frame_count, time_info, status):
        raw = np.frombuffer(in_data, dtype=np.int16)
        samples = raw.astype(np.float64)
        mean_square = float(np.mean(samples ** 2))
        if mean_square > 0.0:
            db = 20.0 * math.log10(math.sqrt(mean_square) / 32768.0)
        else:
            db = -90.0
        db = max(-60.0, min(0.0, db))
        with self._lock:
            self._last_db = db
            if self._recording:
                self._buffer.append(raw.copy())
        return (None, pyaudio.paContinue)
