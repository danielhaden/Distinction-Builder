"""Headless tests for the form canvas: creation, text, nesting, and the
mapping from boxes to the Laws of Form tree.

Runs offscreen (QT_QPA_PLATFORM=offscreen is set in setUpModule).
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from distinction_builder.canvas import FormCanvas, FormItem  # noqa: E402
from laws_of_form import Mark, Space, Text  # noqa: E402

_app: QApplication | None = None


def setUpModule() -> None:
    global _app
    _app = QApplication.instance() or QApplication([])


class CanvasTests(unittest.TestCase):
    def setUp(self):
        self.canvas = FormCanvas()

    def test_create_form_on_canvas(self):
        item = self.canvas.add_form(QPointF(0, 0), text="hello")
        self.assertIn(item, self.canvas.top_level_forms())
        self.assertEqual(item._text, "hello")

    def test_box_grows_to_fit_child_when_nested(self):
        parent = self.canvas.add_form(QPointF(0, 0), text="outer")
        child = self.canvas.add_form(QPointF(500, 500), text="inner")
        parent_h_before = parent._h
        child._reparent_into(parent)
        self.assertIs(child.parentItem(), parent)
        self.assertGreater(parent._h, parent_h_before)  # grew to contain child
        self.assertNotIn(child, self.canvas.top_level_forms())

    def test_detach_returns_child_to_top_level(self):
        parent = self.canvas.add_form(QPointF(0, 0), text="outer")
        child = self.canvas.add_form(QPointF(500, 500), text="inner")
        child._reparent_into(parent)
        child._detach_to_top()
        self.assertIsNone(child.parentItem())
        self.assertIn(child, self.canvas.top_level_forms())

    def test_cannot_nest_into_own_descendant(self):
        outer = self.canvas.add_form(QPointF(0, 0), text="a")
        inner = self.canvas.add_form(QPointF(0, 0), text="b")
        inner._reparent_into(outer)
        # outer is an ancestor of inner, so inner must not accept outer.
        self.assertTrue(inner._is_ancestor_of.__self__ is inner)
        self.assertTrue(inner._is_ancestor_of(outer) is False)
        self.assertTrue(outer._is_ancestor_of(inner))

    def test_edit_text_commits(self):
        item = self.canvas.add_form(QPointF(0, 0), text="old")
        item.begin_edit()
        self.assertIsNotNone(item._editor)
        item._editor[1].setText("new text")
        item._commit_edit()
        self.assertIsNone(item._editor)
        self.assertEqual(item._text, "new text")


class ToFormBridgeTests(unittest.TestCase):
    def setUp(self):
        self.canvas = FormCanvas()

    def test_empty_box_is_the_bare_cross(self):
        item = self.canvas.add_form(QPointF(0, 0), text="")
        self.assertEqual(item.to_form(), Mark(Space(())))
        self.assertEqual(str(item.to_form()), "()")

    def test_text_box_is_marked_text(self):
        item = self.canvas.add_form(QPointF(0, 0), text="idea")
        self.assertEqual(item.to_form(), Mark(Space((Text("idea"),))))
        self.assertEqual(str(item.to_form()), "(idea)")

    def test_nesting_maps_to_containment(self):
        parent = self.canvas.add_form(QPointF(0, 0), text="outer")
        child = self.canvas.add_form(QPointF(0, 100), text="inner")
        child._reparent_into(parent)
        expected = Mark(Space((Text("outer"), Mark(Space((Text("inner"),))))))
        self.assertEqual(parent.to_form(), expected)
        self.assertEqual(str(parent.to_form()), "(outer (inner))")

    def test_canvas_is_space_of_top_forms(self):
        self.canvas.add_form(QPointF(0, 0), text="a")
        self.canvas.add_form(QPointF(0, 200), text="b")
        form = self.canvas.to_form()
        self.assertIsInstance(form, Space)
        self.assertEqual(len(form.parts), 2)


if __name__ == "__main__":
    unittest.main()
