import os
import sys

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPen,
                         QPixmap)
from PyQt6.QtWidgets import QApplication


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
    painter.drawRoundedRect(QRectF(0.0, 0.0, s, s), s * 0.22, s * 0.22)
    pen = QPen(QColor("#FFFFFF"), max(1.0, s * 0.055))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(s * 0.38, s * 0.13, s * 0.24, s * 0.48), s * 0.09, s * 0.09)
    painter.drawLine(int(s * 0.5), int(s * 0.61), int(s * 0.5), int(s * 0.79))
    painter.drawLine(int(s * 0.30), int(s * 0.79), int(s * 0.70), int(s * 0.79))
    painter.drawArc(int(s * 0.30), int(s * 0.30), int(s * 0.40), int(s * 0.40), 180 * 16, 180 * 16)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#5B8CFF"))
    painter.drawEllipse(int(s * 0.78), int(s * 0.20), int(s * 0.12), int(s * 0.12))
    painter.end()
    return pixmap


def main():
    app = QApplication(sys.argv)
    root = os.path.dirname(os.path.abspath(__file__))
    assets = os.path.join(root, "assets")
    os.makedirs(assets, exist_ok=True)
    target = os.path.join(assets, "app.ico")
    pixmap = app_icon_pixmap(256)
    if not pixmap.save(target, "ICO"):
        raise SystemExit("Failed to write %s" % target)
    print("Wrote %s" % target)


if __name__ == "__main__":
    main()
