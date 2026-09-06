"""Generate the prelim presentation deck with figures inlined as data URIs."""
import base64
import json
import os

FIG = "results/figures/web"
SRC = "results/figures"


def build_web_figures(max_width=1500, quality=82):
    """Down-scale the full-resolution PNGs into JPEGs small enough to inline.

    Base64 inflates a file by ~33 %, and the published page has a 16 MB cap, so
    the figures are re-encoded rather than embedded at print resolution. Run
    automatically so a fresh clone can rebuild the deck without extra steps.
    """
    from PIL import Image

    os.makedirs(FIG, exist_ok=True)
    for f in sorted(os.listdir(SRC)):
        if not f.endswith(".png"):
            continue
        out = os.path.join(FIG, f.replace(".png", ".jpg"))
        if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(
                os.path.join(SRC, f)):
            continue
        im = Image.open(os.path.join(SRC, f)).convert("RGB")
        w, h = im.size
        k = min(1.0, max_width / w)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
        im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
        print(f"  web figure {out}  {os.path.getsize(out)/1024:.0f} KB")


def img(name):
    with open(f"{FIG}/{name}.jpg", "rb") as fh:
        return "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode()


build_web_figures()

flat = json.load(open("results/tables/flat_results.json"))
hilly = json.load(open("results/tables/hilly_results.json"))
bench = json.load(open("results/tables/benchmark.json"))

CSS = """
:root{
  --ground:#0d1a1f; --ground-2:#0a1418; --panel:#14262d;
  --line:#24404a; --line-soft:#1b333b;
  --ink:#eaf2f2; --ink-2:#b9cdd4; --muted:#8098a1;
  --hot:#ff7a3d; --cool:#5ad2a8; --blue:#79a9ff; --warn:#ffcc55; --bad:#ff6b6b;
  --mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:'IBM Plex Sans',system-ui,-apple-system,Segoe UI,sans-serif;
  --cond:'IBM Plex Sans Condensed','IBM Plex Sans',system-ui,sans-serif;
  --pad:clamp(26px,4vw,60px);
}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);
  -webkit-font-smoothing:antialiased;line-height:1.5;margin:0}
.deck{scroll-snap-type:y mandatory;overflow-y:auto;height:100vh;scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){.deck{scroll-behavior:auto}}
.slide{scroll-snap-align:start;scroll-snap-stop:always;min-height:100vh;
  padding:var(--pad) var(--pad) 58px;display:flex;flex-direction:column;
  gap:20px;position:relative;border-bottom:1px solid var(--line-soft)}
.rail{display:flex;align-items:baseline;gap:14px;font-family:var(--mono);
  font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
  border-bottom:1px solid var(--line-soft);padding-bottom:10px;flex-wrap:wrap}
.rail .n{color:var(--hot);font-weight:600}
.rail .sec{color:var(--ink-2)}
.rail .tag{margin-left:auto;color:var(--muted);letter-spacing:.1em}
h1{font-family:var(--cond);font-weight:600;font-size:clamp(32px,5.4vw,72px);
  line-height:1.03;margin:0;letter-spacing:-.015em;text-wrap:balance}
h2{font-family:var(--cond);font-weight:600;font-size:clamp(22px,3vw,38px);
  line-height:1.12;margin:0;letter-spacing:-.01em;text-wrap:balance}
h3{font-family:var(--cond);font-weight:600;font-size:17px;margin:0;color:var(--ink)}
p{margin:0;color:var(--ink-2);max-width:76ch}
.lede{font-size:clamp(15px,1.3vw,18px);color:var(--ink-2);max-width:82ch}
.mono{font-family:var(--mono)}
.grid{display:grid;gap:17px}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
@media (max-width:900px){.g2,.g3,.g4{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:3px;
  padding:17px 19px;display:flex;flex-direction:column;gap:9px}
.stat{display:flex;flex-direction:column;gap:4px}
.stat .v{font-family:var(--cond);font-weight:600;font-size:clamp(27px,3.3vw,42px);
  line-height:1;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat .k{font-family:var(--mono);font-size:10.5px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--muted)}
.stat .sub{font-size:12.5px;color:var(--ink-2)}
.hot{color:var(--hot)} .cool{color:var(--cool)} .blue{color:var(--blue)}
.warn{color:var(--warn)} .bad{color:var(--bad)} .dim{color:var(--muted)}
figure{margin:0;display:flex;flex-direction:column;gap:8px;min-height:0}
figure img{width:100%;height:auto;display:block;border:1px solid var(--line);
  border-radius:2px;background:#fcfcfb}
figcaption{font-size:12px;color:var(--muted);font-family:var(--mono)}
.finding{border-left:3px solid var(--hot);padding:12px 0 12px 16px;
  background:linear-gradient(90deg,rgba(255,122,61,.07),transparent 62%)}
.finding .lab{font-family:var(--mono);font-size:10.5px;letter-spacing:.15em;
  text-transform:uppercase;color:var(--hot);display:block;margin-bottom:5px}
.finding p{color:var(--ink);font-size:14.5px;max-width:90ch}
.finding.cool{border-left-color:var(--cool);
  background:linear-gradient(90deg,rgba(90,210,168,.07),transparent 62%)}
.finding.cool .lab{color:var(--cool)}
.finding.warnb{border-left-color:var(--warn);
  background:linear-gradient(90deg,rgba(255,204,85,.07),transparent 62%)}
.finding.warnb .lab{color:var(--warn)}
table{border-collapse:collapse;width:100%;font-size:13px}
.tw{overflow-x:auto}
th,td{text-align:right;padding:7px 11px;border-bottom:1px solid var(--line-soft);
  font-variant-numeric:tabular-nums;font-family:var(--mono);white-space:nowrap}
th:first-child,td:first-child{text-align:left;font-family:var(--sans)}
th{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  font-family:var(--mono);border-bottom:1px solid var(--line)}
tbody tr:hover{background:var(--ground-2)}
td.best{color:var(--cool)} td.bad{color:var(--bad)}
ul{margin:0;padding-left:0;list-style:none;display:flex;flex-direction:column;gap:8px}
li{color:var(--ink-2);padding-left:19px;position:relative;font-size:14px}
li::before{content:'';position:absolute;left:0;top:.62em;width:7px;height:1px;
  background:var(--hot)}
.eq{font-family:var(--mono);font-size:13px;color:var(--ink);
  background:var(--ground-2);border:1px solid var(--line);border-radius:2px;
  padding:12px 15px;overflow-x:auto;line-height:1.75}
.chip{display:inline-flex;align-items:center;font-family:var(--mono);
  font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;padding:4px 9px;
  border:1px solid var(--line);border-radius:2px;color:var(--ink-2)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.contour{position:absolute;inset:0;pointer-events:none;opacity:.55;z-index:0}
.slide>*{position:relative;z-index:1}
.title-wrap{display:flex;flex-direction:column;gap:24px;justify-content:center;flex:1}
.byline{display:flex;flex-wrap:wrap;gap:10px 26px;font-family:var(--mono);
  font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:15px}
.q{display:flex;gap:13px;align-items:flex-start}
.q .i{font-family:var(--mono);font-size:11px;color:var(--hot);
  border:1px solid var(--line);border-radius:2px;padding:3px 7px;flex:none;margin-top:2px}
.progress{position:fixed;left:0;top:0;height:2px;background:var(--hot);
  z-index:50;width:0;transition:width .12s linear}
.pager{position:fixed;right:14px;bottom:12px;font-family:var(--mono);font-size:11px;
  color:var(--muted);background:rgba(13,26,31,.85);border:1px solid var(--line);
  border-radius:2px;padding:5px 10px;z-index:50;letter-spacing:.1em}
.hint{position:fixed;left:14px;bottom:12px;font-family:var(--mono);font-size:10.5px;
  color:var(--muted);z-index:50}
a{color:var(--cool)}
:focus-visible{outline:2px solid var(--hot);outline-offset:3px}
.fig-row{display:grid;gap:16px;grid-template-columns:1.55fr 1fr;align-items:start}
@media (max-width:1000px){.fig-row{grid-template-columns:1fr}}
.tight{gap:12px}
@media print{.deck{height:auto;overflow:visible}
  .slide{page-break-after:always;min-height:auto}
  .progress,.pager,.hint{display:none}}
"""


