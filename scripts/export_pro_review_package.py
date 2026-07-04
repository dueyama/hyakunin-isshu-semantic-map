#!/usr/bin/env python3
"""Export public reading pages as Markdown plus images for external review."""

from __future__ import annotations

import html
import posixpath
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EXPORT_ROOT = ROOT / "_private" / "review_exports"

CHAPTERS = [
    {
        "slug": "00_prologue",
        "title": "序章 なぜ百人一首を意味空間に置くのか",
        "html": DOCS / "paper" / "0" / "index.html",
    },
    {
        "slug": "01_chapter1",
        "title": "第1章 百人秀歌と小倉百人一首を並べてみる",
        "html": DOCS / "paper" / "index.html",
    },
    {
        "slug": "02_chapter2",
        "title": "第2章 こぼれる一首、入ってくる三首",
        "html": DOCS / "paper" / "2" / "index.html",
    },
    {
        "slug": "03_chapter3",
        "title": "第3章 螺旋の小倉、斜めの秀歌",
        "html": DOCS / "paper" / "3" / "index.html",
    },
    {
        "slug": "04_final",
        "title": "終章 意味空間から、もう一度歌へ",
        "html": DOCS / "paper" / "final" / "index.html",
    },
]

SUPPORT_PAGES = [
    {
        "slug": "references",
        "title": "参照資料・参考文献",
        "html": DOCS / "references" / "index.html",
    },
    {
        "slug": "glossary",
        "title": "用語集",
        "html": DOCS / "glossary" / "index.html",
    },
]

EXTRA_REVIEW_FILES = [
    EXPORT_ROOT / "REVIEW_PROTOCOL.md",
    EXPORT_ROOT / "REVIEW_RESPONSE_1707.md",
    EXPORT_ROOT / "REVIEW_RESPONSE_1731_PROTOCOL.md",
    EXPORT_ROOT / "REVIEW_RESPONSE_1748_PROTOCOL.md",
    EXPORT_ROOT / "REVIEW_RESPONSE_1807_PROTOCOL.md",
    EXPORT_ROOT / "REVIEW_RESPONSE_1907_FINAL.md",
]


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)


class TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse_html(path: Path) -> Node:
    parser = TreeBuilder()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.root


def find_first(node: Node, tag: str) -> Node | None:
    if node.tag == tag:
        return node
    for child in node.children:
        if isinstance(child, Node):
            found = find_first(child, tag)
            if found:
                return found
    return None


def direct_text(node: Node) -> str:
    chunks: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            chunks.append(child)
    return normalize_inline("".join(chunks))


