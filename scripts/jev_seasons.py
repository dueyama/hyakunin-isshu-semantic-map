#!/usr/bin/env python3
"""Private, resumable Jev judgments; no API requests unless --execute is given."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from normalize_waka import build_embedding_text

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "_private/experiments/jev_seasons_v1"
MODEL = "jev-1.13.0"
SEASONS = ["spring", "summer", "autumn", "winter"]
LABELS = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬",
          "mixed": "複数季節", "unspecified": "季節不特定", "uncertain": "判定困難"}
QUESTIONS = {
    "season": {
        "type": "choice",
        "instructions": (
            "Read the classical Japanese waka in `text`. Which season is the main setting or "
            "seasonal focus of this poem? Use the supplied wording and historical Japanese waka "
            "conventions, not the author's biography or a remembered anthology classification. "
            "The text may contain a second reading of the SAME poem, not a second poem. "
            "Love poems can have a seasonal setting. Do not force every poem into a season. "
            "For a transition, choose the season that has arrived if the text makes this clear. "
            "Distinguish seasonal imagery used in a comparison from the main setting. "
            "Do not infer autumn from a generic moon, dew or sadness alone without contextual support."
        ),
        "criteria": {
            "spring": "Spring is the main seasonal setting or focus.",
            "summer": "Summer is the main seasonal setting or focus.",
            "autumn": "Autumn is the main seasonal setting or focus.",
            "winter": "Winter is the main seasonal setting or focus.",
            "mixed": "Two or more seasons are equally central; no single main season is justified.",
            "unspecified": "The poem is interpretable, but does not establish a particular main season.",
            "uncertain": "Cannot interpret the supplied classical wording sufficiently to choose reliably."
        },
    },
    **{
        f"cue_{season}": {
            "type": "noul",
            "instructions": (
                f"Does the classical Japanese waka in `text` contain a meaningful reference to {season}, "
                "through an explicit season word or imagery conventionally tied to that season in "
                "historical waka? Include seasons remembered, compared, or said to have passed, "
                "even if another season is the main setting. Judge the wording in context, not "
                "the author's identity or anthology category. Generic nature or sadness alone is insufficient."
            ),
            "criteria": {"true": f"A contextual reference to {season} is present.",
                         "false": f"No supported reference to {season} is present."},
        } for season in SEASONS
    },
    "love": {
        "type": "noul",
        "instructions": "Is romantic love, longing for a lover, or a romantic relationship a central concern of the classical Japanese waka in `text`? Do not treat every loneliness or separation as romantic. Seasonal imagery may coexist with love.",
    },
    "nature": {
        "type": "noul",
        "instructions": "Is observing a natural landscape, weather, or seasonal change a central concern of the classical Japanese waka in `text`, rather than merely a brief metaphor for another concern? A poem may also have a human or romantic concern.",
    },
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_poems() -> list[dict]:
    records = []
    for corpus, path, order_key, mode, count in [
        ("ogura", ROOT / "data/hyakunin_isshu.csv", "id", "original_kana", 100),
        ("shuka", ROOT / "_private/literature/records/hyakunin_shuka_mizugaki_provisional.csv",
         "shuka_order", "original", 101),
    ]:
        rows = sorted(read_csv(path), key=lambda r: int(r[order_key]))
        if [int(r[order_key]) for r in rows] != list(range(1, count + 1)):
            raise ValueError(f"Unexpected IDs or row count in {corpus}")
        for row in rows:
            text = build_embedding_text(row, mode)
            if not text:
                raise ValueError("Empty poem")
            number = int(row[order_key])
            records.append({"id": f"{'H' if corpus == 'ogura' else 'S'}{number:03d}",
                            "corpus": corpus, "order": number, "input_mode": mode,
                            "hyakunin_id": number if corpus == "ogura" else int(row.get("hyakunin_id") or 0) or None,
                            "text": text, "text_sha256": digest(text), "source_row": row})
    return records


def payload_for(poem: dict) -> dict:
    # No IDs, existing labels, source headings, author names or embeddings go to Jev.
    return {"model": MODEL, "state": {"text": poem["text"]}, "questions": QUESTIONS}


def validate_response(response: dict) -> None:
    if response.get("model") != MODEL:
        raise ValueError("Unexpected resolved model")
    answers = response.get("answers", {})
    if set(answers) != set(QUESTIONS):
        raise ValueError("Missing or extra answers")
    def probability(value):
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
    for key, question in QUESTIONS.items():
        answer = answers[key]
        if answer.get("type") != question["type"]:
            raise ValueError("Answer type mismatch")
        if question["type"] == "noul":
            if not probability(answer.get("noul")):
                raise ValueError("Invalid Noul probability")
        else:
            probs = answer.get("probabilities", {})
            if set(probs) != set(LABELS) or not all(probability(p) for p in probs.values()):
                raise ValueError("Invalid choice distribution")
            if abs(sum(probs.values()) - 1) > 0.02 or not probability(answer.get("confidence")):
                raise ValueError("Invalid choice normalization/confidence")
            choice = answer.get("choice")
            if choice not in probs or probs[choice] < max(probs.values()) - 1e-6:
                raise ValueError("Choice is not a maximum-probability option")
    usage = response.get("usage", {})
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        raise ValueError("Invalid usage")


def cache_path(poem: dict) -> Path:
    return RUN / "responses" / (digest(encoded(payload_for(poem))) + ".json")


def load_result(poem: dict) -> dict:
    entry = json.loads(cache_path(poem).read_text())
    if entry.get("request") != payload_for(poem):
        raise ValueError("Cache request mismatch")
    validate_response(entry["response"])
    return entry


def request_once(payload: dict, api_key: str) -> dict:
    request = urllib.request.Request(
        "https://api.typesafe.ai/v1/systemone", data=encoded(payload).encode(),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST")
    # Do not log HTTP bodies or exception details: they may echo private inputs.
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"TypeSafe HTTP {error.code}; stopped, completed responses retained") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("TypeSafe connection failed; completed responses retained") from None
    try:
        validate_response(result)
    except ValueError:
        quarantine = RUN / "invalid_responses"
        quarantine.mkdir(parents=True, exist_ok=True)
        (quarantine / f"{time.time_ns()}.json").write_text(encoded({"request": payload, "response": result}))
        raise
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ids", nargs="*", help="Optional pilot IDs, e.g. H001 S001")
    args = parser.parse_args()
    poems = load_poems()
    if args.ids:
        unknown = set(args.ids) - {p["id"] for p in poems}
        if unknown:
            raise ValueError(f"Unknown IDs: {sorted(unknown)}")
        poems = [p for p in poems if p["id"] in args.ids]
    missing = [p for p in poems if not cache_path(p).exists()]
    print(f"poems={len(poems)} pending={len(missing)} questions_per_poem={len(QUESTIONS)} model={MODEL}", flush=True)
    if not args.execute:
        return
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if missing and not key:
        raise RuntimeError("TYPESAFE_API_KEY is unset")
    for i, poem in enumerate(poems, 1):
        path = cache_path(poem)
        if path.exists():
            entry = load_result(poem)
        else:
            start = time.monotonic()
            payload = payload_for(poem)
            response = request_once(payload, key)
            entry = {"request": payload, "response": response,
                     "created_at": datetime.now(timezone.utc).isoformat(),
                     "elapsed_seconds": time.monotonic() - start}
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as handle:
                json.dump(entry, handle, ensure_ascii=False, indent=2)
        answer = entry["response"]["answers"]["season"]
        print(f"{i}/{len(poems)} {poem['id']} {LABELS[answer['choice']]} confidence={answer['confidence']:.3f}", flush=True)


if __name__ == "__main__":
    main()
