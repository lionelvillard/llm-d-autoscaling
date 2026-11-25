#!/bin/bash
# PF1: what each trigger selector matches. Run through the poller pod (Thanos querier).
NS=$1; ID=$2
q() { echo "### $1"; kubectl -n $NS exec poller -- python3 -c '
import sys,json,urllib.request,urllib.parse
tok=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
import ssl
c=ssl._create_unverified_context()
r=urllib.request.Request("https://thanos-querier.openshift-monitoring.svc.cluster.local:9091/api/v1/query?"+urllib.parse.urlencode({"query":sys.argv[1]}),headers={"Authorization":"Bearer "+tok})
d=json.loads(urllib.request.urlopen(r,context=c).read())["data"]["result"]
for x in d: print(json.dumps(x["metric"],sort_keys=True), x["value"][1])
print("series:",len(d))' "$1"; }
P="namespace=\"$NS\",role=\"prefill\",pod=~\"$ID-prefill-.*\""
Dc="namespace=\"$NS\",role=\"decode\",pod=~\"$ID-decode-.*\""
q "count by (namespace, job, pod, role, engine) (vllm:prompt_tokens_by_source_total{$P,source=\"local_compute\"})"
q "count by (namespace, job, pod, role, engine) (vllm:prompt_tokens_total{$P})"
q "count by (namespace, job, pod, role, engine) (vllm:num_requests_running{$Dc})"
q "count by (namespace, job, pod, role, engine) (vllm:num_requests_waiting{$Dc})"
q "count by (namespace, job, pod, role, engine) (vllm:generation_tokens_total{$Dc})"
q "count by (namespace, job, pod, role, engine) (vllm:request_success_total{$Dc,finished_reason=\"length\"})"
q "count by (namespace, job, pod, role, engine) (vllm:kv_cache_usage_perc{$Dc})"
q "count by (namespace, job, pod, role) (vllm:inter_token_latency_seconds_count{$Dc})"
q "count by (job, plugin_name, endpoint_role, modality) (llm_d_epp_prefix_prompt_tokens_count{namespace=\"$NS\"})"
q "count by (job, plugin_name, endpoint_role, modality) (llm_d_epp_prefix_prompt_tokens_sum{namespace=\"$NS\",job=\"$ID-router-epp\",plugin_name=\"approx-prefix-cache-producer\",endpoint_role=\"prefill\"})"
q "count by (job) (llm_d_epp_request_total{namespace=\"$NS\"})"
q "count by (job) (llm_d_epp_request_total{namespace=\"$NS\",job=\"$ID-router-epp\"})"
echo "### without the role pin (trap T14): decode num_requests_running"
q "count by (job, pod) (vllm:num_requests_running{namespace=\"$NS\",pod=~\"$ID-decode-.*\"})"
echo "### without the role pin: sum vs the pinned sum of num_requests_running (decode, instantaneous)"
q "sum(vllm:num_requests_running{namespace=\"$NS\",pod=~\"$ID-decode-.*\"})"
q "sum(vllm:num_requests_running{$Dc})"
echo "### pods"
q "count(count by (pod) (vllm:num_requests_running{$Dc}))"
q "count(count by (pod) (vllm:num_requests_running{$P}))"
