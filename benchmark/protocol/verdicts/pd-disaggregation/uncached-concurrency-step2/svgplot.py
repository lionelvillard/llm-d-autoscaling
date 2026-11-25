"""Dependency-free SVG time-series plots for the step 2 verdict.

A figure is a list of panels stacked on one shared x axis (seconds from a start time).
Each panel has its own y axis, series (lines or steps), horizontal reference lines and
vertical event markers. Legends sit in the right margin, so nothing covers the data.
Line styles differ by dash pattern as well as by color, so the plots read in grayscale.
"""
import html

W = 1180
PAD_L, PAD_R, PAD_T, PAD_B = 96, 330, 46, 46
PANEL_GAP = 34

COLORS = ["#1b6ca8", "#d95f02", "#1b7f5c", "#7a3e9d", "#222222", "#b8860b"]
DASHES = ["", "7 3", "2 3", "9 3 2 3", "", "4 2"]


def esc(s):
    return html.escape(str(s), quote=True)


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 10 ** (-(len(str(int(1 / raw))) if raw > 0 else 0))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    t = (int(lo / step)) * step
    out = []
    while t <= hi + 1e-9:
        if t >= lo - 1e-9:
            out.append(round(t, 10))
        t += step
    return out


def fmt(v):
    if abs(v) >= 1000 and float(v).is_integer():
        return f"{int(v):,}"
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.3g}"


class Panel:
    def __init__(self, ylabel, height=190, ymin=0.0, ymax=None, yticks=None, log=False):
        self.ylabel, self.height, self.ymin, self.ymax = ylabel, height, ymin, ymax
        self.yticks, self.log = yticks, log
        self.series, self.hlines, self.bands = [], [], []

    def line(self, label, pts, step=False, color=None, dash=None, width=2.0, marker=False):
        i = len(self.series)
        self.series.append(dict(label=label, pts=[(t, v) for t, v in pts if v is not None],
                                step=step, color=color or COLORS[i % len(COLORS)],
                                dash=DASHES[i % len(DASHES)] if dash is None else dash,
                                width=width, marker=marker))
        return self

    def hline(self, value, label, color="#555555", dash="5 4"):
        self.hlines.append(dict(value=value, label=label, color=color, dash=dash))
        return self

    def band(self, lo, hi, label, color="#dddddd"):
        self.bands.append(dict(lo=lo, hi=hi, label=label, color=color))
        return self