def normalize_inline(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def normalize_table_cell(value: str) -> str:
    value = normalize_inline(value)
    return re.sub(r"\s+（", "（", value)


def has_class(node: Node, class_name: str) -> bool:
    return class_name in node.attrs.get("class", "").split()


def clean_block(value: str) -> str:
    lines = [line.rstrip() for line in value.strip().splitlines()]
    compact: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compact.append(line)
        previous_blank = blank
    return "\n".join(compact).strip()


def safe_image_name(chapter_slug: str, src: str, used: dict[str, int]) -> str:
    parsed = urlparse(src)
    base = Path(unquote(parsed.path)).name
    stem = Path(base).stem or "image"
    suffix = Path(base).suffix or ".png"
    candidate = f"{chapter_slug}_{stem}{suffix}"
    count = used.get(candidate, 0)
    used[candidate] = count + 1
    if count:
        candidate = f"{chapter_slug}_{stem}_{count + 1}{suffix}"
    return candidate


def resolve_asset(html_path: Path, src: str) -> Path | None:
    parsed = urlparse(src)
    if parsed.scheme or parsed.netloc:
        return None
    relative = unquote(parsed.path)
    path = (html_path.parent / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return path


def inline_text(node: Node | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag == "span" and has_class(node, "ref-label"):
        label = normalize_inline("".join(inline_text(child) for child in node.children))
        return f"**{label}** "
    if node.tag == "br":
        return "\n"
    if node.tag == "code":
        return "`" + "".join(inline_text(child) for child in node.children).strip() + "`"
    if node.tag == "a":
        if has_class(node, "anchor-link"):
            return ""
        body = normalize_inline("".join(inline_text(child) for child in node.children))
        href = node.attrs.get("href", "")
        if href:
            if has_class(node, "cite"):
                return f" [{body}]({href})"
            return f"[{body}]({href})"
        return body
    return "".join(inline_text(child) for child in node.children)


def heading_text(node: Node | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag == "br":
        return ""
    if node.tag == "code":
        return "`" + "".join(heading_text(child) for child in node.children).strip() + "`"
    if node.tag == "a":
        return normalize_inline("".join(heading_text(child) for child in node.children))
    return "".join(heading_text(child) for child in node.children)


def table_to_md(node: Node) -> str:
    rows: list[list[str]] = []
    for child in node.children:
        if isinstance(child, Node):
            if child.tag in {"thead", "tbody", "tfoot"}:
                for tr in child.children:
                    if isinstance(tr, Node) and tr.tag == "tr":
                        rows.append([
                            normalize_table_cell(inline_text(cell))
                            for cell in tr.children
                            if isinstance(cell, Node) and cell.tag in {"th", "td"}
                        ])
            elif child.tag == "tr":
                rows.append([
                    normalize_table_cell(inline_text(cell))
                    for cell in child.children
                    if isinstance(cell, Node) and cell.tag in {"th", "td"}
                ])
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    output = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in normalized[1:]:
        output.append("| " + " | ".join(row) + " |")
    return "\n".join(output)


def remove_review_only_figure_links(caption: str) -> str:
    caption = re.sub(r"。?\s*\[図だけを開く\]\([^)]+\)\s*。?", "。", caption)
    caption = caption.replace("。。", "。")
    return caption.strip()


def markdown_links_to_text(value: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)


def convert_node(
    node: Node | str,
    *,
    html_path: Path,
    chapter_slug: str,
    image_dir: Path,
    used_images: dict[str, int],
    image_manifest: list[dict[str, str]],
    figure_counter: list[int],
    current_heading: list[str],
) -> str:
    if isinstance(node, str):
        return ""
    tag = node.tag

    if tag in {"script", "style", "nav"}:
        return ""

    if tag == "article" and has_class(node, "poem-card"):
        poem_id = ""
        poem_meta = ""
        waka = ""
        notes: list[str] = []
        for child in node.children:
            if not isinstance(child, Node):
                continue
            if child.tag == "span" and has_class(child, "poem-id"):
                plain_parts: list[str] = []
                for grandchild in child.children:
                    if isinstance(grandchild, Node) and has_class(grandchild, "poem-meta"):
                        poem_meta = normalize_inline(inline_text(grandchild))
                    else:
                        plain_parts.append(inline_text(grandchild))
                poem_id = normalize_inline("".join(plain_parts))
            elif child.tag == "span" and has_class(child, "waka"):
                waka = normalize_inline(inline_text(child))
            elif child.tag == "p":
                notes.append(clean_block(inline_text(child)))
        heading = poem_id
        if poem_meta:
            heading = f"{heading}（{poem_meta}）"
        parts = [f"**{heading}**"] if heading else []
        if waka:
            parts.append("> " + waka)
        parts.extend(note for note in notes if note)
        return "\n\n".join(parts)

    if tag == "div" and has_class(node, "card"):
        title = ""
        body = ""
        for child in node.children:
            if isinstance(child, Node) and child.tag == "b":
                title = normalize_inline(inline_text(child))
            elif isinstance(child, Node) and child.tag == "span":
                body = normalize_inline(inline_text(child))
        if title and body:
            return f"- **{title}:** {body}"
        if title:
            return f"- **{title}**"
        if body:
            return f"- {body}"

    if tag in {"main", "section", "header", "div", "details", "article"}:
        parts = [
            convert_node(
                child,
                html_path=html_path,
                chapter_slug=chapter_slug,
                image_dir=image_dir,
                used_images=used_images,
                image_manifest=image_manifest,
                figure_counter=figure_counter,
                current_heading=current_heading,
            )
            for child in node.children
        ]
        body = "\n\n".join(part for part in parts if part)
        anchor_id = node.attrs.get("id", "")
        if anchor_id and tag in {"section", "article", "details", "div"}:
            return f'<a id="{anchor_id}"></a>\n\n{body}' if body else f'<a id="{anchor_id}"></a>'
        return body

    if tag in {"h1", "h2", "h3", "h4"}:
        level = {"h1": 2, "h2": 2, "h3": 3, "h4": 4}[tag]
        text = normalize_inline(heading_text(node))
        if tag in {"h1", "h2"}:
            current_heading[0] = text
        return f"{'#' * level} {text}"

    if tag == "p":
        link_children = [
            child
            for child in node.children
            if isinstance(child, Node) and child.tag == "a"
        ]
        other_content = [
            child
            for child in node.children
            if (isinstance(child, str) and child.strip()) or (isinstance(child, Node) and child.tag != "a")
        ]
        if link_children and not other_content:
            return " / ".join(normalize_inline(inline_text(child)) for child in link_children)
        tag_spans = [
            child
            for child in node.children
            if isinstance(child, Node) and child.tag == "span" and has_class(child, "tag")
        ]
        if tag_spans:
            bullets = [f"- {normalize_inline(inline_text(child))}" for child in tag_spans]
            return "\n".join(bullets)
        text = clean_block(inline_text(node))
        anchor_id = node.attrs.get("id", "")
        if anchor_id:
            return f'<a id="{anchor_id}"></a>\n\n{text}' if text else f'<a id="{anchor_id}"></a>'
        return text

    if tag == "blockquote":
        text = clean_block(inline_text(node))
        return "\n".join("> " + line.strip() for line in text.splitlines())

    if tag in {"ul", "ol"}:
        ordered = tag == "ol"
        lines: list[str] = []
        index = 1
        for child in node.children:
            if isinstance(child, Node) and child.tag == "li":
                text = clean_block(inline_text(child))
                prefix = f"{index}. " if ordered else "- "
                lines.append(prefix + text.replace("\n", "\n  "))
                index += 1
        return "\n".join(lines)

    if tag == "table":
        return table_to_md(node)

    if tag == "summary":
        label = ""
        rest: list[str] = []
        for child in node.children:
            if isinstance(child, Node) and child.tag == "span":
                label = normalize_inline(inline_text(child))
            else:
                rest.append(inline_text(child))
        detail = normalize_inline("".join(rest))
        if label and detail:
            return f"**補足: {label} — {detail}**"
        return f"**補足: {normalize_inline(inline_text(node))}**"

    if tag == "figure":
        figure_counter[0] += 1
        img_node = next((child for child in node.children if isinstance(child, Node) and child.tag == "img"), None)
        caption_node = next((child for child in node.children if isinstance(child, Node) and child.tag == "figcaption"), None)
        if not img_node:
            return ""
        src = img_node.attrs.get("src", "")
        alt = img_node.attrs.get("alt", "")
        caption = clean_block(inline_text(caption_node)) if caption_node else ""
        caption = remove_review_only_figure_links(caption)
        asset_path = resolve_asset(html_path, src)
        out_name = safe_image_name(chapter_slug, src, used_images)
        if asset_path and asset_path.exists():
            shutil.copy2(asset_path, image_dir / out_name)
        else:
            out_name = src
        image_manifest.append(
            {
                "chapter": chapter_slug,
                "heading": current_heading[0],
                "figure_index": str(figure_counter[0]),
                "image": out_name,
                "source": src,
                "alt": alt,
                "caption": caption,
            }
        )
        md = [f"![{alt}](images/{out_name})"]
        if caption:
            md.append(f"*{caption}*")
        md.append(f"<!-- image-position: {chapter_slug} / {current_heading[0]} / figure {figure_counter[0]} / {out_name} -->")
        return "\n\n".join(md)

    return "\n\n".join(
        part
        for child in node.children
        if (
            part := convert_node(
                child,
                html_path=html_path,
                chapter_slug=chapter_slug,
                image_dir=image_dir,
                used_images=used_images,
                image_manifest=image_manifest,
                figure_counter=figure_counter,
                current_heading=current_heading,
            )
        )
    )


def export_page(page: dict[str, Path | str], out_dir: Path, image_dir: Path, image_manifest: list[dict[str, str]], used_images: dict[str, int]) -> str:
    slug = str(page["slug"])
    title = str(page["title"])
    html_path = Path(page["html"])
    root = parse_html(html_path)
    main = find_first(root, "main") or root
    figure_counter = [0]
    current_heading = [title]
    body = convert_node(
        main,
        html_path=html_path,
        chapter_slug=slug,
        image_dir=image_dir,
        used_images=used_images,
        image_manifest=image_manifest,
        figure_counter=figure_counter,
        current_heading=current_heading,
    )
    markdown = clean_block(f"# {title}\n\n{body}\n")
    out_path = out_dir / f"{slug}.md"
    out_path.write_text(markdown + "\n", encoding="utf-8")
    return markdown


def manifest_markdown(image_manifest: list[dict[str, str]]) -> str:
    lines = [
        "# Image Manifest",
        "",
        "Markdown本文内の画像位置を確認するための一覧です。各章Markdownにも、画像直後に `image-position` コメントを入れています。",
        "",
        "| Chapter | Section | Figure | Image | Caption |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in image_manifest:
        caption = markdown_links_to_text(item["caption"]).replace("|", "\\|")
        lines.append(
            f"| {item['chapter']} | {item['heading'].replace('|', '\\|')} | {item['figure_index']} | `images/{item['image']}` | {caption} |"
        )
    return "\n".join(lines) + "\n"


def make_zip(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path == zip_path or path.is_dir():
                continue
            archive.write(path, path.relative_to(source_dir))


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = EXPORT_ROOT / f"hyakunin_isshu_pro_review_{stamp}"
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    image_manifest: list[dict[str, str]] = []
    used_images: dict[str, int] = {}
    combined_parts: list[str] = []

    for page in CHAPTERS:
        combined_parts.append(export_page(page, out_dir, image_dir, image_manifest, used_images))

    support_dir = out_dir / "support"
    support_dir.mkdir(exist_ok=True)
    for page in SUPPORT_PAGES:
        support_md = export_page(page, support_dir, image_dir, image_manifest, used_images)
        combined_parts.append(f"# 補助資料: {page['title']}\n\n{support_md}")

    for extra in EXTRA_REVIEW_FILES:
        if extra.exists():
            shutil.copy2(extra, out_dir / extra.name)

    (out_dir / "all_chapters_combined.md").write_text("\n\n---\n\n".join(combined_parts) + "\n", encoding="utf-8")
    (out_dir / "image_manifest.md").write_text(manifest_markdown(image_manifest), encoding="utf-8")
    (out_dir / "README_FOR_PRO.md").write_text(
        "\n".join(
            [
                "# GPT Proレビュー用パッケージ",
                "",
                "このzipは、公開予定HTML読み物『意味空間で百人一首を読む』のレビュー用エクスポートです。",
                "",
                "## 内容",
                "",
                "- `00_prologue.md` から `04_final.md`: 序章から終章までの本文Markdown。",
                "- `all_chapters_combined.md`: 全章を一つに結合したMarkdown。",
                "- `images/`: 本文中で参照される図・挿絵。",
                "- `image_manifest.md`: 各画像がどの章・節・図位置に入るかの一覧。",
                "- `support/references.md`, `support/glossary.md`: 参照資料と用語集の補助Markdown。",
                "- `REVIEW_PROTOCOL.md`: GPT Proとのレビュー往復のプロトコル。",
                "- `REVIEW_RESPONSE_1707.md`: 1707版レビューへの対応表。",
                "- `REVIEW_RESPONSE_1731_PROTOCOL.md`: 1731版レビューへの対応表。英語版を外した件はユーザー指示による方針変更として記録。",
                "- `REVIEW_RESPONSE_1748_PROTOCOL.md`: 1748版レビューへの対応表。第1章と第3章の類似度条件差への対応を記録。",
                "- `REVIEW_RESPONSE_1807_PROTOCOL.md`: 1807版レビューへの対応表。公開直前の参照・表記・Markdown注記への対応を記録。",
                "",
                "## 公開本体",
                "",
                "本公開の正本は `docs/` 以下のHTMLです。このMarkdown一式は、GPT Proに全文と画像位置を渡すためのレビュー用エクスポートです。",
                "したがって、Markdown特有の見え方に関する指摘は、公開HTMLへ反映するものと、レビュー用エクスポート側だけで処理するものに分けて扱います。",
                "公開HTMLでは一部の補足説明は折りたたみ表示ですが、レビュー用Markdownでは全文確認のため展開しています。",
                "`all_chapters_combined.md` は検索・全文レビュー用の補助ファイルです。リンクや見出し階層は、章別HTMLの公開構造と完全には一致しません。",
                "",
                "## 画像位置",
                "",
                "各章Markdownでは、画像を本文中の元位置に `![alt](images/...)` として挿入しています。",
                "さらに画像直後に `<!-- image-position: ... -->` コメントを入れ、章・節・図番号を追えるようにしています。",
                "",
                "## 注意",
                "",
                "このパッケージには公開ページ用の本文と画像だけを入れています。解析用の完全CSV、埋め込みベクトル、非公開文献ファイルは含めていません。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    zip_path = EXPORT_ROOT / f"{out_dir.name}.zip"
    make_zip(out_dir, zip_path)
    print(out_dir)
    print(zip_path)
    print(f"images={len(list(image_dir.iterdir()))}")


if __name__ == "__main__":
    main()
