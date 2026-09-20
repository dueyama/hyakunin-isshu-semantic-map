#!/usr/bin/env python3
"""Offline checks for the GPT comparison request, response, and private cache.

Run with: python3 scripts/test_gpt_seasons.py
Uses synthetic texts and responses. The network is replaced in every test.
"""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gpt_seasons as gpt
from jev_seasons import LABELS, QUESTIONS, encoded, payload_for as jev_payload_for


def poem_fixture():
    return {
        "id": "H999", "text": "春の花\nはるのはな", "order": 999,
        "source_row": {"poet_jp": "PRIVATE_AUTHOR", "season": "PRIVATE_TAG"},
    }


def response_fixture():
    return {
        "model": gpt.MODEL, "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": '{"season":"spring"}'}]},
        ],
        "usage": {"input_tokens": 25, "output_tokens": 10, "total_tokens": 35},
    }


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        guard = patch(
            "gpt_seasons.urllib.request.urlopen",
            side_effect=AssertionError("Offline tests must not contact an API"),
        )
        self.urlopen = guard.start()
        self.addCleanup(guard.stop)


class RequestTests(OfflineTestCase):
    def test_same_principal_question_and_text_without_source_labels_or_key(self):
        poem = poem_fixture()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "OFFLINE_SECRET"}):
            payload = gpt.payload_for(poem)
        jev = jev_payload_for(poem)
        self.assertEqual(json.loads(payload["input"]), jev["state"])
        self.assertEqual(
            payload["instructions"],
            jev["questions"]["season"]["instructions"]
            + "\nCriteria:\n" + encoded(jev["questions"]["season"]["criteria"]),
        )
        self.assertEqual(payload["reasoning"], {"effort": "medium"})
        self.assertIs(payload["store"], False)
        output_format = payload["text"]["format"]
        self.assertTrue(output_format["strict"])
        schema = output_format["schema"]
        self.assertEqual(set(schema["properties"]), {"season"})
        self.assertEqual(set(schema["properties"]["season"]["enum"]), set(LABELS))
        self.assertEqual(schema["required"], ["season"])
        self.assertFalse(schema["additionalProperties"])
        serialized = encoded(payload)
        for excluded in ("H999", "PRIVATE_AUTHOR", "PRIVATE_TAG", "OFFLINE_SECRET"):
            self.assertNotIn(excluded, serialized)

    def test_cache_identity_tracks_model_question_and_text_not_poem_id(self):
        poem = poem_fixture()
        baseline = gpt.cache_path(poem)
        self.assertEqual(baseline, gpt.cache_path({**poem, "id": "S999"}))
        self.assertNotEqual(baseline, gpt.cache_path({**poem, "text": "秋の月"}))
        with patch.object(gpt, "MODEL", "different-model"):
            self.assertNotEqual(baseline, gpt.cache_path(poem))
        changed_questions = copy.deepcopy(QUESTIONS)
        changed_questions["season"]["instructions"] += " Changed definition."
        with patch.object(gpt, "QUESTIONS", changed_questions):
            self.assertNotEqual(baseline, gpt.cache_path(poem))


class ResponseTests(OfflineTestCase):
    def test_reasoning_item_is_allowed_and_only_season_is_returned(self):
        self.assertEqual(gpt.validate_response(response_fixture()), {"season": "spring"})

    def test_incomplete_refusal_and_extra_assistant_message_are_rejected(self):
        incomplete = response_fixture()
        incomplete["status"] = "incomplete"
        refusal = response_fixture()
        refusal["output"][1]["content"] = [{"type": "refusal", "refusal": "Synthetic refusal"}]
        duplicate = response_fixture()
        duplicate["output"].append(copy.deepcopy(duplicate["output"][1]))
        for response in (incomplete, refusal, duplicate):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    gpt.validate_response(response)

    def test_wrong_model_and_invalid_token_counts_are_rejected(self):
        bad_model = response_fixture()
        bad_model["model"] = "different-model"
        bad_usage = response_fixture()
        bad_usage["usage"]["output_tokens"] = True
        for response in (bad_model, bad_usage):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    gpt.validate_response(response)

    def test_unknown_label_extra_fields_and_non_json_text_are_rejected(self):
        for text in ('{"season":"unknown"}', '{"season":"spring","explanation":"extra"}',
                     '{}', 'spring'):
            with self.subTest(text=text):
                response = response_fixture()
                response["output"][1]["content"][0]["text"] = text
                with self.assertRaises(ValueError):
                    gpt.validate_response(response)


class CacheTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="test-gpt-seasons-")
        self.addCleanup(temporary.cleanup)
        location = patch.object(gpt, "RUN", Path(temporary.name))
        location.start()
        self.addCleanup(location.stop)

    def mock_response(self, response):
        self.urlopen.side_effect = None
        self.urlopen.return_value = io.BytesIO(encoded(response).encode())

    def test_success_is_saved_without_key_and_then_reused_without_request(self):
        self.mock_response(response_fixture())
        poem = poem_fixture()
        entry = gpt.request_poem(poem, "OFFLINE_SECRET")
        self.assertEqual(gpt.load_result(poem), entry)
        self.assertEqual(len(list((gpt.RUN / "attempts").glob("*.json"))), 1)
        for path in gpt.RUN.rglob("*.json"):
            self.assertNotIn("OFFLINE_SECRET", path.read_text())
        self.urlopen.side_effect = AssertionError("A cache hit must not make a request")
        self.assertEqual(gpt.request_poem(poem, "OFFLINE_SECRET"), entry)
        self.assertEqual(self.urlopen.call_count, 1)

    def test_invalid_response_is_preserved_but_never_cached_as_success(self):
        response = response_fixture()
        response["status"] = "incomplete"
        self.mock_response(response)
        poem = poem_fixture()
        with self.assertRaises(ValueError):
            gpt.request_poem(poem, "OFFLINE_SECRET")
        attempts = list((gpt.RUN / "attempts").glob("*.json"))
        self.assertEqual(len(attempts), 1)
        self.assertEqual(json.loads(attempts[0].read_text())["response"], response)
        self.assertFalse(gpt.cache_path(poem).exists())

    def test_cache_payload_mismatch_is_rejected(self):
        poem = poem_fixture()
        path = gpt.cache_path(poem)
        path.parent.mkdir(parents=True)
        entry = {"request": gpt.payload_for({**poem, "text": "different text"}),
                 "response": response_fixture()}
        path.write_text(encoded(entry))
        with self.assertRaises(ValueError):
            gpt.load_result(poem)


if __name__ == "__main__":
    unittest.main(verbosity=2)
