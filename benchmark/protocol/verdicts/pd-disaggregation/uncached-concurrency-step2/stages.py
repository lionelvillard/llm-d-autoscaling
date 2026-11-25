"""Mean of each trigger value, and the decode terms, over the last SECS seconds of each load stage.
Usage: stages.py samples.csv T0 SECS rate:dur,rate:dur,..."""
import sys, collections
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import terms
rows = terms.load(sys.argv[1])
t0 = int(sys.argv[2]); secs = int(sys.argv[3])
t = t0
print("rate,t_end,conc,lam,gen,ok,pods,kv,itl,itl_mean,dc_conc,dc_lam,dc_kv,dc_itl,W_ms_per_tok,pf_ask")
for st in sys.argv[4].split(","):
    r, d = st.split(":"); t += int(d)
    acc = collections.defaultdict(list)
    for tt, s in rows.items():
        if t - secs <= tt <= t:
            for k, v in s.items():
                if v is not None: acc[k].append(v)
            for k, v in terms.terms(s).items(): acc[k].append(v)
    m = lambda k: sum(acc[k]) / len(acc[k]) if acc[k] else float("nan")
    W = m("conc") / (m("lam") * m("gen") / m("ok")) * 1000 if m("ok") > 0 and m("lam") > 0 else float("nan")
    print(",".join(f"{x:.4g}" if i != 1 else str(int(x)) for i, x in enumerate([float(r), t, m("conc"), m("lam"), m("gen"), m("ok"), m("pods"), m("kv"), m("itl"), m("gt_itl_mean"), m("dc_conc"), m("dc_lam"), m("dc_kv"), m("dc_itl"), W, m("pf_ask")])))
