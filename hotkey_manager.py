import ctypes
import ctypes.wintypes
import os
import threading
import time

import keyboard
import pyperclip

MODIFIERS = {"ctrl", "alt", "shift", "win"}

REMAP = {
    "left ctrl": "ctrl",
    "right ctrl": "ctrl",
    "left control": "ctrl",
    "right control": "ctrl",
    "control": "ctrl",
    "left shift": "shift",
    "right shift": "shift",
    "shift": "shift",
    "left alt": "alt",
    "right alt": "alt",
    "alt gr": "alt",
    "alt": "alt",
    "left windows": "win",
    "right windows": "win",
    "windows": "win",
    "win": "win",
    "cmd": "win",
    "super": "win",
}

DISPLAY = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "space": "Space",
    "enter": "Enter",
    "esc": "Esc",
    "tab": "Tab",
    "backspace": "Backspace",
    "caps lock": "Caps Lock",
    "delete": "Del",
    "insert": "Ins",
    "home": "Home",
    "end": "End",
    "page up": "PgUp",
    "page down": "PgDn",
    "print screen": "PrtSc",
    "scroll lock": "Scroll Lock",
    "pause": "Pause",
    "up": "\u2191",
    "down": "\u2193",
    "left": "\u2190",
    "right": "\u2192",
    "num lock": "Num Lock",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
    "f13": "F13",
    "f14": "F14",
    "f15": "F15",
    "f16": "F16",
    "f17": "F17",
    "f18": "F18",
    "f19": "F19",
    "f20": "F20",
    "f21": "F21",
    "f22": "F22",
    "f23": "F23",
    "f24": "F24",
}


def normalize_key(name):
    n = (name or "").strip().lower()
    if n in REMAP:
        return REMAP[n]
    if n.startswith("left "):
        n = n[5:]
    elif n.startswith("right "):
        n = n[6:]
    return n


def is_modifier(key):
    return key in MODIFIERS


def order_combo(keys):
    first, second = keys[0], keys[1]
    if is_modifier(first) and not is_modifier(second):
        return [first, second]
    if is_modifier(second) and not is_modifier(first):
        return [second, first]
    return [first, second] if first <= second else [second, first]


def display_key(key):
    if key in DISPLAY:
        return DISPLAY[key]
    if len(key) == 1:
        return key.upper()
    return key.capitalize()


def format_combo(keys):
    return " + ".join(display_key(key) for key in keys)


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- Win32 constants ---
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
SM_CXSCREEN = 0
SM_CYSCREEN = 1
HOTKEY_ID = 0x5A5A
PM_NOREMOVE = 0

SW_SHOW = 5
SW_RESTORE = 9
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56

MOD_FLAGS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("message", ctypes.wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_size_t),
        ("time", ctypes.wintypes.DWORD),
        ("pt", ctypes.wintypes.POINT),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.wintypes.LONG),
        ("top", ctypes.wintypes.LONG),
        ("right", ctypes.wintypes.LONG),
        ("bottom", ctypes.wintypes.LONG),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.wintypes.DWORD),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("u", _INPUTUNION),
    ]


KEY_EVENT = 0x0001
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", ctypes.wintypes.BOOL),
        ("wRepeatCount", ctypes.wintypes.WORD),
        ("wVirtualKeyCode", ctypes.wintypes.WORD),
        ("wVirtualScanCode", ctypes.wintypes.WORD),
        ("uChar", ctypes.wintypes.WCHAR),
        ("dwControlKeyState", ctypes.wintypes.DWORD),
    ]


class INPUT_RECORD_UNION(ctypes.Union):
    _fields_ = [("KeyEvent", KEY_EVENT_RECORD)]


class INPUT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventType", ctypes.wintypes.WORD),
        ("Event", INPUT_RECORD_UNION),
    ]


LOWLEVEL_KEYBOARD_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)

