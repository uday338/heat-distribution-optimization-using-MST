"""
make_pptx.py - Build the 5-minute prelim deck as a real .pptx for Moodle.

Format constraints this file is designed around:
  * 5 minutes, strictly enforced -> 7 presented slides, ~43 s each, plus
    one un-presented reference slide (abbreviations + sources) to jump to
    during the 5 minutes of question time
  * "invest around 4 mins in discussing the results" -> slides 3-6 are results
  * runs on a seminar-hall PC -> Segoe UI / Consolas only (shipped with
    Windows), no web fonts, no internet, images embedded
  * read from the back of a hall -> nothing below 14 pt

Speaker timings are printed in the top rail of every slide so the deck can be
rehearsed against the clock, and the full script is written to
build/SPEAKER_NOTES.md as well as into each slide's notes pane.
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------- palette
BG = RGBColor(0x0D, 0x1A, 0x1F)
PANEL = RGBColor(0x14, 0x26, 0x2D)
LINE = RGBColor(0x24, 0x40, 0x4A)
INK = RGBColor(0xEA, 0xF2, 0xF2)
INK2 = RGBColor(0xB9, 0xCD, 0xD4)
MUTED = RGBColor(0x80, 0x98, 0xA1)
HOT = RGBColor(0xFF, 0x7A, 0x3D)
COOL = RGBColor(0x5A, 0xD2, 0xA8)
WARN = RGBColor(0xFF, 0xCC, 0x55)
BAD = RGBColor(0xFF, 0x6B, 0x6B)

SANS = "Segoe UI"
MONO = "Consolas"

W, H = 13.333, 7.5
M = 0.52                      # page margin
CW = W - 2 * M                # content width

FIGDIR = "results/figures"


# ---------------------------------------------------------------- helpers
def textbox(slide, l, t, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, text, size, color, bold=False, font=SANS, space_after=0,
         first=False, align=PP_ALIGN.LEFT, spacing=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    if spacing:
        p.line_spacing = spacing
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = font
    return p


def rich(tf, parts, size, font=SANS, space_after=0, first=False, spacing=None):
    """One paragraph built from [(text, color, bold), ...]."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(space_after)
    if spacing:
        p.line_spacing = spacing
    for text, color, bold in parts:
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = font
    return p


def rect(slide, l, t, w, h, fill=PANEL, line=LINE, line_w=0.75):
    from pptx.enum.shapes import MSO_SHAPE

    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(l), Inches(t),
                               Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    s.shadow.inherit = False
    return s


def bar(slide, l, t, w, h, color):
    """A flat accent bar (no outline) - used for the left rule on findings."""
    return rect(slide, l, t, w, h, fill=color, line=None)


def new_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])       # blank
    bgf = s.background.fill
    bgf.solid()
    bgf.fore_color.rgb = BG
    return s


def rail(slide, n, section):
    """Top rail: slide number and section only.

    Speaker timings deliberately do NOT appear here - they live in the notes
    pane and in SPEAKER_NOTES.md, where the presenter sees them and the
    audience does not.
    """
    tf = textbox(slide, M, 0.30, CW, 0.3)
    rich(tf, [(f"{n:02d}   ", HOT, True), (section.upper(), INK2, False)],
         11.5, font=MONO, first=True)
    ln = rect(slide, M, 0.66, CW, 0.012, fill=LINE, line=None)
    return ln


def heading(slide, text, top=0.85, size=30, color=INK, width=None):
    tf = textbox(slide, M, top, width or CW, 0.9)
    para(tf, text, size, color, bold=True, first=True, spacing=0.92)
    return tf


def picture(slide, name, left, top, width, max_h=None, centre=False):
    """Place a figure, optionally capped by height and horizontally centred.

    A wide multi-panel figure at full content width can run off the bottom of
    a 16:9 slide, so max_h re-solves the width from the available height
    instead of trusting the width alone.
    """
    path = f"{FIGDIR}/{name}.png"
    with Image.open(path) as im:
        w, h = im.size
    height = width * h / w
    if max_h is not None and height > max_h:
        height = max_h
        width = height * w / h
    if centre:
        left = (W - width) / 2
    slide.shapes.add_picture(path, Inches(left), Inches(top), Inches(width),
                             Inches(height))
    return height