def rail(n, sec, tag=""):
    return (f'<div class="rail"><span class="n">{n:02d}</span>'
            f'<span class="sec">{sec}</span><span class="tag">{tag}</span></div>')


CONTOUR = """<svg class="contour" viewBox="0 0 1200 700"
 preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<g fill="none" stroke="#24404a" stroke-width="1">
<path d="M-40 520 C 180 470 300 560 470 520 S 800 430 1240 480"/>
<path d="M-40 560 C 180 512 300 600 470 560 S 800 472 1240 520"/>
<path d="M-40 600 C 180 554 300 640 470 600 S 800 514 1240 560"/>
<path d="M-40 462 C 200 420 320 500 480 466 S 820 384 1240 432"/>
<path d="M-40 408 C 220 372 340 444 490 414 S 830 338 1240 386"/>
</g></svg>"""

S = []
fd, hd = flat["district"], hilly["district"]
hres = hilly["results"]
h1_ = hilly["tradeoff"][1]
rows = {x["n"]: x for x in bench["rows"]}
b = rows[1600]
sc = bench["scaling"]

# 01 -------------------------------------------------------------------
S.append(f"""<section class="slide">{CONTOUR}
<div class="rail"><span class="n">01</span><span class="sec">CLL798D / CHL7903 &middot;
Network Science</span><span class="tag">Prelim review &middot; 09 Sep 2026</span></div>
<div class="title-wrap">
<h1>Minimum spanning trees<br>don't survive contact<br>with a hillside</h1>
<p class="lede">Graph-theoretic topology optimisation of district-heating pipe networks
&mdash; on <span class="cool">two real German networks</span>,
<span class="cool">real SRTM terrain</span>, and a transport-phenomena cost model.
We reproduce Gao et&nbsp;al. (2020), show its published results are not internally
consistent, and rebuild the problem with terrain, hydraulic feasibility and
reliability in the objective.</p>
<div class="grid g3" style="max-width:1020px">
<div class="q"><span class="i">Q1</span><p>Is minimum <em>length</em> the same as
minimum <em>cost</em>?</p></div>
<div class="q"><span class="i">Q2</span><p>Is the cost-optimal tree even
<em>buildable</em>?</p></div>
<div class="q"><span class="i">Q3</span><p>What does <em>fault tolerance</em>
cost?</p></div>
</div>
<div class="byline">
<span>Pathway&nbsp;1 &mdash; reproduce &amp; extend</span>
<span>AixDHN &middot; NASA SRTM 30&nbsp;m &middot; EN&nbsp;253 &middot; Eurostat</span>
<span>Kruskal &middot; Prim &middot; Steiner &middot; Laplacian spectral bisection</span>
</div></div></section>""")

