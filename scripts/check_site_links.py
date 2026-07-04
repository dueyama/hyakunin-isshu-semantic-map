#!/usr/bin/env python3
"""Check internal links and asset references in the public docs site."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PUBLIC_HTML = [
    DOCS / "index.html",
    DOCS / "paper" / "0" / "index.html",
    DOCS / "paper" / "index.html",
    DOCS / "paper" / "2" / "index.html",
    DOCS / "paper" / "3" / "index.html",
    DOCS / "paper" / "final" / "index.html",
    DOCS / "glossary" / "index.html",
    DOCS / "references" / "index.html",
    DOCS / "updates" / "index.html",
]
CSS_FILES = [DOCS / "assets" / "reading.css"]
LINK_ATTRS = {"a": ("href",), "link": ("href",), "img": ("src",), "script": ("src",)}
SKIP_SCHEMES = {"http", "https", "mailto", "tel", "data", "javascript"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        if "id" in attr_map:
            self.ids.add(attr_map["id"])
        if tag == "a" and "name" in attr_map:
            self.ids.add(attr_map["name"])
        for attr in LINK_ATTRS.get(tag, ()):
            if attr in attr_map:
                self.links.append((tag, attr, attr_map[attr]))


def html_target(path: Path) -> Path:
    if path.is_dir():
        return path / "index.html"
    if str(path).endswith("/"):
        return path / "index.html"
    return path


def parse_html(path: Path) -> LinkParser:
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    return parser


def resolve_reference(source: Path, raw_url: str) -> tuple[Path | None, str]:
    parsed = urlparse(raw_url)
    if parsed.scheme in SKIP_SCHEMES or parsed.netloc:
        return None, ""
    raw_path = unquote(parsed.path)
    target = source if raw_path in {"", "."} else (source.parent / raw_path).resolve()
    if not str(target).startswith(str(ROOT)):
        return target, parsed.fragment
    return target, parsed.fragment


def check_html_links() -> list[str]:
    errors: list[str] = []
    parsed_pages = {path.resolve(): parse_html(path) for path in PUBLIC_HTML}

    for source, parser in parsed_pages.items():
        for tag, attr, raw_url in parser.links:
            if not raw_url or raw_url.startswith("#"):
                fragment = raw_url[1:]
                if fragment and fragment not in parser.ids:
                    errors.append(f"{source.relative_to(ROOT)}: missing local anchor #{fragment}")
                continue

            target, fragment = resolve_reference(source, raw_url)
            if target is None:
                continue
            clean_target = html_target(target)
            if not clean_target.exists():
                errors.append(
                    f"{source.relative_to(ROOT)}: {tag}[{attr}] target missing: {raw_url}"
                )
                continue
            if fragment and clean_target.suffix.lower() in {".html", ".htm"}:
                target_parser = parsed_pages.get(clean_target.resolve())
                if target_parser is None:
                    target_parser = parse_html(clean_target)
                    parsed_pages[clean_target.resolve()] = target_parser
                if fragment not in target_parser.ids:
                    errors.append(
                        f"{source.relative_to(ROOT)}: target anchor missing: {raw_url}"
                    )
    return errors


def check_css_assets() -> list[str]:
    errors: list[str] = []
    url_pattern = re.compile(r"url\((['\"]?)([^)'\"]+)\1\)")
    for source in CSS_FILES:
        text = source.read_text(encoding="utf-8", errors="ignore")
        for raw_url in url_pattern.findall(text):
            value = raw_url[1].strip()
            target, _fragment = resolve_reference(source, value)
            if target is not None and not target.exists():
                errors.append(f"{source.relative_to(ROOT)}: CSS asset missing: {value}")
    return errors


def main() -> int:
    errors = check_html_links() + check_css_assets()
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"OK checked internal links in {len(PUBLIC_HTML)} HTML files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
