"""Laws of Form — the primitive calculus, as an immutable expression tree.

A pure, Qt-free library implementing the foundation of G. Spencer-Brown's
*Laws of Form*: the distinction (:class:`Mark`), juxtaposition (:class:`Space`),
inert content (:class:`Text`), and the two axioms that reduce any constant form
to the marked or unmarked state (:func:`value` / :func:`reduce`).

A **note is a form** — the simplest content-bearing one (see :func:`note`) —
so the notes app and the calculus share a single tree.

    >>> from laws_of_form import mark, value
    >>> str(mark(mark()))          # (()) — a crossing made again…
    '(())'
    >>> str(value(mark(mark())))   # …cancels to the void (J2)
    ''
"""

from .calculus import is_marked, reduce, value
from .form import (
    MARKED,
    UNMARKED,
    Form,
    Mark,
    Space,
    Text,
    mark,
    note,
    space,
)

__all__ = [
    "Form",
    "Mark",
    "Space",
    "Text",
    "MARKED",
    "UNMARKED",
    "mark",
    "space",
    "note",
    "value",
    "reduce",
    "is_marked",
]
