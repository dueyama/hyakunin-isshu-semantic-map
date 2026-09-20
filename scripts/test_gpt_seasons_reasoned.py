#!/usr/bin/env python3
"""Offline checks specific to the separate Luna explanation condition.

Run with: python3 scripts/test_gpt_seasons_reasoned.py
Fixtures are synthetic; no private corpus or API credentials are required.
"""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import gpt_seasons as baseline
import gpt_seasons_reasoned as reasoned
from jev_seasons import digest


def poem_fixture():
    return {
        "id": "H999", "text": "春の野に咲く花を見て帰る道\nはるののにさくはなをみてかへるみち",
        "source_row": {"poet_jp": "PRIVATE_AUTHOR", "season": "PRIVATE_LABEL"},
    }


def response_fixture():
    answer = {"season": "spring", "evidence": ["春の野", "咲く花"],
              "explanation": "春の野の花を描いているため、主な季節を春とした。"}
    return {
        "model": reasoned.MODEL, "status": "completed",
        "output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": json.dumps(answer, ensure_ascii=False)}]}],
        "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
    }


def replace_answer(response, **changes):
    answer = json.loads(response["output"][0]["content"][0]["text"])
    answer.update(changes)
    response["output"][0]["content"][0]["text"] = json.dumps(answer, ensure_ascii=False)
    return response


class ExplanationConditionTests(unittest.TestCase):
    def setUp(self):
        guard = patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("Offline tests must not contact an API"),
        )
        guard.start()
        self.addCleanup(guard.stop)

    def test_base_request_is_preserved_except_explanation_instruction_and_schema(self):
        poem = poem_fixture()
        base = baseline.payload_for(poem)
        snapshot = copy.deepcopy(base)
        request = reasoned.payload_for(poem)
        self.assertEqual(base, snapshot)
        self.assertEqual(baseline.payload_for(poem), snapshot)
        self.assertEqual(request["instructions"], base["instructions"] + "\n\n"
                         + reasoned.EXPLANATION_INSTRUCTIONS)
        for key in base:
            if key not in ("instructions", "text"):
                self.assertEqual(request[key], base[key], key)
        self.assertEqual(json.loads(request["input"]), {"text": poem["text"]})
        wire = reasoned.wire_payload(request)
        for excluded in ("H999", "PRIVATE_AUTHOR", "PRIVATE_LABEL", "Authorization"):
            self.assertNotIn(excluded, wire)

    def test_schema_emits_season_before_evidence_and_explanation(self):
        payload = reasoned.payload_for(poem_fixture())
        wire = reasoned.wire_payload(payload)
        schema = json.loads(wire)["text"]["format"]["schema"]
        self.assertEqual(list(schema["properties"]), ["season", "evidence", "explanation"])
        self.assertEqual(schema["required"], ["season", "evidence", "explanation"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["evidence"]["maxItems"], 2)

    def test_cache_is_separate_and_tracks_the_serialized_property_order(self):
        poem = poem_fixture()
        current = reasoned.cache_path(poem)
        self.assertNotEqual(current.parent, baseline.cache_path(poem).parent)
        payload = reasoned.payload_for(poem)
        self.assertEqual(current.name, digest(reasoned.wire_payload(payload)) + ".json")
        reordered = copy.deepcopy(payload)
        properties = reordered["text"]["format"]["schema"]["properties"]
        reordered["text"]["format"]["schema"]["properties"] = dict(reversed(list(properties.items())))
        with patch.object(reasoned, "payload_for", return_value=reordered):
            self.assertNotEqual(reasoned.cache_path(poem), current)

    def test_valid_evidence_and_empty_evidence_are_accepted(self):
        answer = reasoned.validate_response(response_fixture())
        self.assertEqual(answer["season"], "spring")
        self.assertEqual(answer["evidence"], ["春の野", "咲く花"])
        empty = replace_answer(response_fixture(), season="unspecified", evidence=[],
                               explanation="主な季節を確定できる描写がない。")
        self.assertEqual(reasoned.validate_response(empty)["evidence"], [])

    def test_evidence_format_limits_are_enforced(self):
        for evidence in (["春", "花", "野"], ["あ" * 9], [""], [" "], ["春\n野"],
                         [123], "春"):
            with self.subTest(evidence=evidence):
                with self.assertRaises(ValueError):
                    reasoned.validate_response(replace_answer(response_fixture(), evidence=evidence))
        boundary = replace_answer(response_fixture(), evidence=["あ" * 8, "い" * 8])
        self.assertEqual(sum(map(len, reasoned.validate_response(boundary)["evidence"])), 16)

    def test_explanation_format_limits_are_enforced(self):
        for explanation in ("", " ", "あ" * 181, "春。\n花がある。", 123):
            with self.subTest(explanation=explanation):
                with self.assertRaises(ValueError):
                    reasoned.validate_response(replace_answer(response_fixture(), explanation=explanation))
        boundary = replace_answer(response_fixture(), explanation="あ" * 180)
        self.assertEqual(len(reasoned.validate_response(boundary)["explanation"]), 180)

    def test_structurally_valid_nonverbatim_evidence_remains_for_later_review(self):
        # Exact-span checking is a later analysis/publication check, not a reason
        # to discard this season label and solicit a replacement model response.
        response = replace_answer(response_fixture(), evidence=["落葉"])
        answer = reasoned.validate_response(response)
        self.assertNotIn(answer["evidence"][0], poem_fixture()["text"])
        self.assertEqual(answer["season"], "spring")


if __name__ == "__main__":
    unittest.main(verbosity=2)
