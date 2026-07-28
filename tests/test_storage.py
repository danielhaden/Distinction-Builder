"""Tests for the Qt-free storage + link-resolution layer.

Run: ./.venv/bin/python -m pytest   (or plain: python -m unittest)
"""

from __future__ import annotations

import unittest

from distinction_builder.models import parse_wikilinks
from distinction_builder.storage import NoteStore


class ParseWikilinksTests(unittest.TestCase):
    def test_extracts_distinct_targets_in_order(self):
        body = "see [[Form]] and [[Void]], then [[Form]] again"
        self.assertEqual(parse_wikilinks(body), ["Form", "Void"])

    def test_strips_whitespace_and_ignores_empty(self):
        self.assertEqual(parse_wikilinks("[[  Marked  ]] [[]] [[   ]]"), ["Marked"])


class NoteStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = NoteStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_create_and_get(self):
        note = self.store.create_note("Form", "the first distinction")
        self.assertIsNotNone(note.id)
        fetched = self.store.get_note(note.id)
        self.assertEqual(fetched.title, "Form")

    def test_duplicate_title_rejected_case_insensitively(self):
        self.store.create_note("Form", "")
        with self.assertRaises(Exception):
            self.store.create_note("form", "")

    def test_links_resolve_and_backlink(self):
        a = self.store.create_note("A", "point to [[B]]")
        b = self.store.create_note("B", "")
        out = self.store.get_outgoing_links(a.id)
        self.assertEqual([l.target_id for l in out], [b.id])
        self.assertEqual([n.id for n in self.store.get_backlinks(b.id)], [a.id])

    def test_dangling_link_resolves_when_target_created_later(self):
        a = self.store.create_note("A", "point to [[Later]]")
        self.assertIsNone(self.store.get_outgoing_links(a.id)[0].target_id)
        later = self.store.create_note("Later", "")
        self.assertEqual(self.store.get_outgoing_links(a.id)[0].target_id, later.id)

    def test_delete_leaves_inbound_links_dangling(self):
        a = self.store.create_note("A", "point to [[B]]")
        b = self.store.create_note("B", "")
        self.store.delete_note(b.id)
        link = self.store.get_outgoing_links(a.id)[0]
        self.assertEqual(link.target_title, "B")
        self.assertIsNone(link.target_id)

    def test_rename_repoints_links(self):
        a = self.store.create_note("A", "point to [[Target]]")
        b = self.store.create_note("B", "the target")
        self.assertIsNone(self.store.get_outgoing_links(a.id)[0].target_id)
        # Rename B to the title A references -> link should resolve to B.
        self.store.update_note(b.id, "Target", "the target")
        self.assertEqual(self.store.get_outgoing_links(a.id)[0].target_id, b.id)

    def test_search_matches_title_and_body(self):
        self.store.create_note("Form", "distinction")
        self.store.create_note("Other", "mentions form here")
        titles = {n.title for n in self.store.search_notes("form")}
        self.assertEqual(titles, {"Form", "Other"})
        self.assertEqual(len(self.store.search_notes("")), 2)


if __name__ == "__main__":
    unittest.main()