# 02 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(2, 'The problem', 'Graph formulation')}
<h2>A pipe network is a graph, and the topology <em>is</em> the design decision</h2>
<div class="grid g2">
<div class="grid tight">
<div class="eq">V &nbsp;=&nbsp; 1 plant + n consumer substations<br>
E &nbsp;=&nbsp; every feasible trench route, w(e) = construction cost<br>
feasible layout &nbsp;=&nbsp; connected, loop-free &rarr;
<span class="hot">spanning tree</span>, |E| = V &minus; 1<br>
number of spanning trees &nbsp;=&nbsp; <span class="hot">V<sup>V&minus;2</sup></span>
&nbsp;(Cayley)</div>
<p>For our 41-node networks that is 41<sup>39</sup> &asymp; 10<sup>62</sup> candidate
layouts. Enumeration is hopeless, so the design is delegated to a greedy algorithm with
a proof of optimality &mdash; provided the edge weight actually encodes cost.</p>
<div class="finding"><span class="lab">The gap this project attacks</span>
<p>An MST is provably optimal for the weight you give it. Gao et&nbsp;al. give it
straight-line distance. On real ground, distance is not cost, minimum length is not
minimum cost, and the optimal tree may not even be hydraulically buildable.</p></div>
</div>
<div class="grid tight">
<div class="panel"><h3>What the syllabus buys us</h3>
<div class="tw"><table>
<thead><tr><th>Graph concept</th><th>Design question</th></tr></thead><tbody>
<tr><td>Laplacian &lambda;<sub>2</sub></td><td>how hard to break apart</td></tr>
<tr><td>Bridges / Menger</td><td>can one pipe cut supply?</td></tr>
<tr><td>Spectral bisection</td><td>where to split pressure zones</td></tr>
<tr><td>Betweenness</td><td>which pipe must not fail</td></tr>
<tr><td>Degree distribution</td><td>is the optimum special?</td></tr>
<tr><td>Percolation</td><td>graceful decay or collapse?</td></tr>
<tr><td>Modularity</td><td>natural isolation districts</td></tr>
</tbody></table></div></div>
<div class="chips"><span class="chip">Kruskal &mdash; union&ndash;find</span>
<span class="chip">Prim &mdash; heap</span>
<span class="chip">Prim &mdash; dense O(V&sup2;)</span>
<span class="chip">Iterated 1-Steiner</span>
<span class="chip">Greedy augmentation</span></div>
</div></div></section>""")

# 03 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(3, 'Data', 'Everything measured, nothing invented')}
<h2>Real networks, real demand, real terrain</h2>
<div class="grid g4">
<div class="panel stat"><span class="k">AixDHN &middot; RWTH Aachen EBC</span>
<span class="v cool">1,380</span><span class="sub">German DH districts loaded, MIT
licence. Bremen and Stuttgart chosen for maximum relief contrast at comparable
scale.</span></div>
<div class="panel stat"><span class="k">Census cells &rarr; substations</span>
<span class="v cool">2,348</span><span class="sub">real 100&nbsp;m EPSG:3035 cells
clustered into 40 substations + 1 plant per district.</span></div>
<div class="panel stat"><span class="k">NASA SRTM 30&nbsp;m</span>
<span class="v cool">29,248</span><span class="sub">elevation points downloaded, cached
as rasters, sampled every 25&nbsp;m along every candidate route.</span></div>
<div class="panel stat"><span class="k">Annual heat demand</span>
<span class="v cool">859</span><span class="sub">GWh/y of real household district heat
across the two networks &mdash; 67,314 households.</span></div>
</div>
<div class="grid g2">
<div class="panel"><h3>The two study networks</h3>
<div class="tw"><table>
<thead><tr><th></th><th>Bremen</th><th>Stuttgart</th></tr></thead><tbody>
<tr><td>Setting</td><td>N. German Plain</td><td>Neckar basin</td></tr>
<tr><td>Demand [MWh/y]</td><td>{fd['demand_MWh']:,.0f}</td>
<td>{hd['demand_MWh']:,.0f}</td></tr>
<tr><td>Households</td><td>{fd['households']:,}</td><td>{hd['households']:,}</td></tr>
<tr><td>Area [km&sup2;]</td><td>{fd['area_km2']:.1f}</td>
<td>{hd['area_km2']:.1f}</td></tr>
<tr><td>Census cells</td><td>{fd['cells']:,}</td><td>{hd['cells']:,}</td></tr>
<tr><td>Relief along routes [m]</td><td class="best">63</td>
<td class="bad">282</td></tr>
</tbody></table></div></div>
<div class="grid tight">
<div class="finding warnb"><span class="lab">Correction to our own abstract</span>
<p>The abstract said AixDHN would supply node/coordinate data for a pipe network. It
does not &mdash; it has <em>no pipes, no diameters, no per-node demand</em>, only district
polygons, aggregate demand and census cells. We verified this against the repository
before use and built the node set ourselves by clustering the real cells.</p></div>
<div class="panel"><h3>Cited throughout</h3><ul>
<li>Persson &amp; Werner (2011) &mdash; DH trench cost C = C&#8321; + C&#8322;&middot;d</li>
<li>Valin&#269;ius et&nbsp;al. (2015) &mdash; failure rates 0.02&ndash;0.31 /km&middot;y</li>
<li>EN&nbsp;253 / EN&nbsp;13941 &mdash; pipe catalogue, roughness, burial depth</li>
<li>Eurostat H2&nbsp;2025 &mdash; 0.1922 EUR/kWh industrial electricity</li>
</ul></div></div></div></section>""")

