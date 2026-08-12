# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FlowAI (Windows, single-file, no console).
# UI: PyQt6 (pulled in automatically by PyInstaller's Qt hooks).
# Speech: faster-whisper + ctranslate2 + onnxruntime + av + tokenizers + huggingface_hub.
# I/O: keyboard, pyperclip, pyaudio / pyaudiowpatch, numpy, cffi.
import os

from PyInstaller.utils.hooks import (collect_all, collect_data_files,
                                     collect_dynamic_libs)

root = os.path.abspath(SPECPATH)

datas = []
binaries = []
hiddenimports = []

for package in (
    "faster_whisper",
    "ctranslate2",
    "huggingface_hub",
    "tokenizers",
    "onnxruntime",
    "av",
    "numpy",
    "keyboard",
    "pyperclip",
    "pyaudiowpatch",
    "cffi",
):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hidden
    except Exception:
        pass

for package in ("pyaudio", "pyaudiowpatch"):
    try:
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass

a = Analysis(
    ["main.py"],
    pathex=[root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "onnx",
        "tensorflow",
        "torch",
        "torchvision",
        "matplotlib",
        "pandas",
        "scipy",
        "tkinter",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FlowAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root, "assets", "app.ico"),
)