def render(path, title, desc, panels, t_max, xlabel="time since the load started (s)",
           events=(), x_ticks=None, xmin=0.0, x_ticklabel=None, gap=40):
    """events: list of (t, label); drawn as dotted verticals, labels in the top margin."""
    n_ev = len([e for e in events if xmin <= e[0] <= t_max])
    total_h = PAD_T + sum(p.height for p in panels) + PANEL_GAP * (len(panels) - 1) + PAD_B + (n_ev * 14 + 8 if n_ev else 0)
    plot_w = W - PAD_L - PAD_R
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{total_h}" '
           f'viewBox="0 0 {W} {total_h}" font-family="Helvetica, Arial, sans-serif" font-size="11">',
           f'<title>{esc(title)}</title>', f'<desc>{esc(desc)}</desc>',
           f'<rect width="{W}" height="{total_h}" fill="white"/>',
           f'<text x="{PAD_L}" y="18" font-size="14" font-weight="bold">{esc(title)}</text>']

    def X(t):
        return PAD_L + (t - xmin) / (t_max - xmin) * plot_w

    top = PAD_T
    ticks_x = x_ticks or nice_ticks(xmin, t_max, 8)
    ev_slots = {}
    for pi, p in enumerate(panels):
        vals = [v for s in p.series for _, v in s["pts"]] + [h["value"] for h in p.hlines]
        ymax = p.ymax if p.ymax is not None else (max(vals) * 1.08 if vals else 1.0)
        ymin = p.ymin
        if ymax <= ymin:
            ymax = ymin + 1
        if p.log:
            import math
            lo, hi = math.log10(ymin), math.log10(ymax)

            def Y(v, lo=lo, hi=hi, top=top, h=p.height):
                v = max(v, 10 ** lo)
                return top + h - (math.log10(v) - lo) / (hi - lo) * h
            yt = p.yticks or [10 ** k for k in range(int(lo), int(hi) + 1)]
        else:
            def Y(v, ymin=ymin, ymax=ymax, top=top, h=p.height):
                return top + h - (v - ymin) / (ymax - ymin) * h
            yt = p.yticks or nice_ticks(ymin, ymax, 4)
        out.append(f'<rect x="{PAD_L}" y="{top}" width="{plot_w}" height="{p.height}" fill="none" stroke="#999999"/>')
        for v in yt:
            y = Y(v)
            out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + plot_w}" y2="{y:.1f}" stroke="#e6e6e6"/>')
            out.append(f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{fmt(v)}</text>')
        for t in ticks_x:
            out.append(f'<line x1="{X(t):.1f}" y1="{top}" x2="{X(t):.1f}" y2="{top + p.height}" stroke="#f0f0f0"/>')
        for li, line in enumerate(p.ylabel.split("\n")):
            out.append(f'<text transform="translate({14 + 14 * li},{top + p.height / 2}) rotate(-90)" text-anchor="middle">{esc(line)}</text>')
        for b in p.bands:
            out.append(f'<rect x="{X(b["lo"]):.1f}" y="{top}" width="{X(b["hi"]) - X(b["lo"]):.1f}" height="{p.height}" fill="{b["color"]}" opacity="0.45"/>')
        # reference lines
        for h in p.hlines:
            y = Y(h["value"])
            out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + plot_w}" y2="{y:.1f}" stroke="{h["color"]}" stroke-dasharray="{h["dash"]}" stroke-width="1.3"/>')
        # series, clipped to the panel
        cid = f"clip{pi}"
        out.append(f'<clipPath id="{cid}"><rect x="{PAD_L}" y="{top}" width="{plot_w}" height="{p.height}"/></clipPath>')
        out.append(f'<g clip-path="url(#{cid})">')
        for s in p.series:
            pts = [(t, v) for t, v in s["pts"] if xmin <= t <= t_max and (not p.log or v > 0)]
            if not pts:
                continue
            d = []
            for i, (t, v) in enumerate(pts):
                brk = i == 0 or (t - pts[i - 1][0]) > gap
                if s["step"] and not brk:
                    d.append(f'L{X(t):.1f},{Y(pts[i - 1][1]):.1f}')
                d.append(f'{"M" if brk else "L"}{X(t):.1f},{Y(v):.1f}')
            da = f' stroke-dasharray="{s["dash"]}"' if s["dash"] else ""
            out.append(f'<path d="{" ".join(d)}" fill="none" stroke="{s["color"]}" stroke-width="{s["width"]}"{da} stroke-linejoin="round"/>')
            if s["marker"]:
                for t, v in pts:
                    out.append(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="3" fill="{s["color"]}"/>')
        out.append('</g>')
        # legend in the right margin
        ly = top + 12
        lx = PAD_L + plot_w + 12
        for s in p.series:
            da = f' stroke-dasharray="{s["dash"]}"' if s["dash"] else ""
            out.append(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 22}" y2="{ly - 4}" stroke="{s["color"]}" stroke-width="2.4"{da}/>')
            out.append(f'<text x="{lx + 27}" y="{ly}">{esc(s["label"])}</text>')
            ly += 15
        for h in p.hlines:
            out.append(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 22}" y2="{ly - 4}" stroke="{h["color"]}" stroke-width="1.3" stroke-dasharray="{h["dash"]}"/>')
            out.append(f'<text x="{lx + 27}" y="{ly}">{esc(h["label"])}</text>')
            ly += 15
        for b in p.bands:
            out.append(f'<rect x="{lx}" y="{ly - 9}" width="22" height="9" fill="{b["color"]}" opacity="0.7"/>')
            out.append(f'<text x="{lx + 27}" y="{ly}">{esc(b["label"])}</text>')
            ly += 15
        top += p.height + PANEL_GAP
    # x axis labels under the last panel
    last_bottom = PAD_T + sum(p.height for p in panels) + PANEL_GAP * (len(panels) - 1)
    for t in ticks_x:
        lab = x_ticklabel(t) if x_ticklabel else fmt(t)
        out.append(f'<text x="{X(t):.1f}" y="{last_bottom + 15}" text-anchor="middle">{lab}</text>')
    out.append(f'<text x="{PAD_L + plot_w / 2}" y="{last_bottom + 33}" text-anchor="middle">{esc(xlabel)}</text>')
    # events: dotted verticals through all panels; numbered flags in the top margin, key in the legend column
    k = 0
    last_cx = -1e9
    for t, label in events:
        if not (xmin <= t <= t_max):
            continue
        k += 1
        out.append(f'<line x1="{X(t):.1f}" y1="{PAD_T - 4}" x2="{X(t):.1f}" y2="{last_bottom}" stroke="#444444" stroke-dasharray="1 3"/>')
        cx = X(t)
        if cx - last_cx < 20:
            cx = last_cx + 20
        last_cx = cx
        out.append(f'<circle cx="{cx:.1f}" cy="{PAD_T - 12}" r="8" fill="white" stroke="#444444"/>')
        out.append(f'<text x="{cx:.1f}" y="{PAD_T - 8}" text-anchor="middle" font-size="10">{k}</text>')
    # event key below the last panel's legend, in the right margin of the last panel
    ky = last_bottom + 56
    for i, (t, label) in enumerate([e for e in events if xmin <= e[0] <= t_max]):
        out.append(f'<text x="{PAD_L}" y="{ky + i * 14}" font-size="11">{i + 1}: {esc(label)}</text>')
    out.append('</svg>')
    with open(path, "w") as f:
        f.write("\n".join(out))
