import ctypes
import logging
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import webbrowser

from PyQt6.QtCore import QEvent, QObject, QSharedMemory, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient,
                         QPainter, QPen, QPixmap, QPolygonF)
from PyQt6.QtCore import QPoint, QPointF, QRectF
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox,
                             QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QLabel, QLineEdit, QMenu, QMessageBox,
                             QPushButton, QScrollArea, QStackedWidget,
                             QSystemTrayIcon, QToolButton, QVBoxLayout, QWidget)

import pyperclip

import config as config_mod
import updater
from audio_cues import AudioCues
from audio_engine import AudioEngine
from history import HistoryStore
from hotkey_manager import HotkeyManager, format_combo


class Signals(QObject):
    status_changed = pyqtSignal(str)
    transcription_done = pyqtSignal(str, int)
    transcription_error = pyqtSignal(str)
    hotkey_captured = pyqtSignal(list)
    capture_state_changed = pyqtSignal(bool)
    history_added = pyqtSignal(dict)
    history_deleted = pyqtSignal(dict)
    model_ready = pyqtSignal(str)
    model_error = pyqtSignal(str, str)
    update_available = pyqtSignal(str, str, str)
    update_not_available = pyqtSignal()
    update_failed = pyqtSignal(str)
    update_downloaded = pyqtSignal(str)

    def on_status_changed(self, state):
        self.status_changed.emit(state)

    def on_transcription_done(self, text, hwnd):
        self.transcription_done.emit(text, hwnd)

    def on_transcription_error(self, message):
        self.transcription_error.emit(message)

    def on_hotkey_captured(self, combo):
        self.hotkey_captured.emit(combo)

    def on_history_added(self, entry):
        self.history_added.emit(entry)

    def on_history_deleted(self, entry):
        self.history_deleted.emit(entry)

    def on_model_ready(self, size):
        self.model_ready.emit(size)

    def on_model_error(self, size, message):
        self.model_error.emit(size, message)

    def on_update_available(self, version, download_url, release_url):
        self.update_available.emit(version, download_url, release_url)

    def on_update_not_available(self):
        self.update_not_available.emit()

    def on_update_failed(self, message):
        self.update_failed.emit(message)

    def on_update_downloaded(self, new_exe):
        self.update_downloaded.emit(new_exe)

    def on_capture_state_changed(self, active):
        self.capture_state_changed.emit(active)


QSS = """
QWidget {
    color: #ECECEF;
    font-size: 13px;
    background: transparent;
}

#WindowCard {
    background: #16161A;
    border: 1px solid #2A2A2E;
    border-radius: 14px;
}

#WindowCard[winMaximized="true"] {
    border-radius: 0px;
}

#Sidebar[winMaximized="true"] {
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
}

#ContentPane[winMaximized="true"] {
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
}

#TitleBar {
    background: transparent;
}

#Sidebar {
    background: #121214;
    border-right: 1px solid #2A2A2E;
    border-top-left-radius: 13px;
    border-bottom-left-radius: 13px;
}

#ContentPane {
    background: #16161A;
    border-top-right-radius: 13px;
    border-bottom-right-radius: 13px;
}

#Page {
    background: #16161A;
}

#Card {
    background: #1C1C21;
    border: 1px solid #2A2A2E;
    border-radius: 12px;
}

QScrollArea#HistoryScroll {
    background: transparent;
    border: none;
}

QFrame#HistoryItem {
    background: #191920;
    border: 1px solid #26262C;
    border-radius: 10px;
}

QLabel#HistoryTime {
    color: #6B6B74;
    font-size: 12px;
}

QLabel#HistoryText {
    color: #D7D7DC;
    font-size: 13px;
}

#SideTitle {
    font-size: 17px;
    font-weight: 700;
}

#NavLabel {
    color: #6B6B74;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 2px;
    margin-top: 10px;
}

#NavButton {
    text-align: left;
    padding: 10px 12px;
    border: none;
    border-radius: 10px;
    color: #9A9AA3;
    font-size: 14px;
}

#NavButton:hover {
    background: #1F1F24;
    color: #ECECEF;
}

#NavButton:checked {
    background: #22242C;
    color: #FFFFFF;
}

#PageTitle {
    font-size: 21px;
    font-weight: 700;
}

#SectionTitle {
    font-size: 14px;
    font-weight: 600;
}

#Hint {
    color: #9A9AA3;
    font-size: 12px;
}

#BigNumber {
    font-size: 40px;
    font-weight: 700;
    color: #ECECEF;
}

#StatusText {
    font-size: 13px;
    font-weight: 600;
}

#ErrorBanner {
    background: rgba(229, 72, 77, 0.14);
    border: 1px solid #E5484D;
    border-radius: 10px;
}

#BannerText {
    color: #FF9A9A;
    font-size: 12px;
}

QPushButton {
    background: #242429;
    color: #ECECEF;
    border: 1px solid #2A2A2E;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton:hover {
    background: #2C2C33;
}

QPushButton:pressed {
    background: #33333B;
}

QPushButton:disabled {
    color: #6B6B74;
    background: #1E1E23;
}

QPushButton#PrimaryButton {
    background: #5B8CFF;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background: #6E9BFF;
}

QPushButton#PrimaryButton:pressed {
    background: #4C7BEF;
}

QPushButton#PrimaryButton:disabled {
    background: #31446E;
    color: #8B96AE;
}

QPushButton#GhostButton {
    background: transparent;
    border: 1px solid #2A2A2E;
    color: #C9C9D1;
}

QPushButton#GhostButton:hover {
    background: #1F1F24;
}

QPushButton#DangerButton {
    background: transparent;
    border: 1px solid #3A262A;
    color: #E5A0A0;
}

QPushButton#DangerButton:hover {
    background: rgba(229, 72, 77, 0.18);
    border: 1px solid #E5484D;
    color: #FF9A9A;
}

QToolButton#WindowBtn {
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    color: #9A9AA3;
}

QToolButton#WindowBtn:hover {
    background: #2A2A2E;
    color: #ECECEF;
}

QToolButton#CloseBtn {
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    color: #9A9AA3;
}

QToolButton#CloseBtn:hover {
    background: #E5484D;
    color: #FFFFFF;
}

QToolButton#GhostButton {
    background: transparent;
    border: 1px solid #2A2A2E;
    border-radius: 8px;
    color: #C9C9D1;
    padding: 7px 12px;
}

QToolButton#GhostButton:hover {
    background: #1F1F24;
}

QToolButton#GhostButton:checked {
    background: #2C2C33;
    border-color: #5B8CFF;
    color: #FFFFFF;
}

QLineEdit, QComboBox {
    background: #121214;
    border: 1px solid #2A2A2E;
    border-radius: 8px;
    padding: 9px 12px;
    selection-background-color: #5B8CFF;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #5B8CFF;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #9A9AA3;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: #1C1C21;
    border: 1px solid #2A2A2E;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #2C2C33;
    selection-color: #FFFFFF;
    outline: 0;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #33333B;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #44444E;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

QToolTip {
    background: #1C1C21;
    color: #ECECEF;
    border: 1px solid #2A2A2E;
    padding: 6px 8px;
    border-radius: 6px;
}

QCheckBox {
    color: #ECECEF;
    spacing: 9px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #3A3A42;
    background: #121214;
}

QCheckBox::indicator:checked {
    background: #5B8CFF;
    border: 1px solid #5B8CFF;
}

QCheckBox::indicator:hover {
    border-color: #5B8CFF;
}

QMenu {
    background: #1C1C21;
    border: 1px solid #2A2A2E;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 7px 28px 7px 14px;
    border-radius: 6px;
}

QMenu::item:selected {
    background: #2C2C33;
}

QMenu::separator {
    height: 1px;
    background: #2A2A2E;
    margin: 6px 10px;
}
"""


