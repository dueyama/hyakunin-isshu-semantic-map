#!/usr/bin/env python3
"""Offline safety checks for the bounded public explanation exporter."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from compare_luna_reasoned import bounded_public_explanation
from normalize_waka import normalize_text


class PublicExplanationTests(unittest.TestCase):
    def setUp(self):
        guard = patch("urllib.request.urlopen", side_effect=AssertionError("No network in offline tests"))
        guard.start()
        self.addCleanup(guard.stop)
        self.poem = "春の野の花を眺めて山の向こうへ歩いて帰る"
        self.other_poem = "冬の朝には白い雪が遠くの森と川を覆っている"
        self.forms = {normalize_text(self.poem), normalize_text(self.other_poem)}

    def test_short_explanation_and_exact_evidence_are_preserved(self):
        answer = {"season": "spring", "evidence": ["春の野", "花"],
                  "explanation": "春の野と花の描写から、春を選んだ。"}
        original = copy.deepcopy(answer)
        result = bounded_public_explanation(answer, self.poem, self.forms)
        self.assertEqual(answer, original)
        self.assertEqual(result["evidence"], ["春の野", "花"])
        self.assertEqual(result["evidence_matches"], [True, True])
        self.assertEqual(result["explanation"], answer["explanation"])
        self.assertFalse(result["explanation_withheld"])
        self.assertEqual(set(result), {"evidence", "evidence_matches", "explanation", "explanation_withheld"})

    def test_nonverbatim_evidence_is_flagged_without_silent_repair(self):
        answer = {"season": "spring", "evidence": ["春の野", "桜花"],
                  "explanation": "花の描写から春を選んだ。"}
        result = bounded_public_explanation(answer, self.poem, self.forms)
        self.assertEqual(result["evidence"], answer["evidence"])
        self.assertEqual(result["evidence_matches"], [True, False])
        self.assertFalse(result["explanation_withheld"])

    def test_empty_evidence_does_not_invent_a_mismatch(self):
        answer = {"season": "unspecified", "evidence": [],
                  "explanation": "季節を特定する手がかりを選べなかった。"}
        result = bounded_public_explanation(answer, self.poem, self.forms)
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["evidence_matches"], [])
        self.assertFalse(result["explanation_withheld"])

    def test_complete_poem_with_added_spaces_and_punctuation_is_withheld(self):
        quoted = "「" + "、 ".join(self.poem) + "」"
        answer = {"season": "spring", "evidence": ["春の野"],
                  "explanation": quoted + "と書かれている。"}
        result = bounded_public_explanation(answer, self.poem, self.forms)
        self.assertTrue(result["explanation_withheld"])
        self.assertEqual(result["explanation"], "")
        self.assertEqual(result["evidence"], ["春の野"])

    def test_full_poem_split_between_explanation_and_evidence_is_withheld(self):
        answer = {"season": "spring", "evidence": [self.poem[-6:]],
                  "explanation": self.poem[:-6]}
        result = bounded_public_explanation(answer, self.poem, self.forms)
        self.assertTrue(result["explanation_withheld"])
        self.assertEqual(result["explanation"], "")

    def test_complete_different_input_poem_is_also_withheld(self):
        answer = {"season": "spring", "evidence": [], "explanation": self.other_poem}
        result = bounded_public_explanation(answer, self.poem, self.forms)
        self.assertTrue(result["explanation_withheld"])
        self.assertEqual(result["explanation"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
