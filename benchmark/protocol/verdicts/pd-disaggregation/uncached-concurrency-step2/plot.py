"""Draw the step 2 plots from the exported CSVs (run export.py first). Run from this directory:

    python3 plot.py [pf2 pf3 pf4 pf5 pf6 pf7 pf8 pf9 pf10 ...]

Every curve is a captured series; the only drawn lines that are not data are the thresholds the
verdict states, each labelled with its formula.
"""
import csv
import os
import sys

import svgplot
from svgplot import Panel, render

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    cols = {}
    with open(os.path.join(HERE, name)) as f:
        rd = csv.DictReader(f)
        for k in rd.fieldnames:
            cols[k] = []
        for r in rd:
            for k in rd.fieldnames:
                v = r[k]
                try:
                    cols[k].append(float(v) if v != "" else None)
                except ValueError:
                    cols[k].append(None)
    return cols


def pts(c, y, x="t_s"):
    return [(a, b) for a, b in zip(c[x], c[y]) if a is not None and b is not None]


def first_change(c, key, pred, after=-1e9):
    prev = None
    for t, v in zip(c["t_s"], c[key]):
        if v is None or t < after:
            continue
        if pred(v):
            return t
    return None


def out(name):
    return os.path.join(HERE, name)


def plot_pf6():
    c = read("pf6.csv")
    tmax = c["t_s"][-1]
    up = first_change(c, "spec_replicas", lambda v: v >= 3, 0)
    down = first_change(c, "spec_replicas", lambda v: v <= 2, up or 0)
    load_end = 1331.0
    p1 = Panel("offered prompt tokens/s\n(EPP estimate)", 150, ymin=0)
    p1.line("offered (EPP)", pts(c, "offered_tok_s"))
    p1.hline(82588, "82,588 = 2 pods x 1.1 x 37,540")
    p2 = Panel("prefill formula value\n(replicas asked)", 140, ymin=0, ymax=4)
    p2.line("formula value", pts(c, "prefill_ask"))
    p2.hline(2.2, "2.2 = 1.1 x 2 pods (HPA adds above)")
    p3 = Panel("prefill replicas", 120, ymin=1.5, ymax=4.0, yticks=[2, 3, 4])
    p3.line("spec (Deployment)", pts(c, "spec_replicas"), step=True)
    p3.line("ready", pts(c, "ready_replicas"), step=True)
    ev = [(0, "load starts: 2.2 req/s of 33,000-word prompts")]
    ev.append((900, "900 s: end of the scale-up window"))
    if up:
        ev.append((up, f"scale-up to 3 at {up:.0f} s"))
    ev.append((load_end, "load ends"))
    ev.append((load_end + 3600, "load end + 3600 s"))
    if down:
        ev.append((down, f"scale-down to 2 at {down:.0f} s"))
    render(out("pf6.svg"), f"PF6: prefill adds its first pod {up:.0f} s after demand passes the threshold, not sooner",
           "Offered prompt tokens per second, the prefill formula value and the prefill replica count over time, "
           "with the scale-up window and the 3600 s scale-down window marked.",
           [p1, p2, p3], tmax, events=ev, xmin=-60, x_ticks=list(range(0, int(tmax), 600)))


def plot_pf3():
    c = read("pf3.csv")
    tmax = c["t_s"][-1]
    p1 = Panel("prompt tokens/s (1 min rate)", 170, ymin=10, ymax=10000, log=True)
    p1.line("EPP estimate (offered)", pts(c, "offered_tok_s"))
    p1.line("engine prompt_tokens", pts(c, "engine_prompt_tok_s_1m"))
    p2 = Panel("offered / engine tokens", 130, ymin=0, ymax=2.5, yticks=[0, 0.5, 1, 1.5, 2, 2.5])
    p2.line("e = offered / engine", pts(c, "e_offered_over_engine"), marker=True)
    p2.hline(1.0, "e = 1 (the formula's assumption)")
    ev = [(0, "384:50 at 1 req/s"), (267, "8192:256 at 0.5 req/s"), (597, "2048:2048 at 0.2 req/s"), (927, "256:4096 at 0.1 req/s")]
    render(out("pf3.svg"), "PF3: the router's prompt-token estimate is 1.5 times the engine's count",
           "The offered prompt tokens per second read from the router and the prompt tokens per second the prefill pods "
           "counted, on a log axis, and their ratio, for four steady request shapes.",
           [p1, p2], tmax, events=ev, x_ticks=list(range(0, int(tmax), 100)))


