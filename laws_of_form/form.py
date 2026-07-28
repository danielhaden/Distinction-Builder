"""The immutable expression tree for G. Spencer-Brown's *Laws of Form*.

Everything is a :class:`Form`. There are three constructors:

* :class:`Mark` — a single **distinction**, the *cross* ``()``, drawn around a
  form. Marking is the one primitive act of the calculus.
* :class:`Space` — a **juxtaposition** of forms sitting side by side (the
  content of a distinction, or a whole arrangement). The *empty* space is the
  unmarked state — the void.
* :class:`Text` — inert textual **content**. This is what makes a *note* a form:
  a note is simply the simplest content-bearing form, a form that holds a body
  of text. Text carries no arithmetic value of its own; it is preserved through
  the structure so notes and the calculus share one tree.

Forms nest freely — a :class:`Mark` holds a form, a :class:`Space` holds many —
so "a form may hold other forms, or be held by other forms" is just the tree.

The types are frozen dataclasses: immutable, structurally comparable, and
hashable, which keeps the calculus (see :mod:`laws_of_form.calculus`) pure and
easy to test. Construction is *literal* — nothing is auto-simplified here; that
is the calculus's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Form:
    """Abstract base for every node in the expression tree.

    Subclasses are immutable. Shared behaviour here is purely *structural*
    (rendering, traversal); the two axioms live in
    :mod:`laws_of_form.calculus` to keep arithmetic separate from shape.
    """

    __slots__ = ()

    def to_notation(self) -> str:
        """Render this form in cross notation (``()`` for a mark).

        The unmarked state (empty space) renders as the empty string, faithful
        to the notation where "nothing" is written as nothing.
        """
        raise NotImplementedError

    def children(self) -> tuple["Form", ...]:
        """The immediate sub-forms, for traversal. Leaves return ``()``."""
        return ()

    def __str__(self) -> str:  # pragma: no cover - thin wrapper
        return self.to_notation()


@dataclass(frozen=True, slots=True)
class Space(Form):
    """A juxtaposition of forms. The empty space is the unmarked state."""

    parts: tuple[Form, ...] = ()

    def to_notation(self) -> str:
        return " ".join(p.to_notation() for p in self.parts)

    def children(self) -> tuple[Form, ...]:
        return self.parts


@dataclass(frozen=True, slots=True)
class Mark(Form):
    """A single distinction: the cross ``()`` drawn around ``within``.

    With no argument this is the bare mark ``()`` — the marked state — since
    ``within`` defaults to the empty space.
    """

    within: Form = field(default_factory=lambda: Space(()))

    def to_notation(self) -> str:
        return f"({self.within.to_notation()})"

    def children(self) -> tuple[Form, ...]:
        return (self.within,)


@dataclass(frozen=True, slots=True)
class Text(Form):
    """Inert content — a body of text. The seed of a note as a form.

    Text has no arithmetic value (it reduces as the unmarked state) but is
    carried through the tree unchanged so a note's words survive alongside the
    distinctions drawn on them.
    """

    content: str

    def to_notation(self) -> str:
        return self.content


# -- the two constants of the calculus --------------------------------------

#: The unmarked state — the void. Nothing has been distinguished.
UNMARKED: Space = Space(())

#: The marked state — a single distinction, ``()``.
MARKED: Mark = Mark(UNMARKED)


# -- ergonomic constructors --------------------------------------------------


def space(*parts: Form) -> Space:
    """A space juxtaposing ``parts`` (no args → the unmarked state)."""
    return Space(tuple(parts))


def mark(*within: Form) -> Mark:
    """A distinction drawn around ``within``.

    ``mark()`` is the bare cross ``()``; ``mark(mark())`` is ``(())``; several
    arguments are juxtaposed inside the cross: ``mark(a, b)`` → ``(a b)``.
    """
    if not within:
        return Mark(UNMARKED)
    if len(within) == 1:
        return Mark(within[0])
    return Mark(Space(tuple(within)))


def note(text: str, *within: Form) -> Space:
    """The simplest content-bearing form: a body of text, optionally holding
    nested forms beside it.

    ``note("hello")`` is a form whose content is the text ``hello``;
    ``note("hello", mark())`` holds that text *and* a distinction. This is the
    bridge between the notes app and the calculus — a note is a form.
    """
    return Space((Text(text), *within))
