#!/usr/bin/env python3
"""Generate private OpenAI embeddings for the Hyakunin Isshu dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from normalize_waka import build_embedding_text, normalize_row


ROOT = Path(__file__).resolve().parents[1]
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def embedding_payload(
    rows: list[dict[str, str]],
    mode: str,
    model: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in rows:
        normalized = normalize_row(row, mode)
        text = normalized.get("embedding_text", "")
        records.append(
            {
                "id": row.get("id", ""),
                "poet_jp": row.get("poet_jp", ""),
                "input_mode": mode,
                "model": model,
                "text_sha256": sha256_text(text),
                "embedding_text": text,
            }
        )
    return records


def load_existing(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def cache_matches(
    existing: dict[str, object] | None,
    records: list[dict[str, object]],
    model: str,
    mode: str,
) -> bool:
    if not existing:
        return False
    meta = existing.get("meta", {})
    if not isinstance(meta, dict):
        return False
    if meta.get("model") != model or meta.get("input_mode") != mode:
        return False
    existing_records = existing.get("records", [])
    if not isinstance(existing_records, list) or len(existing_records) != len(records):
        return False
    for left, right in zip(existing_records, records):
        if not isinstance(left, dict):
            return False
        if left.get("id") != right.get("id"):
            return False
        if left.get("text_sha256") != right.get("text_sha256"):
            return False
        if not left.get("embedding"):
            return False
    return True


def request_embeddings(texts: list[str], model: str, api_key: str) -> list[list[float]]:
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_EMBEDDINGS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"OpenAI API error {error.code}: {detail}", file=sys.stderr)
        raise
    data = payload.get("data", [])
    data = sorted(data, key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def write_output(
    path: Path,
    records: list[dict[str, object]],
    model: str,
    mode: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "model": model,
            "input_mode": mode,
            "created_at_unix": int(time.time()),
            "record_count": len(records),
            "text_policy": "private embedding cache; do not publish vectors",
        },
        "records": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/hyakunin_isshu.csv",
        help="Input poem CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/embeddings/hyakunin_isshu_original_kana_text-embedding-3-large.json",
        help="Private embedding cache path.",
    )
    parser.add_argument(
        "--model",
        default="text-embedding-3-large",
        help="OpenAI embedding model.",
    )
    parser.add_argument(
        "--mode",
        choices=["original", "kana", "original_kana", "original_tags", "all"],
        default="original_kana",
        help="Embedding text composition mode.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Rows per API request.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report input rows without calling an embedding model.",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate even if cache matches.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_csv(args.input)
    records = embedding_payload(rows, args.mode, args.model)
    nonempty = sum(1 for record in records if str(record["embedding_text"]).strip())
    if args.dry_run:
        print(f"dry run: {len(rows)} rows, {nonempty} rows with embedding_text")
        return 0
    if len(rows) == 0 or nonempty != len(rows):
        print("Input rows are empty or missing embedding text.", file=sys.stderr)
        return 1
    existing = load_existing(args.output)
    if not args.force and cache_matches(existing, records, args.model, args.mode):
        print(f"cache is current: {args.output}")
        return 0
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not available in the environment.", file=sys.stderr)
        return 1

    enriched: list[dict[str, object]] = []
    for start in range(0, len(records), args.batch_size):
        batch = records[start : start + args.batch_size]
        texts = [str(record["embedding_text"]) for record in batch]
        vectors = request_embeddings(texts, args.model, api_key)
        for record, vector in zip(batch, vectors):
            output_record = dict(record)
            output_record.pop("embedding_text", None)
            output_record["embedding"] = vector
            enriched.append(output_record)
        print(f"embedded {len(enriched)}/{len(records)} rows")
    write_output(args.output, enriched, args.model, args.mode)
    print(f"wrote private embedding cache to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
