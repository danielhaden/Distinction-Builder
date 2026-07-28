"""Tests for the Laws of Form primitive calculus."""

from __future__ import annotations

import unittest

from laws_of_form import (
    MARKED,
    UNMARKED,
    Mark,
    Space,
    Text,
    is_marked,
    mark,
    note,
    space,
    value,
)


class ConstructionAndPrintingTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(str(MARKED), "()")
        self.assertEqual(str(UNMARKED), "")  # the void writes as nothing

    def test_nested_marks_notation(self):
        self.assertEqual(str(mark()), "()")
        self.assertEqual(str(mark(mark())), "(())")
        self.assertEqual(str(mark(mark(mark()))), "((()))")

    def test_juxtaposition_notation(self):
        self.assertEqual(str(space(mark(), mark())), "() ()")

    def test_mark_with_several_parts_juxtaposes_inside(self):
        self.assertEqual(str(mark(mark(), mark())), "(() ())")

    def test_note_is_a_form_holding_text(self):
        n = note("hello")
        self.assertIsInstance(n, Space)
        self.assertEqual(n.parts, (Text("hello"),))
        self.assertEqual(str(n), "hello")

    def test_note_can_hold_text_and_nested_forms(self):
        n = note("idea", mark())
        self.assertEqual(str(n), "idea ()")

    def test_forms_are_immutable_and_hashable(self):
        self.assertEqual(mark(mark()), mark(mark()))
        self.assertEqual(hash(mark(mark())), hash(mark(mark())))
        self.assertEqual(len({mark(), mark(), mark(mark())}), 2)
        with self.assertRaises(Exception):
            mark().within = UNMARKED  # frozen


class AxiomTests(unittest.TestCase):
    """The two initials: J1 (calling/number) and J2 (crossing/order)."""

    def test_j1_calling_two_marks_equal_one(self):
        # () () = ()
        self.assertTrue(is_marked(space(mark(), mark())))
        self.assertEqual(value(space(mark(), mark())), MARKED)

    def test_j2_crossing_made_again_cancels(self):
        # (()) = void
        self.assertFalse(is_marked(mark(mark())))
        self.assertEqual(value(mark(mark())), UNMARKED)

    def test_bare_mark_is_marked(self):
        self.assertEqual(value(mark()), MARKED)

    def test_empty_space_is_unmarked(self):
        self.assertEqual(value(space()), UNMARKED)

    def test_parity_of_nesting(self):
        # Odd depth -> marked, even depth -> unmarked.
        self.assertEqual(value(mark(mark(mark()))), MARKED)      # ((())) = ()
        self.assertEqual(value(mark(mark(mark(mark())))), UNMARKED)  # (((()))) =

    def test_marked_dominates_juxtaposition(self):
        # (() ()) : inner space is marked -> outer cross cancels it.
        self.assertEqual(value(mark(mark(), mark())), UNMARKED)

    def test_text_is_inert_but_preserved(self):
        # A note's words carry no value…
        self.assertEqual(value(note("anything")), UNMARKED)
        # …but drawing a distinction on the note marks it, text intact.
        marked_note = space(Text("anything"), mark())
        self.assertEqual(value(marked_note), MARKED)
        self.assertEqual(marked_note.parts[0], Text("anything"))


if __name__ == "__main__":
    unittest.main()