# 04 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(4, 'The networks', 'Result')}
<h2>Two real networks, three topologies, one terrain model</h2>
<figure><img src="{img('fig1_networks')}" alt="District-heating networks drawn on real
SRTM terrain for Bremen and Stuttgart, comparing star, terrain MST and
redundancy-augmented topologies">
<figcaption>Pipe thickness &prop; nominal diameter. Violet = redundant pipes chosen by
the reliability model. Stuttgart's Neckar valley is the blue trough.</figcaption></figure>
<div class="finding"><span class="lab">Read the star column</span>
<p>The star is 3&times; the pipe length and 65&nbsp;% more expensive per MWh &mdash; but it is
the <em>most reliable</em> topology, losing only the largest single customer to any one
failure. That trade-off is the whole subject of this project.</p></div></section>""")

# 05 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(5, 'Physics engine', 'Transport phenomena')}
<h2>Momentum, heat and mass &mdash; and how each reaches back into the graph</h2>
<figure><img src="{img('fig7_transport_phenomena')}" alt="Four panels: Colebrook friction
factor versus Reynolds number, buried twin-pipe heat loss versus DN, oxygen-limited
corrosion life versus DN, and static pressure versus relief">
<figcaption>Colebrook&ndash;White vs the paper's constant &sigma;&nbsp;=&nbsp;0.015 &middot;
buried twin-pipe loss with soil shape factor and mutual coupling &middot; O&#8322;-limited
corrosion life &middot; static pressure vs relief against PN16.</figcaption></figure>
<div class="grid g3">
<div class="panel"><h3 class="hot">Momentum</h3><p style="font-size:13.5px">
Darcy&ndash;Weisbach with Colebrook friction; discrete EN&nbsp;253 sizing on velocity
<em>and</em> 100&nbsp;Pa/m specific drop. In a closed loop the static head
<em>cancels</em> &mdash; pumping is friction only. Getting that wrong overstates hilly
pumping by orders of magnitude.</p></div>
<div class="panel"><h3 class="cool">Heat</h3><p style="font-size:13.5px">
Buried twin-pipe resistance R<sub>self</sub>&nbsp;+&nbsp;R<sub>mutual</sub>; the warm
supply pipe shields the return, <em>reducing</em> total loss. DN300 at
110/50&nbsp;&deg;C loses 64.4&nbsp;W per trench metre.</p></div>
<div class="panel"><h3 class="blue">Mass</h3><p style="font-size:13.5px">
O&#8322; transport to the wall (Linton&ndash;Sherwood) sets corrosion, which sets failure
rate. k<sub>m</sub> &prop; u<sup>0.83</sup>D<sup>&minus;0.17</sup>, so narrow fast
branches corrode faster &mdash; <em>topology changes reliability</em>.</p></div>
</div></section>""")

