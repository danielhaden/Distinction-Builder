"""Plain-data types shared across the app.

Kept deliberately free of Qt and SQLite so the domain model can be reasoned
about (and later reused for analysis) without dragging in the GUI or storage
layers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A wikilink: [[Some Note Title]]. The captured group is the target title,
# stripped of surrounding whitespace by the parser below.
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


@dataclass(slots=True)
class Note:
    """A single note.

    `id` is ``None`` until the note has been persisted. `title` doubles as the
    link target — a wikilink ``[[Foo]]`` resolves to the note titled ``Foo``.
    """

    id: int | None
    title: str
    body: str
    created_at: str = ""
    updated_at: str = ""

    @property
    def links(self) -> list[str]:
        """The distinct wikilink targets referenced in this note's body."""
        return parse_wikilinks(self.body)


@dataclass(slots=True)
class Link:
    """A resolved (or dangling) reference from one note to a title.

    `target_id` is ``None`` when no note with `target_title` exists yet — a
    dangling link, which the UI surfaces so the user can create the missing
    note.
    """

    source_id: int
    target_title: str
    target_id: int | None = None


def parse_wikilinks(body: str) -> list[str]:
    """Return the distinct ``[[wikilink]]`` targets in `body`, in first-seen order.

    Matching is case-preserving here; callers that resolve links against stored
    notes should compare titles case-insensitively.
    """
    seen: dict[str, None] = {}
    for match in WIKILINK_RE.finditer(body):
        title = match.group(1).strip()
        if title:
            seen.setdefault(title, None)
    return list(seen.keys())
