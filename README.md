# FlowAI — Voice-to-Text That Stays on Your Machine

FlowAI is a **100% local, lightning-fast speech-to-text dictation tool** built on
[faster-whisper](https://github.com/SYSTRAN/faster-whisper). Hold your hotkey, speak,
and your words appear instantly in *any* application — Word, email, chat, code editor,
or browser. Your voice never leaves your computer, and there is no account, no cloud,
and no per-minute fees.

## Key Features

- **Local & private** — everything runs on your CPU. Audio is transcribed on-device and
  never uploaded, so your words stay yours.
- **Zero cloud fees** — no API keys, no subscriptions, no usage limits. 100% free.
- **Custom hotkeys** — pick any two-key combination (default `Ctrl + Space`); hold it,
  speak, release, and FlowAI types the result where your cursor is.
- **Audio cues** — optional start/stop sounds confirm when FlowAI is listening and that
  your text was pasted, so you always know its status at a glance.
- **System tray support** — minimize or close to the system tray and FlowAI keeps
  running quietly in the background until you need it.
- **Multiple accuracy tiers** — choose between `tiny`, `base`, `small`, and `medium`
  models to balance speed and accuracy for your hardware.
- **Full history** — every dictation is saved and searchable in the dashboard.
- **Custom microphone selection** — use your default mic or pick any input device.
- **Works everywhere** — active-window detection means dictation pastes into whichever
  app you're using, fullscreen included.

## System Requirements

- **OS:** Windows 10 / 11 (64-bit)
- **Memory:** 4 GB RAM minimum; 8 GB recommended for the `medium` model
- **Disk:** ~500 MB free for the app plus model storage (models range from ~75 MB to
  ~1.5 GB depending on the tier)
- **Sound:** any working microphone or input device
- **Network:** required only for the *first* download of your chosen model. After that,
  FlowAI works fully offline.

## Installation

FlowAI ships as a single portable `FlowAI.exe` — no installer, no dependencies to
configure.

1. **Download** the latest `FlowAI.exe` from the [releases page](https://github.com/yosgosoftware/flow-ai/releases/latest).
2. **Run** the file — that's it. A FlowAI icon appears in the system tray near the clock.
3. When you open the dashboard for the first time, pick your preferred model size. The
   selected model downloads once in the background; your current model keeps working in
   the meantime.

> **Tip:** After each larger model download, FlowAI works completely offline.

### First-run checklist

- Open the **Local Model** tab and choose the accuracy tier that fits your PC
  (`tiny` is best for older machines; `medium` for maximum precision).
- Open the **Hotkeys** tab to confirm (or customize) your hold-to-talk hotkey.
- Click the microphone icon on the dashboard and do a quick test dictation.

### Optional: Start with Windows

Enable **"Launch FlowAI automatically when Windows starts"** on the **Local Model**
tab and your dictation assistant will be ready every boot.

## Quitting FlowAI

FlowAI lives in the system tray. To fully stop the background service, right-click the
tray icon and choose **Quit**.

## Privacy

No data is collected, transmitted, or stored anywhere but on your own machine. FlowAI
has no telemetry, no analytics, and no cloud component. Your transcriptions belong
entirely to you.

---

*FlowAI — fast, private, on-device dictation for Windows.*