# 06 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(6, 'Validation', 'Does our physics agree with theirs?')}
<h2>We re-derived the paper's own heat-transfer coefficient from first principles</h2>
<div class="grid g2">
<div class="grid tight">
<p class="lede">Gao et&nbsp;al.'s Table&nbsp;1 prints &lambda; and &epsilon; with
<em>swapped units</em>. Rather than assume the swap, we computed &epsilon;
independently: Churchill&ndash;Bernstein cross-flow over a 1&nbsp;m cylinder at the
paper's own wind speed v&nbsp;=&nbsp;3.50&nbsp;m/s, plus radiation from galvanised
cladding.</p>
<div class="eq">h<sub>convection</sub> &nbsp;=&nbsp; 10.228
W&middot;m<sup>&minus;2</sup>K<sup>&minus;1</sup><br>
h<sub>radiation</sub> &nbsp;&nbsp;=&nbsp; &nbsp;1.383<br>
<span class="cool">h<sub>total</sub> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;=&nbsp; 11.611</span><br>
published &nbsp;&nbsp;&nbsp;=&nbsp; 11.630</div>
<div class="finding cool"><span class="lab">0.16&nbsp;% error</span>
<p>An independent correlation lands within 0.16&nbsp;% of the published value. That both
validates our thermal model and <em>proves</em> the Table&nbsp;1 units are swapped
&mdash; without ever assuming it.</p></div>
</div>
<div class="grid tight">
<div class="panel"><h3>Other checks that passed</h3><ul>
<li><span class="mono cool">&rho;&nbsp;=&nbsp;0.60&nbsp;kg/m&sup3;</span> &rarr;
saturated steam near 1&nbsp;atm &rarr; T &asymp; 100&nbsp;&deg;C, matching "only
low-pressure steam is considered"</li>
<li>Back-calculated MST heat loss <span class="mono cool">121&nbsp;W/m</span> &mdash;
normal for an insulated steam main</li>
<li>Kruskal, heap-Prim, dense-Prim and NetworkX all return identical tree weight</li>
<li>O(V) tree flow solver matches the Eq(7)&ndash;(12) LP to
<span class="mono">5&times;10<sup>&minus;5</sup></span></li>
</ul></div>
<div class="panel"><h3>Insulation scaling, taken from the standard</h3>
<p style="font-size:13.5px">Log&ndash;log fit over 22 real EN&nbsp;253 catalogue
sizes:</p>
<div class="eq">t<sub>ins</sub> = 0.1025 &middot;
D<sub>steel</sub><sup>0.391</sup> &nbsp;&nbsp;(R = 0.963)</div>
<p style="font-size:13px">Real standards insulate <em>sub</em>-proportionally. The
exponent comes from the standard, not from the data we validate against.</p></div>
</div></div></section>""")

# 07 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(7, 'Reproduction', 'Gao et al. (2020)')}
<h2>The MST column fits exactly. The held-out Star column does not.</h2>
<div class="fig-row">
<figure><img src="{img('fig9_gao_reproduction')}" alt="Left: reproduced versus published
MST costs. Right: percentage error on the held-out star column for three insulation
models">
<figcaption>Left: MST column, calibrated on 3 unpublished parameters. Right: Star column
error &mdash; never used in calibration.</figcaption></figure>
<div class="grid tight">
<div class="panel"><h3>Inverse reconstruction</h3>
<p style="font-size:13.5px">The paper publishes no coordinates. We searched n and layout
to match <em>both</em> published lengths at once:</p>
<div class="eq">n = 33 users, 2.99 km site<br>
star &nbsp;36,500.0 m &nbsp;(&minus;0.00&nbsp;%)<br>
MST &nbsp;&nbsp;11,900.4 m &nbsp;(+0.00&nbsp;%)<br>
ratio 3.067 &nbsp;(paper 3.067)</div>
<p style="font-size:13px">Calibrated: 87.5&nbsp;kg/s steam, 167.6&nbsp;mm insulation,
&zeta;<sub>elbow</sub>&nbsp;=&nbsp;0.598 &mdash; all physically plausible.</p></div>
</div></div>
<div class="grid g2">
<div class="finding warnb"><span class="lab">Finding &mdash; Table 2 is not self-consistent</span>
<p>The published Star pipe cost (0.869) is <em>lower</em> than the MST (1.03) despite
3.07&times; the length. Under the paper's own Eq(13)&ndash;(14) that ratio requires a
total demand of <span class="mono">357&nbsp;kg/s</span>, but the absolute MST cost
requires <span class="mono">87.5&nbsp;kg/s</span> &mdash; a
<span class="bad">3&times; contradiction</span>.</p></div>
<div class="finding warnb"><span class="lab">Finding &mdash; the ESMT sits at a proved bound</span>
<p>Du &amp; Hwang's Steiner ratio theorem proves L<sub>SMT</sub>/L<sub>MST</sub> &ge;
&radic;3/2 = 0.86603 for any planar point set. The paper reports 1.03/1.19 =
<span class="bad">0.86555</span>. Within table rounding, but at the very edge of
geometric possibility.</p></div>
</div></section>""")