def stat(slide, l, t, w, h, key, value, sub, vcolor=INK):
    rect(slide, l, t, w, h)
    tf = textbox(slide, l + 0.16, t + 0.14, w - 0.32, h - 0.28)
    para(tf, key.upper(), 9.5, MUTED, font=MONO, first=True, space_after=4)
    para(tf, value, 27, vcolor, bold=True, space_after=3, spacing=0.9)
    if sub:
        para(tf, sub, 11.5, INK2, spacing=0.95)


def finding(slide, l, t, w, h, label, text, color=HOT):
    bar(slide, l, t, 0.045, h, color)
    tf = textbox(slide, l + 0.20, t + 0.02, w - 0.24, h)
    para(tf, label.upper(), 9.5, color, font=MONO, first=True, space_after=4)
    para(tf, text, 13, INK, spacing=0.98)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ---------------------------------------------------------------- data
flat = json.load(open("results/tables/flat_results.json"))
hilly = json.load(open("results/tables/hilly_results.json"))
bench = json.load(open("results/tables/benchmark.json"))
hr = hilly["results"]
t1 = hilly["tradeoff"][1]
b1600 = {r["n"]: r for r in bench["rows"]}[1600]

SCRIPT = []


def build():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)

    # ============================================================ 1 TITLE
    s = new_slide(prs)
    tf = textbox(s, M, 0.5, CW, 0.4)
    rich(tf, [("CLL798D / CHL7903  ", MUTED, False),
              ("·  NETWORK SCIENCE  ·  PRELIM REVIEW  ·  09 SEP 2026",
               MUTED, False)], 11.5, font=MONO, first=True)

    tf = textbox(s, M, 1.55, CW, 2.6)
    para(tf, "Minimum spanning trees don't survive", 44, INK, bold=True,
         first=True, spacing=0.92)
    para(tf, "contact with a hillside", 44, HOT, bold=True, spacing=0.92)

    tf = textbox(s, M, 3.70, 10.6, 1.8)
    para(tf, "Graph-theoretic topology optimisation of district-heating pipe "
             "networks — on two real German networks, real satellite elevation "
             "data, and a transport-phenomena cost model.", 16, INK2,
         first=True, spacing=1.05, space_after=11)
    para(tf, "MST = Minimum Spanning Tree    ·    TAC = Total Annual Cost"
             "    ·    SRTM = Shuttle Radar Topography Mission",
         11.5, MUTED, font=MONO, spacing=1.0)

    for i, (k, v, c) in enumerate([
        ("Real networks", "Bremen  ·  Stuttgart", COOL),
        ("Elevation data", "NASA SRTM, 30 m grid", COOL),
        ("Algorithms", "Kruskal · Prim · Steiner", COOL),
    ]):
        x = M + i * (CW / 3)
        tf = textbox(s, x, 5.45, CW / 3 - 0.3, 0.7)
        para(tf, k.upper(), 9.5, MUTED, font=MONO, first=True, space_after=4)
        para(tf, v, 14, c, bold=True)

    rect(s, M, 6.55, CW, 0.012, fill=LINE, line=None)
    tf = textbox(s, M, 6.75, CW, 0.4)
    para(tf, "Pathway 1 — reproduce and extend  ·  Gao et al. (2020), "
             "Chem. Eng. Transactions 81, 277–282", 11.5, MUTED, font=MONO,
         first=True)
    notes(s, "TITLE - 15 s. One line: 'We asked whether the minimum spanning "
             "tree, which is the standard answer for pipe network layout, "
             "survives contact with real terrain. It does not, in three "
             "separate ways.' Then move straight on.")
    SCRIPT.append(("1. Title", "0:15",
        "We asked whether the minimum spanning tree — the standard answer "
        "for pipe-network layout — survives contact with real terrain. It "
        "does not, in three separate ways. Those three are the results."))

    # ============================================================ 2 SETUP
    s = new_slide(prs)
    rail(s, 2, "Setup · problem, data, method")
    heading(s, "A pipe network is a graph, and the topology is the design decision")

    h = picture(s, "fig1_networks", M, 1.72, 7.95)
    tfc = textbox(s, M, 6.80, 7.95, 0.68)
    para(tfc, "A district-heating network pipes hot water from one central "
              "plant to every building in a city district. The buried pipe "
              "layout is 80-90 % of lifetime cost, so choosing the topology "
              "IS the design decision.", 12, INK2, first=True, spacing=1.0)

    x = M + 8.35
    w = CW - 8.35
    tf = textbox(s, x, 1.72, w, 1.75)
    para(tf, "THE GRAPH", 9.5, MUTED, font=MONO, first=True, space_after=6)
    para(tf, "V = 1 plant + 40 substations", 12.5, INK, font=MONO, space_after=3)
    para(tf, "E = every feasible trench route", 12.5, INK, font=MONO,
         space_after=3)
    para(tf, "layout = spanning tree", 12.5, INK, font=MONO, space_after=3)
    rich(tf, [("candidates = ", INK, False), ("41", HOT, True),
              ("^39 ~ 10^62", HOT, True)], 12.5, font=MONO, space_after=9)
    para(tf, "Minimum Spanning Tree (MST): the cheapest loop-free layout "
             "that still reaches every consumer.", 11.5, COOL, spacing=0.98)

    stat(s, x, 3.55, w, 1.20, "Real heat demand",
         "859 GWh/y", "67,314 households (AixDHN, RWTH Aachen)", COOL)
    stat(s, x, 4.83, w, 1.36, "Real elevation",
         "29,248 points", "NASA satellite data, sampled every 25 m along "
         "every candidate route", COOL)
    stat(s, x, 6.27, w, 1.16, "Relief = height range",
         "63 m  vs  282 m", "flat Bremen vs hilly Stuttgart", WARN)

    notes(s, "SETUP - 45 s. Nodes are substations, edges are candidate trenches, "
             "a valid layout is a spanning tree, and there are 10^62 of them so "
             "you need an algorithm. Two REAL German networks from the AixDHN "
             "census dataset, real household demand, real SRTM terrain. Bremen "
             "is flat at 63 m relief, Stuttgart is 282 m. That contrast is the "
             "controlled experiment. Note the star on the left is 3x the pipe "
             "length. Move on quickly.")
    SCRIPT.append(("2. Setup", "0:45",
        "Nodes are substations, edges are candidate trenches, and any valid "
        "layout is a spanning tree — there are 10^62 of them, so you need "
        "an algorithm, and that is why MST is the standard tool. Everything "
        "here is real: two German networks from the AixDHN census dataset, "
        "859 GWh/y of real household demand, and NASA SRTM elevation sampled "
        "every 25 m along every candidate route. Bremen is flat at 63 m of "
        "relief; Stuttgart is 282 m. That contrast is our controlled "
        "experiment — same method, same code, two terrains."))

    # ============================================================ 3 RESULT 1
    s = new_slide(prs)
    rail(s, 3, "Result 1 · terrain-weighted routing")
    heading(s, "A longer tree can be the cheaper tree")

    picture(s, "fig3_terrain_effect", M, 1.72, CW, max_h=3.72, centre=True)

    y = 5.62
    stat(s, M, y, 3.9, 1.28, "Stuttgart · hilly", "−3.0 % cost",
         "total annual cost 23.09 → 22.39 EUR per MWh delivered, for a tree "
         "that is 0.03 km LONGER", HOT)
    stat(s, M + 4.1, y, 3.9, 1.28, "Bremen · flat", "0.0 %",
         "terrain weighting returns the identical tree — the control works",
         COOL)
    finding(s, M + 8.2, y + 0.02, CW - 8.2, 1.26, "What we changed",
            "Edge weight is no longer straight-line distance, but true slope "
            "length × a trenching multiplier that rises with gradient. "
            "Minimum length = minimum cost only on flat ground.")

    notes(s, "RESULT 1 - 55 s. We replaced straight-line distance with "
             "terrain-weighted construction cost: 3D slope length times a "
             "trenching multiplier that rises with gradient, sampled on the "
             "real DEM. In Stuttgart this changes which tree is optimal and "
             "saves 3% of total annual cost - for a tree that is LONGER in "
             "metres. In flat Bremen it returns the identical tree, which is "
             "the control experiment behaving exactly as it must.")
    SCRIPT.append(("3. Terrain", "0:55",
        "First result. We replaced straight-line distance with terrain-weighted "
        "construction cost — true slope length times a trenching multiplier "
        "that rises with gradient, sampled on the real DEM. In Stuttgart that "
        "changes which tree is optimal and saves 3 % of total annual cost, for "
        "a tree that is LONGER in metres. And in flat Bremen it returns the "
        "identical tree — the control behaving exactly as it must. So "
        "minimum length equals minimum cost only on flat ground."))

    # ============================================================ 4 RESULT 2
    s = new_slide(prs)
    rail(s, 4, "Result 2 · hydraulic feasibility")
    heading(s, "In Stuttgart the cost-optimal tree cannot legally be built")

    picture(s, "fig8_pressure_zones", M, 1.72, 8.5)

    x = M + 8.8
    w = CW - 8.8
    tf = textbox(s, x, 1.80, w, 1.9)
    para(tf, "STATIC PRESSURE", 9.5, MUTED, font=MONO, first=True, space_after=7)
    para(tf, "p(z) = p₀ + ρg(z₀ − z)", 14, INK, font=MONO,
         space_after=10)
    rich(tf, [("ρgΔz over 282 m   ", INK2, False),
              ("26.3 bar", BAD, True)], 13.5, font=MONO, space_after=5)
    rich(tf, [("PN16 pipe rating    ", INK2, False),
              ("16.0 bar", INK, True)], 13.5, font=MONO, space_after=5)
    rich(tf, [("one-zone limit      ", INK2, False),
              ("151 m", WARN, True)], 13.5, font=MONO)

    stat(s, x, 4.02, w, 1.58, "Pressure zones needed",
         "2  vs  1",
         "hilly Stuttgart needs two, flat Bremen one. PN16 = Pressure "
         "Nominal: a pipe rated to 16 bar.", WARN)
    finding(s, x, 5.72, w, 1.62, "Spectral bisection at work",
            "Where to split is a balanced minimum cut — separate by "
            "elevation, cut as few pipes as possible. The Fiedler vector of the "
            "Laplacian is the classical relaxation of exactly that.")

    notes(s, "RESULT 2 - 55 s. The binding terrain constraint is NOT pumping "
             "cost. In a closed supply/return loop the static head cancels - "
             "the return leg gives it back - so pumping is friction only. What "
             "does not cancel is the static pressure the pipe must physically "
             "hold: 282 m of relief is 26.3 bar against a PN16 pipe class. One "
             "zone can hold 151 m. So Stuttgart needs two pressure zones and "
             "Bremen needs one. We choose where to split with spectral "
             "bisection of the Laplacian - that is a balanced minimum cut, "
             "because every pipe crossing a boundary needs an exchanger "
             "station. Course material doing real engineering.")
    SCRIPT.append(("4. Feasibility", "0:55",
        "Second result, and this is the one I would emphasise. The binding "
        "constraint from terrain is NOT pumping cost — in a closed "
        "supply/return loop the static head cancels, because the return leg "
        "gives it back, so pumping is friction only. What does not cancel is "
        "the pressure the pipe must physically hold. 282 m of relief is "
        "26.3 bar against a PN16 pipe class rated for 16. One zone can hold "
        "151 m of relief. So Stuttgart needs two pressure zones; Bremen needs "
        "one. And where you split them is a balanced minimum-cut problem, "
        "because every pipe crossing a zone boundary needs a heat-exchanger "
        "station — so we use spectral bisection of the graph Laplacian."))

    # ============================================================ 5 RESULT 3
    s = new_slide(prs)
    rail(s, 5, "Result 3 · reliability")
    heading(s, "Every tree edge is a bridge — and Steiner trees make it worse")

    picture(s, "fig4_reliability", M, 1.70, 8.35)

    x = M + 8.65
    w = CW - 8.65

    # compact N-1 table
    tf = textbox(s, x, 1.78, w, 2.4)
    para(tf, "STUTTGART  ·  N-1 = LOSS OF ANY ONE PIPE", 9.5, MUTED,
         font=MONO, first=True, space_after=6)
    rich(tf, [("topology         ", MUTED, False), ("EUR/MWh  ", MUTED, False),
              ("brdg  ", MUTED, False), ("served", MUTED, False)],
         10, font=MONO, space_after=5)
    for name, cost, br, n1, col in [
        ("Star", "43.72", "40", "95.6 %", COOL),
        ("MST-terrain", "22.39", "40", "0.0 %", BAD),
        ("RSMT Steiner", "20.87", "59", "0.0 %", BAD),
        ("MST-terrain +R", "26.46", "17", "91.9 %", COOL),
    ]:
        rich(tf, [(f"{name:<16}", INK2, False), (f"{cost:>6}  ", INK, False),
                  (f"{br:>3} br  ", MUTED, False), (f"{n1:>7}", col, True)],
             11.5, font=MONO, space_after=5)

    finding(s, x, 4.42, w, 1.68, "Does a Steiner tree fix it?",
            "RSMT = Rectilinear Steiner Minimal Tree: extra junction points "
            "are allowed, so it is shorter and cheapest here. But it is still "
            "a TREE, and it concentrates flow into shared trunks — so it is "
            "MORE fragile, not less.")
    finding(s, x, 6.28, w, 1.15, "Only a loop fixes it — for 4.3 %",
            "One redundant pipe: −57 % Expected Unserved Demand (EUD); "
            "N-1 survival rises 0 → 68 %.", COOL)

    notes(s, "RESULT 3 - 60 s. Structurally, every edge of a tree is a bridge, "
             "so any single pipe failure strands everything downstream. This "
             "answers a question we were asked: does a Steiner tree fix it? No. "
             "A Steiner tree is still a tree. RSMT is the CHEAPEST topology we "
             "found at 20.87 EUR/MWh, but it has 59 bridges against the MST's "
             "40, because Steiner points concentrate flow into shared trunks. "
             "Steiner solves cost; only cycles solve faults. Adding one "
             "redundant pipe costs 4.3% and removes 57% of expected unserved "
             "demand. Note the star is the most RELIABLE topology - that is the "
             "trade-off in one line.")
    SCRIPT.append(("5. Reliability", "1:00",
        "Third result. Structurally, every edge of a tree is a bridge — so "
        "any single pipe failure strands everything downstream. A natural "
        "question is whether a Steiner tree fixes that. It does not: a Steiner "
        "tree is still a tree. In fact the rectilinear Steiner tree is the "
        "cheapest topology we found, at 20.87 EUR per MWh, but it has 59 "
        "bridges against the MST's 40, because Steiner points concentrate flow "
        "into shared trunks. Steiner solves cost; only cycles solve faults. "
        "So we price the cycles: one redundant pipe costs 4.3 % and removes "
        "57 % of expected unserved demand, taking N−1 survival from zero "
        "to 68 %. And notice the star is the most reliable topology of all "
        "— that is the whole trade-off in one line."))

    # ============================================================ 6 RESULT 4
    s = new_slide(prs)
    rail(s, 6, "Result 4 · algorithms and the reproduction")
    heading(s, "Kruskal vs Prim, and two findings against the source paper")

    picture(s, "fig5_algorithms", M, 1.70, 7.15)

    x = M + 7.45
    w = CW - 7.45
    tf = textbox(s, x, 1.78, w, 1.9)
    para(tf, "V = 1600,  E = 1,279,200", 9.5, MUTED, font=MONO, first=True,
         space_after=8)
    for name, val, col in [
        ("Kruskal  union-find", f"{b1600['kruskal_s']*1000:>7.0f} ms", INK),
        ("Prim     binary heap", f"{b1600['prim_s']*1000:>7.0f} ms", BAD),
        ("Prim     dense array", f"{b1600['prim_dense_s']*1000:>7.1f} ms", COOL),
    ]:
        rich(tf, [(f"{name:<21}", INK2, False), (val, col, True)], 12.5,
             font=MONO, space_after=6)

    finding(s, x, 3.72, w, 1.35, "We were wrong, and measured it",
            "We predicted density favours Prim. It favours DENSE Prim — "
            "212× faster than the heap version. Kruskal wins by early exit, "
            "examining 0.7 % of edges.")
    finding(s, x, 5.25, w, 1.0, "Paper finding 1",
            "Table 2 is not self-consistent: the Star/MST cost ratio implies "
            "357 kg/s, the absolute cost implies 87.5 — 3×.", WARN)
    finding(s, x, 6.34, w, 1.02, "Paper finding 2",
            "Their Euclidean Steiner / MST length ratio 0.86555 sits below "
            "the proved Du-Hwang lower bound √3/2 = 0.86603.", WARN)

    notes(s, "RESULT 4 - 50 s. All three MST implementations written from "
             "scratch and verified to return identical tree weight. Our own "
             "earlier slides predicted that a dense graph favours Prim. The "
             "measurement says it favours the DENSE ARRAY Prim - 212x faster "
             "than the heap version - while heap Prim is the worst choice. "
             "Kruskal beats heap Prim by terminating early, examining 0.7% of "
             "the sorted edge list. On the reproduction: we matched the paper's "
             "MST column exactly, but found its Table 2 is not internally "
             "consistent, and its reported Steiner ratio sits below a proved "
             "geometric lower bound. If asked, we also re-derived their heat "
             "transfer coefficient independently to 0.16%.")
    SCRIPT.append(("6. Algorithms", "0:50",
        "Fourth. All three MST variants written from scratch and verified to "
        "return identical tree weight. Our own earlier slides predicted that a "
        "dense graph favours Prim — the measurement says it favours the "
        "DENSE ARRAY Prim, 212 times faster than the heap version, while heap "
        "Prim is actually the worst choice. Kruskal beats it by terminating "
        "early, examining only 0.7 % of the edge list. On the reproduction: we "
        "matched the paper's MST column exactly, but found Table 2 is not "
        "internally self-consistent — a 3× contradiction — and "
        "its reported Steiner ratio sits below a proved geometric bound."))

    # ============================================================ 7 CLOSE
    s = new_slide(prs)
    rail(s, 7, "Conclusion")
    heading(s, "Terrain belongs in the weight. Pressure class belongs in the "
               "constraints. Reliability belongs in the objective.", size=27)

    y = 2.65
    for i, (k, v, sub, c) in enumerate([
        ("Cost", "−3.0 %", "terrain-weighted MST, Stuttgart", HOT),
        ("Feasibility", "2 zones", "PN16 exceeded by 10 bar", WARN),
        ("Reliability", "+4.3 % → −57 %", "cost premium vs unserved demand",
         COOL),
        ("Algorithms", "212×", "dense Prim over heap Prim", COOL),
    ]):
        stat(s, M + i * (CW / 4), y, CW / 4 - 0.24, 1.58, k, v, sub, c)

    tf = textbox(s, M, 4.55, CW, 0.9)
    para(tf, "On flat ground a minimum spanning tree is the right answer. On "
             "real terrain it is neither minimum-cost nor necessarily "
             "buildable — and because every tree edge is a bridge, it is "
             "never robust.", 17, INK, first=True, spacing=1.05)

    rect(s, M, 5.65, CW, 0.012, fill=LINE, line=None)
    tf = textbox(s, M, 5.85, 6.6, 1.2)
    para(tf, "NEXT", 9.5, MUTED, font=MONO, first=True, space_after=6)
    para(tf, "Exact ILP bound on the greedy redundancy  ·  seasonal "
             "part-load  ·  a third district to test the 151 m threshold",
         12.5, INK2, spacing=1.0)
    tf = textbox(s, M + 6.9, 5.85, CW - 6.9, 1.2)
    para(tf, "DATA", 9.5, MUTED, font=MONO, first=True, space_after=6)
    para(tf, "AixDHN (RWTH Aachen, MIT)  ·  NASA SRTM 30 m  ·  "
             "EN 253  ·  Eurostat  ·  Persson & Werner (2011)",
         12.5, INK2, spacing=1.0)

    notes(s, "CLOSE - 20 s. One sentence: terrain belongs in the edge weight, "
             "pressure class belongs in the constraints, reliability belongs in "
             "the objective. Then stop and take questions. Do NOT read the four "
             "numbers aloud - they are there for the audience to scan.")
    SCRIPT.append(("7. Close", "0:20",
        "To close: terrain belongs in the edge weight, pressure class belongs "
        "in the constraints, and reliability belongs in the objective. On flat "
        "ground the MST is the right answer; on real terrain it is neither "
        "minimum-cost nor necessarily buildable, and it is never robust. "
        "Happy to take questions."))

    # ======================================================= 8 REFERENCE
    # Not presented - a backup slide to jump to during the 5 min of QnA.
    s = new_slide(prs)
    rail(s, 8, "Reference · not presented")
    heading(s, "Abbreviations and data sources", size=27)

    tf = textbox(s, M, 1.72, 6.0, 5.3)
    para(tf, "ABBREVIATIONS", 9.5, MUTED, font=MONO, first=True, space_after=9)
    for ab, full in [
        ("MST", "Minimum Spanning Tree"),
        ("ESMT", "Euclidean Steiner Minimal Tree"),
        ("RSMT", "Rectilinear Steiner Minimal Tree"),
        ("TAC", "Total Annual Cost"),
        ("EUD", "Expected Unserved Demand"),
        ("N-1", "loss of any one component (single contingency)"),
        ("DN", "Diameter Nominal - standard pipe size"),
        ("PN16", "Pressure Nominal - pipe rated to 16 bar"),
        ("DEM", "Digital Elevation Model"),
        ("SRTM", "Shuttle Radar Topography Mission (NASA)"),
        ("LP", "Linear Programming"),
        ("lambda_2", "algebraic connectivity (Fiedler value)"),
    ]:
        rich(tf, [(f"{ab:<10}", HOT, True), (full, INK2, False)],
             12.5, font=MONO, space_after=6)

    tf = textbox(s, M + 6.4, 1.72, CW - 6.4, 5.3)
    para(tf, "DATA AND SOURCES - ALL REAL, ALL CITED", 9.5, MUTED, font=MONO,
         first=True, space_after=9)
    for src, what in [
        ("AixDHN", "RWTH Aachen EBC, MIT licence - real German district "
                   "heating areas, demand and census cells"),
        ("NASA SRTM 30 m", "elevation, via the OpenTopoData API"),
        ("EN 253", "European standard for pre-insulated bonded pipe - "
                   "the diameter catalogue"),
        ("Persson & Werner 2011", "district-heating trench cost function"),
        ("Valincius et al. 2015", "pipe failure rates, 0.02-0.31 per km-year"),
        ("Eurostat H2 2025", "German industrial electricity, 0.1922 EUR/kWh"),
        ("Gao et al. 2020", "the reproduced paper, Chem. Eng. Trans. 81"),
    ]:
        para(tf, src, 12.5, COOL, bold=True, space_after=2)
        para(tf, what, 11.5, INK2, spacing=0.96, space_after=8)

    notes(s, "BACKUP - do not present. Jump here in QnA if asked what an "
             "abbreviation means or where a number came from. Full provenance "
             "for every value is in docs/DATA_SOURCES.md.")

    os.makedirs("build", exist_ok=True)
    out = "build/CLL798_prelim_5min.pptx"
    try:
        prs.save(out)
    except PermissionError:
        # PowerPoint holds an exclusive lock while the deck is open. Rather
        # than lose the build, write beside it and say so loudly.
        alt = out.replace(".pptx", "_NEW.pptx")
        prs.save(alt)
        print("")
        print(f"  !! {out} is open in PowerPoint and could not be written.")
        print(f"  !! Wrote {alt} instead. Close PowerPoint and re-run to")
        print("  !! collapse it back to the single canonical filename.")
        print("")
        return alt
    return out