def decode_events(c):
    ev = []
    prev = None
    for t, v in zip(c["t_s"], c["spec_replicas"]):
        if v is not None and prev is not None and v != prev and t >= 0:
            ev.append((t, f"decode {int(prev)} to {int(v)}"))
        if v is not None:
            prev = v
    return ev


STAGES_D2 = [(0, 420, 0.5), (420, 840, 1.0), (840, 1260, 1.5), (1260, 1680, 2.2), (1680, 2100, 1.0), (2100, 3000, 0.4)]


def plot_pf4():
    c = read("d2.csv")
    tmax = 3300
    p1 = Panel("replicas each term asks\n(log)", 170, ymin=0.003, ymax=10, log=True, yticks=[0.01, 0.1, 1, 10])
    p1.line("conc / 510", pts(c, "term_conc"))
    p1.line("lam x gen / ok / 17,917", pts(c, "term_lam"))
    p2 = Panel("decode residency\n(ms per output token)", 140, ymin=0, ymax=70)
    p2.line("conc / (lam x gen/ok)", pts(c, "W_ms_per_token"), marker=True)
    p2.hline(28.46, "28.46 ms = 510 / 17,917")
    p3 = Panel("offered req/s (lam)\nand decode replicas", 120, ymin=0, ymax=7, yticks=[0, 2, 4, 6])
    p3.line("lam (req/s)", pts(c, "lam"))
    p3.line("decode replicas", pts(c, "spec_replicas"), step=True)
    render(out("pf4.svg"), "PF4: the offered-output term is the larger one below 28.46 ms per token, conc / 510 above it",
           "Two decode terms, the residency per output token that decides between them, and the offered rate and decode "
           "replica count, through the second decode staircase.",
           [p1, p2, p3], tmax, events=[(s, f"{r} req/s") for s, e, r in STAGES_D2],
           x_ticks=list(range(0, tmax, 300)))


def plot_pf5():
    c = read("d2.csv")
    tmax = 3300
    p1 = Panel("replicas each term asks (log)", 190, ymin=0.003, ymax=20, log=True, yticks=[0.01, 0.1, 1, 10])
    p1.line("conc / 510", pts(c, "term_conc"))
    p1.line("lam term", pts(c, "term_lam"))
    p1.line("pods x kv / 0.8", pts(c, "term_kv"))
    p1.line("pods x itl p90 / 0.05", pts(c, "term_itl"))
    hp = [(t, 1.1 * v) for t, v in pts(c, "ready_replicas")]
    p1.line("1.1 x ready replicas", hp, step=True, color="#888888", dash="1 2", width=1.5)
    p2 = Panel("decode replicas", 120, ymin=0, ymax=7, yticks=[0, 2, 4, 6])
    p2.line("spec", pts(c, "spec_replicas"), step=True)
    p2.line("ready", pts(c, "ready_replicas"), step=True)
    p2.hline(2, "minReplicas 2")
    p2.hline(6, "maxReplicas 6")
    render(out("pf5.svg"), "PF5: in the simulator the ITL guard, not conc or lam, adds decode pods",
           "The four decode terms in replicas, with 1.1 times the ready replicas (the HPA's tolerance), and the decode "
           "replica count, through the second decode staircase.",
           [p1, p2], tmax, events=[(s, f"{r} req/s") for s, e, r in STAGES_D2], x_ticks=list(range(0, tmax, 300)))