# 08 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(8, 'Result 1', 'Terrain-weighted routing')}
<h2>A longer tree can be the cheaper tree</h2>
<figure><img src="{img('fig3_terrain_effect')}" alt="Stuttgart: differences between the
Euclidean and terrain-weighted MST, route elevation profiles, and cost comparison">
<figcaption>Edge weight = &Sigma; slope-length &times; trenching multiplier
f(s) = 1 + 1.176s + 3.968s&sup2;, sampled every 25&nbsp;m on the real DEM.</figcaption>
</figure>
<div class="grid g3">
<div class="panel stat"><span class="k">Stuttgart &mdash; hilly</span>
<span class="v hot">&minus;3.0&nbsp;%</span><span class="sub">total annual cost, for a
tree that is <em>0.03&nbsp;km longer</em>. 23.09 &rarr; 22.39 EUR/MWh.</span></div>
<div class="panel stat"><span class="k">Bremen &mdash; flat</span>
<span class="v cool">0.0&nbsp;%</span><span class="sub">terrain weighting returns the
identical tree. The control experiment behaves exactly as it must.</span></div>
<div class="finding cool" style="align-self:center"><span class="lab">Why this matters</span>
<p>Minimising length and minimising cost are the same problem only on flat ground. The
saving is modest but it is <em>free</em> &mdash; same algorithm, better weight.</p></div>
</div></section>""")

# 09 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(9, 'Result 2', 'Hydraulic feasibility')}
<h2>In Stuttgart the cost-optimal tree cannot legally be built</h2>
<div class="fig-row">
<figure><img src="{img('fig8_pressure_zones')}" alt="Spectral bisection of the Stuttgart
network into pressure zones, the Fiedler vector, and relief within each zone">
<figcaption>Recursive Fiedler bisection of the network Laplacian, splitting until every
zone's internal relief fits the usable pressure band.</figcaption></figure>
<div class="grid tight">
<div class="eq">p(z) = p<sub>ref</sub> + &rho;g(z<sub>ref</sub> &minus; z)<br><br>
required at high point &nbsp;p<sub>sat</sub>+margin = 1.93 bar<br>
static over 282 m &nbsp;&nbsp;&rho;g&Delta;z = <span class="bad">26.3 bar</span><br>
pipe class &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;PN16 = 16 bar<br>
<span class="warn">single-zone relief limit = 151 m</span></div>
<div class="finding warnb"><span class="lab">The constraint terrain really imposes</span>
<p>Not pumping cost &mdash; <em>pressure class</em>. One zone can hold 151&nbsp;m of
relief. Stuttgart has 282&nbsp;m, so a single-zone network is infeasible and the design
needs <span class="bad">2 pressure zones</span> with an exchanger station between them.
Bremen needs <span class="cool">1</span>.</p></div>
</div></div>
<div class="finding cool"><span class="lab">Spectral bisection doing real engineering</span>
<p>Choosing where to split is a balanced minimum-cut problem: separate nodes by elevation
while cutting as few pipes as possible, because every cut pipe needs a heat-exchanger
station. The Fiedler vector of the Laplacian is the classical relaxation of exactly that
&mdash; the course's spectral bisection used as a hydraulic design tool.</p></div>
</section>""")

# 10 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(10, 'Result 3', 'Reliability')}
<h2>Every tree edge is a bridge &mdash; and Steiner trees make it worse</h2>
<div class="grid g2">
<div class="panel"><h3>Stuttgart, N&minus;1 single pipe failure</h3>
<div class="tw"><table>
<thead><tr><th>Topology</th><th>km</th><th>EUR/MWh</th><th>bridges</th>
<th>N&minus;1 served</th></tr></thead><tbody>
<tr><td>Star</td><td>{hres['Star']['length_3d_km']:.1f}</td>
<td class="bad">{hres['Star']['specific_cost']:.2f}</td><td>40</td>
<td class="best">95.6&nbsp;%</td></tr>
<tr><td>MST&ndash;2D</td><td>{hres['MST-2D']['length_3d_km']:.1f}</td>
<td>{hres['MST-2D']['specific_cost']:.2f}</td><td>40</td><td>33.1&nbsp;%</td></tr>
<tr><td>MST&ndash;terrain</td><td>{hres['MST-terrain']['length_3d_km']:.1f}</td>
<td>{hres['MST-terrain']['specific_cost']:.2f}</td><td>40</td>
<td class="bad">0.0&nbsp;%</td></tr>
<tr><td>ESMT</td><td>{hres['ESMT']['length_3d_km']:.1f}</td>
<td>{hres['ESMT']['specific_cost']:.2f}</td><td>57</td>
<td class="bad">0.0&nbsp;%</td></tr>
<tr><td>RSMT</td><td>{hres['RSMT']['length_3d_km']:.1f}</td>
<td class="best">{hres['RSMT']['specific_cost']:.2f}</td><td>59</td>
<td class="bad">0.0&nbsp;%</td></tr>
<tr><td>MST&ndash;terrain +R</td><td>{hres['MST-terrain+R']['length_3d_km']:.1f}</td>
<td>{hres['MST-terrain+R']['specific_cost']:.2f}</td><td class="best">17</td>
<td class="best">91.9&nbsp;%</td></tr>
</tbody></table></div></div>
<div class="grid tight">
<div class="finding"><span class="lab">Answering the fault-propagation question</span>
<p>A Steiner tree is <em>still a tree</em>. Adding Steiner points buys length &mdash;
RSMT is the cheapest topology at 20.87&nbsp;EUR/MWh &mdash; but it concentrates flow into
shared trunks, so it is <em>more</em> fragile, not less. Steiner solves cost; only cycles
solve faults.</p></div>
<div class="finding cool"><span class="lab">Expected Unserved Demand</span>
<p>EUD = &Sigma;<sub>e</sub> &lambda;<sub>e</sub> &times; MTTR &times;
D<sub>stranded</sub>(e), with &lambda;<sub>e</sub> from real DH failure statistics,
scaled per branch by our own O&#8322;-corrosion model. Topology &rarr; velocity &rarr;
corrosion &rarr; failure rate.</p></div>
</div></div></section>""")

# 11 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(11, 'Result 3', 'The price of robustness')}
<h2>The first redundant pipe is extraordinarily cheap insurance</h2>
<figure><img src="{img('fig4_reliability')}" alt="Reliability versus cost premium, N-1
security, and percolation robustness curves">
<figcaption>All points re-costed with the network fully re-sized under the N&minus;1
criterion &mdash; a looped network must carry full load when one path is lost, so it
cannot be sized on split flows.</figcaption></figure>
<div class="grid g4">
<div class="panel stat"><span class="k">Stuttgart &middot; first edge</span>
<span class="v hot">+{h1_['cost_premium_pct']:.1f}&nbsp;%</span>
<span class="sub">total annual cost</span></div>
<div class="panel stat"><span class="k">Expected unserved demand</span>
<span class="v cool">&minus;{h1_['eud_reduction_pct']:.0f}&nbsp;%</span>
<span class="sub">from one added pipe</span></div>
<div class="panel stat"><span class="k">N&minus;1 demand served</span>
<span class="v cool">0 &rarr; {100*h1_['n1_served_fraction']:.0f}&nbsp;%</span>
<span class="sub">worst single failure</span></div>
<div class="panel stat"><span class="k">Targeted attack</span>
<span class="v bad">3&nbsp;%</span><span class="sub">served after 12&nbsp;% of pipes cut
&mdash; plain tree. The looped network holds 87&nbsp;%.</span></div>
</div></section>""")