_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LOWLEVEL_KEYBOARD_PROC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
_user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK
_user32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
_user32.CallNextHookEx.restype = ctypes.wintypes.LPARAM
_user32.UnhookWindowsHookEx.argtypes = [ctypes.wintypes.HHOOK]
_user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL
_user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
_user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL
_user32.RegisterHotKey.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.c_int,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
_user32.RegisterHotKey.restype = ctypes.wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = ctypes.wintypes.BOOL
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int
_user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(RECT)]
_user32.GetWindowRect.restype = ctypes.wintypes.BOOL
_user32.GetWindowLongPtrW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_longlong
_user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
_user32.IsIconic.restype = ctypes.wintypes.BOOL
_user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.ShowWindow.restype = ctypes.wintypes.BOOL
_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
_user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
_user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL
_user32.BringWindowToTop.argtypes = [ctypes.wintypes.HWND]
_user32.BringWindowToTop.restype = ctypes.wintypes.BOOL
_user32.AttachThreadInput.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.BOOL,
]
_user32.AttachThreadInput.restype = ctypes.wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
_user32.SendInput.argtypes = [
    ctypes.wintypes.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
]
_user32.SendInput.restype = ctypes.wintypes.UINT
_kernel32.GetCurrentThreadId.argtypes = []
_kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD
_kernel32.GetModuleHandleW.argtypes = [ctypes.wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE
_kernel32.AttachConsole.argtypes = [ctypes.wintypes.DWORD]
_kernel32.AttachConsole.restype = ctypes.wintypes.BOOL
_kernel32.FreeConsole.argtypes = []
_kernel32.FreeConsole.restype = ctypes.wintypes.BOOL
_kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
]
_kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
_kernel32.WriteConsoleInputW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(INPUT_RECORD),
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_kernel32.WriteConsoleInputW.restype = ctypes.wintypes.BOOL
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
_user32.GetMessageW.argtypes = [
    ctypes.POINTER(MSG),
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
_user32.GetMessageW.restype = ctypes.wintypes.BOOL
_user32.PeekMessageW.argtypes = [
    ctypes.POINTER(MSG),
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
_user32.PeekMessageW.restype = ctypes.wintypes.BOOL
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
_user32.DispatchMessageW.restype = ctypes.wintypes.LPARAM

# Virtual-key code -> normalized name (the only keys FlowAI ever inspects).
VK_TO_NAME = {
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x5B: "win", 0x5C: "win",
    0x20: "space",
    0x0D: "enter",
    0x1B: "esc",
    0x09: "tab",
    0x08: "backspace",
    0x14: "caps lock",
    0x2E: "delete",
    0x2D: "insert",
    0x24: "home",
    0x23: "end",
    0x21: "page up",
    0x22: "page down",
    0x2C: "print screen",
    0x91: "scroll lock",
    0x13: "pause",
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x90: "num lock",
}


def vk_to_name(vk):
    if vk in VK_TO_NAME:
        return VK_TO_NAME[vk]
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return "f%d" % (vk - 0x70 + 1)
    return None


def name_to_vks(name):
    name = normalize_key(name)
    if name == "win":
        return [0x5B, 0x5C]
    if name == "ctrl":
        return [0x11, 0xA2, 0xA3]
    if name == "shift":
        return [0x10, 0xA0, 0xA1]
    if name == "alt":
        return [0x12, 0xA4, 0xA5]
    direct = [vk for vk, n in VK_TO_NAME.items() if n == name]
    if direct:
        return direct
    if len(name) == 1 and name.isalpha():
        return [ord(name.upper())]
    if len(name) == 1 and name.isdigit():
        return [ord(name)]
    if name.startswith("f") and name[1:].isdigit():
        n = int(name[1:])
        if 1 <= n <= 24:
            return [0x70 + n - 1]
    return []


def _press_ctrl_v():
    def send(events):
        buf = (INPUT * len(events))()
        for i, (vk, flags) in enumerate(events):
            buf[i].type = INPUT_KEYBOARD
            buf[i].u.ki.wVk = vk
            buf[i].u.ki.dwFlags = flags
        inputs = ctypes.cast(buf, ctypes.POINTER(INPUT))
        return _user32.SendInput(len(events), inputs, ctypes.sizeof(INPUT))

    for _ in range(3):
        if send([(VK_CONTROL, 0)]) < 1:
            time.sleep(0.06)
            continue
        time.sleep(0.02)
        v_ok = send([(VK_V, 0), (VK_V, KEYEVENTF_KEYUP)]) >= 2
        time.sleep(0.02)
        send([(VK_CONTROL, KEYEVENTF_KEYUP)])
        if v_ok:
            return True
        time.sleep(0.06)
    return False


def activate_window(hwnd):
    if not hwnd:
        return False
    try:
        if not _user32.IsWindow(hwnd):
            return False
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, SW_RESTORE)
        cur_thread = _kernel32.GetCurrentThreadId()
        fg = _user32.GetForegroundWindow()
        fg_thread = _user32.GetWindowThreadProcessId(fg, None)
        target_thread = _user32.GetWindowThreadProcessId(hwnd, None)
        attached = []
        for tid in (fg_thread, target_thread):
            if tid and tid != cur_thread:
                if _user32.AttachThreadInput(cur_thread, tid, True):
                    attached.append(tid)
        try:
            _user32.BringWindowToTop(hwnd)
            _user32.SetForegroundWindow(hwnd)
            return int(_user32.GetForegroundWindow()) == int(hwnd)
        finally:
            for tid in attached:
                _user32.AttachThreadInput(cur_thread, tid, False)
    except Exception:
        return False


def _write_console_input(pid, text):
    """Inject text straight into another process's console input buffer.

    Terminal apps like OpenCode run the console in raw/VT input mode, where a
    Ctrl+V paste is delivered to the app as a literal ^V key event instead of
    pasting. Writing the text as console input records works regardless of the
    console's input mode. Returns True when the text was queued.
    """
    if not pid:
        return False
    attached = bool(_kernel32.AttachConsole(pid))
    if not attached:
        _kernel32.FreeConsole()
        attached = bool(_kernel32.AttachConsole(pid))
    if not attached:
        return False
    try:
        conin = _kernel32.CreateFileW(
            "CONIN$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if not conin or conin == INVALID_HANDLE_VALUE:
            return False
        text = text.replace("\r", " ").replace("\n", " ")
        records = (INPUT_RECORD * (len(text) * 2))()
        for i, char in enumerate(text):
            records[2 * i].EventType = KEY_EVENT
            records[2 * i].Event.KeyEvent.bKeyDown = True
            records[2 * i].Event.KeyEvent.wRepeatCount = 1
            records[2 * i].Event.KeyEvent.wVirtualKeyCode = 0
            records[2 * i].Event.KeyEvent.wVirtualScanCode = 0
            records[2 * i].Event.KeyEvent.uChar = char
            records[2 * i].Event.KeyEvent.dwControlKeyState = 0
            records[2 * i + 1].EventType = KEY_EVENT
            records[2 * i + 1].Event.KeyEvent.bKeyDown = False
            records[2 * i + 1].Event.KeyEvent.wRepeatCount = 1
            records[2 * i + 1].Event.KeyEvent.wVirtualKeyCode = 0
            records[2 * i + 1].Event.KeyEvent.wVirtualScanCode = 0
            records[2 * i + 1].Event.KeyEvent.uChar = char
            records[2 * i + 1].Event.KeyEvent.dwControlKeyState = 0
        written = ctypes.wintypes.DWORD()
        ok = _kernel32.WriteConsoleInputW(
            conin, records, len(records), ctypes.byref(written)
        )
        _kernel32.CloseHandle(conin)
        return bool(ok) and written.value > 0
    finally:
        _kernel32.FreeConsole()


def _paste_to_console(hwnd, text):
    """Paste text into a window that owns a console (OpenCode, cmd, etc.)."""
    pid = ctypes.wintypes.DWORD()
    try:
        if not _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
            return False
        if not pid.value:
            return False
    except Exception:
        return False
    if not _write_console_input(pid.value, text):
        return False
    activate_window(hwnd)
    return True


def inject_text(text, hwnd=0):
    if not text:
        return
    if hwnd and _paste_to_console(hwnd, text):
        return
    original = None
    try:
        original = pyperclip.paste()
    except Exception:
        original = None
    try:
        for _ in range(6):
            try:
                pyperclip.copy(text)
                if pyperclip.paste() == text:
                    break
            except Exception:
                time.sleep(0.04)
        if hwnd and not activate_window(hwnd):
            activate_window(_user32.GetForegroundWindow())
        time.sleep(0.15)
        if not _press_ctrl_v():
            try:
                keyboard.press_and_release("ctrl+v")
            except Exception:
                raise RuntimeError("Could not inject the transcribed text into the active window.")
        time.sleep(0.15)
    finally:
        if original is not None:
            try:
                pyperclip.copy(original)
            except Exception:
                pass


class Transcriber:
    def __init__(self, config):
        self.config = config
        self._model = None
        self._error = None
        self._model_size = None
        self._loading = False
        self._on_load_done = None
        self._pending_model = config.model or "base"
        self._lock = threading.Lock()
        self._start_loader()

    def _start_loader(self):
        with self._lock:
            if self._loading:
                return
            self._loading = True
        threading.Thread(target=self._load_loop, daemon=True, name="FlowAI-ModelLoader").start()

    def _load_loop(self):
        while True:
            with self._lock:
                size = self._pending_model
                self._pending_model = None
            loaded = None
            error = None
            try:
                from faster_whisper import WhisperModel
                loaded = WhisperModel(
                    size,
                    device="cpu",
                    compute_type="int8",
                )
            except Exception as exc:
                error = str(exc)
            with self._lock:
                stale = self._pending_model is not None
            if stale:
                continue
            with self._lock:
                if loaded is not None:
                    self._model = loaded
                    self._model_size = size
                    self._error = None
                elif self._model is None:
                    self._model = None
                    self._error = error
                self._loading = False
            self._notify_done(size, error)
            return

    def is_ready(self):
        with self._lock:
            return self._model is not None and self._error is None

    def is_loading(self):
        with self._lock:
            return self._loading

    def active_model(self):
        with self._lock:
            if self._model is not None and self._model_size:
                return self._model_size
        return self.config.model

    def set_completion_callback(self, on_done):
        self._on_load_done = on_done

    def _notify_done(self, size, error):
        callback = getattr(self, "_on_load_done", None)
        if callback:
            try:
                callback(size, error)
            except Exception:
                pass

    def switch_model(self, size):
        size = (size or "").strip().lower()
        if not size or size == self.config.model:
            return True
        with self._lock:
            if self._pending_model == size:
                return True
            self._pending_model = size
        self.config.model = size
        self._start_loader()
        return True

    def transcribe(self, wav_path, hwnd, on_done, on_error):
        thread = threading.Thread(
            target=self._run,
            args=(wav_path, hwnd, on_done, on_error),
            daemon=True,
            name="FlowAI-Transcriber",
        )
        thread.start()

    def _run(self, wav_path, hwnd, on_done, on_error):
        text = ""
        try:
            with self._lock:
                model = self._model
                error = self._error
            if model is None:
                raise RuntimeError(error or "Local model is still loading. Wait a moment and try again.")
            segments, _info = model.transcribe(wav_path, language="en", beam_size=5)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:
            on_error(str(exc))
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass
        if text:
            on_done(text, hwnd)


class HotkeyManager:
    # Hold-to-listen is driven by a global low-level keyboard hook
    # (WH_KEYBOARD_LL) running on its own message-loop thread, so push-to-talk
    # reacts instantly no matter which window is focused. The hook only
    # observes keys - it never suppresses or delays normal keystrokes. A slow
    # GetAsyncKeyState poller backs it up for windows the hook cannot see (a
    # foreground app running at a higher integrity level, e.g. an elevated
    # terminal), because that call reads the physical key state directly.
    POLL_INTERVAL = 0.02

    def __init__(self, config, audio, callbacks, is_app_focused, app=None):
        self.config = config
        self.audio = audio
        self.callbacks = callbacks
        self.is_app_focused = is_app_focused
        self._running = True
        self._capturing = False
        self._service_on = True
        self._state = "idle"
        self._foreground_hwnd = 0
        self._last_target_hwnd = 0
        self._capture_active = False
        self._capture_pressed = set()
        self._capture_hook = None
        self._watcher = None
        self._tracker = None
        self._lock = threading.Lock()
        self._transcriber = Transcriber(config)
        self._combo_vks = frozenset(self._refresh_combo_vks())
        self._fullscreen_now = False
        self._combo_event = threading.Event()
        self._held_vks = set()
        self._hook_combo_down = False
        self._async_combo_down = False
        self._hook_active = False
        self._hook_thread = None
        self._hook_thread_id = 0
        self._hook_proc_ref = None
        self._hook_ready = threading.Event()
        self._async_poller = None

    # --- lifecycle -------------------------------------------------------

    def start(self):
        self._running = True
        if self._watcher is None:
            self._watcher = threading.Thread(
                target=self._watch_loop,
                daemon=True,
                name="FlowAI-HotkeyWatch",
            )
            self._watcher.start()
        if self._hook_thread is None:
            self._hook_thread = threading.Thread(
                target=self._hook_loop,
                daemon=True,
                name="FlowAI-HotkeyHook",
            )
            self._hook_thread.start()
        if self._async_poller is None:
            self._async_poller = threading.Thread(
                target=self._async_poll_loop,
                daemon=True,
                name="FlowAI-HotkeyPoll",
            )
            self._async_poller.start()
        if self._tracker is None:
            self._tracker = threading.Thread(
                target=self._track_foreground,
                daemon=True,
                name="FlowAI-FocusTracker",
            )
            self._tracker.start()

    def stop(self):
        self._running = False
        if self._hook_thread is not None and self._hook_thread.is_alive():
            self._hook_ready.wait(timeout=1.0)
            try:
                _user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
            self._hook_thread = None
        if self._capture_hook is not None:
            try:
                keyboard.unhook(self._capture_hook)
            except Exception:
                pass
            self._capture_hook = None

    def set_service(self, enabled):
        enabled = bool(enabled)
        self._service_on = enabled
        if not enabled and self._state == "listening":
            with self._lock:
                if self._state == "listening":
                    self._state = "idle"
            self.audio.cancel_recording()
            self.callbacks.status_changed.emit("ready")

    def service_enabled(self):
        return self._service_on

    def set_capturing(self, active):
        self._capturing = bool(active)

    def is_capturing(self):
        return self._capture_active

    def set_hotkey(self, combo):
        if not self._valid_combo(combo):
            return False
        self.config.hotkey = list(combo)
        self._refresh_combo_vks()
        return True

    def switch_model(self, size, on_ready, on_error):
        def done(loaded_size, load_error):
            if load_error:
                fallback = self._transcriber.active_model()
                if fallback and fallback != self.config.model:
                    self.config.model = fallback
                on_error(loaded_size, load_error)
            else:
                on_ready(loaded_size)

        self._transcriber.set_completion_callback(done)
        return self._transcriber.switch_model(size)

    # --- hold-to-listen keyword detection --------------------------------

    def _valid_combo(self, combo):
        keys = [normalize_key(k) for k in combo]
        return len(keys) == 2 and all(name_to_vks(k) for k in keys)

    def _combo_down(self):
        try:
            for key in self.config.hotkey:
                vks = name_to_vks(key)
                if not any(_user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks):
                    return False
            return True
        except Exception:
            return False

    def _refresh_combo_vks(self):
        codes = set()
        for key in self.config.hotkey:
            codes.update(name_to_vks(key))
        self._combo_vks = frozenset(codes)
        return self._combo_vks

    def _watch_loop(self):
        with self._lock:
            was_down = self._hook_combo_down or self._async_combo_down
        while self._running:
            self._combo_event.wait(timeout=0.15)
            self._combo_event.clear()
            try:
                with self._lock:
                    down = self._hook_combo_down or self._async_combo_down
                if self._state == "idle":
                    if down and not was_down:
                        active = (
                            self._service_on
                            and not self._fullscreen_now
                            and not self._capturing
                            and not self._capture_active
                            and not self.is_app_focused()
                        )
                        if active:
                            with self._lock:
                                if self._state == "idle" and self._service_on:
                                    self._state = "listening"
                                    self._foreground_hwnd = self._paste_target()
                                    self.audio.start_recording()
                                    self.callbacks.status_changed.emit("listening")
                elif self._state == "listening":
                    if was_down and not down:
                        with self._lock:
                            if self._state == "listening":
                                self._finish_listening()
                was_down = down
            except Exception:
                pass

    # --- global low-level keyboard hook ----------------------------------

    def _hook_loop(self):
        """Install a global WH_KEYBOARD_LL hook and pump its message loop.

        The hook only *observes* keys for the push-to-talk combo; the callback
        always chains to CallNextHookEx, so every keystroke still reaches the
        foreground application unchanged and nothing is ever blocked or delayed.
        """
        proc = LOWLEVEL_KEYBOARD_PROC(self._hook_callback)
        with self._lock:
            self._hook_proc_ref = proc
        hook = _user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, proc, _kernel32.GetModuleHandleW(None), 0
        )
        if not hook:
            with self._lock:
                self._hook_active = False
                self._hook_proc_ref = None
            return
        with self._lock:
            self._hook_active = True
            self._hook_thread_id = _kernel32.GetCurrentThreadId()
        self._hook_ready.set()
        msg = MSG()
        try:
            while _user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                _user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            _user32.UnhookWindowsHookEx(hook)
            with self._lock:
                self._hook_active = False
                self._hook_proc_ref = None

    def _hook_callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                with self._lock:
                    if down:
                        self._held_vks.add(info.vkCode)
                    else:
                        self._held_vks.discard(info.vkCode)
                    held = self._combo_held_locked()
                    if held != self._hook_combo_down:
                        self._hook_combo_down = held
                        self._combo_event.set()
            except Exception:
                pass
        return _user32.CallNextHookEx(0, n_code, w_param, l_param)

    def _combo_held_locked(self):
        for key in self.config.hotkey:
            if not any(vk in self._held_vks for vk in name_to_vks(key)):
                return False
        return True

    def _async_poll_loop(self):
        """GetAsyncKeyState fallback for windows a low-level hook cannot see.

        WH_KEYBOARD_LL does not receive input bound for a foreground window
        running at a higher integrity level (e.g. an elevated terminal hosting
        OpenCode or VS Code). GetAsyncKeyState reads the physical key state
        directly and is not subject to that isolation, so this fallback keeps
        push-to-talk working in that case too.
        """
        msg = MSG()
        _user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, PM_NOREMOVE)
        while self._running:
            try:
                down = self._combo_down()
            except Exception:
                down = False
            with self._lock:
                if down != self._async_combo_down:
                    self._async_combo_down = down
                    self._combo_event.set()
            time.sleep(self.POLL_INTERVAL)

    # --- full-screen / game detection ------------------------------------

    @staticmethod
    def _foreground():
        try:
            return int(_user32.GetForegroundWindow())
        except Exception:
            return 0

    def _paste_target(self):
        fg = self._foreground()
        if fg and not self._is_shell_window(fg):
            return fg
        return self._last_target_hwnd

    @staticmethod
    def _is_shell_window(hwnd):
        try:
            class_name = ctypes.create_unicode_buffer(64)
            _user32.GetClassNameW(hwnd, class_name, 64)
            name = class_name.value or ""
            skip = (
                "Windows.UI.Core.CoreWindow",
                "ImmersiveLauncher",
                "Shell_TrayWnd",
                "Progman",
                "WorkerW",
                "MultitaskingViewFrame",
                "SearchPane",
            )
            return name in skip or name.startswith("WindowsInternal")
        except Exception:
            return False

    def _is_fullscreen_app(self):
        try:
            fg = self._foreground()
            if not fg or self._is_shell_window(fg):
                return False
            rect = RECT()
            if not _user32.GetWindowRect(fg, ctypes.byref(rect)):
                return False
            screen_w = _user32.GetSystemMetrics(SM_CXSCREEN)
            screen_h = _user32.GetSystemMetrics(SM_CYSCREEN)
            covers = (rect.right - rect.left) >= screen_w and (rect.bottom - rect.top) >= screen_h
            if not covers:
                return False
            style = _user32.GetWindowLongPtrW(fg, GWL_STYLE)
            has_caption = bool(style & WS_CAPTION)
            return not has_caption
        except Exception:
            return False

    def _finish_listening(self):
        self._state = "transcribing"
        self.callbacks.status_changed.emit("transcribing")
        wav_path = self.audio.finish_recording()
        if wav_path:
            self._transcriber.transcribe(
                wav_path,
                self._foreground_hwnd,
                self._on_transcription_done,
                self._on_transcription_error,
            )
        else:
            self._state = "idle"
            self.callbacks.status_changed.emit("ready" if self._service_on else "paused")

    # --- hotkey capture (record a new combo) -----------------------------

    def start_capture(self):
        if self._capture_active:
            return
        self._capture_active = True
        self._capture_pressed = set()
        self.set_capturing(True)
        self.callbacks.capture_state_changed.emit(True)
        self._capture_hook = keyboard.hook(self._capture_event)

    def cancel_capture(self):
        if not self._capture_active:
            return
        self._capture_active = False
        if self._capture_hook is not None:
            try:
                keyboard.unhook(self._capture_hook)
            except Exception:
                pass
            self._capture_hook = None
        self.set_capturing(False)
        self.callbacks.capture_state_changed.emit(False)

    def _capture_event(self, event):
        if not self._capture_active:
            return
        name = normalize_key(event.name)
        if event.event_type == keyboard.KEY_DOWN:
            if name == "esc":
                self.cancel_capture()
                return
            self._capture_pressed.add(name)
            if len(self._capture_pressed) >= 2:
                combo = order_combo(list(self._capture_pressed)[:2])
                self._finish_capture(combo)
        elif event.event_type == keyboard.KEY_UP:
            self._capture_pressed.discard(name)

    def _finish_capture(self, combo):
        self._capture_active = False
        if self._capture_hook is not None:
            try:
                keyboard.unhook(self._capture_hook)
            except Exception:
                pass
            self._capture_hook = None
        self.set_capturing(False)
        if not self._valid_combo(combo):
            self.callbacks.transcription_error.emit(
                "Could not use that hotkey. Pick two recognisable keys, e.g. Ctrl+Space or Ctrl+Win."
            )
            self.callbacks.capture_state_changed.emit(False)
            return
        self.config.hotkey = combo
        self._refresh_combo_vks()
        self.callbacks.hotkey_captured.emit(combo)
        self.callbacks.capture_state_changed.emit(False)

    # --- helpers ---------------------------------------------------------

    def _track_foreground(self):
        while self._running:
            try:
                self._fullscreen_now = self._is_fullscreen_app()
                if not self._fullscreen_now and not self._capturing and not self._capture_active and not self.is_app_focused():
                    fg = self._foreground()
                    if fg and not self._is_shell_window(fg):
                        self._last_target_hwnd = fg
            except Exception:
                pass
            time.sleep(0.12)

    def _on_transcription_done(self, text, hwnd):
        self._state = "idle"
        self.callbacks.status_changed.emit("ready" if self._service_on else "paused")
        if not text:
            return
        try:
            inject_text(text, hwnd)
        except Exception as exc:
            self.callbacks.transcription_error.emit("Paste failed: %s" % exc)
            return
        self.callbacks.transcription_done.emit(text, hwnd)

    def _on_transcription_error(self, message):
        self._state = "idle"
        self.callbacks.status_changed.emit("ready" if self._service_on else "paused")
        self.callbacks.transcription_error.emit(message)
