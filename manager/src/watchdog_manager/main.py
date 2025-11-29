"""Main entry point for Watchdog Manager GUI."""

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType

from .backend import ChatBackend, TopicListModel


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Watchdog Manager")
    app.setOrganizationName("watchdog")
    app.setDesktopFileName("watchdog-manager")

    # Set icon
    app.setWindowIcon(QIcon.fromTheme("view-list-details"))

    # Register types
    qmlRegisterType(ChatBackend, "Watchdog", 1, 0, "ChatBackend")
    qmlRegisterType(TopicListModel, "Watchdog", 1, 0, "TopicListModel")

    engine = QQmlApplicationEngine()

    # Find QML file
    qml_file = Path(__file__).parent.parent.parent / "qml" / "Main.qml"
    if not qml_file.exists():
        # Try installed location
        qml_file = Path(__file__).parent / "qml" / "Main.qml"

    if not qml_file.exists():
        print(f"Error: QML file not found at {qml_file}")
        sys.exit(1)

    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        print("Error: Failed to load QML")
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