def plot_pf8():
    c = read("d2.csv")
    tmax = c["t_s"][-1]
    p1 = Panel("decode ITL p90 (s)", 150, ymin=0, ymax=0.1)
    p1.line("ITL p90 (itl trigger)", pts(c, "itl_p90_s"))
    p1.line("ITL mean (ground truth)", pts(c, "itl_mean_s"))
    p1.hline(0.05, "0.05 s SLO")
    p1.hline(0.055, "0.055 s = 1.1 x SLO")
    pp = [(t, i / p) for (t, i), p in zip(pts(c, "term_itl"), [v for v in c["pods"] if v is not None] or [1])]
    per_pod = []
    for t, ti, pods in zip(c["t_s"], c["term_itl"], c["pods"]):
        if ti is not None and pods:
            per_pod.append((t, ti / pods))
    p2 = Panel("itl term per pod", 120, ymin=0, ymax=1.6)
    p2.line("itl term / pods", per_pod)
    p2.hline(1.1, "1.1 (HPA adds above)")
    p3 = Panel("decode replicas", 100, ymin=0, ymax=7, yticks=[0, 2, 4, 6])
    p3.line("spec", pts(c, "spec_replicas"), step=True)
    render(out("pf8.svg"), "PF8: the ITL guard reads 0 at idle, 0.4 to 0.95 per pod under load, and adds a pod once p90 passes 0.055 s",
           "Decode ITL p90 and mean, the ITL term per pod, and the decode replica count through the second decode "
           "staircase and the idle period after it.",
           [p1, p2, p3], tmax, events=[(s, f"{r} req/s") for s, e, r in STAGES_D2], x_ticks=list(range(0, int(tmax), 300)))


def plot_pf9():
    c = read("d2.csv")
    l = read("d2-load.csv")
    tmax = 3300
    p1 = Panel("decode replicas", 110, ymin=0, ymax=7, yticks=[0, 2, 4, 6])
    p1.line("spec", pts(c, "spec_replicas"), step=True)
    p1.line("ready", pts(c, "ready_replicas"), step=True)
    p2 = Panel("requests per 15 s\n(by completion time)", 150, ymin=0)
    p2.line("completed 200", pts(l, "completed_200"), step=True)
    p2.line("client errors", pts(l, "errors"), step=True, width=2.6)
    render(out("pf9.svg"), "PF9: each decode scale-in is followed by failed in-flight requests",
           "Decode replicas and the requests completed or failed per 15 seconds through the second decode staircase.",
           [p1, p2], tmax, events=decode_events(c)[:12], x_ticks=list(range(0, tmax, 300)))


def plot_pf10():
    c = read("pf10.csv")
    p1 = Panel("replicas each term asks (log)", 190, ymin=0.003, ymax=5, log=True, yticks=[0.01, 0.1, 1])
    p1.line("conc / 510", pts(c, "term_conc"))
    p1.line("lam term", pts(c, "term_lam"))
    p1.line("pods x kv / 0.8", pts(c, "term_kv"))
    p1.line("pods x itl p90 / 0.05", pts(c, "term_itl"))
    p2 = Panel("offered req/s (lam)", 100, ymin=0, ymax=1.6)
    p2.line("lam", pts(c, "lam"))
    render(out("pf10.svg"), "PF10: on 8192:256 the KV term is 6 to 9 times conc and lam, but the ITL term is larger still",
           "The four decode terms in replicas and the offered request rate through a 360 s stage of 8192:256 requests "
           "at 1 req/s on two decode pods.",
           [p1, p2], 540, events=[(0, "8192:256 at 1 req/s starts"), (360, "load stops")], xmin=-30,
           x_ticks=list(range(0, 540, 60)))


