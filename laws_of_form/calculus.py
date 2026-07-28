"""The calculus of indications — the two axioms — over the expression tree.

Spencer-Brown's primitive arithmetic rests on two initials:

* **J1, the law of Calling** — *the value of a call made again is the value of
  the call*: ``() () = ()``. Repeating a mark adds nothing.
* **J2, the law of Crossing** — *the value of a crossing made again is not the
  value of the crossing*: ``(()) =`` (the void). Crossing back cancels.

From these, every form built only from marks and spaces (no variables) reduces
to one of two values: the **marked** state ``()`` or the **unmarked** state (the
void). :func:`value` computes that value; :func:`reduce` returns it as a
:class:`~laws_of_form.form.Form`.

The reduction is a bottom-up walk:

* A :class:`Mark` **flips** the value of its content — an expression of J2. A
  mark around the unmarked state is marked (``()``); a mark around the marked
  state cancels to unmarked (``(()) =``).
* A :class:`Space` is **marked iff any part is marked**, else unmarked — an
  expression of J1 together with the fact that the marked state dominates
  juxtaposition (``() () = ()``, and the empty space is unmarked).
* :class:`Text` is inert and reduces as the unmarked state; its value does not
  affect the arithmetic, though the original text is untouched in the tree.
"""

from __future__ import annotations

from .form import MARKED, UNMARKED, Form, Mark, Space, Text


def is_marked(form: Form) -> bool:
    """Whether ``form`` reduces to the marked state under J1 and J2."""
    if isinstance(form, Mark):
        # J2: a crossing flips the value of what it crosses.
        return not is_marked(form.within)
    if isinstance(form, Space):
        # J1 + dominance: marked if any juxtaposed part is marked.
        return any(is_marked(part) for part in form.parts)
    if isinstance(form, Text):
        # Inert content: the unmarked state until a distinction is drawn.
        return False
    raise TypeError(f"not a Form: {form!r}")


def value(form: Form) -> Mark | Space:
    """Reduce ``form`` to its constant value: :data:`MARKED` or :data:`UNMARKED`."""
    return MARKED if is_marked(form) else UNMARKED


#: Alias — reading a form *down* to its value is "reducing" it.
reduce = value