# 12 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(12, 'Structure', 'Network science characterisation')}
<h2>What the graph metrics say about a cost-optimal pipe network</h2>
<figure><img src="{img('fig6_network_science')}" alt="Degree distribution, edge
betweenness map, algebraic connectivity and bridge count across topologies">
<figcaption>Stuttgart. Edge betweenness identifies the trunk pipes that carry every
source-to-load path.</figcaption></figure>
<div class="grid g4">
<div class="panel stat"><span class="k">Algebraic connectivity &lambda;&#8322;</span>
<span class="v cool">2.4&times;</span><span class="sub">1.67 &rarr; 4.03
&times;10<sup>&minus;5</sup> after 4 redundant pipes</span></div>
<div class="panel stat"><span class="k">Bridges removed</span>
<span class="v cool">40 &rarr; 17</span><span class="sub">single points of
failure</span></div>
<div class="panel stat"><span class="k">Max edge betweenness</span>
<span class="v hot">0.68 &rarr; 0.44</span><span class="sub">load spread off the
trunk</span></div>
<div class="panel stat"><span class="k">Modularity</span>
<span class="v blue">0.698</span><span class="sub">strong community structure &mdash;
natural isolation districts; the star scores 0.000</span></div>
</div></section>""")

# 13 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(13, 'Algorithms', 'Kruskal vs Prim, implemented from scratch')}
<h2>The textbook prediction is wrong for this graph</h2>
<div class="fig-row">
<figure><img src="{img('fig5_algorithms')}" alt="Log-log runtime scaling of Kruskal, heap
Prim and dense Prim, and the fraction of edges Kruskal examines">
<figcaption>Complete graphs, E = V(V&minus;1)/2. All three implementations verified to
return identical tree weight.</figcaption></figure>
<div class="grid tight">
<div class="panel"><h3>At V = 1600 &nbsp;<span class="dim mono">(E = 1,279,200)</span></h3>
<div class="tw"><table>
<thead><tr><th>Implementation</th><th>Runtime</th><th>&alpha;</th></tr></thead><tbody>
<tr><td>Kruskal &mdash; union&ndash;find</td><td>{b['kruskal_s']*1000:.0f} ms</td>
<td>{sc['kruskal']:.2f}</td></tr>
<tr><td>Prim &mdash; binary heap</td><td class="bad">{b['prim_s']*1000:.0f} ms</td>
<td>{sc['prim']:.2f}</td></tr>
<tr><td>Prim &mdash; dense array</td>
<td class="best">{b['prim_dense_s']*1000:.1f} ms</td>
<td>{sc['prim_dense']:.2f}</td></tr>
</tbody></table></div></div>
<div class="finding"><span class="lab">Correction to our own prelim slides</span>
<p>We predicted density would favour Prim. It favours the <em>dense array</em> Prim
&mdash; <span class="cool">212&times; faster</span> than the heap version and 15&times;
faster than Kruskal. Heap-Prim is the worst choice here: it pushes O(E) entries through a
priority queue. Kruskal beats it by <em>terminating early</em>, examining only
<span class="mono">0.7&nbsp;%</span> of the sorted edge list.</p></div>
</div></div>
<p class="lede">Asymptotic order alone does not pick the algorithm. Graph density and
implementation constants decide it &mdash; which is exactly the kind of claim a
benchmark, not a textbook, has to settle.</p></section>""")

