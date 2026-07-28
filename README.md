# Distinction Builder

A PySide6 desktop app for creating, searching, and managing **networked notes**.

This is the starting scaffold for a larger aim: a workbench for textual and
hermeneutical analysis grounded in G. Spencer-Brown's *Laws of Form*. For now it
does the fundamentals well — write notes, link them with `[[wikilinks]]`, and
navigate the resulting network via search and backlinks.

## Features

- **Notes** — title + body, persisted in a single SQLite file (`notes.sqlite`).
- **Networked** — reference another note with `[[its title]]`. Links are parsed
  on save; the right-hand pane shows **backlinks** (who points here) and
  **outgoing links**. Dangling links (targets that don't exist yet) are shown
  greyed with a *(create)* affordance — one click makes the note.
- **Search** — live substring search over titles and bodies.

## Running

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python main.py
```

## Layout

```
main.py                       — entry point
distinction_builder/
  app.py                      — QApplication + window bootstrap
  main_window.py              — three-pane UI (list / editor / connections)
  storage.py                  — SQLite NoteStore; derives links from bodies
  models.py                   — Note/Link data types + wikilink parsing
tests/
  test_storage.py             — storage + link-resolution tests
```

The domain (`models.py`) and storage (`storage.py`) layers are Qt-free so they
can be reused for analysis work later without the GUI.

## Notes on design

- **Titles are the link target**, so they're unique (case-insensitive).
  Renaming a note re-points links that name the new title and detaches ones
  that named the old.
- Deleting a note leaves inbound links **dangling** rather than erasing them.
- Search is `LIKE`-based for now; it can be swapped for SQLite FTS5 without
  changing `NoteStore.search_notes`'s signature.
