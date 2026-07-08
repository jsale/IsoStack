"""IsoStack entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from isostack.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("IsoStack")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
