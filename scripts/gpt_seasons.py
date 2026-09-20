#!/usr/bin/env python3
"""Resumable, private OpenAI seasonal judgments; API calls require --execute."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
import time
import urllib.error
import urllib.request

from jev_seasons import ROOT, LABELS, QUESTIONS, digest, encoded, load_poems

MODEL = "gpt-5.6-luna"
RUN = ROOT / "_private/experiments/gpt_seasons_v1"


def payload_for(poem):
    # Exactly the same principal-season instructions, alternatives and text as Jev.
    # The six other Jev questions are not sent; this comparison concerns season only.
    question = QUESTIONS["season"]
    return {
        "model": MODEL, "store": False, "reasoning": {"effort": "medium"},
        "max_output_tokens": 4096,
        "instructions": question["instructions"] + "\nCriteria:\n" + encoded(question["criteria"]),
        "input": encoded({"text": poem["text"]}),
        "text": {"format": {"type": "json_schema", "name": "waka_season", "strict": True,
            "schema": {"type": "object", "properties": {
                "season": {"type": "string", "enum": list(LABELS)}},
                "required": ["season"], "additionalProperties": False}}},
    }


def validate_response(response):
    if response.get("model") != MODEL or response.get("status") != "completed":
        raise ValueError("Unexpected model or incomplete response")
    messages = [item for item in response.get("output", []) if item.get("type") == "message"]
    if len(messages) != 1 or messages[0].get("role") != "assistant":
        raise ValueError("Expected one assistant message")
    content = messages[0].get("content", [])
    if len(content) != 1 or content[0].get("type") != "output_text":
        raise ValueError("Missing structured output or refusal")
    answer = json.loads(content[0]["text"])
    if set(answer) != {"season"} or answer["season"] not in LABELS:
        raise ValueError("Invalid season result")
    usage = response.get("usage", {})
    if any(type(usage.get(k)) is not int or usage[k] < 0
           for k in ("input_tokens", "output_tokens", "total_tokens")):
        raise ValueError("Invalid usage")
    return answer


def cache_path(poem):
    return RUN / "responses" / (digest(encoded(payload_for(poem))) + ".json")


def load_result(poem):
    entry = json.loads(cache_path(poem).read_text())
    if entry.get("request") != payload_for(poem):
        raise ValueError("Cached request does not match current configuration")
    validate_response(entry["response"])
    return entry


def request_poem(poem, key):
    if cache_path(poem).exists():
        return load_result(poem)
    payload = payload_for(poem)
    request = urllib.request.Request("https://api.openai.com/v1/responses",
        data=encoded(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=180) as result:
            response = json.load(result)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"OpenAI HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("OpenAI connection failure") from None
    entry = {"request": payload, "response": response,
             "created_at": datetime.now(timezone.utc).isoformat(),
             "elapsed_seconds": time.monotonic() - started}
    # Keep every received response, including incomplete or invalid responses,
    # before parsing. A failed response must never disappear from the usage record.
    attempt = RUN / "attempts" / f"{poem['id']}-{time.time_ns()}.json"
    attempt.parent.mkdir(parents=True, exist_ok=True)
    with attempt.open("x", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False, indent=2)
    validate_response(response)
    path = cache_path(poem)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False, indent=2)
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--corpus", choices=["ogura", "shuka"])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    poems = load_poems()
    if args.corpus:
        poems = [p for p in poems if p["corpus"] == args.corpus]
    if args.ids:
        unknown = set(args.ids) - {p["id"] for p in poems}
        if unknown:
            parser.error(f"Unknown IDs: {sorted(unknown)}")
        poems = [p for p in poems if p["id"] in args.ids]
    pending = []
    for poem in poems:
        if cache_path(poem).exists():
            load_result(poem)
        else:
            pending.append(poem)
    print(f"model={MODEL} reasoning=medium poems={len(poems)} pending={len(pending)}", flush=True)
    if not args.execute or not pending:
        return
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is unset")
    # Bounded concurrency and no automatic retries. Submit a new poem only after
    # a completed request, so a failure leaves at most workers-1 calls in flight.
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        remaining = iter(pending)
        active = {executor.submit(request_poem, p, key): p
                  for p in [next(remaining, None) for _ in range(args.workers)] if p}
        completed = len(poems) - len(pending)
        while active:
            future = next(as_completed(active))
            poem = active.pop(future)
            try:
                entry = future.result()
                season = validate_response(entry["response"])["season"]
                completed += 1
                print(f"{completed}/{len(poems)} {poem['id']} {LABELS[season]}", flush=True)
            except Exception as error:
                # Report only class and poem ID; error bodies may echo private input.
                failed.append(poem["id"])
                print(f"FAILED {poem['id']} {type(error).__name__}; no more requests scheduled", flush=True)
            if not failed:
                following = next(remaining, None)
                if following:
                    active[executor.submit(request_poem, following, key)] = following
    if failed:
        raise SystemExit("Stopped; inspect private attempts. Failed IDs: " + ", ".join(failed))


if __name__ == "__main__":
    main()
