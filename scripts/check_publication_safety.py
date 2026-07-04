#!/usr/bin/env python3
"""Publication safety check for the HTML-only release boundary."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_DIRS = ["README.md", "AI_RESEARCHER_GUIDE.md", ".gitignore", "docs", "scripts"]
SECRET_PATTERNS = {
    "openai_key_like": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    "github_token_like": re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
}
LOCAL_PATH_PATTERNS = (
    "/" + "Users/",
    "/" + "private/",
    "Documents" + "/Codex",
    "file" + "://",
)
FORBIDDEN_PUBLIC_SUFFIXES = (".pyc",)
INTERNAL_PUBLIC_TREE_EXCLUSIONS = {
    Path("docs/progress.md"),
    Path("docs/hyakunin_shuka_comparison_notes.md"),
}
INTERNAL_PUBLIC_DIR_EXCLUSIONS = {
    Path("docs/viewer"),
}
REQUIRED_GITIGNORE_MARKERS = (
    "_private/",
    "data/raw/",
    "data/embeddings/",
    "public/data/",
    "docs/viewer/",
    "docs/progress.md",
    "docs/hyakunin_shuka_comparison_notes.md",
    ".env",
)


def should_skip(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if relative in INTERNAL_PUBLIC_TREE_EXCLUSIONS:
        return True
    for excluded_dir in INTERNAL_PUBLIC_DIR_EXCLUSIONS:
        if relative == excluded_dir or excluded_dir in relative.parents:
            return True
    return False


def iter_public_files() -> list[Path]:
    files: list[Path] = []
    for item in CHECK_DIRS:
        path = ROOT / item
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                child
                for child in path.rglob("*")
                if child.is_file() and "__pycache__" not in child.parts and not should_skip(child)
            )
    return sorted(files)


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".pdf"}


def main() -> int:
    errors: list[str] = []
    gitignore = ROOT / ".gitignore"
    gitignore_text = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
    for marker in REQUIRED_GITIGNORE_MARKERS:
        if marker not in gitignore_text:
            errors.append(f".gitignore: missing required marker {marker!r}")
    for path in iter_public_files():
        relative = path.relative_to(ROOT)
        if str(relative).endswith(FORBIDDEN_PUBLIC_SUFFIXES):
            errors.append(f"{relative}: forbidden generated suffix")
        if not is_text_file(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{relative}: matched {name}")
        if relative != Path("docs/PUBLICATION.md"):
            for marker in LOCAL_PATH_PATTERNS:
                if marker in text:
                    errors.append(f"{relative}: local path marker {marker!r}")
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"OK checked {len(iter_public_files())} publication candidate files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
