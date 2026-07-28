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
laws_of_form/                 — pure calculus library (Qt-free)
  form.py                     — immutable expression tree (Mark / Space / Text)
  calculus.py                 — the two axioms; reduce a form to marked/unmarked
tests/
  test_storage.py             — storage + link-resolution tests
  test_laws_of_form.py        — construction, printing, and the two axioms
```

## Laws of Form

The longer-term aim runs on a small, pure calculus in `laws_of_form/`. Everything
is a `Form`, built from three constructors:

- **`Mark`** — a single *distinction*, the cross `()`, drawn around a form. The
  one primitive act.
- **`Space`** — a *juxtaposition* of forms side by side. The empty space is the
  unmarked state (the void).
- **`Text`** — inert content. This is what makes **a note a form**: a note is the
  simplest content-bearing form, a form that holds a body of text. Forms nest, so
  a note may hold other forms or be held by them.

Two axioms reduce any constant form to the **marked** `()` or **unmarked** (void)
state:

- **J1 (Calling / number)** — `() () = ()`. A mark repeated adds nothing.
- **J2 (Crossing / order)** — `(()) =`. A crossing made again cancels.

```python
from laws_of_form import mark, note, value

str(value(mark(mark())))        # '' — (()) cancels to the void (J2)
str(value(mark(mark(mark()))))  # '()' — odd nesting is marked
value(note("a thought"))        # UNMARKED — text is inert until distinguished
```

`laws_of_form` is deliberately Qt-free and standalone; wiring the app's `Note`
onto `Form` is the next integration step.

The domain (`models.py`) and storage (`storage.py`) layers are Qt-free so they
can be reused for analysis work later without the GUI.

## Notes on design

- **Titles are the link target**, so they're unique (case-insensitive).
  Renaming a note re-points links that name the new title and detaches ones
  that named the old.
- Deleting a note leaves inbound links **dangling** rather than erasing them.
- Search is `LIKE`-based for now; it can be swapped for SQLite FTS5 without
  changing `NoteStore.search_notes`'s signature.
