#!/usr/bin/env python3
"""Generate the two README figures as static SVG, from COMMITTED files only.

Standard library only (no matplotlib, no numpy). Deterministic: no timestamps, no randomness, fixed
number formatting, "\n" line endings - running it twice gives byte-identical files.

Figures (written to docs/img/):

1. prospective_paired_deltas.svg
   Forest plot of the paired fixture-level RPS differences of the prospective 2026 benchmark.
   Source table : notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md  ("Paired fixture-level deltas")
   Cross-check  : data/reference/prospective_frozen_input_manifest.csv (market snapshot lead time)

2. power_curve.svg
   Match-clustered power to detect an absolute RPS gain, versus the number of independent matches.
   Source data  : data/reference/international_event_lake_power_analysis.json
   Grid sizes   : the ``m_grid`` literal in scripts/run_international_event_lake_power_analysis.py

   IMPORTANT (honesty note): the committed JSON does NOT store power at every grid size. It stores
   (a) the simulated power at the observed match count and at a 60%-coverage match count, and
   (b) the FIRST grid size at which simulated power reached 0.60 / 0.80 / 0.90. The figure therefore
   plots (a) as filled circles and (b) as open triangles drawn AT the threshold (the simulated estimate
   at that grid size was at or above it; the estimate itself is not stored), and the dashed lines only
   join those committed values as a visual guide. No power value is simulated, fitted or estimated here.
   Every committed value is a single Monte-Carlo estimate, not an exact power.

Nothing in this script fits, tunes, selects or re-scores a model. It only re-draws numbers that are
already committed. It fails closed: if a source cannot be parsed, or a sentence printed on a figure is
no longer true for the parsed numbers, or two labels would overlap, it exits non-zero with a message.

Usage:
    python scripts/make_readme_figures.py            # write both SVGs into docs/img/
    python scripts/make_readme_figures.py --check    # exit 1 if the committed SVGs are out of date
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_MD = ROOT / "notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md"
FROZEN_MANIFEST_CSV = ROOT / "data/reference/prospective_frozen_input_manifest.csv"
POWER_JSON = ROOT / "data/reference/international_event_lake_power_analysis.json"
POWER_BUILDER_PY = ROOT / "scripts/run_international_event_lake_power_analysis.py"
OUT_DIR = ROOT / "docs/img"
FOREST_SVG = OUT_DIR / "prospective_paired_deltas.svg"
POWER_SVG = OUT_DIR / "power_curve.svg"

# ---------------------------------------------------------------------------------------------------
# style
# ---------------------------------------------------------------------------------------------------
WIDTH = 900
PAD = 24
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
INK = "#24292f"
MUTED = "#57606a"
GRID = "#d0d7de"
AXIS = "#8c959f"
BG = "#ffffff"
STROKE = 1.5
# Series colours. Order chosen so that red / green / brown (confusable under colour-vision deficiency)
# are never neighbours; identity is also carried by direct labels and the legend, never by colour alone.
C_BLUE, C_RED, C_GREEN, C_PURPLE, C_BROWN = "#0969da", "#cf222e", "#1a7f37", "#8250df", "#9a6700"
POWER_COLOURS = [C_BLUE, C_GREEN, C_PURPLE, C_RED, MUTED, C_BROWN]  # largest gain first
FOREST_COLOURS = {"M1_B1": C_BLUE, "M2_market": C_BROWN}

MINUS = "\u2212"
EN_DASH = "\u2013"
TIMES = "\u00d7"
ARROW_L = "\u2190"
ARROW_R = "\u2192"

HEADLINE_GAIN = 0.005  # the gain whose numbers are annotated on the power figure
GUIDE_DASH = "5 3"     # series lines on the power figure are visual guides, not simulated curves: drawn dashed


class SourceError(Exception):
    """A committed source file could not be parsed, or contradicts a sentence printed on a figure."""


class LayoutError(Exception):
    """The computed layout would put something outside the viewBox or make two labels overlap."""


# ---------------------------------------------------------------------------------------------------
# tiny SVG canvas with bounding-box bookkeeping
# ---------------------------------------------------------------------------------------------------
def _char_em(ch: str) -> float:
    """Rough advance width (in em) of one character in a Segoe-UI / Helvetica-like sans-serif."""
    if ch == " ":
        return 0.28
    if ch in "ijl|!.,:;'`":
        return 0.27
    if ch in "ftr()[]{}/\\-\"*":
        return 0.37
    if ch in "mw":
        return 0.84
    if ch in "MW":
        return 0.92
    if ch in "%@":
        return 0.88
    if ch.isdigit():
        return 0.56
    if ch in "+=<>~" + MINUS + EN_DASH + TIMES:
        return 0.60
    if ch in ARROW_L + ARROW_R:
        return 1.00
    if ch.isupper():
        return 0.67
    return 0.55


def text_width(s: str, size: float, bold: bool = False) -> float:
    """Estimated rendered width in px. Deliberately a little generous (x1.04) - used for layout."""
    w = sum(_char_em(c) for c in s) * size
    return w * (1.07 if bold else 1.0) * 1.04


def wrap(s: str, size: float, max_width: float, bold: bool = False) -> List[str]:
    lines: List[str] = []
    cur = ""
    for word in s.split():
        trial = word if not cur else cur + " " + word
        if cur and text_width(trial, size, bold) > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def esc(s: str) -> str:
    """XML-escape and turn every non-ASCII character into a numeric reference (file stays pure ASCII)."""
    out = []
    for ch in s:
        if ch == "&":
            out.append("&amp;")
        elif ch == "<":
            out.append("&lt;")
        elif ch == ">":
            out.append("&gt;")
        elif ch == '"':
            out.append("&quot;")
        elif ord(ch) > 126:
            out.append(f"&#{ord(ch)};")
        else:
            out.append(ch)
    return "".join(out)


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


Box = Tuple[float, float, float, float]


def _intersects(a: Box, b: Box, gap: float = 0.0) -> bool:
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


class Canvas:
    def __init__(self, width: int, title: str, desc: str):
        self.width = width
        self.title = title
        self.desc = desc
        self.body: List[str] = []
        self.text_boxes: List[Tuple[str, Box]] = []
        self.xs: List[float] = []
        self.ys: List[float] = []

    def _track(self, pts: Sequence[Tuple[float, float]]) -> None:
        for x, y in pts:
            self.xs.append(x)
            self.ys.append(y)

    # -- primitives -----------------------------------------------------------------------------
    def line(self, x1, y1, x2, y2, stroke=INK, width=STROKE, dash: Optional[str] = None, cap="butt"):
        self._track([(x1, y1), (x2, y2)])
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<line x1="{num(x1)}" y1="{num(y1)}" x2="{num(x2)}" y2="{num(y2)}" '
                         f'stroke="{stroke}" stroke-width="{num(width)}" stroke-linecap="{cap}"{d}/>')

    def rect(self, x, y, w, h, fill="none", stroke="none", width=1.0, rx=0.0):
        self._track([(x, y), (x + w, y + h)])
        self.body.append(f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" '
                         f'rx="{num(rx)}" fill="{fill}" stroke="{stroke}" stroke-width="{num(width)}"/>')

    def circle(self, cx, cy, r, fill, stroke=BG, width=STROKE):
        self._track([(cx - r, cy - r), (cx + r, cy + r)])
        self.body.append(f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="{fill}" '
                         f'stroke="{stroke}" stroke-width="{num(width)}"/>')

    def triangle_up(self, cx, cy, r, stroke, fill=BG, width=STROKE):
        pts = [(cx, cy - r), (cx + r * 0.95, cy + r * 0.72), (cx - r * 0.95, cy + r * 0.72)]
        self._track(pts)
        p = " ".join(f"{num(x)},{num(y)}" for x, y in pts)
        self.body.append(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" '
                         f'stroke-width="{num(width)}" stroke-linejoin="round"/>')

    def polyline(self, pts: Sequence[Tuple[float, float]], stroke, width=STROKE, dash: Optional[str] = None):
        self._track(pts)
        p = " ".join(f"{num(x)},{num(y)}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        cap = "butt" if dash else "round"
        self.body.append(f'<polyline points="{p}" fill="none" stroke="{stroke}" stroke-width="{num(width)}" '
                         f'stroke-linejoin="round" stroke-linecap="{cap}"{d}/>')

    def text(self, x, y, s, size=12.0, anchor="start", bold=False, fill=INK, rotate=False,
             tabular=False, halo=False) -> Box:
        w = text_width(s, size, bold)
        up, down = 0.78 * size, 0.24 * size
        if rotate:  # rotated -90 degrees about (x, y); always centred
            box = (x - up, y - w / 2, x + down, y + w / 2)
        elif anchor == "start":
            box = (x, y - up, x + w, y + down)
        elif anchor == "end":
            box = (x - w, y - up, x, y + down)
        else:
            box = (x - w / 2, y - up, x + w / 2, y + down)
        self.text_boxes.append((s, box))
        self._track([(box[0], box[1]), (box[2], box[3])])
        attrs = [f'x="{num(x)}"', f'y="{num(y)}"', f'font-size="{num(size)}"', f'fill="{fill}"']
        if rotate:
            attrs.append('text-anchor="middle"')
            attrs.append(f'transform="rotate(-90 {num(x)} {num(y)})"')
        elif anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if bold:
            attrs.append('font-weight="600"')
        if tabular:
            attrs.append('style="font-variant-numeric:tabular-nums"')
        if halo:  # white outline painted under the glyphs, so gridlines never run through a label
            attrs.append(f'stroke="{BG}" stroke-width="3.5" stroke-linejoin="round" paint-order="stroke"')
        self.body.append(f'<text {" ".join(attrs)}>{esc(s)}</text>')
        return box

    def paragraph(self, x, y, s, size, max_width, leading, fill=MUTED) -> float:
        """Left-aligned wrapped text; returns the baseline y of the NEXT line."""
        for ln in wrap(s, size, max_width):
            self.text(x, y, ln, size=size, fill=fill)
            y += leading
        return y

    # -- checks + output ------------------------------------------------------------------------
    def check(self, height: float, obstacles: Sequence[Tuple[str, Box]] = (),
              guarded: Sequence[Box] = ()) -> None:
        eps = 0.01
        if min(self.xs) < -eps or max(self.xs) > self.width + eps or min(self.ys) < -eps \
                or max(self.ys) > height + eps:
            raise LayoutError(f"geometry outside the viewBox 0 0 {self.width} {num(height)}: "
                              f"x {min(self.xs):.1f}..{max(self.xs):.1f}, y {min(self.ys):.1f}..{max(self.ys):.1f}")
        tb = self.text_boxes
        for i in range(len(tb)):
            for j in range(i + 1, len(tb)):
                if _intersects(tb[i][1], tb[j][1], gap=1.0):
                    raise LayoutError(f"labels overlap: {tb[i][0]!r} and {tb[j][0]!r}")
        for g in guarded:  # text boxes that sit among the data: must not touch any data mark
            for name, ob in obstacles:
                if _intersects(g, ob, gap=1.5):
                    raise LayoutError(f"a label at {tuple(round(v, 1) for v in g)} touches data mark {name}")

    def render(self, height: float) -> str:
        h = num(math.ceil(height))
        head = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {h}" width="{self.width}" '
            f'height="{h}" role="img" aria-labelledby="fig-title fig-desc" font-family="{FONT}">',
            f'<title id="fig-title">{esc(self.title)}</title>',
            f'<desc id="fig-desc">{esc(self.desc)}</desc>',
            f'<rect x="0.5" y="0.5" width="{num(self.width - 1)}" height="{num(math.ceil(height) - 1)}" '
            f'rx="6" fill="{BG}" stroke="{GRID}" stroke-width="1"/>',
        ]
        return "\n".join(head + self.body + ["</svg>"]) + "\n"


def draw_heading(cv: Canvas, title: str, subtitle: str) -> float:
    """Title + wrapped subtitle; returns the y below which content may start."""
    y = 33.0
    for ln in wrap(title, 17, WIDTH - 2 * PAD, bold=True):
        cv.text(PAD, y, ln, size=17, bold=True)
        y += 22
    y -= 2
    for ln in wrap(subtitle, 12.5, WIDTH - 2 * PAD):
        cv.text(PAD, y, ln, size=12.5, fill=MUTED)
        y += 17
    return y - 17 + 8


# ---------------------------------------------------------------------------------------------------
# FIGURE 1 - source parsing
# ---------------------------------------------------------------------------------------------------
_ROW_RE = re.compile(
    r"^\|\s*(?P<ref>[A-Za-z0-9_]+)\s*\|\s*(?P<model>[A-Za-z0-9_]+)\s*\|\s*(?P<metric>[a-z_]+)\s*\|"
    r"\s*(?P<mean>-?\d+\.\d+)\s*\[\s*(?P<lo>-?\d+\.\d+)\s*,\s*(?P<hi>-?\d+\.\d+)\s*\]\s*\|"
    r"\s*(?P<excl>yes|no)\s*\|\s*$")


def parse_scorecard(path: Path) -> Dict:
    if not path.exists():
        raise SourceError(f"missing source file: {path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    m_n = re.search(r"benchmark on \*\*(\d+)\*\* completed", text)
    m_tier = re.search(r"sample-size tier ([A-D])_([a-z]+)", text)
    m_boot = re.search(r"[Mm]atch-level bootstrap \((\d+)\)", text)
    if not (m_n and m_tier and m_boot):
        raise SourceError(f"{path.name}: could not find the fixture count / tier / bootstrap size sentence")

    head_idx = None
    for i, ln in enumerate(lines):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] == "reference" and cells[1] == "model" and cells[2] == "metric":
            head_idx = i
            break
    if head_idx is None:
        raise SourceError(f"{path.name}: paired-delta table header "
                          f"'| reference | model | metric | ... |' not found")
    section = ""
    for j in range(head_idx - 1, -1, -1):
        if lines[j].startswith("#"):
            section = lines[j]
            break
    if "negative" not in section or "row model better" not in section:
        raise SourceError(f"{path.name}: the table heading no longer states the sign convention "
                          f"'negative => row model better' (found: {section!r})")

    rows = []
    for ln in lines[head_idx + 2:]:
        if not ln.strip().startswith("|"):
            break
        m = _ROW_RE.match(ln.strip())
        if not m:
            raise SourceError(f"{path.name}: cannot parse paired-delta row: {ln!r}")
        r = {"ref": m["ref"], "model": m["model"], "metric": m["metric"], "mean": float(m["mean"]),
             "lo": float(m["lo"]), "hi": float(m["hi"]), "excludes_zero": m["excl"] == "yes"}
        if not (r["lo"] <= r["mean"] <= r["hi"]):
            raise SourceError(f"{path.name}: mean outside its interval in row: {ln!r}")
        if r["excludes_zero"] != (r["lo"] > 0 or r["hi"] < 0):
            raise SourceError(f"{path.name}: 'CI excludes 0' flag contradicts the interval in row: {ln!r}")
        rows.append(r)
    if not rows:
        raise SourceError(f"{path.name}: paired-delta table has no rows")
    rps = [r for r in rows if r["metric"] == "rps"]
    if not rps:
        raise SourceError(f"{path.name}: paired-delta table has no 'rps' rows")
    return {"n_fixtures": int(m_n[1]), "tier": m_tier[1], "tier_word": m_tier[2],
            "n_boot": int(m_boot[1]), "rows": rows, "rps_rows": rps}


COMPARED_MODELS = ("M1_B1", "M2_market", "M3_75_25", "M4_50_50", "M5_25_75")


def market_lead_hours(path: Path, n_expected: int) -> Dict:
    """Re-derive the market snapshot lead time from the committed frozen-input manifest, using the same
    outcome-independent rule as the benchmark (notes/research/prospective_score_harvest_preregistration.md):
    per fixture, the LATEST pre-kickoff source snapshot that carries all five compared models, using only
    rows the manifest marks valid. Returns the median lead (hours) over fixtures."""
    if not path.exists():
        raise SourceError(f"missing source file: {path}")
    snaps: Dict[str, Dict[str, List[dict]]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        need = {"match_id", "model_version", "prediction_timestamp", "source_snapshot_timestamp", "kickoff_utc"}
        if not need.issubset(set(rd.fieldnames or [])):
            raise SourceError(f"{path.name}: expected columns {sorted(need)}")
        for r in rd:
            snaps.setdefault(r["match_id"], {}).setdefault(r["source_snapshot_timestamp"], []).append(r)
    leads = []
    for mid in sorted(snaps):
        best = None
        for ss, rs in snaps[mid].items():
            rs5 = [r for r in rs if r["model_version"] in COMPARED_MODELS]
            if {r["model_version"] for r in rs5} != set(COMPARED_MODELS):
                continue
            if any(r.get("valid", "True") != "True" for r in rs5):
                continue
            ko = datetime.fromisoformat(rs5[0]["kickoff_utc"])
            if not all(datetime.fromisoformat(r["prediction_timestamp"]) < ko for r in rs5):
                continue
            t = datetime.fromisoformat(ss)
            if best is None or t > best[0]:
                best = (t, ko)
        if best is not None:
            leads.append((best[1] - best[0]).total_seconds() / 3600.0)
    if len(leads) != n_expected:
        raise SourceError(f"{path.name}: {len(leads)} fixtures have a common market snapshot, but the "
                          f"scorecard reports {n_expected} scored fixtures")
    leads.sort()
    k = len(leads)
    median = leads[k // 2] if k % 2 else 0.5 * (leads[k // 2 - 1] + leads[k // 2])
    return {"median_h": median, "n": k, "n_over_24h": sum(1 for v in leads if v > 24.0)}


def model_words(model_id: str) -> str:
    if model_id == "M1_B1":
        return "B1 Elo"
    if model_id == "M2_market":
        return "Market (early line)"
    m = re.fullmatch(r"(M\d+)_(\d+)_(\d+)", model_id)
    if m and int(m[2]) + int(m[3]) == 100:
        return f"{m[1]} ({int(m[2])}% Elo / {int(m[3])}% market)"
    raise SourceError(f"unknown model id in the paired-delta table: {model_id!r} (no plain-words label)")


REF_WORDS = {"M1_B1": ("B1 Elo", "Reference: B1 Elo (M1_B1)"),
             "M2_market": ("market", "Reference: market (M2_market)")}


def signed(v: float, nd: int = 4) -> str:
    s = f"{abs(v):.{nd}f}"
    if float(s) == 0.0:
        return s
    return ("+" if v > 0 else MINUS) + s


def nice_symmetric_axis(max_abs: float, max_ticks: int = 8) -> Tuple[float, float, int]:
    """(limit, step, decimals) for a zero-centred axis."""
    raw = 2 * max_abs * 1.08 / max_ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw - 1e-15)
    limit = math.ceil(max_abs * 1.08 / step - 1e-9) * step
    decimals = max(0, -int(math.floor(math.log10(step) + 1e-9)))
    return limit, step, decimals


# ---------------------------------------------------------------------------------------------------
# FIGURE 1 - drawing
# ---------------------------------------------------------------------------------------------------
def build_forest(sc: Dict, lead: Dict) -> Tuple[str, List[str]]:
    rows = sc["rps_rows"]
    report: List[str] = []

    if any(r["excludes_zero"] for r in rows):
        raise SourceError("an RPS interval now excludes zero: the figure subtitle ('every 95% interval "
                          "crosses zero') would be false - review the figure text before regenerating")
    n_all = len(sc["rows"])
    n_all_excl = sum(1 for r in sc["rows"] if r["excludes_zero"])

    groups: List[Tuple[str, List[dict]]] = []
    for ref in ("M1_B1", "M2_market"):
        g = [r for r in rows if r["ref"] == ref]
        if g:
            groups.append((ref, g))
    if sum(len(g) for _, g in groups) != len(rows):
        raise SourceError("paired-delta table has an RPS row with an unexpected reference model")

    title = f"Prospective 2026 benchmark: paired RPS differences (n = {sc['n_fixtures']} fixtures)"
    subtitle = (f"Every 95% interval crosses zero {EN_DASH} no model is distinguishable from B1 Elo or from "
                f"the market at this sample size. {sc['tier_word'].capitalize()} sample (the lab's own tier "
                f"{sc['tier']}). Market = early line, not a closing line: snapshot taken a median of "
                f"~{round(lead['median_h'])} h before kickoff.")
    desc = (f"Forest plot of {len(rows)} paired ranked-probability-score differences on {sc['n_fixtures']} "
            f"World Cup 2026 group fixtures. Every 95% bootstrap interval includes zero.")
    cv = Canvas(WIDTH, title, desc)
    y = draw_heading(cv, title, subtitle)

    label_size, value_size = 12.5, 12.0
    labels = {id(r): f"{model_words(r['model'])} vs {REF_WORDS[r['ref']][0]}" for r in rows}
    values = {id(r): f"{signed(r['mean'])}  [{signed(r['lo'])}, {signed(r['hi'])}]" for r in rows}
    value_head = "mean difference [95% CI]"
    label_w = max([text_width(labels[id(r)], label_size) for r in rows] +
                  [text_width(REF_WORDS[ref][1], label_size, bold=True) for ref, _ in groups])
    value_w = max([text_width(v, value_size) for v in values.values()] + [text_width(value_head, 11, True)])
    x0 = PAD + label_w + 18
    x1 = WIDTH - PAD - value_w - 18
    if x1 - x0 < 260:
        raise LayoutError("forest plot: labels leave less than 260 px for the plot")

    limit, step, dec = nice_symmetric_axis(max(max(abs(r["lo"]), abs(r["hi"])) for r in rows))

    def px(v: float) -> float:
        return x0 + (v + limit) / (2 * limit) * (x1 - x0)

    strip_h, head_h, row_h, group_gap = 24.0, 23.0, 23.0, 8.0
    top = y + 12
    rows_top = top + strip_h
    n_rows = sum(len(g) for _, g in groups)
    axis_y = rows_top + len(groups) * head_h + n_rows * row_h + (len(groups) - 1) * group_gap + 6

    # legend strip (inside the plot area, above the first row; no data is ever drawn in it)
    key = "point = mean difference;  bar = 95% match-level bootstrap interval"
    key_w = 30 + 8 + text_width(key, 11)
    kx = (x0 + x1) / 2 - key_w / 2
    ky = top + strip_h / 2
    cv.line(kx, ky, kx + 30, ky, stroke=MUTED)
    cv.line(kx, ky - 4, kx, ky + 4, stroke=MUTED)
    cv.line(kx + 30, ky - 4, kx + 30, ky + 4, stroke=MUTED)
    cv.circle(kx + 15, ky, 4, fill=MUTED)
    cv.text(kx + 38, ky + 4, key, size=11, fill=MUTED)
    cv.text(WIDTH - PAD, ky + 4, value_head, size=11, anchor="end", bold=True, fill=MUTED)

    # gridlines, zero line, axis
    n_ticks = int(round(limit / step))
    for k in range(-n_ticks, n_ticks + 1):
        v = k * step
        if k != 0:
            cv.line(px(v), rows_top, px(v), axis_y, stroke=GRID, width=1)
    cv.line(px(0), rows_top, px(0), axis_y, stroke=MUTED, width=STROKE)
    cv.line(x0, axis_y, x1, axis_y, stroke=AXIS, width=1)
    for k in range(-n_ticks, n_ticks + 1):
        v = k * step
        cv.line(px(v), axis_y, px(v), axis_y + 4, stroke=AXIS, width=1)
        lab = "0" if k == 0 else (MINUS if v < 0 else "") + f"{abs(v):.{dec}f}"
        cv.text(px(v), axis_y + 17, lab, size=11.5, anchor="middle", fill=MUTED, tabular=True)

    # rows
    yy = rows_top
    for gi, (ref, g) in enumerate(groups):
        colour = FOREST_COLOURS[ref]
        cv.text(PAD, yy + head_h / 2 + 4.5, REF_WORDS[ref][1], size=label_size, bold=True)
        yy += head_h
        for r in g:
            cy = yy + row_h / 2
            xl, xm, xh = px(r["lo"]), px(r["mean"]), px(r["hi"])
            if not (x0 <= xl <= xm <= xh <= x1 and xl < xh):
                raise LayoutError(f"forest plot: interval not drawn left-to-right inside the plot: {r}")
            cv.text(PAD + 12, cy + 4.5, labels[id(r)], size=label_size)
            cv.line(xl, cy, xh, cy, stroke=colour, width=STROKE)
            cv.line(xl, cy - 4.5, xl, cy + 4.5, stroke=colour, width=STROKE)
            cv.line(xh, cy - 4.5, xh, cy + 4.5, stroke=colour, width=STROKE)
            cv.circle(xm, cy, 4.5, fill=colour)
            cv.text(WIDTH - PAD, cy + 4.5, values[id(r)], size=value_size, anchor="end", tabular=True)
            report.append(f"  {r['ref']:>9} <- {r['model']:<9} rps  mean {r['mean']:+.4f}  "
                          f"CI [{r['lo']:+.4f}, {r['hi']:+.4f}]  x = {xl:.1f} .. {xm:.1f} .. {xh:.1f}")
            yy += row_h
        if gi < len(groups) - 1:
            yy += group_gap

    # direction hints + axis label
    cv.text(x0, axis_y + 35, f"{ARROW_L} row model better", size=11, fill=MUTED)
    cv.text(x1, axis_y + 35, f"reference better {ARROW_R}", size=11, anchor="end", fill=MUTED)
    cv.text((x0 + x1) / 2, axis_y + 56, "RPS difference (negative = row model better)", size=12,
            anchor="middle")

    # footnotes
    if n_all_excl == 0:
        excl_words = f"none of the {n_all} reported paired differences has an interval that excludes zero."
    else:
        excl_words = f"{n_all_excl} of the {n_all} reported paired differences have an interval that excludes zero."
    fy = axis_y + 80
    fy = cv.paragraph(
        PAD, fy,
        f"B1 Elo = ternary-Elo model with no fitted parameters; market = no-vig bookmaker consensus; "
        f"M3{EN_DASH}M5 = fixed, untuned blends of the two. "
        f"RPS = ranked probability score (lower is better). Intervals: match-level percentile bootstrap, "
        f"{sc['n_boot']:,} resamples, fixture = unit of analysis. Across all metrics in the source table, "
        f"{excl_words} "
        f"Forecast-quality metrics only {EN_DASH} research, not betting advice.",
        size=11, max_width=WIDTH - 2 * PAD, leading=14.5)
    fy = cv.paragraph(
        PAD, fy + 2,
        "Source: notes/research/PROSPECTIVE_SHADOW_SCORECARD_V1.md (paired fixture-level deltas, RPS rows); "
        "lead time from data/reference/prospective_frozen_input_manifest.csv. "
        "Regenerate: python scripts/make_readme_figures.py",
        size=11, max_width=WIDTH - 2 * PAD, leading=14.5)
    height = fy - 14.5 + 16

    cv.check(height)
    head = [f"FIGURE 1  {FOREST_SVG.relative_to(ROOT).as_posix()}",
            f"  source: {SCORECARD_MD.relative_to(ROOT).as_posix()}",
            f"  n fixtures {sc['n_fixtures']}, tier {sc['tier']}_{sc['tier_word']}, bootstrap {sc['n_boot']}; "
            f"{n_all} paired deltas parsed, {n_all_excl} exclude zero; {len(rows)} RPS rows plotted",
            f"  market lead time: median {lead['median_h']:.1f} h over {lead['n']} fixtures "
            f"({lead['n_over_24h']} more than 24 h before kickoff)",
            f"  x axis {-limit:+.{dec}f} .. {limit:+.{dec}f} step {step:.{dec}f}; plot x {x0:.1f} .. {x1:.1f}; "
            f"zero line x = {px(0):.1f}; viewBox 0 0 {WIDTH} {math.ceil(height)}"]
    return cv.render(height), head + report


# ---------------------------------------------------------------------------------------------------
# FIGURE 2 - source parsing
# ---------------------------------------------------------------------------------------------------
def parse_power(json_path: Path, builder_path: Path) -> Dict:
    if not json_path.exists():
        raise SourceError(f"missing source file: {json_path}")
    try:
        d = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SourceError(f"{json_path.name}: invalid JSON ({e})") from e
    need = ["bootstrap_unit", "template_info", "observed_M_matches", "abs_rps_gain_grid",
            "current_power_at_observed_M", "matches_needed_for_power", "coverage_imbalance_effect", "seeds"]
    missing = [k for k in need if k not in d]
    if missing:
        raise SourceError(f"{json_path.name}: missing keys {missing}")
    if d["bootstrap_unit"] != "match":
        raise SourceError(f"{json_path.name}: bootstrap_unit is {d['bootstrap_unit']!r}, not 'match' - "
                          f"the figure's 'match-clustered' wording would be false")
    ti = d["template_info"]
    for k in ("n_matches", "n_competitions", "observed_sd_delta", "reference_model", "candidate_model"):
        if k not in ti:
            raise SourceError(f"{json_path.name}: template_info.{k} missing")
    m_obs = int(d["observed_M_matches"])
    if m_obs != int(ti["n_matches"]):
        raise SourceError(f"{json_path.name}: observed_M_matches != template_info.n_matches")

    if not builder_path.exists():
        raise SourceError(f"missing source file: {builder_path}")
    mg = re.search(r"^\s*m_grid\s*=\s*\[([0-9,\s]+)\]", builder_path.read_text(encoding="utf-8"), re.M)
    if not mg:
        raise SourceError(f"{builder_path.name}: could not find the 'm_grid = [...]' literal")
    grid = [int(v) for v in mg[1].replace(" ", "").split(",") if v]
    if grid != sorted(grid) or len(grid) < 2:
        raise SourceError(f"{builder_path.name}: m_grid is not an increasing list")

    series = []
    for g in d["abs_rps_gain_grid"]:
        key = f"{g:.4f}"
        try:
            p_obs = float(d["current_power_at_observed_M"][key])
            cov = d["coverage_imbalance_effect"][key]
            needed = d["matches_needed_for_power"][key]
        except KeyError as e:
            raise SourceError(f"{json_path.name}: gain {key} missing under {e}") from e
        if int(cov["M_full"]) != m_obs or float(cov["power_full_cohort"]) != p_obs:
            raise SourceError(f"{json_path.name}: coverage block disagrees with current power for gain {key}")
        pts: Dict[int, Tuple[float, str]] = {}
        for tgt in (60, 80, 90):
            m_need = needed.get(f"{tgt}pct")
            if m_need is None:
                continue
            if int(m_need) not in grid:
                raise SourceError(f"{json_path.name}: matches_needed {m_need} is not a grid size {grid}")
            pts[int(m_need)] = (tgt / 100.0, "at_least")          # later (higher) targets overwrite
        pts[int(cov["M_at_60pct"])] = (float(cov["power_at_60pct_coverage"]), "simulated")
        pts[m_obs] = (p_obs, "simulated")
        for m_, (p_, _) in pts.items():
            if not (0.0 <= p_ <= 1.0) or m_ <= 0:
                raise SourceError(f"{json_path.name}: impossible value for gain {key}: M={m_}, power={p_}")
        series.append({"gain": float(g), "key": key, "needed": needed, "p_obs": p_obs,
                       "points": [(m_, pts[m_][0], pts[m_][1]) for m_ in sorted(pts)]})
    if not series:
        raise SourceError(f"{json_path.name}: abs_rps_gain_grid is empty")
    series.sort(key=lambda s: -s["gain"])
    return {"m_obs": m_obs, "m_cov": int(d["coverage_imbalance_effect"][series[0]["key"]]["M_at_60pct"]),
            "grid": grid, "series": series, "template": ti, "seeds": d["seeds"],
            "uncertainty": d.get("power_estimate_uncertainty", {})}


def gain_label(g: float) -> str:
    s = f"{g:.4f}".rstrip("0")
    while len(s.split(".")[1]) < 3:
        s += "0"
    return s


def nice_log_bounds(lo: float, hi: float) -> Tuple[int, int, List[int]]:
    nice = [m * 10 ** e for e in range(0, 7) for m in (1, 2, 5)]
    a = max(v for v in nice if v <= lo)
    b = min(v for v in nice if v >= hi)
    return a, b, [v for v in nice if a <= v <= b]


# ---------------------------------------------------------------------------------------------------
# FIGURE 2 - drawing
# ---------------------------------------------------------------------------------------------------
def build_power(pw: Dict) -> Tuple[str, List[str]]:
    ti, series, m_obs, grid = pw["template"], pw["series"], pw["m_obs"], pw["grid"]
    if len(series) > len(POWER_COLOURS):
        raise LayoutError(f"{len(series)} effect sizes but only {len(POWER_COLOURS)} colours defined")
    head_s = next((s for s in series if abs(s["gain"] - HEADLINE_GAIN) < 1e-12), None)
    if head_s is None:
        raise SourceError(f"headline gain {HEADLINE_GAIN} is not in abs_rps_gain_grid")

    ref_id = str(ti["reference_model"]).split(".")[-1]
    cand_id = str(ti["candidate_model"]).split(".")[-1]
    if (ref_id, cand_id) != ("e2", "e7") or "event_process" not in str(ti["candidate_model"]):
        raise SourceError(f"noise template is {cand_id} minus {ref_id}, not event-process e7 minus the e2 "
                          f"remaining-time Poisson reference - review the subtitle wording")
    title = "How many matches would it take? Match-clustered power to detect an RPS improvement"
    subtitle = (f"Noise template: the per-match paired RPS differences actually observed on the {m_obs} "
                f"eligible internationals ({ti['n_competitions']} tournaments; event-process model {cand_id} "
                f"minus the {ref_id} remaining-time Poisson reference), centred to zero, SD "
                f"{float(ti['observed_sd_delta']):.3f}. "
                f"The independent unit is the match, not the in-play snapshot: every simulated dataset is "
                f"resampled by match. \"Detect\" = the match-level bootstrap 95% interval lies wholly below "
                f"zero.")
    desc = (f"Power against number of matches on a log axis for {len(series)} absolute RPS gains. With the "
            f"{m_obs} matches available, power for a {gain_label(HEADLINE_GAIN)} gain is {head_s['p_obs']:.2f}.")
    cv = Canvas(WIDTH, title, desc)
    y = draw_heading(cv, title, subtitle)

    all_m = [m for s in series for m, _, _ in s["points"]]
    lo, hi, xticks = nice_log_bounds(min(all_m), max(max(all_m), m_obs))

    end_label_w = max(text_width(f"gain {gain_label(s['gain'])}", 11.5) for s in series)
    x0 = PAD + 16 + 8 + text_width("0.0", 11.5) + 8
    x1 = WIDTH - PAD - end_label_w - 12
    inset = 16.0
    frame_top = y + 12
    band_h = 46.0                     # legend band: inside the frame, above power = 1.0, never holds data
    y_top = frame_top + band_h        # power = 1
    y_bot = y_top + 236.0             # power = 0

    def px(m: float) -> float:
        return x0 + inset + (math.log10(m) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) \
            * (x1 - x0 - 2 * inset)

    def py(p: float) -> float:
        return y_bot - p * (y_bot - y_top)

    # frame, gridlines, axes
    cv.rect(x0, frame_top, x1 - x0, y_bot - frame_top, fill="none", stroke=GRID, width=1)
    for k in range(0, 6):
        p = k / 5
        if 0 < k:
            cv.line(x0, py(p), x1, py(p), stroke=GRID, width=1)
        cv.text(x0 - 8, py(p) + 4, f"{p:.1f}", size=11.5, anchor="end", fill=MUTED, tabular=True)
    for m in xticks:
        cv.line(px(m), y_top, px(m), y_bot, stroke=GRID, width=1)
        cv.line(px(m), y_bot, px(m), y_bot + 4, stroke=AXIS, width=1)
        cv.text(px(m), y_bot + 17, f"{m:,}", size=11.5, anchor="middle", fill=MUTED, tabular=True)
    cv.line(x0, y_bot, x1, y_bot, stroke=AXIS, width=1)
    cv.text(PAD + 10, (y_top + y_bot) / 2, "Power (chance of detecting the gain)", size=12, rotate=True)
    cv.text((x0 + x1) / 2, y_bot + 38, "Number of independent matches (log scale)", size=12, anchor="middle")

    # legend band (two rows, centred; widths computed from the entries)
    guarded: List[Box] = []
    row1_y, row2_y = frame_top + 17, frame_top + 35
    lead_txt = "Absolute RPS gain to detect:"
    entry_w = [26 + 5 + text_width(gain_label(s["gain"]), 11.5) for s in series]
    total = text_width(lead_txt, 11.5, bold=True) + 12 + sum(entry_w) + 14 * (len(series) - 1)
    if total > x1 - x0 - 16:
        raise LayoutError("power figure: the legend row does not fit inside the plot frame")
    lx = (x0 + x1) / 2 - total / 2
    cv.text(lx, row1_y + 4, lead_txt, size=11.5, bold=True)
    lx += text_width(lead_txt, 11.5, bold=True) + 12
    for s, colour, w in zip(series, POWER_COLOURS, entry_w):
        cv.line(lx, row1_y, lx + 26, row1_y, stroke=colour, width=STROKE, dash=GUIDE_DASH)
        cv.circle(lx + 13, row1_y, 4, fill=colour)
        cv.text(lx + 31, row1_y + 4, gain_label(s["gain"]), size=11.5, tabular=True)
        lx += w + 14
    k1 = "simulated power at that match count"
    k2 = "first grid size whose estimate reached 0.60 / 0.80 / 0.90 (drawn at the threshold)"
    total2 = 10 + 6 + text_width(k1, 11) + 22 + 11 + 6 + text_width(k2, 11)
    if total2 > x1 - x0 - 16:
        raise LayoutError("power figure: the marker key does not fit inside the plot frame")
    lx = (x0 + x1) / 2 - total2 / 2
    cv.circle(lx + 5, row2_y, 4, fill=MUTED)
    cv.text(lx + 16, row2_y + 4, k1, size=11, fill=MUTED)
    lx += 16 + text_width(k1, 11) + 22
    cv.triangle_up(lx + 5.5, row2_y + 0.5, 5.5, stroke=MUTED)
    cv.text(lx + 17, row2_y + 4, k2, size=11, fill=MUTED)

    # reference lines: 0.80 target and the matches actually available
    cv.line(x0, py(0.8), x1, py(0.8), stroke=MUTED, width=STROKE, dash="6 4")
    guarded.append(cv.text(x0 + 8, py(0.8) - 6, "0.80 power (conventional target)", size=11, fill=MUTED,
                           halo=True))
    cv.line(px(m_obs), y_top, px(m_obs), y_bot, stroke=INK, width=STROKE, dash="3 3")
    guarded.append(cv.text(px(m_obs) + 7, y_top + 15, f"{m_obs} matches available", size=11.5, bold=True,
                           halo=True))

    # data: lines first, then markers on top
    obstacles: List[Tuple[str, Box]] = []
    report: List[str] = []
    for s, colour in zip(series, POWER_COLOURS):
        pts = [(px(m), py(p)) for m, p, _ in s["points"]]
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xb <= xa:
                raise LayoutError("power figure: a series is not drawn left-to-right")
            n = max(2, int(math.hypot(xb - xa, yb - ya) / 3))
            for i in range(n + 1):
                t = i / n
                qx, qy = xa + t * (xb - xa), ya + t * (yb - ya)
                obstacles.append((f"line {s['key']}", (qx - 1, qy - 1, qx + 1, qy + 1)))
        cv.polyline(pts, stroke=colour, dash=GUIDE_DASH)
    for s, colour in zip(series, POWER_COLOURS):
        for (m, p, kind) in s["points"]:
            x_, y_ = px(m), py(p)
            if kind == "simulated":
                cv.circle(x_, y_, 4, fill=colour)
            else:
                cv.triangle_up(x_, y_ + 0.5, 5.5, stroke=colour)
            obstacles.append((f"marker {s['key']} M={m}", (x_ - 5.5, y_ - 5.5, x_ + 5.5, y_ + 5.5)))
            report.append(f"  gain {s['key']}  M = {m:>5}  power {'>=' if kind == 'at_least' else ' ='} {p:.4f}"
                          f"  ({kind})  x = {x_:.1f}, y = {y_:.1f}")

    # direct labels for the series that extend beyond the observed match count
    for s in series:
        m_last, p_last, _ = s["points"][-1]
        if m_last <= m_obs:
            continue
        lab = f"gain {gain_label(s['gain'])}"
        if m_last >= hi:
            guarded.append(cv.text(px(m_last) + 10, py(p_last) + 4, lab, size=11.5))
        else:
            guarded.append(cv.text(px(m_last), py(p_last) - 11, lab, size=11.5, anchor="middle", halo=True))

    # the two headline numbers, read straight from the JSON
    guarded.append(cv.text(px(m_obs) - 9, py(head_s["p_obs"]) - 12,
                           f"power {head_s['p_obs']:.2f} for a {gain_label(HEADLINE_GAIN)} gain",
                           size=11.5, anchor="end", halo=True))
    m80 = head_s["needed"].get("80pct")
    if m80 is not None:
        guarded.append(cv.text(px(m80) - 11, py(0.8) - 7, f"0.80 first reached at {int(m80):,}",
                               size=11.5, anchor="end", halo=True))

    # footnotes (every clause is computed from the parsed data)
    never60 = [s for s in series if s["needed"].get("60pct") is None]
    reach60 = [s for s in series if s["needed"].get("60pct") is not None]
    notes = ["Dashed lines only join committed values: a visual guide, not simulated curves."]
    if never60:
        if reach60 and max(s["gain"] for s in never60) > min(s["gain"] for s in reach60):
            raise SourceError("gains that never reach 0.60 power are not the smallest ones - review the footnote")
        notes.append(f"Gains of {gain_label(max(s['gain'] for s in never60))} or smaller never reached 0.60 "
                     f"power on the grid (up to {max(grid):,} matches).")
    unc = pw["uncertainty"].get(head_s["key"])
    if unc:
        notes.append(f"Each value is one Monte-Carlo estimate: {unc['k_streams']} repeats at {m_obs} "
                     f"matches ranged {float(unc['min']):.3f}{EN_DASH}{float(unc['max']):.3f} for the "
                     f"{gain_label(HEADLINE_GAIN)} gain.")
    notes.append(f"{pw['m_cov']} matches = the 60%-coverage scenario.")
    fy = y_bot + 62
    fy = cv.paragraph(PAD, fy, " ".join(notes), size=11, max_width=WIDTH - 2 * PAD, leading=14.5)
    fy = cv.paragraph(
        PAD, fy + 2,
        f"Source: data/reference/international_event_lake_power_analysis.json ({pw['seeds']['n_outer']} "
        f"simulated datasets {TIMES} {pw['seeds']['b_inner']} bootstrap resamples per estimate; grid sizes from "
        f"scripts/run_international_event_lake_power_analysis.py). "
        f"Regenerate: python scripts/make_readme_figures.py",
        size=11, max_width=WIDTH - 2 * PAD, leading=14.5)
    height = fy - 14.5 + 16

    cv.check(height, obstacles=obstacles, guarded=guarded)
    head = [f"FIGURE 2  {POWER_SVG.relative_to(ROOT).as_posix()}",
            f"  source: {POWER_JSON.relative_to(ROOT).as_posix()}",
            f"  observed M = {m_obs}; 60%-coverage M = {pw['m_cov']}; template {cand_id} minus {ref_id}, "
            f"SD {float(ti['observed_sd_delta']):.5f}, {ti['n_competitions']} competitions; "
            f"n_outer {pw['seeds']['n_outer']}, b_inner {pw['seeds']['b_inner']}",
            f"  grid sizes (from the builder script): {grid}",
            f"  x axis log {lo} .. {hi}, ticks {xticks}; plot x {x0:.1f} .. {x1:.1f}, y {y_top:.1f} (power 1) .. "
            f"{y_bot:.1f} (power 0); 0.80 line y = {py(0.8):.1f}; M = {m_obs} line x = {px(m_obs):.1f}; "
            f"viewBox 0 0 {WIDTH} {math.ceil(height)}"]
    return cv.render(height), head + report


# ---------------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the SVGs in docs/img/ differ from what would be generated")
    args = ap.parse_args(argv)

    try:
        sc = parse_scorecard(SCORECARD_MD)
        lead = market_lead_hours(FROZEN_MANIFEST_CSV, sc["n_fixtures"])
        forest_svg, forest_report = build_forest(sc, lead)
        power_svg, power_report = build_power(parse_power(POWER_JSON, POWER_BUILDER_PY))
    except SourceError as e:
        print(f"ERROR (source): {e}", file=sys.stderr)
        return 2
    except LayoutError as e:
        print(f"ERROR (layout): {e}", file=sys.stderr)
        return 3

    print("\n".join(forest_report))
    print("\n".join(power_report))

    outputs = [(FOREST_SVG, forest_svg), (POWER_SVG, power_svg)]
    if args.check:
        stale = [p for p, svg in outputs if not p.exists() or p.read_text(encoding="utf-8") != svg]
        for p in stale:
            print(f"OUT OF DATE: {p.relative_to(ROOT).as_posix()}", file=sys.stderr)
        if not stale:
            print("check: docs/img SVGs are up to date")
        return 1 if stale else 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p, svg in outputs:
        with p.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        print(f"wrote {p.relative_to(ROOT).as_posix()} ({len(svg.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
