import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import config as config_mod

APP_VERSION = "1.0.5"
REPO = "yosgosoftware/flow-ai"
RELEASE_URL = "https://github.com/%s/releases/latest" % REPO
API_URL = "https://api.github.com/repos/%s/releases/latest" % REPO
USER_AGENT = "FlowAI-Updater/%s" % APP_VERSION


class UpdateError(RuntimeError):
    pass


def _version_numbers(value):
    return [int(part) for part in re.findall(r"\d+", value or "")]


def is_newer(latest, current):
    latest = _version_numbers(latest)
    current = _version_numbers(current)
    for index in range(max(len(latest), len(current))):
        left = latest[index] if index < len(latest) else 0
        right = current[index] if index < len(current) else 0
        if left != right:
            return left > right
    return False


def fetch_latest():
    """Return {'version', 'download_url', 'release_url'} for the newest release."""
    request = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise UpdateError("Could not reach GitHub: %s" % exc) from exc
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise UpdateError("Unexpected response from GitHub.")
    download_url = ""
    for asset in data.get("assets") or []:
        name = asset.get("name") or ""
        if name.lower().endswith(".exe"):
            download_url = asset.get("browser_download_url") or ""
            break
    return {
        "version": str(data.get("tag_name") or "").lstrip("v"),
        "download_url": download_url,
        "release_url": data.get("html_url") or RELEASE_URL,
    }


def _try_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def download_exe(url, dest_dir, cancel=None):
    """Stream the update exe into dest_dir and return the final path.

    Validates the download (Content-Length + Windows PE header) so a
    truncated or bogus file never gets installed.
    """
    os.makedirs(dest_dir, exist_ok=True)
    destination = os.path.join(dest_dir, "FlowAI_update.exe")
    partial = destination + ".part"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise UpdateError("Download failed (HTTP %s)." % status)
            content_length = response.headers.get("Content-Length")
            try:
                expected = int(content_length) if content_length is not None else None
            except ValueError:
                expected = None
            with open(partial, "wb") as out:
                while True:
                    if cancel and cancel():
                        out.close()
                        _try_remove(partial)
                        raise UpdateError("Update download cancelled.")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
    except UpdateError:
        raise
    except Exception as exc:
        _try_remove(partial)
        raise UpdateError("Download failed: %s" % exc) from exc

    try:
        size = os.path.getsize(partial)
    except OSError as exc:
        _try_remove(partial)
        raise UpdateError("Download failed: %s" % exc) from exc
    if expected is not None and size != expected:
        _try_remove(partial)
        raise UpdateError("Download failed: file was truncated.")
    if size < 1024 * 1024:
        _try_remove(partial)
        raise UpdateError("Download failed: file is not a valid installer.")
    with open(partial, "rb") as fh:
        header = fh.read(2)
    if header != b"MZ":
        _try_remove(partial)
        raise UpdateError("Download failed: file is not a valid installer.")
    os.replace(partial, destination)
    config_mod.unblock_file(destination)
    return destination


def _write_updater_script():
    script = (
        "@echo off\r\n"
        "setlocal EnableExtensions\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        "set /a tries=0\r\n"
        ":loop\r\n"
        "tasklist /fi \"imagename eq FlowAI.exe\" 2>nul | find /i \"FlowAI.exe\" >nul\r\n"
        "if errorlevel 1 goto :replace\r\n"
        "set /a tries+=1\r\n"
        "if %tries% GEQ 15 goto :force\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        "goto :loop\r\n"
        ":force\r\n"
        "taskkill /f /im FlowAI.exe >nul 2>&1\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        ":replace\r\n"
        "set /a tries=0\r\n"
        ":copy_loop\r\n"
        "copy /y \"%~f1\" \"%~f2\" >nul 2>&1\r\n"
        "if not errorlevel 1 goto :unblock\r\n"
        "set /a tries+=1\r\n"
        "if %tries% GEQ 15 goto :failed\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        "goto :copy_loop\r\n"
        ":unblock\r\n"
        "powershell -NoProfile -NonInteractive -Command \"Unblock-File -LiteralPath '%~f2'\" >nul 2>&1\r\n"
        ":done\r\n"
        "start \"\" \"%~f2\"\r\n"
        "del /q \"%~f1\" >nul 2>&1\r\n"
        "exit /b 0\r\n"
        ":failed\r\n"
        "del /q %~f1 >nul 2>&1\r\n"
        "exit /b 1\r\n"
    )
    handle, bat_path = tempfile.mkstemp(
        suffix=".bat", prefix="flowai_apply_update_", dir=tempfile.gettempdir()
    )
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        fh.write(script)
    return bat_path


def apply_update(new_exe, target_exe):
    """Detach a helper that swaps the exe once FlowAI has exited, then relaunches."""
    if not getattr(sys, "frozen", False):
        raise UpdateError("Direct install is only available in the packaged app.")
    if not os.path.exists(new_exe) or not os.path.exists(target_exe):
        raise UpdateError("Update file missing.")
    bat_path = _write_updater_script()
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [bat_path, new_exe, target_exe],
        close_fds=True,
        creationflags=flags,
        cwd=os.path.dirname(target_exe) or None,
    )