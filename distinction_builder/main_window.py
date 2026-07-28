"""The main application window: a three-pane notes workbench.

Layout (left → right):
  * Notes list with a live search box.
  * Editor: title field + body text area. ``[[wikilinks]]`` in the body
    define the network.
  * Connections: backlinks (notes pointing here) and outgoing links
    (including dangling ones you can create in a click).
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .canvas import FormCanvas
from .models import Note
from .storage import NoteStore

# Roles for stashing data on list items.
_NOTE_ID = Qt.ItemDataRole.UserRole
_LINK_TITLE = Qt.ItemDataRole.UserRole + 1


class MainWindow(QMainWindow):
    def __init__(self, store: NoteStore) -> None:
        super().__init__()
        self.store = store
        self._current: Note | None = None  # note in the editor (id=None if new)
        self._dirty = False

        self.setWindowTitle("Distinction Builder")
        self.resize(1100, 700)

        self._build_ui()
        self._build_actions()
        self.refresh_list()
        self._update_editor_enabled()

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_notes_pane(), "Notes")
        self.canvas = FormCanvas()
        self.tabs.addTab(self.canvas, "Forms")
        self.setCentralWidget(self.tabs)
        self.tabs.setCurrentWidget(self.canvas)
        self.statusBar().showMessage("Ready")

    def _build_notes_pane(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_list_pane())
        splitter.addWidget(self._build_editor_pane())
        splitter.addWidget(self._build_connections_pane())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        return splitter

    def _build_list_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 6, 6, 6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search notes…  (Ctrl+F)")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self.refresh_list)
        layout.addWidget(self.search_box)

        self.note_list = QListWidget()
        self.note_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.note_list.currentItemChanged.connect(self._on_list_selection)
        layout.addWidget(self.note_list)
        return pane

    def _build_editor_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 6, 6, 6)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title")
        self.title_edit.textEdited.connect(self._mark_dirty)
        layout.addWidget(self.title_edit)

        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText(
            "Write here. Link to another note with [[its title]]."
        )
        self.body_edit.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.body_edit)

        self.save_button = QPushButton("Save  (Ctrl+S)")
        self.save_button.clicked.connect(self.save_current)
        layout.addWidget(self.save_button)
        return pane

    def _build_connections_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 6, 6, 6)

        layout.addWidget(_section_label("Backlinks"))
        self.backlinks_list = QListWidget()
        self.backlinks_list.itemActivated.connect(self._on_backlink_activated)
        layout.addWidget(self.backlinks_list)

        layout.addWidget(_section_label("Outgoing links"))
        self.outgoing_list = QListWidget()
        self.outgoing_list.itemActivated.connect(self._on_outgoing_activated)
        layout.addWidget(self.outgoing_list)
        return pane

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&Note")

        new = QAction("&New", self)
        new.setShortcut(QKeySequence.StandardKey.New)
        new.triggered.connect(self.new_note)
        file_menu.addAction(new)

        save = QAction("&Save", self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save_current)
        file_menu.addAction(save)

        delete = QAction("&Delete", self)
        delete.setShortcut(QKeySequence("Ctrl+Backspace"))
        delete.triggered.connect(self.delete_current)
        file_menu.addAction(delete)

        file_menu.addSeparator()
        focus_search = QAction("&Find", self)
        focus_search.setShortcut(QKeySequence.StandardKey.Find)
        focus_search.triggered.connect(self.search_box.setFocus)
        file_menu.addAction(focus_search)

    # -- list / search -------------------------------------------------------

    def refresh_list(self) -> None:
        """Repopulate the note list from the current search query."""
        selected_id = self._current.id if self._current else None
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for note in self.store.search_notes(self.search_box.text()):
            item = QListWidgetItem(note.title or "(untitled)")
            item.setData(_NOTE_ID, note.id)
            self.note_list.addItem(item)
            if note.id == selected_id:
                self.note_list.setCurrentItem(item)
        self.note_list.blockSignals(False)

    def _on_list_selection(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        note_id = current.data(_NOTE_ID)
        if self._current and note_id == self._current.id:
            return
        if not self._maybe_autosave():
            return
        note = self.store.get_note(note_id)
        if note:
            self._load_note(note)

    # -- editor state --------------------------------------------------------

    def _load_note(self, note: Note) -> None:
        self._current = note
        self.title_edit.blockSignals(True)
        self.body_edit.blockSignals(True)
        self.title_edit.setText(note.title)
        self.body_edit.setPlainText(note.body)
        self.title_edit.blockSignals(False)
        self.body_edit.blockSignals(False)
        self._set_dirty(False)
        self._update_editor_enabled()
        self._refresh_connections()

    def new_note(self) -> None:
        if not self._maybe_autosave():
            return
        self._current = Note(id=None, title="", body="")
        self.title_edit.clear()
        self.body_edit.clear()
        self.note_list.clearSelection()
        self.note_list.setCurrentItem(None)
        self._set_dirty(False)
        self._update_editor_enabled()
        self._refresh_connections()
        self.title_edit.setFocus()

    def save_current(self) -> None:
        if self._current is None:
            return
        title = self.title_edit.text().strip()
        body = self.body_edit.toPlainText()
        if not title:
            self.statusBar().showMessage("A note needs a title before saving.")
            self.title_edit.setFocus()
            return
        try:
            if self._current.id is None:
                note = self.store.create_note(title, body)
            else:
                note = self.store.update_note(self._current.id, title, body)
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Duplicate title",
                f"A note titled “{title}” already exists. Titles must be unique "
                "because they are how links find their target.",
            )
            return
        self._current = note
        self._set_dirty(False)
        self.refresh_list()
        self._refresh_connections()
        self.statusBar().showMessage(f"Saved “{note.title}”", 3000)

    def delete_current(self) -> None:
        if self._current is None or self._current.id is None:
            # Nothing persisted yet; just clear the editor.
            self.new_note()
            return
        title = self._current.title
        confirm = QMessageBox.question(
            self,
            "Delete note",
            f"Delete “{title}”? Links pointing to it will become dangling.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_note(self._current.id)
        self._current = None
        self.title_edit.clear()
        self.body_edit.clear()
        self._set_dirty(False)
        self.refresh_list()
        self._update_editor_enabled()
        self._refresh_connections()
        self.statusBar().showMessage(f"Deleted “{title}”", 3000)

    def _maybe_autosave(self) -> bool:
        """Persist unsaved edits before navigating away.

        Returns ``False`` only when the user must intervene (e.g. an untitled
        dirty note), so callers can abort the navigation.
        """
        if not self._dirty or self._current is None:
            return True
        if not self.title_edit.text().strip():
            # Can't silently save an untitled note; keep the user put.
            QTimer.singleShot(0, self._reselect_current)
            self.statusBar().showMessage("Give this note a title, then save.")
            return False
        self.save_current()
        return not self._dirty

    def _reselect_current(self) -> None:
        """Restore the list selection to the note in the editor."""
        if not self._current or self._current.id is None:
            return
        for i in range(self.note_list.count()):
            item = self.note_list.item(i)
            if item.data(_NOTE_ID) == self._current.id:
                self.note_list.setCurrentItem(item)
                return

    def _mark_dirty(self) -> None:
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        title = self.title_edit.text().strip() or "untitled"
        star = "• " if dirty else ""
        self.setWindowTitle(f"{star}{title} — Distinction Builder")

    def _update_editor_enabled(self) -> None:
        editing = self._current is not None
        self.title_edit.setEnabled(editing)
        self.body_edit.setEnabled(editing)
        self.save_button.setEnabled(editing)

    # -- connections pane ----------------------------------------------------

    def _refresh_connections(self) -> None:
        self.backlinks_list.clear()
        self.outgoing_list.clear()
        if self._current is None or self._current.id is None:
            return

        for note in self.store.get_backlinks(self._current.id):
            item = QListWidgetItem(note.title)
            item.setData(_NOTE_ID, note.id)
            self.backlinks_list.addItem(item)
        if self.backlinks_list.count() == 0:
            self.backlinks_list.addItem(_placeholder("No backlinks yet"))

        for link in self.store.get_outgoing_links(self._current.id):
            if link.target_id is not None:
                item = QListWidgetItem(link.target_title)
                item.setData(_NOTE_ID, link.target_id)
            else:
                item = QListWidgetItem(f"{link.target_title}  (create)")
                item.setData(_NOTE_ID, None)
                item.setData(_LINK_TITLE, link.target_title)
                item.setForeground(Qt.GlobalColor.gray)
            self.outgoing_list.addItem(item)
        if self.outgoing_list.count() == 0:
            self.outgoing_list.addItem(_placeholder("No outgoing links"))

    def _on_backlink_activated(self, item: QListWidgetItem) -> None:
        self._navigate_to(item.data(_NOTE_ID))

    def _on_outgoing_activated(self, item: QListWidgetItem) -> None:
        note_id = item.data(_NOTE_ID)
        if note_id is not None:
            self._navigate_to(note_id)
            return
        title = item.data(_LINK_TITLE)
        if title and self._maybe_autosave():
            note = self.store.create_note(title, "")
            self.refresh_list()
            self._navigate_to(note.id)

    def _navigate_to(self, note_id: int | None) -> None:
        if note_id is None:
            return
        note = self.store.get_note(note_id)
        if note is None:
            return
        if not self._maybe_autosave():
            return
        self._load_note(note)
        self._reselect_current()

    # -- window --------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._maybe_autosave()
        self.store.close()
        super().closeEvent(event)


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


def _placeholder(text: str) -> QListWidgetItem:
    item = QListWidgetItem(text)
    item.setForeground(Qt.GlobalColor.gray)
    item.setFlags(Qt.ItemFlag.NoItemFlags)
    return item
