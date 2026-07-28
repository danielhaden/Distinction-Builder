"""SQLite-backed persistence for notes and their links.

The store owns one connection and exposes a small, synchronous API. Links are
*derived* from note bodies: every time a note is saved we re-parse its
wikilinks and rewrite that note's rows in the ``links`` table. That keeps the
graph consistent without asking callers to maintain it by hand.

Titles are the link target, so they are treated as unique case-insensitively.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Link, Note, parse_wikilinks

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per (note, referenced title). target_id is filled in when a note
-- with that title exists, else NULL (a dangling link).
CREATE TABLE IF NOT EXISTS links (
    source_id    INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL,
    target_id    INTEGER REFERENCES notes(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_title
    ON notes (title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_links_source ON links (source_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON links (target_id);
CREATE INDEX IF NOT EXISTS idx_links_target_title
    ON links (target_title COLLATE NOCASE);
"""


class NoteStore:
    """A note database. Pass ``":memory:"`` for an ephemeral store (tests)."""

    def __init__(self, path: str | Path = "notes.sqlite") -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- notes ---------------------------------------------------------------

    def create_note(self, title: str, body: str = "") -> Note:
        """Insert a new note and index its links. Raises on duplicate title."""
        cur = self.conn.execute(
            "INSERT INTO notes (title, body) VALUES (?, ?)", (title, body)
        )
        note_id = int(cur.lastrowid)
        self._reindex_links(note_id, body)
        self._resolve_dangling_to(title, note_id)
        self.conn.commit()
        return self.get_note(note_id)  # type: ignore[return-value]

    def update_note(self, note_id: int, title: str, body: str) -> Note:
        """Update a note's title/body, re-indexing links and dangling refs."""
        old = self.get_note(note_id)
        self.conn.execute(
            "UPDATE notes SET title = ?, body = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (title, body, note_id),
        )
        self._reindex_links(note_id, body)
        if old is not None and old.title.lower() != title.lower():
            # This note no longer answers to its old title; drop it as a
            # resolved target and (re)resolve links that point at the new one.
            self._unresolve_target(note_id, keep_title=title)
        self._resolve_dangling_to(title, note_id)
        self.conn.commit()
        return self.get_note(note_id)  # type: ignore[return-value]

    def delete_note(self, note_id: int) -> None:
        """Delete a note. Links *from* it are removed; links *to* it become
        dangling again (target_id -> NULL via ON DELETE SET NULL)."""
        self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()

    def get_note(self, note_id: int) -> Note | None:
        row = self.conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        return _row_to_note(row) if row else None

    def get_note_by_title(self, title: str) -> Note | None:
        row = self.conn.execute(
            "SELECT * FROM notes WHERE title = ? COLLATE NOCASE", (title,)
        ).fetchone()
        return _row_to_note(row) if row else None

    def list_notes(self) -> list[Note]:
        rows = self.conn.execute(
            "SELECT * FROM notes ORDER BY title COLLATE NOCASE"
        ).fetchall()
        return [_row_to_note(r) for r in rows]

    def search_notes(self, query: str) -> list[Note]:
        """Case-insensitive substring search over title and body.

        An empty query returns all notes. (FTS can replace this later without
        changing the signature.)
        """
        query = query.strip()
        if not query:
            return self.list_notes()
        like = f"%{query}%"
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? "
            "ORDER BY title COLLATE NOCASE",
            (like, like),
        ).fetchall()
        return [_row_to_note(r) for r in rows]

    # -- links ---------------------------------------------------------------

    def get_outgoing_links(self, note_id: int) -> list[Link]:
        rows = self.conn.execute(
            "SELECT source_id, target_title, target_id FROM links "
            "WHERE source_id = ? ORDER BY target_title COLLATE NOCASE",
            (note_id,),
        ).fetchall()
        return [Link(r["source_id"], r["target_title"], r["target_id"]) for r in rows]

    def get_backlinks(self, note_id: int) -> list[Note]:
        """Notes that link *to* `note_id`."""
        rows = self.conn.execute(
            "SELECT DISTINCT n.* FROM notes n "
            "JOIN links l ON l.source_id = n.id "
            "WHERE l.target_id = ? ORDER BY n.title COLLATE NOCASE",
            (note_id,),
        ).fetchall()
        return [_row_to_note(r) for r in rows]

    # -- internals -----------------------------------------------------------

    def _reindex_links(self, note_id: int, body: str) -> None:
        """Replace `note_id`'s outgoing links to match its body's wikilinks."""
        self.conn.execute("DELETE FROM links WHERE source_id = ?", (note_id,))
        for title in parse_wikilinks(body):
            target = self.conn.execute(
                "SELECT id FROM notes WHERE title = ? COLLATE NOCASE", (title,)
            ).fetchone()
            self.conn.execute(
                "INSERT INTO links (source_id, target_title, target_id) "
                "VALUES (?, ?, ?)",
                (note_id, title, target["id"] if target else None),
            )

    def _resolve_dangling_to(self, title: str, note_id: int) -> None:
        """Point any dangling links naming `title` at the now-existing note."""
        self.conn.execute(
            "UPDATE links SET target_id = ? "
            "WHERE target_id IS NULL AND target_title = ? COLLATE NOCASE",
            (note_id, title),
        )

    def _unresolve_target(self, note_id: int, keep_title: str) -> None:
        """Detach links that resolved to `note_id` but no longer name it."""
        self.conn.execute(
            "UPDATE links SET target_id = NULL "
            "WHERE target_id = ? AND target_title <> ? COLLATE NOCASE",
            (note_id, keep_title),
        )


def _row_to_note(row: sqlite3.Row) -> Note:
    return Note(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
