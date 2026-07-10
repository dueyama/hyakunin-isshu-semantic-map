#!/usr/bin/env python3
"""Shared random-placement helpers for the 10x10 analyses."""

from __future__ import annotations

import random
import statistics
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only on minimal Python installs
    np = None


def random_layout_permutations(size: int, trials: int, seed: int) -> Any:
    """Return reproducible uniform permutations of ``range(size)``."""
    rng = random.Random(seed)
    order = list(range(size))
    if np is not None:
        permutations = np.empty((trials, size), dtype=np.int16)
        for trial in range(trials):
            rng.shuffle(order)
            permutations[trial] = order
        return permutations

    permutations: list[list[int]] = []
    for _ in range(trials):
        rng.shuffle(order)
        permutations.append(order[:])
    return permutations


def random_layout_samples(
    sim: list[list[float]],
    edges: list[tuple[int, int]],
    permutations: Any,
) -> list[float]:
    """Measure edge means after assigning poems randomly to fixed grid cells."""
    if np is not None and isinstance(permutations, np.ndarray):
        matrix = np.asarray(sim, dtype=float)
        left_positions = np.fromiter((left for left, _ in edges), dtype=np.int16)
        right_positions = np.fromiter((right for _, right in edges), dtype=np.int16)
        left = permutations[:, left_positions]
        right = permutations[:, right_positions]
        return matrix[left, right].mean(axis=1).tolist()

    values: list[float] = []
    for order in permutations:
        values.append(statistics.fmean(sim[order[left]][order[right]] for left, right in edges))
    return values
