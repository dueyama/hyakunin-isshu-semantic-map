"""Build polished data charts for chapter 2.

These figures keep the original bar-chart structure, but restyle labels,
spacing, legends, and annotations for the public reading pages.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"

W = 1280

COLORS = {
    "paper": "#fbfaf7",
    "panel": "#fffdf8",
    "wash": "#f4f1ea",
    "grid": "#ded6c9",
    "ink": "#202124",
    "muted": "#6f6a62",
    "plum": "#4b2447",
    "plum_soft": "#8f4e76",
    "cinnabar": "#9a3f2f",
    "moss": "#526b55",
    "indigo": "#263c61",
    "blue": "#496f86",
    "gold": "#a77d35",
    "low": "#938b80",
    "pale_gold": "#efe4c9",
    "pale_indigo": "#dfe5ef",
}


def tag(name: str, content: str = "", **attrs: object) -> str:
    clean = {
        key.replace("_", "-"): value
        for key, value in attrs.items()
        if value is not None
    }
    attr = " ".join(f'{key}="{escape(str(value), quote=True)}"' for key, value in clean.items())
    if attr:
        attr = " " + attr
    if content:
        return f"<{name}{attr}>{content}</{name}>"
    return f"<{name}{attr}/>"


def text(
    x: float,
    y: float,
    value: str,
    size: int = 18,
    fill: str | None = None,
    weight: int | str | None = None,
    family: str = "sans",
    anchor: str | None = None,
) -> str:
    family_value = (
        "Hiragino Mincho ProN, Yu Mincho, serif"
        if family == "serif"
        else "Hiragino Sans, Yu Gothic, sans-serif"
    )
    return tag(
        "text",
        escape(value),
        x=x,
        y=y,
        fill=fill or COLORS["ink"],
        font_family=family_value,
        font_size=size,
        font_weight=weight,
        text_anchor=anchor,
        letter_spacing=0,
    )


def rect(
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    stroke: str | None = None,
    rx: float = 8,
    opacity: float | None = None,
    stroke_width: float | None = None,
) -> str:
    return tag(
        "rect",
        x=x,
        y=y,
        width=width,
        height=height,
        fill=fill,
        stroke=stroke,
        rx=rx,
        opacity=opacity,
        stroke_width=stroke_width,
    )


def line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str,
    width: float = 1,
    opacity: float | None = None,
    dasharray: str | None = None,
) -> str:
    return tag(
        "line",
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        stroke=stroke,
        stroke_width=width,
        opacity=opacity,
        stroke_dasharray=dasharray,
    )


def circle(cx: float, cy: float, r: float, fill: str, stroke: str | None = None) -> str:
    return tag("circle", cx=cx, cy=cy, r=r, fill=fill, stroke=stroke, stroke_width=2 if stroke else None)


def multiline(x: float, y: float, lines: Iterable[str], size: int = 16, fill: str | None = None, line_height: int = 24) -> str:
    return "\n".join(text(x, y + i * line_height, line, size, fill) for i, line in enumerate(lines))


def svg_doc(height: int, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img">
<defs>
  <filter id="shadow" x="-12%" y="-12%" width="124%" height="124%">
    <feDropShadow dx="0" dy="16" stdDeviation="16" flood-color="#202124" flood-opacity="0.11"/>
  </filter>
  <linearGradient id="barGloss" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.18"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{height}" fill="{COLORS["paper"]}"/>
<rect x="34" y="34" width="{W - 68}" height="{height - 68}" rx="18" fill="{COLORS["panel"]}" stroke="{COLORS["grid"]}" filter="url(#shadow)"/>
{body}
</svg>
'''


def axis(x: float, y1: float, y2: float, width: float) -> str:
    parts = []
    for value in [0, 0.25, 0.5, 0.75, 1.0]:
        px = x + width * value
        parts.append(line(px, y1, px, y2, COLORS["grid"], 1, opacity=0.75))
        label = f"{value:.2f}" if value not in (0, 1.0) else f"{value:.0f}"
        parts.append(text(px, y1 - 12, label, 13, COLORS["muted"], anchor="middle"))
    parts.append(line(x, y2, x + width, y2, COLORS["grid"], 1.2))
    return "\n".join(parts)


def bar(x: float, y: float, width: float, value: float, color: str, height: float = 24, label: str | None = None) -> str:
    fill_width = max(2, width * value)
    parts = [
        rect(x, y, width, height, "#ede8dd", None, rx=height / 2),
        rect(x, y, fill_width, height, color, None, rx=height / 2, opacity=0.93),
        rect(x, y, fill_width, height, "url(#barGloss)", None, rx=height / 2),
    ]
    if label:
        if value > 0.33:
            parts.append(text(x + fill_width - 10, y + height - 7, label, 14, "#fffdf8", 700, anchor="end"))
        else:
            parts.append(text(x + fill_width + 10, y + height - 7, label, 14, COLORS["ink"], 700))
    return "\n".join(parts)


def chip(x: float, y: float, label: str, color: str, width: float = 162) -> str:
    return "\n".join(
        [
            rect(x, y, width, 34, COLORS["wash"], color, rx=17, stroke_width=1.4),
            text(x + width / 2, y + 23, label, 15, color, 700, anchor="middle"),
        ]
    )


def layout_label(raw: str) -> str:
    return {
        "spiral": "渦巻き型",
        "row_major": "通常行型",
        "column_major": "通常列型",
        "row_serpentine": "行つづら折り",
        "column_serpentine": "列つづら折り",
        "diagonal_nw": "斜め NW-SE",
        "diagonal_ne": "斜め NE-SW",
    }[raw]


def row_major_path(size: int = 10) -> list[tuple[int, int]]:
    return [(index // size, index % size) for index in range(size * size)]


def row_serpentine_path(size: int = 10) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    for row in range(size):
        cols = range(size) if row % 2 == 0 else range(size - 1, -1, -1)
        cells.extend((row, col) for col in cols)
    return cells


def diagonal_serpentine_path(size: int = 10) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    for total in range(2 * size - 1):
        diagonal = [(row, total - row) for row in range(size) if 0 <= total - row < size]
        if total % 2:
            diagonal.reverse()
        cells.extend(diagonal)
    return cells


def spiral_path(size: int = 10) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    top, left = 0, 0
    bottom, right = size - 1, size - 1
    while top <= bottom and left <= right:
        for col in range(left, right + 1):
            cells.append((top, col))
        top += 1
        for row in range(top, bottom + 1):
            cells.append((row, right))
        right -= 1
        if top <= bottom:
            for col in range(right, left - 1, -1):
                cells.append((bottom, col))
            bottom -= 1
        if left <= right:
            for row in range(bottom, top - 1, -1):
                cells.append((row, left))
            left += 1
    return cells


def mini_grid_path(x: float, y: float, cell: float, path: list[tuple[int, int]], color: str) -> str:
    grid_size = cell * 10
    points = [
        (x + col * cell + cell / 2, y + row * cell + cell / 2)
        for row, col in path
    ]
    point_text = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
    parts: list[str] = [
        rect(x - 8, y - 8, grid_size + 16, grid_size + 16, "#fffefa", COLORS["grid"], rx=12, stroke_width=1.1),
    ]
    for row in range(10):
        for col in range(10):
            parts.append(rect(x + col * cell, y + row * cell, cell - 1, cell - 1, "#f3efe6", None, rx=3))
    parts.append(
        tag(
            "polyline",
            points=point_text,
            fill="none",
            stroke=color,
            stroke_width=3.3,
            stroke_linecap="round",
            stroke_linejoin="round",
            opacity=0.82,
        )
    )
    start_x, start_y = points[0]
    end_x, end_y = points[-1]
    parts.extend(
        [
            circle(start_x, start_y, 8, color, "#fffdf8"),
            text(start_x, start_y + 5, "1", 11, "#fffdf8", 800, anchor="middle"),
            circle(end_x, end_y, 10, "#fffdf8", color),
            text(end_x, end_y + 5, "100", 10, color, 800, anchor="middle"),
        ]
    )
    return "\n".join(parts)


def pattern_card(
    x: float,
    y: float,
    title: str,
    lines: list[str],
    path: list[tuple[int, int]],
    color: str,
) -> str:
    parts = [
        rect(x, y, 262, 342, "#fffefa", COLORS["grid"], rx=16, stroke_width=1.2),
        text(x + 24, y + 42, title, 22, color, 700, "serif"),
        mini_grid_path(x + 38, y + 70, 18, path, color),
        multiline(x + 24, y + 278, lines, 15, COLORS["ink"], line_height=24),
    ]
    return "\n".join(parts)


def figure_layout_models() -> str:
    body = [
        text(78, 82, "10×10にどう置くか", 32, COLORS["plum"], 700, "serif"),
        text(78, 116, "同じ100首でも、マス目へ置く順番を変えると、隣り合う歌の組み合わせが変わる。", 17, COLORS["muted"]),
        pattern_card(
            70,
            160,
            "通常行型",
            ["一行ずつ左から右へ置く。", "行末から次の行頭へ戻る。"],
            row_major_path(),
            COLORS["indigo"],
        ),
        pattern_card(
            370,
            160,
            "行つづら折り",
            ["一行ごとに向きを反転。", "横のつながりが続く。"],
            row_serpentine_path(),
            COLORS["blue"],
        ),
        pattern_card(
            670,
            160,
            "斜めつづら折り",
            ["斜めの帯へ順に置く。", "百人秀歌側で目立った型。"],
            diagonal_serpentine_path(),
            COLORS["plum_soft"],
        ),
        pattern_card(
            970,
            160,
            "渦巻き型",
            ["外側から内側へ置く。", "小倉側で上がった型。"],
            spiral_path(),
            COLORS["cinnabar"],
        ),
        rect(78, 538, 1124, 66, COLORS["wash"], COLORS["grid"], rx=14),
        text(104, 578, "この章では、置き終えた後の近所どうしを拾い、意味的に近い歌が集まりやすいかを比べる。", 17, COLORS["ink"]),
    ]
    return svg_doc(640, "\n".join(body))


def comparison_grid(
    x: float,
    y: float,
    cell: float,
    color: str,
    include_diagonal: bool = False,
) -> str:
    labels = [
        ["S012", "S041", "S083", "S006", "S058"],
        ["S097", "S024", "S073", "S031", "S089"],
        ["S045", "S066", "S076", "S009", "S052"],
        ["S014", "S030", "S090", "S061", "S018"],
        ["S100", "S005", "S037", "S048", "S071"],
    ]
    neighbor_cells = [(1, 2), (2, 1), (2, 3), (3, 2)]
    diagonal_cells = [(1, 1), (1, 3), (3, 1), (3, 3)] if include_diagonal else []
    parts = [
        rect(x - 12, y - 12, cell * 5 + 24, cell * 5 + 24, "#fffefa", COLORS["grid"], rx=16, stroke_width=1.2),
    ]
    for row in range(5):
        for col in range(5):
            fill = "#f4efe6"
            stroke = COLORS["grid"]
            stroke_width = 1
            label_color = COLORS["muted"]
            if (row, col) == (2, 2):
                fill = color
                stroke = color
                stroke_width = 2
                label_color = "#fffdf8"
            elif (row, col) in neighbor_cells:
                fill = "#eadfcf"
                stroke = COLORS["gold"]
                stroke_width = 2
                label_color = COLORS["ink"]
            elif (row, col) in diagonal_cells:
                fill = "#f1e6ee"
                stroke = COLORS["plum_soft"]
                stroke_width = 2
                label_color = COLORS["ink"]
            parts.append(rect(x + col * cell, y + row * cell, cell - 2, cell - 2, fill, stroke, rx=8, stroke_width=stroke_width))
            parts.append(text(x + col * cell + cell / 2, y + row * cell + cell / 2 + 6, labels[row][col], 14, label_color, 700, anchor="middle"))
    cx = x + 2 * cell + cell / 2
    cy = y + 2 * cell + cell / 2
    for row, col in neighbor_cells + diagonal_cells:
        nx = x + col * cell + cell / 2
        ny = y + row * cell + cell / 2
        parts.append(line(cx, cy, nx, ny, color, 3, opacity=0.65))
    return "\n".join(parts)


def formula_box(x: float, y: float, title: str, lines: list[str], color: str, width: float = 308) -> str:
    parts = [
        rect(x, y, width, 168, "#fffefa", COLORS["grid"], rx=16, stroke_width=1.2),
        text(x + 24, y + 38, title, 22, color, 700, "serif"),
        multiline(x + 24, y + 76, lines, 16, COLORS["ink"], line_height=26),
    ]
    return "\n".join(parts)


def figure_grid_comparison_method() -> str:
    body = [
        text(78, 82, "置いたあと、何を比べるか", 32, COLORS["indigo"], 700, "serif"),
        text(78, 116, "マスに置いた順番そのものではなく、置いた後に隣り合う歌の組み合わせを全部拾って平均する。", 17, COLORS["muted"]),
        text(92, 166, "上下左右で拾う", 22, COLORS["blue"], 700, "serif"),
        comparison_grid(92, 196, 58, COLORS["blue"], include_diagonal=False),
        text(470, 166, "斜めも含めて拾う", 22, COLORS["plum_soft"], 700, "serif"),
        comparison_grid(470, 196, 58, COLORS["plum_soft"], include_diagonal=True),
        line(820, 306, 878, 306, COLORS["grid"], 5),
        circle(850, 306, 7, COLORS["gold"], "#fffdf8"),
        formula_box(
            900,
            186,
            "一組ずつ近さを出す",
            [
                "S076-S073: 0.41",
                "S076-S066: 0.37",
                "S076-S009: 0.46",
                "S076-S090: 0.35",
            ],
            COLORS["cinnabar"],
        ),
        line(1054, 364, 1054, 414, COLORS["grid"], 5),
        circle(1054, 392, 7, COLORS["gold"], "#fffdf8"),
        formula_box(
            900,
            430,
            "最後に平均する",
            [
                "上下左右なら180組",
                "8近傍なら342組",
                "平均値をランダム配置と比べる",
            ],
            COLORS["moss"],
        ),
        rect(78, 628, 1124, 66, COLORS["wash"], COLORS["grid"], rx=14),
        text(104, 668, "図の小さな数値は説明用の例であり、この章の実データ値そのものではない。実際には全セルの隣接ペアを集計する。", 17, COLORS["ink"]),
    ]
    return svg_doc(730, "\n".join(body))


def step_card(
    x: float,
    y: float,
    width: float,
    height: float,
    number: str,
    title: str,
    lines: list[str],
    color: str,
) -> str:
    parts = [
        rect(x, y, width, height, "#fffefa", COLORS["grid"], rx=14, stroke_width=1.2),
        circle(x + 34, y + 34, 20, color, "#fffdf8"),
        text(x + 34, y + 42, number, 20, "#fffdf8", 800, anchor="middle"),
        text(x + 64, y + 40, title, 21, color, 700, "serif"),
        multiline(x + 24, y + 82, lines, 15, COLORS["ink"], line_height=25),
    ]
    return "\n".join(parts)


def figure_overlay_workflow() -> str:
    card_y = 178
    card_w = 204
    card_h = 198
    gap = 24
    xs = [70 + i * (card_w + gap) for i in range(5)]
    steps = [
        (
            "1",
            "基準を決める",
            ["百人秀歌の", "10×10配置を", "出発点にする。"],
            COLORS["moss"],
        ),
        (
            "2",
            "97首を固定",
            ["両方にある歌は", "百人秀歌側の", "セルに置く。"],
            COLORS["indigo"],
        ),
        (
            "3",
            "一首を枠外へ",
            ["S053 / S073", "S076 / S090", "から一首を外す。"],
            COLORS["plum"],
        ),
        (
            "4",
            "三首を入れる",
            ["H074 / H099", "H100を残りの", "三セルへ6通り。"],
            COLORS["cinnabar"],
        ),
        (
            "5",
            "隣を集計する",
            ["上下左右と", "8近傍の隣を", "まとめて平均する。"],
            COLORS["gold"],
        ),
    ]
    body = [
        text(78, 82, "小倉三首を入れる検査手順", 32, COLORS["moss"], 700, "serif"),
        text(78, 116, "この図は結果ではなく、次の棒グラフを作るまでの処理手順である。", 17, COLORS["muted"]),
    ]
    connector_y = card_y + card_h / 2
    for i in range(4):
        x1 = xs[i] + card_w + 8
        x2 = xs[i + 1] - 8
        body.append(line(x1, connector_y, x2, connector_y, COLORS["grid"], 5))
        body.append(circle((x1 + x2) / 2, connector_y, 7, COLORS["gold"], "#fffdf8"))
    for x, (number, title, lines, color) in zip(xs, steps, strict=True):
        body.append(step_card(x, card_y, card_w, card_h, number, title, lines, color))
    body.extend(
        [
            rect(78, 412, 1124, 54, COLORS["wash"], COLORS["grid"], rx=14),
            text(104, 446, "ここで得た各条件の値を、次の図2-5の棒グラフで比べる。", 17, COLORS["ink"]),
        ]
    )
    return svg_doc(500, "\n".join(body))


def figure_shuka() -> str:
    rows = [
        ("diagonal_ne", 0.924, 1.40, 0.4678, COLORS["plum_soft"]),
        ("diagonal_nw", 0.924, 1.40, 0.4678, COLORS["plum_soft"]),
        ("column_serpentine", 0.269, -0.61, 0.4574, COLORS["blue"]),
        ("row_serpentine", 0.269, -0.61, 0.4574, COLORS["blue"]),
        ("spiral", 0.197, -0.86, 0.4561, COLORS["low"]),
        ("column_major", 0.132, -1.13, 0.4547, COLORS["low"]),
        ("row_major", 0.132, -1.13, 0.4547, COLORS["low"]),
    ]
    chart_x, chart_y, chart_w = 304, 174, 610
    row_h = 58
    body = [
        text(78, 82, "百人秀歌 10×10置き方比較", 32, COLORS["plum"], 700, "serif"),
        text(78, 116, "S076 源俊頼別歌を枠外に置いた場合。棒は上下左右近傍平均のランダムpercentile。", 17, COLORS["muted"]),
        chip(930, 78, "外す歌 S076", COLORS["cinnabar"], 174),
        chip(1114, 78, "上下左右", COLORS["plum"], 116),
        axis(chart_x, 154, chart_y + row_h * len(rows) + 12, chart_w),
        text(78, 154, "置き方", 14, COLORS["muted"], 700),
        text(970, 154, "平均", 14, COLORS["muted"], 700, anchor="middle"),
        text(1060, 154, "z", 14, COLORS["muted"], 700, anchor="middle"),
        text(1152, 154, "目安", 14, COLORS["muted"], 700, anchor="middle"),
    ]
    for i, (name, pct, z, mean, color) in enumerate(rows):
        y = chart_y + i * row_h
        body.append(text(78, y + 24, layout_label(name), 18, COLORS["ink"], 700))
        body.append(bar(chart_x, y, chart_w, pct, color, label=f"{pct:.3f}"))
        body.append(text(970, y + 21, f"{mean:.4f}", 16, COLORS["ink"], anchor="middle"))
        body.append(text(1060, y + 21, f"{z:.2f}", 16, COLORS["ink"], anchor="middle"))
        note = "上位" if pct > 0.8 else "低め" if pct < 0.3 else "中位"
        body.append(text(1152, y + 21, note, 16, color, 700, anchor="middle"))
    footer_y = 628
    body.extend(
        [
            rect(78, footer_y, 1124, 66, COLORS["wash"], COLORS["grid"], rx=14),
            text(104, footer_y + 40, "図で見ること", 19, COLORS["plum"], 700, "serif"),
            text(218, footer_y + 40, "斜めつづら折り型が上位に来る。一方、行・列型や渦巻き型はこの条件では低めに出る。", 17, COLORS["ink"]),
        ]
    )
    return svg_doc(730, "\n".join(body))


def figure_ogura() -> str:
    rows = [
        ("spiral", 0.9007, 1.302, 0.3724, 0.8870, 1.217, 0.3697),
        ("row_major", 0.8881, 1.238, 0.3720, 0.9441, 1.589, 0.3712),
        ("column_major", 0.8881, 1.238, 0.3720, 0.9441, 1.589, 0.3712),
        ("row_serpentine", 0.7363, 0.633, 0.3685, 0.6315, 0.337, 0.3661),
        ("column_serpentine", 0.7363, 0.633, 0.3685, 0.6315, 0.337, 0.3661),
        ("diagonal_nw", 0.4496, -0.151, 0.3640, 0.6921, 0.489, 0.3667),
        ("diagonal_ne", 0.4496, -0.151, 0.3640, 0.6921, 0.489, 0.3667),
    ]
    chart_x, chart_y, chart_w = 300, 186, 660
    row_h = 60
    body = [
        text(78, 82, "小倉百人一首 10×10置き方比較", 32, COLORS["indigo"], 700, "serif"),
        text(78, 116, "100首をそのまま10×10へ置く。棒は上下左右、点は斜めを含む8近傍のランダムpercentile。", 17, COLORS["muted"]),
        chip(915, 78, "棒: 上下左右", COLORS["blue"], 156),
        chip(1085, 78, "点: 8近傍", COLORS["cinnabar"], 130),
        axis(chart_x, 164, chart_y + row_h * len(rows) + 14, chart_w),
        text(78, 166, "置き方", 14, COLORS["muted"], 700),
        text(1018, 166, "上下左右", 14, COLORS["muted"], 700, anchor="middle"),
        text(1114, 166, "8近傍", 14, COLORS["muted"], 700, anchor="middle"),
        text(1190, 166, "z", 14, COLORS["muted"], 700, anchor="middle"),
    ]
    for i, (name, orth, orth_z, orth_mean, eight, eight_z, eight_mean) in enumerate(rows):
        y = chart_y + i * row_h
        color = COLORS["blue"] if orth >= 0.7 else COLORS["low"]
        body.append(text(78, y + 27, layout_label(name), 18, COLORS["ink"], 700))
        body.append(bar(chart_x, y + 2, chart_w, orth, color, height=22, label=f"{orth:.3f}"))
        dot_x = chart_x + chart_w * eight
        body.append(line(dot_x, y - 5, dot_x, y + 34, COLORS["cinnabar"], 2, opacity=0.65))
        body.append(circle(dot_x, y + 13, 7, COLORS["cinnabar"], "#fffdf8"))
        body.append(text(1018, y + 24, f"{orth:.3f}", 15, COLORS["ink"], anchor="middle"))
        body.append(text(1114, y + 24, f"{eight:.3f}", 15, COLORS["ink"], anchor="middle"))
        body.append(text(1190, y + 24, f"{orth_z:.2f}/{eight_z:.2f}", 14, COLORS["muted"], anchor="middle"))
    footer_y = 640
    body.extend(
        [
            rect(78, footer_y, 1124, 66, COLORS["pale_indigo"], COLORS["indigo"], rx=14, stroke_width=1.2),
            text(104, footer_y + 40, "図で見ること", 19, COLORS["indigo"], 700, "serif"),
            text(218, footer_y + 40, "小倉単体では渦巻き型や通常行・列型が高め。百人秀歌で目立った斜め型は同じようには上がらない。", 17, COLORS["ink"]),
        ]
    )
    return svg_doc(742, "\n".join(body))


def figure_overlay() -> str:
    rows = [
        ("spiral", 0.4780, -0.06, 0.4596, 0.9536, 1.70, 0.3744),
        ("diagonal_nw", 0.9242, 1.44, 0.4678, 0.9218, 1.43, 0.3729),
        ("diagonal_ne", 0.9242, 1.44, 0.4678, 0.9218, 1.43, 0.3729),
        ("row_serpentine", 0.6110, 0.28, 0.4613, 0.8151, 0.90, 0.3698),
        ("column_serpentine", 0.6110, 0.28, 0.4613, 0.8151, 0.90, 0.3698),
        ("row_major", 0.4365, -0.15, 0.4585, 0.7992, 0.84, 0.3695),
        ("column_major", 0.4365, -0.15, 0.4585, 0.7992, 0.84, 0.3695),
    ]
    chart_x, chart_y, chart_w = 310, 188, 620
    row_h = 62
    body = [
        text(78, 82, "百人秀歌基準・共通97首固定比較", 32, COLORS["moss"], 700, "serif"),
        text(78, 116, "共通97首のセルを固定し、百人秀歌側の差し替えセルへ小倉74・99・100を入れる。", 17, COLORS["muted"]),
        chip(860, 78, "百人秀歌", COLORS["moss"], 130),
        chip(1004, 78, "小倉差替", COLORS["cinnabar"], 138),
        chip(1154, 78, "上下左右", COLORS["plum"], 104),
        axis(chart_x, 164, chart_y + row_h * len(rows) + 14, chart_w),
        text(78, 166, "置き方", 14, COLORS["muted"], 700),
        text(982, 166, "百人秀歌", 14, COLORS["muted"], 700, anchor="middle"),
        text(1088, 166, "小倉差替", 14, COLORS["muted"], 700, anchor="middle"),
        text(1190, 166, "小倉z", 14, COLORS["muted"], 700, anchor="middle"),
    ]
    for i, (name, shuka, shuka_z, shuka_mean, ogura, ogura_z, ogura_mean) in enumerate(rows):
        y = chart_y + i * row_h
        body.append(text(78, y + 29, layout_label(name), 18, COLORS["ink"], 700))
        body.append(bar(chart_x, y, chart_w, shuka, COLORS["moss"], height=20, label=f"{shuka:.3f}"))
        body.append(bar(chart_x, y + 26, chart_w, ogura, COLORS["cinnabar"], height=20, label=f"{ogura:.3f}"))
        body.append(text(982, y + 18, f"{shuka:.3f}", 15, COLORS["ink"], anchor="middle"))
        body.append(text(1088, y + 44, f"{ogura:.3f}", 15, COLORS["ink"], anchor="middle"))
        body.append(text(1190, y + 44, f"{ogura_z:.2f}", 15, COLORS["muted"], anchor="middle"))
    footer_y = 644
    body.extend(
        [
            rect(78, footer_y, 540, 70, "#f6efe4", COLORS["gold"], rx=14, stroke_width=1.2),
            text(104, footer_y + 28, "上下左右の最高", 16, COLORS["gold"], 700),
            text(104, footer_y + 54, "渦巻き型 / S053枠外 / 小倉差替 percentile 0.954", 17, COLORS["ink"], 700),
            rect(642, footer_y, 560, 70, "#f1e8ef", COLORS["plum"], rx=14, stroke_width=1.2),
            text(668, footer_y + 28, "8近傍の最高", 16, COLORS["plum"], 700),
            text(668, footer_y + 54, "斜め型 / S076枠外 / 小倉差替 percentile 0.982", 17, COLORS["ink"], 700),
        ]
    )
    return svg_doc(752, "\n".join(body))


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "layout-models-polished.svg": figure_layout_models(),
        "grid-comparison-method-polished.svg": figure_grid_comparison_method(),
        "shuka-10x10-layout-polished.svg": figure_shuka(),
        "ogura-10x10-layout-polished.svg": figure_ogura(),
        "shuka-overlay-workflow-polished.svg": figure_overlay_workflow(),
        "shuka-base-shared-cell-polished.svg": figure_overlay(),
    }
    for filename, content in outputs.items():
        path = FIG_DIR / filename
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
