import csv,collections,sys
T0=int(sys.argv[1]); step=int(sys.argv[2])
d=collections.defaultdict(dict)
for r in csv.DictReader(open('pod-pods.csv')):
    if r['role']=='decode' and r['metric'] in('kv','running','waiting') and int(r['t_epoch'])>=T0:
        d[(int(r['t_epoch'])//15*15)][(r['pod'][-5:],r['metric'])]=float(r['value'])
for t in sorted(d)[::step]:
    v=d[t]; pods=sorted({k[0] for k in v})
    print(t-T0," ".join(f"{p}: kv {v.get((p,'kv'),-1):.2f} run {v.get((p,'running'),-1):.0f} wait {v.get((p,'waiting'),-1):.0f}" for p in pods))
