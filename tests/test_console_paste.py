"""Regression test: pasting transcribed text into a raw/VT-mode console (TUI).

Terminal apps like OpenCode run the console in raw input mode, where an
injected Ctrl+V is delivered to the app as a literal ^V key event instead of
pasting. FlowAI must inject the text straight into the console input buffer
instead.

This test launches a real raw-mode console receiver, calls the app's
inject_text() against its window, and verifies the text arrives.

Run from the repo root:
    .venv\\Scripts\\python.exe tests\\test_console_paste.py <result_file>
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hotkey_manager as hkm

RECEIVER = r"""
import ctypes
import msvcrt
import sys
import time

hwnd_file, cap_file = sys.argv[1], sys.argv[2]
kernel32 = ctypes.windll.kernel32
console = int(kernel32.GetConsoleWindow())
with open(hwnd_file, "w") as fh:
    fh.write(str(console))

handle = kernel32.GetStdHandle(-10)
mode = ctypes.c_uint()
kernel32.GetConsoleMode(handle, ctypes.byref(mode))
kernel32.SetConsoleMode(handle, 0x0200)

buf = bytearray()
deadline = time.time() + 12
while time.time() < deadline:
    while msvcrt.kbhit():
        buf.extend(msvcrt.getch())
    time.sleep(0.005)

with open(cap_file, "wb") as fh:
    fh.write(bytes(buf))
"""


def main():
    result_file = sys.argv[1] if len(sys.argv) > 1 else None
    status = "PASS"

    def record(text):
        nonlocal status
        status = text
        if result_file:
            try:
                Path(result_file).write_text(text, encoding="utf-8")
            except Exception:
                pass

    tmp = Path(tempfile.mkdtemp(prefix="flowai_console_"))
    hwnd_file = tmp / "hwnd.txt"
    cap_file = tmp / "cap.bin"
    script = tmp / "receiver.py"
    script.write_text(RECEIVER, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(script), str(hwnd_file), str(cap_file)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    try:
        deadline = time.time() + 6
        while time.time() < deadline and not hwnd_file.exists():
            time.sleep(0.05)
        if not hwnd_file.exists():
            record("FAIL: receiver console never started")
            return 1
        hwnd = int(hwnd_file.read_text().strip())
        hkm.inject_text("HELLO_OPENCODE_PASTE", hwnd)
        deadline = time.time() + 14
        while time.time() < deadline and not cap_file.exists():
            time.sleep(0.1)
        if not cap_file.exists():
            record("FAIL: receiver captured nothing")
            return 1
        data = cap_file.read_bytes()
        if b"HELLO_OPENCODE_PASTE" not in data:
            record("FAIL: pasted text did not reach the TUI console: %r" % data)
            return 1
    finally:
        try:
            proc.kill()
        except Exception:
            pass
    record("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())