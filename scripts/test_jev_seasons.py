#!/usr/bin/env python3
"""Offline regression checks for Jev validation, alignment, and neighbor tests.

Run with: python3 scripts/test_jev_seasons.py
Requires numpy. All fixtures are synthetic; no private data or API key is used.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

import numpy as np

from compare_jev_seasons import align_embeddings, neighbor_statistics
from jev_seasons import LABELS, MODEL, QUESTIONS, digest, validate_response
from normalize_waka import build_embedding_text


def response_fixture() -> dict:
    probabilities = {label: 0.0 for label in LABELS}
    probabilities.update(autumn=0.7, unspecified=0.3)
    answers = {
        name: {"type": "noul", "noul": 0.5}
        for name, question in QUESTIONS.items()
        if question["type"] == "noul"
    }
    answers["season"] = {
        "type": "choice", "choice": "autumn", "confidence": 0.6,
        "probabilities": probabilities,
    }
    return {
        "model": MODEL, "answers": answers,
        "usage": {"input_tokens": 20, "output_tokens": 10},
    }


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        network_guard = patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("Offline tests must not contact an API"),
        )
        network_guard.start()
        self.addCleanup(network_guard.stop)


class ResponseValidationTests(OfflineTestCase):
    def test_valid_typed_response(self):
        validate_response(response_fixture())

    def test_invalid_choice_probabilities_are_rejected(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1, True, "0.7"):
            with self.subTest(value=value):
                response = response_fixture()
                response["answers"]["season"]["probabilities"]["autumn"] = value
                with self.assertRaises(ValueError):
                    validate_response(response)

    def test_missing_extra_and_unnormalized_choices_are_rejected(self):
        baseline = response_fixture()["answers"]["season"]["probabilities"]
        missing = {key: value for key, value in baseline.items() if key != "winter"}
        extra = {**baseline, "not_a_season": 0.0}
        unnormalized = {**baseline, "autumn": 0.8}
        for probabilities in (missing, extra, unnormalized):
            with self.subTest(probabilities=probabilities):
                response = response_fixture()
                response["answers"]["season"]["probabilities"] = probabilities
                with self.assertRaises(ValueError):
                    validate_response(response)

    def test_unknown_or_nonmaximum_choice_is_rejected(self):
        for choice in ("not_a_season", "unspecified"):
            with self.subTest(choice=choice):
                response = response_fixture()
                response["answers"]["season"]["choice"] = choice
                with self.assertRaises(ValueError):
                    validate_response(response)

    def test_invalid_noul_and_confidence_are_rejected(self):
        for field, value in (("noul", float("nan")), ("noul", True),
                             ("confidence", -0.1), ("confidence", float("inf"))):
            with self.subTest(field=field, value=value):
                response = response_fixture()
                question = "love" if field == "noul" else "season"
                response["answers"][question][field] = value
                with self.assertRaises(ValueError):
                    validate_response(response)


class EmbeddingAlignmentTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.poems = [
            {"order": number, "source_row": {"waka_original": text}}
            for number, text in ((1, "春の花"), (2, "夏の海"), (3, "秋の月"))
        ]
        self.records = [
            {"id": f"H{poem['order']:03d}",
             "embedding": vector,
             "text_sha256": digest(build_embedding_text(poem["source_row"], "original"))}
            for poem, vector in zip(self.poems, [[1, 0], [0, 1], [-1, 0]])
        ]

    def test_reordered_records_align_by_id_and_flag_stale_text(self):
        records = copy.deepcopy(self.records)
        records[1]["text_sha256"] = digest("previous wording")
        matrix, valid = align_embeddings(
            self.poems, {"records": [records[2], records[0], records[1]]}, "original",
        )
        np.testing.assert_array_equal(matrix, [[1, 0], [0, 1], [-1, 0]])
        np.testing.assert_array_equal(valid, [True, False, True])

    def test_duplicate_or_missing_ids_are_rejected(self):
        for records in (self.records[:2],
                        [self.records[0], self.records[0], self.records[2]]):
            with self.subTest(ids=[record["id"] for record in records]):
                with self.assertRaises(ValueError):
                    align_embeddings(self.poems, {"records": records}, "original")


class NeighborStatisticsTests(OfflineTestCase):
    def test_separated_groups_have_perfect_k5_with_count_preserving_null(self):
        # Six poems in each group: every poem has exactly five same-group peers.
        vectors = [[1.0, 0.0]] * 6 + [[-1.0, 0.0]] * 6
        labels = ["spring"] * 6 + ["autumn"] * 6
        result = neighbor_statistics(vectors, labels, trials=10000, seed=7)
        self.assertEqual(result["same_label_neighbor_rate"], 1.0)
        self.assertEqual(result["counts"], {"spring": 6, "autumn": 6})
        # Without replacement, a poem has five matching labels among eleven peers.
        self.assertAlmostEqual(result["random_expectation"], 5 / 11)
        self.assertAlmostEqual(result["null_mean"], 5 / 11, delta=0.01)
        self.assertLess(result["permutation_p_one_sided"], 0.01)
        self.assertGreater(result["permutation_p_one_sided"], 0.0)

    def test_self_is_excluded_and_permutations_keep_imbalanced_counts(self):
        # All five other poems must be neighbors, regardless of cosine ties.
        # The singleton has zero matching peers; the other five each have four.
        result = neighbor_statistics(
            np.eye(6), ["spring"] * 5 + ["winter"], trials=100, seed=19,
        )
        self.assertAlmostEqual(result["same_label_neighbor_rate"], 20 / 30)
        self.assertAlmostEqual(result["random_expectation"], 20 / 30)
        self.assertAlmostEqual(result["null_mean"], 20 / 30)
        np.testing.assert_allclose(result["null_95_percent_interval"], [20 / 30, 20 / 30])
        self.assertEqual(result["permutation_p_one_sided"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
