import json
import os
import shutil
import subprocess
import sys
import winreg

APP_NAME = "FlowAI"

DEFAULTS = {
    "hotkey": ["ctrl", "space"],
    "device": None,
    "model": "base",
    "autostart": False,
    "audio_cues": True,
    "samplerate": 16000,
}

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def config_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = os.path.join(base, APP_NAME)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def config_path():
    return os.path.join(config_dir(), "config.json")


def installed_exe():
    """Stable per-user install location for the packaged executable."""
    return os.path.join(config_dir(), APP_NAME + ".exe")


def _zone_id_stream(path):
    return path + ":Zone.Identifier"


def has_mark_of_web(path):
    try:
        return os.path.exists(_zone_id_stream(path))
    except (OSError, ValueError):
        return False


def unblock_file(path):
    """Strip the Windows Mark-of-the-Web (Zone.Identifier ADS) from a file."""
    try:
        escaped = path.replace("'", "''")
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Unblock-File -LiteralPath '%s'" % escaped],
            capture_output=True,
            timeout=60,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Remove-Item -LiteralPath '%s' -Stream Zone.Identifier -Force -ErrorAction SilentlyContinue" % path.replace("'", "''")],
            capture_output=True,
            timeout=60,
        )
    except Exception:
        pass
    return not has_mark_of_web(path)


def ensure_installed():
    """Copy the running executable into the stable install dir (unblocked).

    Returns the installed exe path, or the source path if copying failed.
    Returns None when running from source (not packaged).
    """
    if not getattr(sys, "frozen", False):
        return None
    target = installed_exe()
    source = os.path.abspath(sys.executable)
    if source.lower() == os.path.abspath(target).lower():
        return target
    try:
        os.makedirs(config_dir(), exist_ok=True)
        shutil.copy2(source, target)
        unblock_file(target)
    except OSError:
        return source
    return target


def set_autostart(enabled):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
    except OSError:
        return False
    try:
        if enabled:
            if getattr(sys, "frozen", False):
                exe = ensure_installed()
                if not exe:
                    raise OSError("no executable")
                command = '"%s"' % exe
            else:
                script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
                command = '"%s" "%s"' % (sys.executable, script)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def autostart_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
    except OSError:
        return False
    try:
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except OSError:
            return False
    finally:
        winreg.CloseKey(key)


class Config:
    def __init__(self, path=None):
        self.path = path or config_path()
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    stored = json.load(fh)
                if isinstance(stored, dict):
                    for key in DEFAULTS:
                        if key in stored:
                            self.data[key] = stored[key]
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass

    @property
    def hotkey(self):
        value = self.data.get("hotkey")
        if not isinstance(value, list) or len(value) != 2:
            return list(DEFAULTS["hotkey"])
        return [str(key) for key in value]

    @hotkey.setter
    def hotkey(self, value):
        self.data["hotkey"] = [str(key) for key in value][:2]
        self.save()

    @property
    def device(self):
        return self.data.get("device")

    @device.setter
    def device(self, value):
        self.data["device"] = (value or "").strip() or None
        self.save()

    @property
    def samplerate(self):
        return int(self.data.get("samplerate") or 16000)

    @samplerate.setter
    def samplerate(self, value):
        self.data["samplerate"] = int(value)
        self.save()

    @property
    def model(self):
        value = str(self.data.get("model") or "base").lower()
        allowed = ("tiny", "tiny.en", "base", "base.en", "small", "small.en",
                   "medium", "medium.en", "large-v3", "large-v3-turbo", "distil-small.en",
                   "distil-medium.en", "distil-large-v3")
        if value not in allowed:
            return "base"
        return value

    @model.setter
    def model(self, value):
        self.data["model"] = str(value or "base").lower()
        self.save()

    @property
    def autostart(self):
        return bool(self.data.get("autostart"))

    @autostart.setter
    def autostart(self, value):
        self.data["autostart"] = bool(value)
        self.save()

    @property
    def audio_cues(self):
        return bool(self.data.get("audio_cues", True))

    @audio_cues.setter
    def audio_cues(self, value):
        self.data["audio_cues"] = bool(value)
        self.save()
