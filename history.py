import json
import os
import threading
import time

MAX_ENTRIES = 50


class HistoryStore:
    def __init__(self, json_path, txt_path):
        self._json_path = json_path
        self._txt_path = txt_path
        self._lock = threading.Lock()
        self._entries = self._load()

    def _load(self):
        try:
            with open(self._json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict) and e.get("text")][:MAX_ENTRIES]
        except (OSError, ValueError):
            pass
        return []

    def entries(self):
        with self._lock:
            return list(self._entries)

    def add(self, text):
        text = (text or "").strip()
        if not text:
            return None
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts": time.time(),
            "text": text,
        }
        with self._lock:
            self._entries.insert(0, entry)
            del self._entries[MAX_ENTRIES:]
            self._save_locked()
        return entry

    def delete(self, entry):
        ts = entry.get("ts")
        text = entry.get("text")
        removed = False
        with self._lock:
            keep = []
            for existing in self._entries:
                if not removed:
                    if ts is not None and existing.get("ts") == ts:
                        removed = True
                        continue
                    if ts is None and existing.get("text") == text:
                        removed = True
                        continue
                keep.append(existing)
            if removed:
                self._entries = keep
                self._save_locked()
        return removed

    def clear(self):
        with self._lock:
            self._entries = []
            self._save_locked()

    def _save_locked(self):
        try:
            directory = os.path.dirname(self._json_path)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)
            with open(self._json_path, "w", encoding="utf-8") as fh:
                json.dump(self._entries, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass
        try:
            directory = os.path.dirname(self._txt_path)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)
            with open(self._txt_path, "a", encoding="utf-8") as fh:
                for entry in (self._entries[0],) if self._entries else ():
                    fh.write("[%s]\n%s\n\n" % (entry["time"], entry["text"]))
        except OSError:
            pass