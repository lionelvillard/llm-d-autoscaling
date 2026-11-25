"""Per-pod poller (stdlib only), run in the poller pod next to poller.py.
Every INTERVAL seconds, one row per (pod, metric): t_epoch,role,pod,metric,value.
Usage: poller2.py OUT.csv NAMESPACE ID_LABEL [INTERVAL]"""
import json, ssl, sys, time, urllib.parse, urllib.request

out, ns, idl = sys.argv[1], sys.argv[2], sys.argv[3]
interval = float(sys.argv[4]) if len(sys.argv) > 4 else 15
URL = "https://thanos-querier.openshift-monitoring.svc.cluster.local:9091/api/v1/query"
TOKEN = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
ctx = ssl._create_unverified_context()
Q = {}
for role in ("decode", "prefill"):
    sel = f'namespace="{ns}",role="{role}",pod=~"{idl}-{role}-.*"'
    Q[(role, "kv")] = f'max by (pod) (vllm:kv_cache_usage_perc{{{sel}}})'
    Q[(role, "running")] = f'max by (pod) (vllm:num_requests_running{{{sel}}})'
    Q[(role, "waiting")] = f'max by (pod) (vllm:num_requests_waiting{{{sel}}})'
    Q[(role, "abort")] = f'sum by (pod) (vllm:request_success_total{{{sel},finished_reason="abort"}})'
    Q[(role, "success")] = f'sum by (pod) (vllm:request_success_total{{{sel}}})'
Q[("decode", "itl_mean")] = f'sum by (pod) (rate(vllm:inter_token_latency_seconds_sum{{namespace="{ns}",role="decode",pod=~"{idl}-decode-.*"}}[2m])) / sum by (pod) (rate(vllm:inter_token_latency_seconds_count{{namespace="{ns}",role="decode",pod=~"{idl}-decode-.*"}}[2m]))'


def query(q):
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode({"query": q}), headers={"Authorization": "Bearer " + TOKEN})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30, context=ctx).read())["data"]["result"]
    except Exception:  # noqa: BLE001
        return []


with open(out, "a", buffering=1) as f:
    if f.tell() == 0:
        f.write("t_epoch,role,pod,metric,value\n")
    while True:
        t0 = time.time()
        for (role, m), q in Q.items():
            for r in query(q):
                f.write(f'{time.time():.0f},{role},{r["metric"].get("pod","")},{m},{r["value"][1]}\n')
        time.sleep(max(0, interval - (time.time() - t0)))
