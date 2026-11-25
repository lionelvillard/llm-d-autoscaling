"""Slice the raw captures (pod-samples.csv, pods.csv, replicas.csv, pod-load-*.csv, events.csv)
into one CSV per property for plot.py. Run from this directory: python3 export.py

Raw captures:
  pod-samples.csv   t_epoch,name,value   poller.py: every trigger's PromQL (verbatim) and ground truth, 15 s
  pods.csv          t_epoch,role,pod,metric,value   poller2.py: per-pod KV, running, waiting, ITL, 15 s
  replicas.csv      t_epoch,role,spec,ready,hpa_desired,hpa_current,hpa_current_metric,hpa_target_metric
  pod-load-*.csv    loadgen.py: one line per request (t_send s since start, mix, status, latency)
  events.csv        t_epoch,event
"""
import csv
import collections
import math
import sys

import terms

EV = {}
for r in csv.DictReader(open("events.csv")):
    EV[r["event"].split(":")[0].strip()] = int(r["t_epoch"])
# Pairs of "name start" events; the load starts are the loadgen's own t0 (the first request is within 1 s)
T = {k.split()[0]: v for k, v in EV.items() if k.endswith("start")}

S = terms.load("pod-samples.csv")


def hpa_val(s):
    if s is None or s == "":
        return None
    s = s.strip()
    if s.endswith("m"):
        return float(s[:-1]) / 1000
    return float(s)


def read_replicas():
    d = collections.defaultdict(dict)
    for r in csv.DictReader(open("replicas.csv")):
        try:
            t = int(r["t_epoch"]) // 15 * 15
        except ValueError:
            continue
        d[r["role"]][t] = r
    return d


R = read_replicas()


def rep(role, t, key):
    r = R[role].get(t) or R[role].get(t - 15) or R[role].get(t + 15)
    if not r:
        return None
    v = r.get(key)
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def timeline(role, lo, hi):
    """(raw t, sample dict, replicas row) for every replicas.csv reading of ROLE in [lo, hi]; the sample is the
    poller's 15 s bin that contains the reading."""
    out = []
    for r in csv.DictReader(open("replicas.csv")):
        try:
            t = int(r["t_epoch"])
        except ValueError:
            continue
        if r["role"] == role and lo <= t <= hi:
            b = t // 15 * 15
            out.append((t, b, r))
    return out


def rv(r, key):
    try:
        return float(r[key]) if r.get(key) not in (None, "") else None
    except ValueError:
        return None


def hms(x):
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.6g}"


def write(name, header, rows):
    with open(name, "w") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(hms(v) if not isinstance(v, str) else v for v in r) + "\n")
    print(name, len(rows), "rows")


def window(lo, hi):
    return [t for t in S if lo <= t <= hi]


def tt(t):
    return terms.terms(S[t])


def export_pf3():
    lo, hi = T["e1"], T["e2"] + 1000
    rows = []
    for t in window(lo, hi):
        s = S[t]
        o, g = s.get("offered"), s.get("gt_prefill_tok_1m")
        e = o / g if (o is not None and g is not None and g > 20) else None
        rows.append([t - lo, o, g, e])
    write("pf3.csv", ["t_s", "offered_tok_s", "engine_prompt_tok_s_1m", "e_offered_over_engine"], rows)


def export_pf6():
    lo = T["pf6"] - 60
    hi = T["pf6"] + 6000
    rows = []
    for t, b, r in timeline("prefill", lo, hi):
        s = S.get(b, {})
        rows.append([t - T["pf6"], s.get("offered"), terms.terms(s).get("pf_ask") if s else None, rv(r, "spec"),
                     rv(r, "ready"), rv(r, "hpa_desired")])
    write("pf6.csv", ["t_s", "offered_tok_s", "prefill_ask", "spec_replicas", "ready_replicas", "hpa_desired"], rows)


def export_decode(name, lo, hi, t0):
    rows = []
    for t, b, r in timeline("decode", lo, hi):
        s = S.get(b, {})
        x = terms.terms(s) if s else {}
        conc, lam, gen, ok = s.get("conc"), s.get("lam"), s.get("gen"), s.get("ok")
        w = conc / (lam * gen / ok) * 1000 if all(v is not None for v in (conc, lam, gen, ok)) and ok > 0.02 and lam > 0.02 and gen > 0 else None
        rows.append([t - t0, conc, lam, gen, ok, s.get("pods"), s.get("kv"), s.get("itl"), s.get("gt_itl_mean"),
                     x.get("dc_conc"), x.get("dc_lam"), x.get("dc_kv"), x.get("dc_itl"), x.get("dc_ask"), w,
                     rv(r, "spec"), rv(r, "ready"), rv(r, "hpa_desired"),
                     s.get("gt_waiting"), s.get("gt_running")])
    write(name, ["t_s", "conc", "lam", "gen", "ok", "pods", "kv", "itl_p90_s", "itl_mean_s", "term_conc", "term_lam",
                 "term_kv", "term_itl", "ask", "W_ms_per_token", "spec_replicas", "ready_replicas", "hpa_desired",
                 "waiting", "running"], rows)


