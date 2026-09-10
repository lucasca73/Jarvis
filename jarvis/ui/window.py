"""Optional minimal Qt window for displaying Jarvis status."""

from __future__ import annotations

from typing import Callable

from jarvis.ui.status import StatusSnapshot


def qt_available() -> bool:
    """Return whether the optional desktop UI dependency is installed."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        return False
    return True


def create_window(snapshot: StatusSnapshot, *, on_quit: Callable[[], None] | None = None):
    """Create a small status window without starting a Qt event loop."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
        from PySide6.QtWidgets import QLabel, QMenu, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget
    except ImportError as exc:
        raise RuntimeError("Install the optional GUI dependency with: pip install -e '.[gui]'") from exc

    class StatusWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Jarvis")
            self.setFixedSize(240, 160)
            self._indicator = QLabel()
            self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._indicator.setFixedHeight(72)
            self._label = QLabel()
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._label.setStyleSheet("font-size: 18px; font-weight: 600;")
            self._detail = QLabel()
            self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._detail.setWordWrap(True)
            self._detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(18, 14, 18, 14)
            layout.addWidget(self._indicator)
            layout.addWidget(self._label)
            layout.addWidget(self._detail)
            self._tray = QSystemTrayIcon(self)
            self._tray.setIcon(self._make_icon())
            menu = QMenu()
            show_action = QAction("Show Jarvis", self)
            show_action.triggered.connect(self.showNormal)
            menu.addAction(show_action)
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self._quit)
            menu.addAction(quit_action)
            self._tray.setContextMenu(menu)
            self._tray.show()
            self.set_snapshot(snapshot)

        def _make_icon(self):
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setBrush(QColor("#4b5563"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(4, 4, 24, 24)
            painter.end()
            return QIcon(pixmap)

        def set_snapshot(self, value: StatusSnapshot) -> None:
            if not isinstance(value, StatusSnapshot):
                raise TypeError("value must be a StatusSnapshot")
            self._label.setText(value.label)
            self._detail.setText(value.detail)
            colors = {"ready": "#6b7280", "listening": "#2563eb", "thinking": "#7c3aed",
                      "speaking": "#059669", "starting": "#d97706", "stopping": "#6b7280",
                      "unavailable": "#dc2626"}
            self._indicator.setStyleSheet(
                f"background-color: {colors[value.state.value]}; border-radius: 36px;"
            )

        def closeEvent(self, event):
            self.hide()
            event.ignore()

        def _quit(self):
            if on_quit is not None:
                on_quit()

    return StatusWindow()
