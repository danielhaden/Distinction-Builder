"""Application bootstrap: build the QApplication, store, and main window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .storage import NoteStore

# Default on-disk location for the note database. Kept next to the project for
# now; a settings-driven location can come later.
DEFAULT_DB = Path("notes.sqlite")


def run(db_path: str | Path = DEFAULT_DB) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Distinction Builder")

    store = NoteStore(db_path)
    window = MainWindow(store)
    window.show()
    return app.exec()