def export_load(name, src, t0, bin_s=15):
    """Requests completed per bin, by status class; completion time = t_send + latency."""
    cnt = collections.defaultdict(lambda: collections.Counter())
    for r in csv.DictReader(open(src)):
        try:
            tc = float(r["t_send"]) + float(r["latency_s"])
        except ValueError:
            continue
        b = int(tc // bin_s) * bin_s
        cnt[b]["ok" if r["status"] == "200" else "err"] += 1
    rows = [[b, cnt[b]["ok"], cnt[b]["err"]] for b in sorted(cnt)]
    write(name, ["t_s", "completed_200", "errors"], rows)


def export_pf7():
    """Per-pod decode KV, running and waiting through the 1 GiB KV staircases (d3, then d3b)."""
    lo = T["d3"] - 30
    hi = T["d3b"] + 1300
    per = collections.defaultdict(dict)
    pods = set()
    for r in csv.DictReader(open("pod-pods.csv")):
        if r["role"] != "decode" or r["metric"] not in ("kv", "running", "waiting"):
            continue
        t = int(r["t_epoch"]) // 15 * 15
        if lo <= t <= hi:
            per[t][(r["pod"], r["metric"])] = float(r["value"])
            pods.add(r["pod"])
    pods = sorted(pods)
    rows = []
    for t in sorted(per):
        v = per[t]
        s = S.get(t, {})
        x = tt(t) if t in S else {}
        row = [t - T["d3"]]
        for p in pods[:2]:
            row += [v.get((p, "kv")), v.get((p, "running")), v.get((p, "waiting"))]
        row += [s.get("kv"), x.get("dc_kv"), x.get("dc_itl"), x.get("dc_conc"), x.get("dc_lam")]
        rows.append(row)
    write("pf7.csv", ["t_s", "kv_podA", "running_podA", "waiting_podA", "kv_podB", "running_podB", "waiting_podB",
                      "kv_mean", "term_kv", "term_itl", "term_conc", "term_lam"], rows)


def export_pf7live():
    """d5: decode SO live on the 1 GiB KV pods at 2 req/s: per-pod KV, the four terms and the replicas."""
    lo, hi = T["d5"] - 30, T["d5"] + 900
    per = collections.defaultdict(dict)
    for r in csv.DictReader(open("pod-pods.csv")):
        if r["role"] != "decode" or r["metric"] != "kv":
            continue
        t = int(r["t_epoch"]) // 15 * 15
        if lo <= t <= hi:
            per[t][r["pod"]] = float(r["value"])
    rows = []
    for t, b, r in timeline("decode", lo, hi):
        s = S.get(b, {})
        x = terms.terms(s) if s else {}
        kvs = per.get(b, {})
        mx = max(kvs.values()) if kvs else None
        mn = min(kvs.values()) if kvs else None
        rows.append([t - T["d5"], mn, mx, s.get("kv"), s.get("pods"), x.get("dc_conc"), x.get("dc_lam"), x.get("dc_kv"),
                     x.get("dc_itl"), x.get("dc_ask"), rv(r, "spec"), rv(r, "ready"), s.get("gt_waiting")])
    write("pf7live.csv", ["t_s", "kv_min_pod", "kv_max_pod", "kv_mean", "pods", "term_conc", "term_lam", "term_kv",
                          "term_itl", "ask", "spec_replicas", "ready_replicas", "waiting"], rows)


def export_pf2():
    """Trigger values (blank = no series), ScaledObject failure counts, Fallback condition and replicas around the EPP restart."""
    lo, hi = T["pf2"] - 60, T["pf2"] + 520
    som = collections.defaultdict(dict)
    for r in csv.DictReader(open("somon.csv")):
        t = int(r["t_epoch"]) // 10 * 10
        som[t][r["role"]] = r
    rows = []
    for t in sorted(som):
        if not lo <= t <= hi:
            continue
        s = S.get(t // 15 * 15) or S.get(t // 15 * 15 + 15) or {}
        p, d = som[t].get("prefill", {}), som[t].get("decode", {})
        rows.append([t - T["pf2"], s.get("offered"), s.get("lam"), p.get("max_failures"), d.get("max_failures"),
                     1 if p.get("fallback") == "True" else 0, 1 if d.get("fallback") == "True" else 0,
                     p.get("spec_replicas"), d.get("spec_replicas")])
    write("pf2.csv", ["t_s", "offered_tok_s", "lam_req_s", "prefill_trigger_failures", "decode_trigger_failures",
                      "prefill_fallback", "decode_fallback", "prefill_replicas", "decode_replicas"], rows)


def export_pf10():
    lo, hi = T["d4"] - 30, T["d4"] + 520
    rows = []
    for t in window(lo, hi):
        s = S[t]
        x = tt(t)
        rows.append([t - T["d4"], s.get("lam"), s.get("kv"), s.get("conc"), x.get("dc_conc"), x.get("dc_lam"),
                     x.get("dc_kv"), x.get("dc_itl"), s.get("offered"), x.get("pf_ask")])
    write("pf10.csv", ["t_s", "lam", "kv", "conc", "term_conc", "term_lam", "term_kv", "term_itl", "offered_tok_s", "prefill_ask"], rows)


if __name__ == "__main__":
    which = sys.argv[1:] or ["pf3", "pf6", "d1", "d2"]
    if "pf3" in which:
        export_pf3()
    if "pf6" in which:
        export_pf6()
    if "d1" in which:
        export_decode("d1.csv", T["d1"], T["d1"] + 1700, T["d1"])
    if "pf7live" in which:
        export_pf7live()
    if "pf2" in which:
        export_pf2()
    if "pf7" in which:
        export_pf7()
    if "pf10" in which:
        export_pf10()
    if "d2" in which:
        export_decode("d2.csv", T["d2"] - 60, T["d2"] + 3400, T["d2"])
        export_load("d2-load.csv", "pod-load-d2.csv", 0)
