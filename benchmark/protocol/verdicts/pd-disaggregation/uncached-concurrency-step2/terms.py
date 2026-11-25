"""Pivot samples.csv (t_epoch,name,value) and compute the formulas' terms.
Usage: terms.py samples.csv [t_from t_to]  -> prints one row per sample time (every 15 s)."""
import csv, sys, collections

def load(path):
    rows = collections.OrderedDict()
    for r in csv.DictReader(open(path)):
        t = int(r["t_epoch"]) // 15 * 15
        try:
            v = float(r["value"])
        except ValueError:
            v = None
        rows.setdefault(t, {})[r["name"]] = v
    return rows

def terms(s):
    g = lambda k: s.get(k)
    out = {}
    o, c, d = g("offered"), g("comp"), g("done")
    if o is not None and c is not None and d is not None:
        out["pf_ask"] = max(o * c / d if d > 0 else o, c) / 37540
    conc, lam, gen, ok, pods, kv, itl = (g(k) for k in ("conc", "lam", "gen", "ok", "pods", "kv", "itl"))
    if conc is not None:
        out["dc_conc"] = conc / 510
    if lam is not None and gen is not None and ok is not None:
        out["dc_lam"] = (lam * gen / ok if ok > 0 else lam * 2133) / (8.4 * 2133)
    if None not in (pods, kv):
        out["dc_kv"] = pods * kv / 0.8
    if None not in (pods, itl):
        out["dc_itl"] = pods * itl / 0.05
    if len(out) >= 5:
        out["dc_ask"] = max(out[k] for k in ("dc_conc", "dc_lam", "dc_kv", "dc_itl") if k in out)
    return out

if __name__ == "__main__":
    rows = load(sys.argv[1])
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 60
    cols = ["offered", "comp", "done", "conc", "lam", "gen", "ok", "pods", "kv", "itl", "gt_itl_mean"]
    print("t," + ",".join(cols) + ",pf_ask,dc_conc,dc_lam,dc_kv,dc_itl,dc_ask")
    for t, s in rows.items():
        if lo <= t <= hi:
            tt = terms(s)
            f = lambda x: "" if x is None else f"{x:.4g}"
            print(f"{t}," + ",".join(f(s.get(k)) for k in cols) + "," + ",".join(f(tt.get(k)) for k in ("pf_ask", "dc_conc", "dc_lam", "dc_kv", "dc_itl", "dc_ask")))