def plot_pf7():
    c = read("pf7.csv")
    tmax = c["t_s"][-1]
    p1 = Panel("decode KV cache usage", 190, ymin=0, ymax=1.1, yticks=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
    p1.line("pod A", pts(c, "kv_podA"))
    p1.line("pod B", pts(c, "kv_podB"))
    p1.line("mean (the kv trigger's series)", pts(c, "kv_mean"), width=2.8)
    p1.hline(0.8, "0.8: router's kvCacheUtilThreshold")
    p1.hline(0.88, "0.88 = 1.1 x 0.8: kv adds a pod above this mean")
    p2 = Panel("requests per pod", 120, ymin=0)
    for k, lab in (("running_podA", "running A"), ("running_podB", "running B"), ("waiting_podA", "waiting A"), ("waiting_podB", "waiting B")):
        p2.line(lab, pts(c, k))
    ev = [(0, "0.3 req/s"), (300, "0.4 req/s"), (600, "0.5 req/s (d3 stopped here)")]
    render(out("pf7.svg"), "PF7: decode KV per pod against the router's 0.8 threshold and the kv guard's 0.88",
           "KV cache usage of each of the two decode pods and their mean, and the running and waiting requests per pod, "
           "while the load rises with the KV cache cut to 1 GiB per pod.",
           [p1, p2], tmax, events=PF7_EVENTS, x_ticks=list(range(0, int(tmax), 300)))


_D3B = 1795570330 - 1795569505
PF7_EVENTS = [(0, "0.3 req/s"), (300, "0.4 req/s"), (600, "0.5 req/s; load stopped at 740 s"),
              (_D3B, "0.7 req/s"), (_D3B + 240, "1.0 req/s"), (_D3B + 480, "1.4 req/s"), (_D3B + 720, "1.8 req/s"),
              (_D3B + 960, "2.2 req/s")]


def plot_pf7live():
    c = read("pf7live.csv")
    tmax = c["t_s"][-1]
    p1 = Panel("decode KV cache usage", 150, ymin=0, ymax=1.1, yticks=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
    p1.line("fullest pod", pts(c, "kv_max_pod"))
    p1.line("emptiest pod", pts(c, "kv_min_pod"))
    p1.line("mean (kv trigger series)", pts(c, "kv_mean"), width=2.8)
    p1.hline(0.8, "0.8: router's threshold")
    p1.hline(0.88, "0.88: kv adds a pod above this mean")
    p2 = Panel("replicas each term asks (log)", 170, ymin=0.05, ymax=20, log=True, yticks=[0.1, 1, 10])
    p2.line("conc / 510", pts(c, "term_conc"))
    p2.line("lam term", pts(c, "term_lam"))
    p2.line("pods x kv / 0.8", pts(c, "term_kv"))
    p2.line("pods x itl p90 / 0.05", pts(c, "term_itl"))
    p2.line("1.1 x ready replicas", [(t, 1.1 * v) for t, v in pts(c, "ready_replicas")], step=True, color="#888888", dash="1 2", width=1.5)
    p3 = Panel("decode replicas", 100, ymin=0, ymax=7, yticks=[0, 2, 4, 6])
    p3.line("spec", pts(c, "spec_replicas"), step=True)
    p3.line("ready", pts(c, "ready_replicas"), step=True)
    render(out("pf7live.svg"), "PF7: with the KV cache cut to 1 GiB the kv guard adds the decode pods, as the formula says",
           "Decode KV per pod, the four decode terms and the decode replica count while 2 requests per second of decode-heavy "
           "load run on pods with a 1 GiB KV cache and the decode ScaledObject active.",
           [p1, p2, p3], tmax, events=[(0, "2 req/s starts")], xmin=-30, x_ticks=list(range(0, int(tmax), 120)))


def plot_pf2():
    c = read("pf2.csv")
    tmax = c["t_s"][-1]
    p1 = Panel("trigger value read by KEDA\n(blank = no series)", 120, ymin=0)
    p1.line("offered (prompt tokens/s, prefill)", pts(c, "offered_tok_s"), marker=True)
    p2 = Panel("lam (req/s, decode)", 90, ymin=0)
    p2.line("lam", pts(c, "lam_req_s"), marker=True, color="#d95f02")
    p3 = Panel("consecutive trigger failures", 110, ymin=0)
    p3.line("prefill: offered", pts(c, "prefill_trigger_failures"), step=True)
    p3.line("decode: lam", pts(c, "decode_trigger_failures"), step=True)
    p3.hline(3, "failureThreshold 3: fallback engages")
    p4 = Panel("fallback active (1) and\nreplicas", 100, ymin=0, ymax=3.5, yticks=[0, 1, 2, 3])
    p4.line("prefill fallback", pts(c, "prefill_fallback"), step=True)
    p4.line("decode fallback", pts(c, "decode_fallback"), step=True)
    p4.line("prefill replicas", pts(c, "prefill_replicas"), step=True)
    p4.line("decode replicas", pts(c, "decode_replicas"), step=True)
    ev = [(0, "EPP pod deleted"), (310, "first request after the restart")]
    render(out("pf2.svg"), "PF2: after an EPP restart both triggers fail until the first request, and fallback holds 2 replicas",
           "The offered and lam trigger values, the consecutive failure counts, the Fallback condition and the replica "
           "counts of both ScaledObjects around an EPP restart with no traffic.",
           [p1, p2, p3, p4], tmax, events=ev, xmin=-60, x_ticks=list(range(0, int(tmax), 60)),
           xlabel="time since the EPP pod was deleted (s)")


if __name__ == "__main__":
    which = sys.argv[1:] or ["pf3", "pf4", "pf5", "pf6", "pf8", "pf9"]
    for w in which:
        globals()["plot_" + w]()