def app_icon_pixmap(size=256):
    s = float(size)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, s, s)
    gradient.setColorAt(0.0, QColor("#23232B"))
    gradient.setColorAt(1.0, QColor("#0E0E12"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawRoundedRect(0, 0, int(s), int(s), int(s * 0.22), int(s * 0.22))
    pen = QPen(QColor("#FFFFFF"), max(1.0, s * 0.055))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(int(s * 0.38), int(s * 0.13), int(s * 0.24), int(s * 0.48), int(s * 0.09), int(s * 0.09))
    painter.drawLine(int(s * 0.5), int(s * 0.61), int(s * 0.5), int(s * 0.79))
    painter.drawLine(int(s * 0.30), int(s * 0.79), int(s * 0.70), int(s * 0.79))
    painter.drawArc(int(s * 0.30), int(s * 0.30), int(s * 0.40), int(s * 0.40), 180 * 16, 180 * 16)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#5B8CFF"))
    painter.drawEllipse(int(s * 0.78), int(s * 0.20), int(s * 0.12), int(s * 0.12))
    painter.end()
    return pixmap


def make_app_icon(size=256):
    return QIcon(app_icon_pixmap(size))


def nav_icon(kind, color="#8AA6FF", size=18):
    s = float(size)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    stroke = max(1.0, s * 0.09)
    pen = QPen(QColor(color), stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "dashboard":
        cell = (s - 3.0 * stroke) / 2.0
        for row in range(2):
            for col in range(2):
                painter.drawRoundedRect(
                    int(stroke + col * (cell + stroke)),
                    int(stroke + row * (cell + stroke)),
                    int(cell),
                    int(cell),
                    int(s * 0.06),
                    int(s * 0.06),
                )
    elif kind == "hotkeys":
        bolt = QPolygonF([
            QPointF(s * 0.56, s * 0.08),
            QPointF(s * 0.28, s * 0.55),
            QPointF(s * 0.47, s * 0.55),
            QPointF(s * 0.42, s * 0.92),
            QPointF(s * 0.72, s * 0.43),
            QPointF(s * 0.52, s * 0.43),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(bolt)
    elif kind == "audio":
        painter.drawRoundedRect(int(s * 0.40), int(s * 0.14), int(s * 0.20), int(s * 0.42), int(s * 0.08), int(s * 0.08))
        painter.drawLine(int(s * 0.5), int(s * 0.56), int(s * 0.5), int(s * 0.76))
        painter.drawLine(int(s * 0.33), int(s * 0.76), int(s * 0.67), int(s * 0.76))
        painter.drawArc(int(s * 0.33), int(s * 0.30), int(s * 0.34), int(s * 0.34), 180 * 16, 180 * 16)
    elif kind == "ai":
        star = QPolygonF([
            QPointF(s * 0.50, s * 0.06),
            QPointF(s * 0.61, s * 0.39),
            QPointF(s * 0.94, s * 0.50),
            QPointF(s * 0.61, s * 0.61),
            QPointF(s * 0.50, s * 0.94),
            QPointF(s * 0.39, s * 0.61),
            QPointF(s * 0.06, s * 0.50),
            QPointF(s * 0.39, s * 0.39),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(star)
    painter.end()
    return QIcon(pixmap)


class StatusPill(QWidget):
    COLORS = {
        "ready": "#2BD576",
        "listening": "#FF5A5A",
        "transcribing": "#F5C44A",
        "error": "#FF5A5A",
        "paused": "#8A8A93",
    }
    LABELS = {
        "ready": "Ready",
        "listening": "Listening...",
        "transcribing": "Transcribing...",
        "error": "Error",
        "paused": "Suspended",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "ready"
        self._pulse = 0.0
        self._pulse_dir = 1
        self.setFixedHeight(30)
        self.setMinimumWidth(126)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._step)

    def sizeHint(self):
        return QSize(130, 30)

    def set_state(self, state):
        self._state = state if state in self.COLORS else "ready"
        if state == "listening":
            self._timer.start()
        else:
            self._timer.stop()
            self._pulse = 0.0
        self.update()

    def _step(self):
        self._pulse += 0.07 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse = 1.0
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse = 0.0
            self._pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        height = float(self.height())
        color = QColor(self.COLORS[self._state])
        if self._state == "listening":
            for i in range(3):
                r = (self._pulse + i / 3.0) % 1.0
                alpha = int(110 * (1.0 - r))
                radius = 6.0 + r * 16.0
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), alpha)))
                painter.drawEllipse(QPointF(16.0, height / 2.0), radius, radius)
        background = QColor(color)
        background.setAlpha(36)
        border = QColor(color)
        border.setAlpha(95)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(0.0, 0.0, float(self.width()), height), height / 2.0, height / 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(15.0, height / 2.0), 4.0, 4.0)
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(9.5)
        painter.setFont(font)
        painter.setPen(QColor("#ECECEF"))
        painter.drawText(
            QRectF(25.0, 0.0, float(self.width()) - 27.0, height),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.LABELS.get(self._state, self._state),
        )
        painter.end()


class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_db = -60.0
        self._display_db = -60.0
        self._peak_db = -60.0
        self.setMinimumHeight(58)

    def set_level(self, db):
        self._target_db = max(-60.0, min(0.0, db))

    def tick(self):
        self._display_db += (self._target_db - self._display_db) * 0.38
        if abs(self._target_db - self._display_db) < 0.05:
            self._display_db = self._target_db
        if self._display_db > self._peak_db:
            self._peak_db = self._display_db
        else:
            self._peak_db = max(-60.0, self._peak_db - 0.8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = float(self.width())
        bar_top = 10.0
        bar_height = 18.0
        track = QRectF(0.0, bar_top, width, bar_height)
        painter.setPen(QPen(QColor("#2A2A2E"), 1.0))
        painter.setBrush(QColor("#121214"))
        painter.drawRoundedRect(track, bar_height / 2.0, bar_height / 2.0)
        fraction = max(0.0, min(1.0, (self._display_db + 60.0) / 60.0))
        if fraction > 0.004:
            fill_width = max(0.0, (width - 4.0) * fraction)
            fill = QRectF(track.left() + 2.0, bar_top + 2.0, fill_width, bar_height - 4.0)
            gradient = QLinearGradient(track.left(), 0.0, track.right(), 0.0)
            gradient.setColorAt(0.0, QColor("#2BD576"))
            gradient.setColorAt(0.55, QColor("#F5C44A"))
            gradient.setColorAt(1.0, QColor("#FF5A5A"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill, (bar_height - 4.0) / 2.0, (bar_height - 4.0) / 2.0)
        peak_fraction = max(0.0, min(1.0, (self._peak_db + 60.0) / 60.0))
        if peak_fraction > 0.004:
            peak_x = track.left() + 2.0 + max(0.0, (width - 4.0) * peak_fraction - 1.5)
            painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
            painter.drawLine(QPointF(peak_x, bar_top + 1.0), QPointF(peak_x, bar_top + bar_height - 1.0))
        painter.setPen(QPen(QColor(255, 255, 255, 55), 1.0))
        for i in range(1, 3):
            x = track.left() + width * i / 3.0
            painter.drawLine(QPointF(x, bar_top), QPointF(x, bar_top + bar_height))
        font = QFont(self.font())
        font.setPointSizeF(8.0)
        painter.setFont(font)
        painter.setPen(QColor("#6B6B74"))
        painter.drawText(
            QRectF(0.0, bar_top + bar_height + 4.0, 46.0, 14.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "-60",
        )
        painter.drawText(
            QRectF(width - 46.0, bar_top + bar_height + 4.0, 46.0, 14.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "0 dB",
        )
        painter.end()


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self._target = 1.0 if self._checked else 0.0
        self._position = self._target
        self.setFixedSize(46, 26)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._animate)
        self._timer.start()

    def isChecked(self):
        return self._checked

    def set_checked(self, checked):
        self._checked = bool(checked)
        self._target = 1.0 if self._checked else 0.0

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self._target = 1.0 if self._checked else 0.0
            self.toggled.emit(self._checked)
            self.update()
        super().mouseReleaseEvent(event)

    def _animate(self):
        self._position += (self._target - self._position) * 0.35
        if abs(self._target - self._position) < 0.01:
            self._position = self._target
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = float(self.width())
        height = float(self.height())
        track_color = QColor("#5B8CFF") if self._checked else QColor("#3A3A42")
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1.0))
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0.0, 0.0, width, height), height / 2.0, height / 2.0)
        knob_x = 4.0 + self._position * (width - 26.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QPointF(knob_x + 9.0, height / 2.0), 9.0, 9.0)
        painter.end()


class RecordingBox(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capturing = False
        self._combo = ["ctrl", "space"]
        self._pulse = 0.0
        self._pulse_dir = 1
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to record a new push-to-talk combination")
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._step)

    def set_combo(self, keys):
        self._combo = list(keys)
        self.update()

    def set_capturing(self, active):
        self._capturing = bool(active)
        if active:
            self._timer.start()
        else:
            self._timer.stop()
            self._pulse = 0.0
        self.update()

    def _step(self):
        self._pulse += 0.08 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse = 1.0
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse = 0.0
            self._pulse_dir = 1
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = float(self.width())
        height = float(self.height())
        border_color = QColor("#5B8CFF") if self._capturing else QColor("#2A2A2E")
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(QColor("#121214"))
        painter.drawRoundedRect(QRectF(0.5, 0.5, width - 1.0, height - 1.0), 12.0, 12.0)
        if self._capturing:
            ring_color = QColor(255, 90, 90, int(140 * (1.0 - self._pulse)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ring_color)
            painter.drawEllipse(QPointF(30.0, height / 2.0), 8.0 + 10.0 * self._pulse, 8.0 + 10.0 * self._pulse)
            dot_color = QColor("#FF5A5A")
        elif self._combo:
            dot_color = QColor("#2BD576")
        else:
            dot_color = QColor("#8A8A93")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(QPointF(30.0, height / 2.0), 6.0, 6.0)
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(13.0)
        painter.setFont(font)
        painter.setPen(QColor("#ECECEF"))
        title_text = "Press two keys simultaneously..." if self._capturing else format_combo(self._combo)
        painter.drawText(
            QRectF(48.0, 8.0, width - 60.0, 24.0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            title_text,
        )
        font.setBold(False)
        font.setPointSizeF(10.0)
        painter.setFont(font)
        painter.setPen(QColor("#9A9AA3"))
        sub_text = "Listening for keys (Esc to cancel)" if self._capturing else "Push-to-talk combination - click to change"
        painter.drawText(
            QRectF(48.0, 34.0, width - 60.0, 20.0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            sub_text,
        )
        painter.end()


class ErrorBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ErrorBanner")
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self._label = QLabel("")
        self._label.setObjectName("BannerText")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(7000)
        self._timer.timeout.connect(self.hide)

    def show_error(self, message):
        self._label.setText(message)
        self.setVisible(True)
        self._timer.start()

class DashboardTab(QWidget):
    toggle_changed = pyqtSignal(bool)
    check_updates_requested = pyqtSignal()
    history_delete_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_words = 0
        self._history = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        hint = QLabel("Hold your push-to-talk combination in any app, speak, and FlowAI pastes the transcription.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(14)

        self._pill = StatusPill()
        self._status_text = QLabel("Ready")
        self._status_text.setObjectName("StatusText")
        status_text_wrap = QVBoxLayout()
        status_text_wrap.setSpacing(2)
        status_text_wrap.addWidget(self._status_text)
        sub = QLabel("Background transcription service")
        sub.setObjectName("Hint")
        status_text_wrap.addWidget(sub)
        status_text_wrap.addStretch(1)

        status_layout.addWidget(self._pill)
        status_layout.addLayout(status_text_wrap)
        status_layout.addStretch(1)

        toggle_wrap = QVBoxLayout()
        toggle_wrap.setSpacing(2)
        toggle_label = QLabel("Background Listener")
        toggle_label.setObjectName("SectionTitle")
        toggle_hint = QLabel("Master switch for the hotkey service")
        toggle_hint.setObjectName("Hint")
        toggle_wrap.addWidget(toggle_label)
        toggle_wrap.addWidget(toggle_hint)
        self._toggle = ToggleSwitch(checked=True)
        self._toggle.toggled.connect(self.toggle_changed)
        status_layout.addLayout(toggle_wrap)
        status_layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(status_card)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        words_card = QFrame()
        words_card.setObjectName("Card")
        words_layout = QVBoxLayout(words_card)
        words_layout.setContentsMargins(18, 16, 18, 16)
        words_layout.setSpacing(4)
        words_caption = QLabel("Session Words Transcribed")
        words_caption.setObjectName("Hint")
        self._words_value = QLabel("0")
        self._words_value.setObjectName("BigNumber")
        words_layout.addWidget(words_caption)
        words_layout.addWidget(self._words_value)
        stats_row.addWidget(words_card, 1)

        self._banner = ErrorBanner()
        stats_row.addWidget(self._banner, 1, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(stats_row)

        history_card = QFrame()
        history_card.setObjectName("Card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(18, 16, 18, 16)
        history_layout.setSpacing(10)
        history_header = QHBoxLayout()
        history_title = QLabel("Recent Transcriptions")
        history_title.setObjectName("SectionTitle")
        history_header.addWidget(history_title)
        history_header.addStretch(1)
        self._history_count = QLabel("0")
        self._history_count.setObjectName("Hint")
        history_header.addWidget(self._history_count)
        history_layout.addLayout(history_header)

        self._history_scroll = QScrollArea()
        self._history_scroll.setObjectName("HistoryScroll")
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._history_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self._history_scroll.setFixedHeight(300)
        self._history_container = QWidget()
        self._history_items_layout = QVBoxLayout(self._history_container)
        self._history_items_layout.setContentsMargins(2, 2, 2, 2)
        self._history_items_layout.setSpacing(8)
        self._history_scroll.setWidget(self._history_container)
        history_layout.addWidget(self._history_scroll)
        root.addWidget(history_card)

        updates_card = QFrame()
        updates_card.setObjectName("Card")
        updates_layout = QHBoxLayout(updates_card)
        updates_layout.setContentsMargins(18, 16, 18, 16)
        updates_layout.setSpacing(14)

        updates_info = QVBoxLayout()
        updates_info.setSpacing(2)
        updates_title = QLabel("Updates")
        updates_title.setObjectName("SectionTitle")
        self._version_label = QLabel("Version v%s" % updater.APP_VERSION)
        self._version_label.setObjectName("StatusText")
        self._update_note = QLabel("Checks for new releases on startup")
        self._update_note.setObjectName("Hint")
        updates_info.addWidget(updates_title)
        updates_info.addWidget(self._version_label)
        updates_info.addWidget(self._update_note)
        updates_layout.addLayout(updates_info)
        updates_layout.addStretch(1)

        self._update_btn = QPushButton("Check for Updates")
        self._update_btn.setObjectName("PrimaryButton")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.clicked.connect(self.check_updates_requested)
        updates_layout.addWidget(self._update_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(updates_card)
        root.addStretch(1)

    def set_version(self, version):
        self._version_label.setText("Version v%s" % version)

    def set_update_note(self, text):
        self._update_note.setText(text)

    def set_updates_checking(self, active):
        self._update_btn.setEnabled(not active)
        self._update_btn.setText("Checking\u2026" if active else "Check for Updates")

    def set_history(self, entries):
        self._history = [entry for entry in list(entries) if entry.get("text")][:50]
        self._rebuild_history()

    def add_history_entry(self, entry):
        self._history.insert(0, entry)
        del self._history[50:]
        self._rebuild_history()

    def _rebuild_history(self):
        layout = self._history_items_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for entry in self._history:
            layout.addWidget(self._make_history_item(entry))
        layout.addStretch(1)
        count = len(self._history)
        self._history_count.setText("%d transcript%s" % (count, "" if count == 1 else "s"))

    def _make_history_item(self, entry):
        item = QFrame()
        item.setObjectName("HistoryItem")
        row = QHBoxLayout(item)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        time_label = QLabel(entry.get("time", ""))
        time_label.setObjectName("HistoryTime")
        time_label.setFixedWidth(130)
        row.addWidget(time_label, 0, Qt.AlignmentFlag.AlignTop)
        text_label = QLabel(entry.get("text", ""))
        text_label.setObjectName("HistoryText")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        row.addWidget(text_label, 1)
        text = entry.get("text", "")
        copy_btn = QPushButton("Copy again")
        copy_btn.setObjectName("GhostButton")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(
            lambda _checked=False, t=text: self._copy_history(t)
        )
        row.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignTop)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DangerButton")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(
            lambda _checked=False, e=entry: self.history_delete_requested.emit(e)
        )
        row.addWidget(delete_btn, 0, Qt.AlignmentFlag.AlignTop)
        return item

    def remove_history_entry(self, entry):
        ts = entry.get("ts")
        text = entry.get("text")
        self._history = [
            e
            for e in self._history
            if not (
                (ts is not None and e.get("ts") == ts)
                or (ts is None and e.get("text") == text)
            )
        ]
        self._rebuild_history()

    def _copy_history(self, text):
        try:
            pyperclip.copy(text or "")
        except Exception as exc:
            self.show_error("Could not copy text: %s" % exc)

    def set_status(self, state):
        self._pill.set_state(state)
        label_map = {
            "ready": "Ready",
            "listening": "Listening...",
            "transcribing": "Transcribing...",
            "error": "Error",
            "paused": "Suspended",
        }
        self._status_text.setText(label_map.get(state, state))

    def set_service_toggle(self, enabled):
        self._toggle.blockSignals(True)
        self._toggle.set_checked(enabled)
        self._toggle.blockSignals(False)
        self._toggle.update()

    def add_words(self, count):
        self._session_words += max(0, count)
        self._words_value.setText(f"{self._session_words:,}")

    def show_error(self, message):
        self._banner.show_error(message)


class HotkeysTab(QWidget):
    record_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Hotkeys")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        hint = QLabel("Set the two-key combination that arms the microphone while held down.")
        hint.setObjectName("Hint")
        root.addWidget(hint)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(14)

        card_title = QLabel("Push-to-Talk Combination")
        card_title.setObjectName("SectionTitle")
        card_layout.addWidget(card_title)

        self.box = RecordingBox()
        self.box.clicked.connect(self.record_requested)
        card_layout.addWidget(self.box)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.record_btn = QPushButton("Record New Hotkey")
        self.record_btn.setObjectName("PrimaryButton")
        self.record_btn.clicked.connect(self.record_requested)
        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.setObjectName("GhostButton")
        self.reset_btn.clicked.connect(self.reset_requested)
        buttons.addWidget(self.record_btn)
        buttons.addWidget(self.reset_btn)
        buttons.addStretch(1)
        card_layout.addLayout(buttons)
        root.addWidget(card)

        how_card = QFrame()
        how_card.setObjectName("Card")
        how_layout = QVBoxLayout(how_card)
        how_layout.setContentsMargins(18, 16, 18, 16)
        how_layout.setSpacing(6)
        how_title = QLabel("How it works")
        how_title.setObjectName("SectionTitle")
        how_layout.addWidget(how_title)
        for line in (
            "Hold both keys down anywhere to start recording.",
            "Release either key to stop and transcribe.",
            "The recognized text is pasted into the window you were typing in.",
            "Press Esc while recording a hotkey to cancel.",
        ):
            how_layout.addWidget(QLabel(line))
        root.addWidget(how_card)
        root.addStretch(1)

    def set_combo(self, keys):
        self.box.set_combo(keys)

    def set_capturing(self, active):
        self.box.set_capturing(active)
        self.record_btn.setText("Cancel Recording" if active else "Record New Hotkey")
        self.reset_btn.setEnabled(not active)


class AudioSettingsTab(QWidget):
    error_raised = pyqtSignal(str)
    cues_toggled = pyqtSignal(bool)

    def __init__(self, engine, config, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.config = config
        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Audio Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        hint = QLabel("FlowAI listens continuously so the input meter stays live even while idle.")
        hint.setObjectName("Hint")
        root.addWidget(hint)

        device_card = QFrame()
        device_card.setObjectName("Card")
        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(18, 18, 18, 18)
        device_layout.setSpacing(14)

        device_title = QLabel("Microphone")
        device_title.setObjectName("SectionTitle")
        device_layout.addWidget(device_title)

        combo_row = QHBoxLayout()
        combo_row.setSpacing(10)
        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_device_selected)
        self._refresh_btn = QPushButton("Refresh Devices")
        self._refresh_btn.setObjectName("GhostButton")
        self._refresh_btn.clicked.connect(self.refresh_devices)
        combo_row.addWidget(self._combo, 1)
        combo_row.addWidget(self._refresh_btn)
        device_layout.addLayout(combo_row)

        self._device_info = QLabel("No devices detected")
        self._device_info.setObjectName("Hint")
        device_layout.addWidget(self._device_info)
        root.addWidget(device_card)

        meter_card = QFrame()
        meter_card.setObjectName("Card")
        meter_layout = QVBoxLayout(meter_card)
        meter_layout.setContentsMargins(18, 18, 18, 18)
        meter_layout.setSpacing(12)

        meter_header = QHBoxLayout()
        meter_title = QLabel("Input Level")
        meter_title.setObjectName("SectionTitle")
        self._db_label = QLabel("-60.0 dBFS")
        self._db_label.setObjectName("Hint")
        meter_header.addWidget(meter_title)
        meter_header.addStretch(1)
        meter_header.addWidget(self._db_label)
        meter_layout.addLayout(meter_header)

        self._meter = LevelMeter()
        meter_layout.addWidget(self._meter)

        self._rate_label = QLabel("16 kHz / mono / PCM")
        self._rate_label.setObjectName("Hint")
        meter_layout.addWidget(self._rate_label)
        root.addWidget(meter_card)

        cues_card = QFrame()
        cues_card.setObjectName("Card")
        cues_layout = QVBoxLayout(cues_card)
        cues_layout.setContentsMargins(18, 16, 18, 16)
        cues_layout.setSpacing(8)
        cues_title = QLabel("Feedback")
        cues_title.setObjectName("SectionTitle")
        cues_layout.addWidget(cues_title)
        self._cues_check = QCheckBox("Play short audio tones when recording starts, stops, and when text is pasted")
        self._cues_check.stateChanged.connect(self._on_cues_toggled)
        cues_layout.addWidget(self._cues_check)
        cues_hint = QLabel("Soft beeps confirm each step without needing to look at the app.")
        cues_hint.setObjectName("Hint")
        cues_layout.addWidget(cues_hint)
        root.addWidget(cues_card)
        root.addStretch(1)

    def refresh_devices(self):
        devices = self.engine.list_devices()
        if not devices:
            self._combo.clear()
            self._combo.setEnabled(False)
            self._device_info.setText("No input devices detected.")
            self.error_raised.emit("No microphone input devices were detected on this system.")
            return
        names = [device["name"] for device in devices]
        current = self.config.device
        if current not in names:
            current = self.engine.default_device_name()
            if current not in names:
                current = devices[0]["name"]
        self._combo.blockSignals(True)
        self._combo.clear()
        for device in devices:
            self._combo.addItem(device["name"], device["name"])
        select_index = self._combo.findData(current)
        self._combo.setCurrentIndex(max(0, select_index))
        self._combo.blockSignals(False)
        self._combo.setEnabled(True)
        self._device_info.setText('Capturing from "%s"' % self._combo.currentText())
        if current not in names:
            self.config.device = current
            self._open_device(current)

    def _on_device_selected(self, index):
        if index < 0:
            return
        device = self._combo.itemData(index)
        self._device_info.setText('Capturing from "%s"' % self._combo.itemText(index))
        self.config.device = device
        self._open_device(device)

    def _open_device(self, device):
        if not device:
            return
        if not self.engine.open(device):
            self.error_raised.emit('Could not open the microphone "%s".' % device)

    def _tick(self):
        if not self.isVisible():
            return
        db = self.engine.current_db()
        self._meter.set_level(db)
        self._meter.tick()
        self._db_label.setText(f"{db:.1f} dBFS")
        samplerate = self.engine.samplerate
        self._rate_label.setText(f"{samplerate:,} Hz / mono / PCM" if samplerate else "Stream closed")

    def set_cues(self, enabled):
        self._cues_check.blockSignals(True)
        self._cues_check.setChecked(bool(enabled))
        self._cues_check.blockSignals(False)

    def _on_cues_toggled(self, state):
        self.cues_toggled.emit(state == Qt.CheckState.Checked.value)


class ModelTab(QWidget):
    autostart_toggled = pyqtSignal(bool)
    model_changed = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Local Model")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        hint = QLabel("FlowAI transcribes speech locally with faster-whisper. "
                      "100% free, no API key, and no account required.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        model_card = QFrame()
        model_card.setObjectName("Card")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(18, 18, 18, 18)
        model_layout.setSpacing(14)

        model_title = QLabel("Recognition Engine")
        model_title.setObjectName("SectionTitle")
        model_layout.addWidget(model_title)

        engine_row = QHBoxLayout()
        engine_row.setSpacing(10)
        engine_badge = QLabel("faster-whisper")
        engine_badge.setObjectName("GhostButton")
        engine_badge.setStyleSheet(
            "background: #2C2C33; border: 1px solid #2A2A2E; border-radius: 8px;"
            " padding: 6px 12px; color: #ECECEF;"
        )
        self._combo = QComboBox()
        self._combo.addItem("tiny - Fastest & lightest (best for older PCs / instant response, lower accuracy)", "tiny")
        self._combo.addItem("base - Balanced standard (great mix of speed and everyday accuracy)", "base")
        self._combo.addItem("small - High accuracy (better at catching tricky words and names)", "small")
        self._combo.addItem("medium - Maximum precision (near-perfect transcription, slightly slower processing)", "medium")
        self._combo.currentIndexChanged.connect(self._on_model_selected)
        engine_row.addWidget(engine_badge)
        engine_row.addWidget(self._combo, 1)
        engine_row.addStretch(1)
        model_layout.addLayout(engine_row)

        self._status_label = QLabel("")
        self._status_label.setObjectName("Hint")
        self._status_label.setWordWrap(True)
        model_layout.addWidget(self._status_label)

        model_hint = QLabel("The model runs entirely on your computer on CPU. Switching downloads "
                            "the new model once; after that everything works offline. Any dictation "
                            "already in progress keeps working until the new model is ready.")
        model_hint.setObjectName("Hint")
        model_hint.setWordWrap(True)
        model_layout.addWidget(model_hint)
        root.addWidget(model_card)

        start_card = QFrame()
        start_card.setObjectName("Card")
        start_layout = QVBoxLayout(start_card)
        start_layout.setContentsMargins(18, 16, 18, 16)
        start_layout.setSpacing(8)
        start_title = QLabel("Startup")
        start_title.setObjectName("SectionTitle")
        start_layout.addWidget(start_title)
        self._autostart_check = QCheckBox("Launch FlowAI automatically when Windows starts")
        self._autostart_check.stateChanged.connect(self._on_autostart_changed)
        start_layout.addWidget(self._autostart_check)
        start_hint = QLabel("Registers a startup entry for the current user. Use the tray icon to quit.")
        start_hint.setObjectName("Hint")
        start_layout.addWidget(start_hint)
        root.addWidget(start_card)
        root.addStretch(1)

    def set_autostart(self, enabled):
        self._autostart_check.blockSignals(True)
        self._autostart_check.setChecked(bool(enabled))
        self._autostart_check.blockSignals(False)

    def set_selection(self, size):
        size = (size or "base").lower()
        self._combo.blockSignals(True)
        index = self._combo.findData(size)
        if index < 0:
            self._combo.addItem(size, size)
            index = self._combo.count() - 1
        self._combo.setCurrentIndex(index)
        self._combo.setToolTip(self._combo.itemText(index))
        self._combo.blockSignals(False)

    def set_model_loading(self, size):
        self.set_selection(size)
        self._status_label.setText(
            "Loading the '%s' model in the background... "
            "your current model keeps working until the new one is ready." % size
        )

    def set_model_ready(self, size):
        self.set_selection(size)
        self._status_label.setText("Ready - using the '%s' model." % size)

    def set_model_failed(self, size, active):
        self.set_selection(active)
        self._status_label.setText(
            "Could not load the '%s' model. Still using the '%s' model." % (size, active)
        )

    def _on_model_selected(self, index):
        if index < 0:
            return
        self._combo.setToolTip(self._combo.itemText(index))
        self.model_changed.emit(self._combo.itemData(index))

    def _on_autostart_changed(self, state):
        enabled = state == Qt.CheckState.Checked.value
        if self.config.autostart != enabled:
            self.autostart_toggled.emit(enabled)

class TitleBar(QWidget):
    close_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    maximize_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(52)
        self._drag_offset = None
        self._drag_from_maximized = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(app_icon_pixmap(22))
        layout.addWidget(icon_label)

        title = QLabel("FlowAI")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(title)

        tagline = QLabel("Dictate anywhere - hold the hotkey and speak")
        tagline.setObjectName("Hint")
        layout.addWidget(tagline)
        layout.addStretch(1)

        minimize_btn = QToolButton()
        minimize_btn.setObjectName("WindowBtn")
        minimize_btn.setText("\u2014")
        minimize_btn.setFixedSize(34, 26)
        minimize_btn.setToolTip("Minimize")
        minimize_btn.clicked.connect(self._on_minimize)
        layout.addWidget(minimize_btn)

        self.maximize_btn = QToolButton()
        self.maximize_btn.setObjectName("WindowBtn")
        self.maximize_btn.setText("\u25a1")
        self.maximize_btn.setFixedSize(34, 26)
        self.maximize_btn.setToolTip("Maximize")
        self.maximize_btn.clicked.connect(self._on_maximize)
        layout.addWidget(self.maximize_btn)

        close_btn = QToolButton()
        close_btn.setObjectName("CloseBtn")
        close_btn.setText("\u2715")
        close_btn.setFixedSize(34, 26)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.close_requested)
        layout.addWidget(close_btn)

    def _on_minimize(self):
        self.minimize_requested.emit()

    def _on_maximize(self):
        self.maximize_requested.emit()

    def set_maximized(self, maximized):
        self.maximize_btn.setText("\u2750" if maximized else "\u25a1")
        self.maximize_btn.setToolTip("Restore" if maximized else "Maximize")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            self._drag_offset = event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            self._drag_from_maximized = window.isMaximized()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            window = self.window()
            if self._drag_from_maximized:
                window.showNormal()
                cursor = event.globalPosition().toPoint()
                ratio = (cursor.x() - window.frameGeometry().x()) / max(1, window.width())
                ratio = min(1.0, max(0.0, ratio))
                self._drag_offset = QPoint(int(window.width() * ratio), cursor.y() - window.y())
                self._drag_from_maximized = False
            window.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self._drag_from_maximized = False
        super().mouseReleaseEvent(event)


class MainWindow(QWidget):
    close_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    maximize_requested = pyqtSignal()

    def __init__(self, config, engine, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(920, 620)
        self.resize(1000, 660)
        self._build(config, engine)

    def _build(self, config, engine):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 16, 16, 16)
        self._outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("WindowCard")
        self._card.setProperty("winMaximized", False)
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self._shadow = shadow
        self._card.setGraphicsEffect(shadow)
        self._outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.close_requested.connect(self.close_requested)
        self.title_bar.minimize_requested.connect(self.minimize_requested)
        self.title_bar.maximize_requested.connect(self.maximize_requested)
        card_layout.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = self._build_sidebar()
        body.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("ContentPane")
        self.dashboard = DashboardTab()
        self.hotkeys_tab = HotkeysTab()
        self.audio_tab = AudioSettingsTab(engine, config)
        self.model_tab = ModelTab(config)
        for page in (self.dashboard, self.hotkeys_tab, self.audio_tab, self.model_tab):
            page.setObjectName("Page")
            self._stack.addWidget(page)
        body.addWidget(self._stack, 1)
        card_layout.addLayout(body, 1)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.title_bar.set_maximized(self.isMaximized())
            self._apply_maximized_state(self.isMaximized())
        super().changeEvent(event)

    def _apply_maximized_state(self, maximized):
        self._outer.setContentsMargins(0, 0, 0, 0) if maximized else self._outer.setContentsMargins(16, 16, 16, 16)
        if maximized:
            self._card.setGraphicsEffect(None)
        elif not self._card.graphicsEffect():
            shadow = QGraphicsDropShadowEffect(self._card)
            shadow.setBlurRadius(48)
            shadow.setOffset(0, 8)
            shadow.setColor(QColor(0, 0, 0, 150))
            self._shadow = shadow
            self._card.setGraphicsEffect(shadow)
        for widget in (self._card, self._sidebar, self._stack):
            widget.setProperty("winMaximized", maximized)
            self.style().unpolish(widget)
            self.style().polish(widget)

    def closeEvent(self, event):
        self.close_requested.emit()
        event.ignore()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(196)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(6)

        brand = QLabel("FlowAI")
        brand.setObjectName("SideTitle")
        layout.addWidget(brand)

        brand_sub = QLabel("Voice to Text")
        brand_sub.setObjectName("Hint")
        layout.addWidget(brand_sub)
        layout.addSpacing(10)

        nav_label = QLabel("NAVIGATION")
        nav_label.setObjectName("NavLabel")
        layout.addWidget(nav_label)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons = {}
        for key, label in (
            ("dashboard", "Dashboard"),
            ("hotkeys", "Hotkeys"),
            ("audio", "Audio Settings"),
            ("model", "Local Model"),
        ):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(nav_icon("ai" if key == "model" else key))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda _checked=False, k=key: self.switch_page(k))
            self._nav_group.addButton(button)
            layout.addWidget(button)
            self._nav_buttons[key] = button

        layout.addStretch(1)

        version = QLabel("v%s" % updater.APP_VERSION)
        version.setObjectName("Hint")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        self._nav_buttons["dashboard"].setChecked(True)
        return sidebar

    def switch_page(self, key):
        names = ("dashboard", "hotkeys", "audio", "model")
        if key not in names:
            return
        self._stack.setCurrentIndex(names.index(key))
        if not self._nav_buttons[key].isChecked():
            self._nav_buttons[key].setChecked(True)

    def set_status(self, state):
        self.dashboard.set_status(state)

    def add_words(self, count):
        self.dashboard.add_words(count)

    def set_history(self, entries):
        self.dashboard.set_history(entries)

    def set_version(self, version):
        self.dashboard.set_version(version)

    def set_update_note(self, text):
        self.dashboard.set_update_note(text)

    def set_updates_checking(self, active):
        self.dashboard.set_updates_checking(active)

    def add_history_entry(self, entry):
        self.dashboard.add_history_entry(entry)

    def delete_history_entry(self, entry):
        self.dashboard.remove_history_entry(entry)

    def show_error(self, message):
        self.dashboard.show_error(message)

    def set_service_toggle(self, enabled):
        self.dashboard.set_service_toggle(enabled)

    def set_capture_state(self, active):
        self.hotkeys_tab.set_capturing(active)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, icon, on_open, on_toggle, on_quit, on_check_updates):
        super().__init__(icon)
        self._on_open = on_open
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self.setToolTip("FlowAI - Voice to Text")
        menu = QMenu()
        self._open_action = menu.addAction("Show")
        self._open_action.triggered.connect(self._on_open)
        self._toggle_action = menu.addAction("Suspend Hotkeys")
        self._toggle_action.triggered.connect(self._on_toggle)
        menu.addSeparator()
        check_action = menu.addAction("Check for Updates\u2026")
        check_action.triggered.connect(on_check_updates)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._on_quit)
        self.setContextMenu(menu)
        self.activated.connect(self._activated)

    def set_listener_state(self, enabled):
        self._toggle_action.setText("Suspend Hotkeys" if enabled else "Resume Hotkeys")

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._on_open()


class FlowAIApplication:
    def __init__(self, app, memory=None):
        self.app = app
        self.memory = memory
        self._quitting = False
        self._ipc_server = None
        self._app_hwnd = 0
        self._update_checking = False
        self._update_downloading = False
        self._cancel_download = False
        self._manual_check = False
        self._update_phase = "check"

        self._setup_logging()
        sys.excepthook = self._excepthook

        self.config = config_mod.Config()
        self.signals = Signals()
        self.cues = AudioCues()
        self.cues.set_enabled(self.config.audio_cues)
        self.history = HistoryStore(
            os.path.join(config_mod.config_dir(), "history.json"),
            os.path.join(config_mod.config_dir(), "history.txt"),
        )
        self.audio = AudioEngine()
        self.window = MainWindow(self.config, self.audio)
        self.manager = HotkeyManager(
            self.config,
            self.audio,
            self.signals,
            self._is_app_focused,
            app,
        )

        self._open_audio()
        self._wire_signals()

        self.tray = TrayIcon(
            make_app_icon(64),
            on_open=self._open_window,
            on_toggle=self._toggle_service,
            on_quit=self.quit_app,
            on_check_updates=lambda: self._check_for_updates(True),
        )

    def run(self):
        self._app_hwnd = int(self.window.winId())
        self.manager.start()
        self.tray.show()
        self.config.save()
        current_autostart = config_mod.autostart_enabled()
        if current_autostart:
            config_mod.set_autostart(True)
        if current_autostart != self.config.autostart:
            self.config.autostart = current_autostart
        self.window.set_service_toggle(True)
        self.window.set_status("ready")
        self.window.set_history(self.history.entries())
        self.window.hotkeys_tab.set_combo(self.config.hotkey)
        self.window.model_tab.set_autostart(self.config.autostart)
        self.window.model_tab.set_selection(self.config.model)
        self.window.audio_tab.refresh_devices()
        self.window.audio_tab.set_cues(self.config.audio_cues)
        self.window.set_version(updater.APP_VERSION)
        self.window.show()
        QTimer.singleShot(300, self._open_window)
        QTimer.singleShot(10000, lambda: self._check_for_updates(False))
        self._start_ipc_server()

    def _start_ipc_server(self):
        try:
            self._ipc_server = QLocalServer(self.app)
            self._ipc_server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
            self._ipc_server.newConnection.connect(self._on_ipc_connection)
            QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
            if not self._ipc_server.listen(SINGLE_INSTANCE_KEY):
                self._ipc_server = None
        except Exception:
            self._ipc_server = None

    def _on_ipc_connection(self):
        while self._ipc_server is not None and self._ipc_server.hasPendingConnections():
            connection = self._ipc_server.nextPendingConnection()
            connection.readyRead.connect(lambda c=connection: self._on_ipc_message(c))
            connection.disconnected.connect(connection.deleteLater)

    def _on_ipc_message(self, connection):
        try:
            data = bytes(connection.readAll().data())
        except Exception:
            data = b""
        if b"show" in data:
            self._open_window()

    def _setup_logging(self):
        log_path = config_mod.config_path().replace("config.json", "flowai.log")
        try:
            logging.basicConfig(
                filename=log_path,
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s %(message)s",
            )
        except OSError:
            pass

    def _excepthook(self, exc_type, exc_value, exc_tb):
        lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        try:
            logging.critical("Unhandled exception\n%s", "".join(lines))
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "FlowAI", "An unexpected error occurred.\n\n%s" % exc_value)
        except Exception:
            pass

    def _open_audio(self):
        devices = self.audio.list_devices()
        if not devices:
            self.window.show_error("No microphone input devices were detected on this system.")
            return
        names = [device["name"] for device in devices]
        name = self.config.device
        if name not in names:
            name = self.audio.default_device_name()
            if name not in names:
                name = devices[0]["name"]
            self.config.device = name
        if not self.audio.open(name):
            self.window.show_error("Could not open the selected microphone. Check that it is not in use.")

    def _wire_signals(self):
        self.signals.status_changed.connect(self.window.set_status)
        self.signals.status_changed.connect(self.cues.on_status)
        self.signals.transcription_done.connect(self._on_transcribed)
        self.signals.transcription_done.connect(self.cues.on_success)
        self.signals.transcription_error.connect(self.window.show_error)
        self.signals.transcription_error.connect(self.cues.on_error)
        self.signals.history_added.connect(self.window.add_history_entry)
        self.window.dashboard.history_delete_requested.connect(self._delete_history)
        self.signals.history_deleted.connect(self.window.delete_history_entry)
        self.signals.hotkey_captured.connect(self._on_hotkey_captured)
        self.signals.capture_state_changed.connect(self.window.set_capture_state)

        self.window.close_requested.connect(self.quit_app)
        self.window.minimize_requested.connect(self._minimize_window)
        self.window.maximize_requested.connect(self._toggle_maximize)
        self.window.dashboard.toggle_changed.connect(self.set_service)
        self.window.dashboard.check_updates_requested.connect(
            lambda: self._check_for_updates(True)
        )
        self.window.hotkeys_tab.record_requested.connect(self._record_requested)
        self.window.hotkeys_tab.reset_requested.connect(self._reset_hotkey)
        self.window.audio_tab.error_raised.connect(self.window.show_error)
        self.window.audio_tab.cues_toggled.connect(self._set_cues)
        self.window.model_tab.autostart_toggled.connect(self._set_autostart)
        self.window.model_tab.model_changed.connect(self._set_model)
        self.signals.model_ready.connect(self._on_model_ready)
        self.signals.model_error.connect(self._on_model_error)
        self.signals.update_available.connect(self._on_update_available)
        self.signals.update_not_available.connect(self._on_update_not_available)
        self.signals.update_failed.connect(self._on_update_failed)
        self.signals.update_downloaded.connect(self._on_update_downloaded)

    def _on_transcribed(self, text, hwnd):
        words = [w for w in text.split() if w.strip()]
        self.window.add_words(len(words))
        entry = self.history.add(text)
        if entry:
            self.signals.on_history_added(entry)

    def _delete_history(self, entry):
        if self.history.delete(entry):
            self.signals.on_history_deleted(entry)

    def _on_hotkey_captured(self, combo):
        self.window.hotkeys_tab.set_combo(combo)

    def _record_requested(self):
        if self.manager.is_capturing():
            self.manager.cancel_capture()
        else:
            self.manager.start_capture()

    def _reset_hotkey(self):
        self.manager.set_hotkey(["ctrl", "space"])
        self.window.hotkeys_tab.set_combo(self.config.hotkey)

    def _set_autostart(self, enabled):
        ok = config_mod.set_autostart(enabled)
        if ok:
            self.config.autostart = enabled
        else:
            self.config.autostart = config_mod.autostart_enabled()
            self.window.model_tab.set_autostart(self.config.autostart)
            self.window.show_error("Could not update the Windows startup entry.")

    def _set_cues(self, enabled):
        self.config.audio_cues = enabled
        self.cues.set_enabled(enabled)

    def _set_model(self, size):
        if size == self.config.model:
            return
        self.window.model_tab.set_model_loading(size)
        self.manager.switch_model(
            size,
            lambda loaded: self.signals.on_model_ready(loaded),
            lambda failed, message: self.signals.on_model_error(failed, message),
        )

    def _on_model_ready(self, size):
        self.window.model_tab.set_model_ready(size)

    def _on_model_error(self, size, message):
        self.window.model_tab.set_model_failed(size, self.config.model)
        self.window.show_error("Could not load the '%s' model: %s" % (size, message))

    # --- updates ---------------------------------------------------------

    def _check_for_updates(self, manual):
        if self._update_checking:
            return
        self._update_checking = True
        self._manual_check = manual
        self._update_phase = "check"
        self.window.set_updates_checking(True)
        self.window.set_update_note("Checking for updates\u2026")

        def work():
            try:
                info = updater.fetch_latest()
            except updater.UpdateError as exc:
                self.signals.on_update_failed(str(exc))
            else:
                if updater.is_newer(info["version"], updater.APP_VERSION):
                    self.signals.on_update_available(
                        info["version"], info["download_url"], info["release_url"]
                    )
                else:
                    self.signals.on_update_not_available()
            finally:
                self._update_checking = False

        threading.Thread(target=work, daemon=True, name="FlowAI-Updater").start()

    def _on_update_not_available(self):
        self.window.set_updates_checking(False)
        self.window.set_update_note("You're up to date.")
        if self._manual_check:
            self.tray.showMessage(
                "FlowAI",
                "You're running the latest version (v%s)." % updater.APP_VERSION,
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def _on_update_failed(self, message):
        self.window.set_updates_checking(False)
        if self._update_phase == "download":
            self.window.set_update_note("Download failed.")
        else:
            self.window.set_update_note("Couldn\u2019t check for updates.")
        if self._manual_check:
            self.tray.showMessage(
                "FlowAI",
                "Could not check for updates: %s" % message,
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

    def _on_update_available(self, version, download_url, release_url):
        self.window.set_updates_checking(False)
        self.window.set_update_note("Update v%s is available." % version)
        self._open_window()
        dialog = QDialog(self.window)
        dialog.setWindowTitle("FlowAI Update")
        dialog.setModal(True)
        dialog.setMinimumWidth(380)
        dialog.setStyleSheet(
            "background: #16161A; color: #ECECEF;"
            " font-size: 13px;"
        )
        root = QVBoxLayout(dialog)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Update available")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(title)

        body = QLabel(
            "FlowAI v%s is now available. You're running v%s.\n\n"
            "You can download the new version and let FlowAI install "
            "it automatically, or take a look at the release page first."
            % (version, updater.APP_VERSION)
        )
        body.setObjectName("Hint")
        body.setWordWrap(True)
        root.addWidget(body)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        install_btn = QPushButton("Download & Install")
        install_btn.setObjectName("PrimaryButton")
        page_btn = QPushButton("Open Release Page")
        page_btn.setObjectName("GhostButton")
        later_btn = QPushButton("Later")
        later_btn.setObjectName("GhostButton")
        buttons.addWidget(install_btn)
        buttons.addWidget(page_btn)
        buttons.addWidget(later_btn)
        root.addLayout(buttons)

        if not download_url:
            install_btn.setEnabled(False)
            install_btn.setText("Installer Unavailable")
            body.setText(
                "FlowAI v%s is now available. You're running v%s.\n\n"
                "This release has no bundled installer, so open the release "
                "page to download it."
                % (version, updater.APP_VERSION)
            )
        install_btn.clicked.connect(
            lambda: self._download_update(download_url, version)
        )
        page_btn.clicked.connect(
            lambda: (webbrowser.open(release_url), dialog.accept())
        )
        later_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def _download_update(self, download_url, version):
        if self._update_downloading:
            return
        self._update_downloading = True
        self._cancel_download = False
        self._update_phase = "download"
        self.window.set_updates_checking(True)
        self.window.set_update_note("Downloading update v%s\u2026" % version)

        dialog = QDialog(self.window)
        dialog.setWindowTitle("FlowAI Update")
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        dialog.setStyleSheet("background: #16161A; color: #ECECEF; font-size: 13px;")
        root = QVBoxLayout(dialog)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        status = QLabel("Downloading FlowAI v%s\u2026" % version)
        status.setStyleSheet("font-size: 15px; font-weight: 600;")
        root.addWidget(status)

        detail = QLabel(
            "This happens in the background and won't interrupt your dictation. "
            "The new version will be applied when the download finishes."
        )
        detail.setObjectName("Hint")
        detail.setWordWrap(True)
        root.addWidget(detail)

        cancel_btn = QPushButton("Cancel Download")
        cancel_btn.setObjectName("GhostButton")
        root.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)
        cancel_btn.clicked.connect(lambda: setattr(self, "_cancel_download", True))
        dialog.show()
        self.signals.update_downloaded.connect(dialog.accept)
        self.signals.update_failed.connect(lambda _message: dialog.accept())

        def work():
            try:
                dest_dir = os.path.join(tempfile.gettempdir(), "FlowAI_update")
                new_exe = updater.download_exe(
                    download_url, dest_dir, cancel=lambda: self._cancel_download
                )
                self.signals.on_update_downloaded(new_exe)
            except updater.UpdateError as exc:
                self.signals.on_update_failed(str(exc))
            except Exception as exc:
                self.signals.on_update_failed("Download failed: %s" % exc)
            finally:
                self._update_downloading = False

        threading.Thread(target=work, daemon=True, name="FlowAI-Download").start()

    def _on_update_downloaded(self, new_exe):
        self.window.set_updates_checking(False)
        self.window.set_update_note("Update ready \u2014 restart to install.")
        if not getattr(sys, "frozen", False):
            subprocess.Popen(["explorer", "/select," + os.path.normpath(new_exe)])
            return

        dialog = QDialog(self.window)
        dialog.setWindowTitle("FlowAI Update")
        dialog.setModal(True)
        dialog.setMinimumWidth(380)
        dialog.setStyleSheet("background: #16161A; color: #ECECEF; font-size: 13px;")
        root = QVBoxLayout(dialog)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Ready to install")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(title)

        body = QLabel(
            "The update has been downloaded. FlowAI will now restart "
            "automatically to finish installing the new version."
        )
        body.setObjectName("Hint")
        body.setWordWrap(True)
        root.addWidget(body)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        restart_btn = QPushButton("Restart & Update")
        restart_btn.setObjectName("PrimaryButton")
        not_now_btn = QPushButton("Not Now")
        not_now_btn.setObjectName("GhostButton")
        buttons.addWidget(restart_btn)
        buttons.addWidget(not_now_btn)
        root.addLayout(buttons)

        def apply():
            dialog.accept()
            try:
                updater.apply_update(new_exe, sys.executable)
            except updater.UpdateError as exc:
                self.tray.showMessage(
                    "FlowAI", "Could not install the update: %s" % exc,
                    QSystemTrayIcon.MessageIcon.Warning, 4000
                )
                webbrowser.open(updater.RELEASE_URL)
                return
            self.quit_app()

        restart_btn.clicked.connect(apply)
        not_now_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def set_service(self, enabled):
        self.manager.set_service(enabled)
        self.tray.set_listener_state(enabled)
        self.window.set_service_toggle(enabled)
        self.window.set_status("ready" if enabled else "paused")

    def _toggle_service(self):
        self.set_service(not self.manager.service_enabled())

    def _open_window(self):
        window = self.window
        if window.isMinimized():
            window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()

    def _minimize_window(self):
        if sys.platform == "win32":
            hwnd = int(self.window.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 6)
        else:
            self.window.showMinimized()

    def _toggle_maximize(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def _is_app_focused(self):
        try:
            foreground = int(ctypes.windll.user32.GetForegroundWindow())
            return self._app_hwnd != 0 and foreground == self._app_hwnd
        except Exception:
            return False

    def quit_app(self):
        if self._quitting:
            return
        self._quitting = True
        try:
            self.manager.cancel_capture()
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass
        self.manager.stop()
        self.audio.close()
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        force_exit = threading.Timer(2.0, lambda: os._exit(0))
        force_exit.daemon = True
        force_exit.start()
        self.app.quit()


SINGLE_INSTANCE_KEY = "FlowAI_SingleInstance_7f3a9c"


def single_instance(key):
    memory = QSharedMemory(key)
    if memory.attach():
        return False, None
    if not memory.create(1):
        return False, None
    return True, memory


def _migrate_to_stable_path():
    """If the packaged app is running from an unstable location (Downloads,
    temp, or a Mark-of-the-Web-flagged copy), move it to the stable install
    dir and relaunch from there. Returns True when the caller should exit.
    """
    if not getattr(sys, "frozen", False):
        return False
    installed = config_mod.installed_exe()
    running = os.path.abspath(sys.executable)
    if running.lower() == os.path.abspath(installed).lower():
        return False

    home = (os.path.expanduser("~") or "").lower()
    running_lower = running.lower()
    temp_root = (os.path.normpath(tempfile.gettempdir()) or "").lower()
    unstable = (
        config_mod.has_mark_of_web(running)
        or running_lower.startswith(os.path.join(home, "downloads"))
        or running_lower.startswith(temp_root)
    )
    if not unstable:
        return False

    target = config_mod.ensure_installed()
    if not target or os.path.abspath(target).lower() == running_lower:
        return False
    subprocess.Popen([target])
    return True


def main():
    if _migrate_to_stable_path():
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("FlowAI")
    app.setOrganizationName("FlowAI")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyleSheet(QSS)
    app.setWindowIcon(make_app_icon(256))

    ok, memory = single_instance("FlowAI_SingleInstance_7f3a9c")
    if not ok:
        socket = QLocalSocket()
        socket.connectToServer(SINGLE_INSTANCE_KEY)
        if socket.waitForConnected(1500):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(1500)
        else:
            QMessageBox.information(None, "FlowAI", "FlowAI is already running.")
        return 1

    controller = FlowAIApplication(app, memory)
    controller.run()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
