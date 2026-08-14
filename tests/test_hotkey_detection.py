"""Smoke test for FlowAI's global push-to-talk hotkey detection.

Runs the real HotkeyManager with stub audio/callbacks and simulates the
default Ctrl+Space combo through SendInput, verifying that holding the combo
flips the manager into "listening" and releasing it stops the recording.

The second scenario blinds the low-level hook (simulating a foreground window
running at a higher integrity level, where WH_KEYBOARD_LL cannot see input) and
confirms the GetAsyncKeyState fallback still triggers push-to-talk.

Run from the repo root:
    .venv\\Scripts\\python.exe tests\\test_hotkey_detection.py
"""

import ctypes
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hotkey_manager as hkm

VK_LCTRL = 0xA2
VK_SPACE = 0x20


class _Signal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _Callbacks:
    def __init__(self):
        self.status_changed = _Signal()
        self.transcription_done = _Signal()
        self.transcription_error = _Signal()
        self.hotkey_captured = _Signal()
        self.capture_state_changed = _Signal()


class _Audio:
    def __init__(self):
        self.recording = False
        self.started = 0
        self.finished = 0

    def start_recording(self):
        self.recording = True
        self.started += 1

    def finish_recording(self):
        self.recording = False
        self.finished += 1
        return None

    def cancel_recording(self):
        self.recording = False


class _Config:
    def __init__(self):
        self.hotkey = ["ctrl", "space"]
        self.model = "tiny"


class _FakeTranscriber:
    def __init__(self, config):
        self.config = config

    def is_ready(self):
        return True

    def is_loading(self):
        return False

    def active_model(self):
        return self.config.model

    def set_completion_callback(self, on_done):
        pass

    def switch_model(self, size):
        return True

    def transcribe(self, wav_path, hwnd, on_done, on_error):
        pass


_user32 = hkm._user32


def _send_key(vk, down):
    buf = (hkm.INPUT * 1)()
    buf[0].type = hkm.INPUT_KEYBOARD
    buf[0].u.ki.wVk = vk
    buf[0].u.ki.dwFlags = 0 if down else hkm.KEYEVENTF_KEYUP
    inputs = ctypes.cast(buf, ctypes.POINTER(hkm.INPUT))
    ctypes.windll.kernel32.SetLastError(0)
    sent = _user32.SendInput(1, inputs, ctypes.sizeof(hkm.INPUT))
    if sent != 1:
        print("SendInput failed: vk=%s down=%s err=%s" % (hex(vk), down, ctypes.get_last_error()))
    return sent == 1


def _send_combo(press):
    return _send_key(VK_LCTRL, press) and _send_key(VK_SPACE, press)


def _wait_for(predicate, timeout=4.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _build_manager(blind_hook=False):
    hkm.Transcriber = _FakeTranscriber
    config = _Config()
    audio = _Audio()
    callbacks = _Callbacks()
    manager = hkm.HotkeyManager(config, audio, callbacks, lambda: False, None)
    # The test session's borderless console looks "fullscreen" to the
    # app's game-detection heuristic; treat it as a normal window so the
    # push-to-talk state machine runs.
    manager._is_fullscreen_app = lambda: False
    if blind_hook:
        def blind(n_code, w_param, l_param):
            return _user32.CallNextHookEx(0, n_code, w_param, l_param)
        manager._hook_callback = blind
    return manager, audio, callbacks


def _hold_then_release(manager, audio, callbacks):
    assert _send_combo(True), "failed to inject combo press"
    try:
        ok = _wait_for(lambda: manager._state == "listening" and audio.recording)
        assert ok, "combo press did not start listening (state=%s, recording=%s)" % (
            manager._state, audio.recording)
        assert any(c and c[0] == "listening" for c in callbacks.status_changed.calls)
        time.sleep(0.25)
        assert manager._state == "listening", "listening dropped while still held"
    finally:
        _send_combo(False)
    ok = _wait_for(lambda: manager._state == "idle" and not audio.recording)
    assert ok, "combo release did not stop listening (state=%s, recording=%s)" % (
        manager._state, audio.recording)


def _test_hook_path():
    manager, audio, callbacks = _build_manager(blind_hook=False)
    manager.start()
    try:
        assert manager._hook_ready.wait(3.0), "global hook thread did not start"
        assert manager._hook_active, "WH_KEYBOARD_LL hook was not installed"
        time.sleep(0.3)
        assert manager._state == "idle"
        _hold_then_release(manager, audio, callbacks)
    finally:
        manager.stop()


def _test_async_fallback_path():
    manager, audio, callbacks = _build_manager(blind_hook=True)
    manager.start()
    try:
        assert manager._hook_ready.wait(3.0), "global hook thread did not start"
        time.sleep(0.3)
        _hold_then_release(manager, audio, callbacks)
    finally:
        manager.stop()


def main():
    _test_hook_path()
    print("PASS: WH_KEYBOARD_LL hook path triggers and stops push-to-talk")
    _test_async_fallback_path()
    print("PASS: GetAsyncKeyState fallback triggers and stops push-to-talk")
    return 0


if __name__ == "__main__":
    sys.exit(main())