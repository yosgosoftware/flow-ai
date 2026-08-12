import os
import subprocess
import sys


def desktop_path():
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.shell32.SHGetFolderPathW(0, 0x0000, 0, 0, buf)
        if buf.value and os.path.isdir(buf.value):
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def create_shortcut(exe_path, shortcut_path, icon_path=None):
    ps = (
        "$w = New-Object -ComObject WScript.Shell; "
        "$s = $w.CreateShortcut(%r); "
        "$s.TargetPath = %r; "
        "$s.WorkingDirectory = %r; "
        "$s.Description = 'FlowAI - push-to-talk AI transcription'; "
    ) % (
        shortcut_path,
        exe_path,
        os.path.dirname(exe_path),
    )
    if icon_path and os.path.exists(icon_path):
        ps += "$s.IconLocation = %r; " % icon_path
    ps += "$s.Save();"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise OSError("Shortcut creation failed: %s" % result.stderr.strip())


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    exe = os.path.join(root, "dist", "FlowAI.exe")
    if not os.path.exists(exe):
        raise SystemExit("FlowAI.exe not found. Run the PyInstaller build first.")

    shortcut = os.path.join(desktop_path(), "FlowAI.lnk")
    icon = os.path.join(root, "assets", "app.ico")
    create_shortcut(exe, shortcut, icon)
    print("Created desktop shortcut: %s" % shortcut)


if __name__ == "__main__":
    main()