# 14 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(14, 'Summary', 'Cost breakdown')}
<h2>Where the money actually goes</h2>
<figure><img src="{img('fig2_cost_breakdown')}" alt="Stacked cost breakdown per topology
for both districts, in euros per MWh delivered">
<figcaption>Specific cost in EUR per MWh delivered &mdash; the scale-invariant
comparison. Capital dominates; pumping is a thin sliver because static head cancels in a
closed loop.</figcaption></figure>
<div class="grid g3">
<div class="finding"><span class="lab">Capital dominates</span>
<p>Trench cost is 80&ndash;90&nbsp;% of TAC. That is why topology &mdash; which sets how
many metres you dig &mdash; is the dominant design decision, and why the MST framing is
right even when its weight is wrong.</p></div>
<div class="finding cool"><span class="lab">Pumping is small</span>
<p>Because the static head cancels round a closed loop. A model that adds
&rho;g&Delta;z to the pump duty would overstate hilly pumping by three orders of
magnitude.</p></div>
<div class="finding warnb"><span class="lab">Zones are not small</span>
<p>Stuttgart's second pressure zone is a real annualised cost that <em>no length-based
objective can see</em>. It appears only when terrain enters the constraint set.</p></div>
</div></section>""")

# 15 -------------------------------------------------------------------
S.append(f"""<section class="slide">{rail(15, 'Status', 'Where the project stands')}
<h2>Done, and what's next before the final</h2>
<div class="grid g2">
<div class="panel"><h3 class="cool">Complete</h3><ul>
<li>Full Python codebase, 16 modules, all algorithms written from scratch</li>
<li>Gao et&nbsp;al. cost model Eq(1)&ndash;(24) implemented and calibrated; two internal
inconsistencies in the published results identified</li>
<li>Two real networks built from AixDHN census cells + NASA SRTM terrain</li>
<li>Terrain-weighted MST, ESMT and RSMT via iterated 1-Steiner</li>
<li>Transport phenomena: Colebrook, buried twin-pipe, O&#8322; corrosion</li>
<li>Reliability: EUD, N&minus;1 sizing, greedy augmentation, percolation</li>
<li>Spectral bisection pressure zoning; Kruskal/Prim/dense-Prim benchmark</li>
</ul></div>
<div class="panel"><h3 class="hot">Next</h3><ul>
<li>Scale to 100+ substations and test whether the terrain advantage grows</li>
<li>Replace greedy augmentation with an exact ILP for k &le; 3 to bound the greedy
optimality gap</li>
<li>Seasonal operation: ambient temperature and part-load, not just design load</li>
<li>Sensitivity sweep on &Delta;T (110/50 vs 4GDH 90/45) and on PN class</li>
<li>A third district in the Erzgebirge to test the 151&nbsp;m zoning threshold</li>
<li>Individual contribution statement and final report appendix</li>
</ul></div></div>
<div class="finding"><span class="lab">The thesis in one line</span>
<p>On flat ground a minimum spanning tree is the right answer. On real terrain it is
neither minimum-cost nor necessarily buildable &mdash; and because every tree edge is a
bridge, it is never robust. Terrain belongs in the weight, pressure class belongs in the
constraints, and reliability belongs in the objective.</p></div>
<div class="byline"><span>Data &middot; AixDHN (MIT) &middot; NASA SRTM 30&nbsp;m
&middot; Eurostat &middot; EN&nbsp;253</span>
<span>Full provenance in docs/DATA_SOURCES.md</span></div></section>""")

JS = """
const deck=document.getElementById('deck'),slides=[...document.querySelectorAll('.slide')];
const prog=document.getElementById('prog'),pager=document.getElementById('pager');
function cur(){let b=0,d=1e9;slides.forEach((s,i)=>{
  const t=Math.abs(s.getBoundingClientRect().top);if(t<d){d=t;b=i}});return b}
function upd(){const i=cur();
  pager.textContent=String(i+1).padStart(2,'0')+' / '+String(slides.length).padStart(2,'0');
  prog.style.width=(100*i/(slides.length-1))+'%'}
deck.addEventListener('scroll',upd,{passive:true});upd();
function go(d){const i=Math.max(0,Math.min(slides.length-1,cur()+d));
  slides[i].scrollIntoView({behavior:'smooth',block:'start'})}
addEventListener('keydown',e=>{
  if(['ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();go(1)}
  if(['ArrowUp','PageUp'].includes(e.key)){e.preventDefault();go(-1)}
  if(e.key==='Home'){e.preventDefault();slides[0].scrollIntoView()}
  if(e.key==='End'){e.preventDefault();slides.at(-1).scrollIntoView()}});
"""

html = f"""<title>Terrain-Aware Heat Networks</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="progress" id="prog"></div>
<div class="pager" id="pager">01 / {len(S)}</div>
<div class="hint">&uarr; &darr; to navigate</div>
<main class="deck" id="deck">
{''.join(S)}
</main>
<script>{JS}</script>
"""

os.makedirs("build", exist_ok=True)
with open("build/deck.html", "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"wrote build/deck.html  "
      f"{os.path.getsize('build/deck.html')/1024/1024:.2f} MB, {len(S)} slides")