if __name__ == "__main__":
    out = build()
    size = os.path.getsize(out) / 1024 / 1024
    from pptx import Presentation as _P
    n_slides = len(_P(out).slides._sldIdLst)

    with open("build/SPEAKER_NOTES.md", "w", encoding="utf-8") as fh:
        fh.write("# Speaker script — 5 minute prelim\n\n")
        fh.write("Strictly 5 minutes, ~4 of them on results (slides 3–6).\n"
                 "Timings are cumulative in the top-right of each slide.\n\n")
        total = 0
        for title, t, text in SCRIPT:
            m, sec = t.split(":")
            total += int(m) * 60 + int(sec)
            fh.write(f"## {title}  —  {t}\n\n{text}\n\n")
        fh.write(f"\n**Total: {total//60}:{total%60:02d}**\n")
    print(f"wrote {out}  ({size:.1f} MB, {n_slides} slides: "
          f"7 presented + 1 reference)")

    # A box that holds more text than it can show is invisible in the file and
    # obvious on a projector, so the build checks itself.
    sys.path.insert(0, "build")
    from audit_pptx import audit
    print("\nchecking for text overflow ...")
    if audit(out):
        print("  ^ fix these before presenting")
    else:
        print("  no text overflow")
    print("wrote build/SPEAKER_NOTES.md")
