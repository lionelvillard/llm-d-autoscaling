"""Step 2 poller (stdlib only), run in a pod in the stack's namespace.

Every INTERVAL seconds it evaluates, against the Thanos querier, the exact PromQL of
each ScaledObject trigger (as rendered in 27_keda-scaledobjects.yaml) and some
ground-truth queries, and appends one row per query: t_epoch,name,value. A query that
returns no series writes an empty value; several series are summed only where the name
says so. Usage: poller.py OUT.csv NAMESPACE ID_LABEL [INTERVAL]
"""
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request

out, ns, idl = sys.argv[1], sys.argv[2], sys.argv[3]
interval = float(sys.argv[4]) if len(sys.argv) > 4 else 15
URL = "https://thanos-querier.openshift-monitoring.svc.cluster.local:9091/api/v1/query"
TOKEN = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
ctx = ssl.create_default_context(cafile="/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt") \
    if False else ssl._create_unverified_context()
P = f'namespace="{ns}",role="prefill",pod=~"{idl}-prefill-.*"'
Dc = f'namespace="{ns}",role="decode",pod=~"{idl}-decode-.*"'
E = f'namespace="{ns}",job="{idl}-router-epp"'
Q = {
    # the ScaledObjects' triggers, verbatim
    "offered": f'sum(rate(llm_d_epp_prefix_prompt_tokens_sum{{namespace="{ns}",job="{idl}-router-epp",plugin_name="approx-prefix-cache-producer",endpoint_role="prefill"}}[1m]))',
    "comp": f'sum(rate(vllm:prompt_tokens_by_source_total{{{P},source="local_compute"}}[5m]))',
    "done": f'sum(rate(vllm:prompt_tokens_total{{{P}}}[5m]))',
    "conc": f'sum(vllm:num_requests_running{{{Dc}}}) + sum(vllm:num_requests_waiting{{{Dc}}})',
    "lam": f'sum(rate(llm_d_epp_request_total{{{E}}}[1m])) + (sum(rate(llm_d_epp_request_error_total{{{E},error_code="ServiceUnavailable"}}[1m])) or vector(0))',
    "gen": f'sum(rate(vllm:generation_tokens_total{{{Dc}}}[5m])) or vector(0)',
    "ok": f'sum(rate(vllm:request_success_total{{{Dc}}}[5m])) or vector(0)',
    "pods": f'count(count by (pod) (vllm:num_requests_running{{{Dc}}})) or vector(0)',
    "kv": f'avg(vllm:kv_cache_usage_perc{{{Dc}}}) or vector(0)',
    "itl": f'(histogram_quantile(0.9, sum by (le) (rate(vllm:inter_token_latency_seconds_bucket{{{Dc}}}[2m]))) > 0) or vector(0)',
    # ground truth and context
    "gt_prefill_tok_1m": f'sum(rate(vllm:prompt_tokens_total{{{P}}}[1m]))',
    "gt_running": f'sum(vllm:num_requests_running{{{Dc}}})',
    "gt_waiting": f'sum(vllm:num_requests_waiting{{{Dc}}})',
    "gt_pf_running": f'sum(vllm:num_requests_running{{{P}}})',
    "gt_pf_waiting": f'sum(vllm:num_requests_waiting{{{P}}})',
    "gt_kv_max": f'max(vllm:kv_cache_usage_perc{{{Dc}}})',
    "gt_pf_kv_max": f'max(vllm:kv_cache_usage_perc{{{P}}})',
    "gt_itl_mean": f'sum(rate(vllm:inter_token_latency_seconds_sum{{{Dc}}}[2m])) / sum(rate(vllm:inter_token_latency_seconds_count{{{Dc}}}[2m]))',
    "gt_ttft_p90": f'histogram_quantile(0.9, sum by (le) (rate(vllm:time_to_first_token_seconds_bucket{{{P}}}[2m])))',
    "gt_decode_abort": f'sum(vllm:request_success_total{{{Dc},finished_reason="abort"}})',
    "gt_decode_success": f'sum(vllm:request_success_total{{{Dc}}})',
    "gt_epp_req_5m": f'sum(rate(llm_d_epp_request_total{{{E}}}[5m]))',
    "gt_flow_queue": f'sum(llm_d_epp_flow_control_queue_size{{{E}}}) or vector(-1)',
}


def query(q):
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode({"query": q}),
                                 headers={"Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            res = json.loads(r.read())["data"]["result"]
    except Exception:  # noqa: BLE001
        return "err"
    return "" if not res else repr(sum(float(x["value"][1]) for x in res)) if len(res) > 1 else res[0]["value"][1]


with open(out, "a", buffering=1) as f:
    if f.tell() == 0:
        f.write("t_epoch,name,value\n")
    while True:
        t = time.time()
        for name, q in Q.items():
            f.write(f"{time.time():.0f},{name},{query(q)}\n")
        time.sleep(max(0, interval - (time.time() - t)))
