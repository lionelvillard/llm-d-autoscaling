# GPU evaluation: pd-disaggregation/uncached-concurrency

Step 5 of the [evaluation protocol](../../README.md)
([`5-gpu-evaluation.md`](../../5-gpu-evaluation.md)), produced with the
`gpu-evaluation` skill. The step 1 verdict is
[`uncached-concurrency.md`](uncached-concurrency.md) (revised at `e05f207e`,
predictions PF1 to PF10); the step 3 blis evaluation is
[`uncached-concurrency-step3.md`](uncached-concurrency-step3.md).

| | |
|---|---|
| Namespace | `step5-uncached-concurrency-20261124` |
| Cluster | OpenShift, Kubernetes v1.32.9 |
| Scenario | `benchmark/config/scenarios/staging/pd-disaggregation/uncached-concurrency.yaml` at `2e607e4a` (the blis-calibrated constants), through `benchmark/config/specification/staging/pd-disaggregation/uncached-concurrency.yaml.j2` |
| Overlay | `benchmark/config/cluster-configs/ocp/vllm.yaml`, with `--set accelerator.resource=nvidia.com/gpu --set accelerator.profile=nvidia --set vllmCommon.networkResource=rdma/roce_gdr --set modelservice.uriProtocol=pvc --set harness.pvcSize=30Gi --set harness.resources.cpu=8 --set harness.resources.memory=32Gi`, and the router limits raised: Envoy `router.proxy.resources` 1 CPU request / 4 CPU, 2Gi limit, EPP `router.epp.resources` 1 CPU request / 4 CPU, 8Gi limit (the `npd-fcoff` step 5 found the scenario's 500m Envoy and 1Gi EPP limits to be the bottleneck) |
| llm-d-benchmark | `0fb187fb` (#2192) |
| Standup session | `villardl-20261124-173459-361` (standup with the scenario's earlier GLM-5.3 constants); ScaledObjects re-rendered from `2e607e4a` (`villardl-20261124-180351-094`, `--dry-run`) and applied in place at 23:04 UTC. The live formulas were then read back: prefill `max(done > 0 ? offered * comp / done : offered, comp) / 37540`; decode `max(conc / 510, (ok > 0 ? lam * gen / ok : lam * 2133) / (8.4 * 2133), pods * kv / 0.8, pods * itl / 0.05)`. The two renders differ only in the two formulas (and in values the offline render leaves at `auto`) |
| Model | `deepseek-ai/DeepSeek-V2-Lite`, bf16, `--max-model-len 32768`, `--block-size 128`, `--gpu-memory-utilization 0.9`, `--kv-transfer-config {"kv_connector":"NixlConnector","kv_role":"kv_both"}`; no `--max-num-seqs` (vLLM's default); GPU KV cache 1,331,840 tokens per pod (vLLM's log) |
| GPU | NVIDIA H100 80GB HBM3, 1 per replica (TP1), both roles |
| Replica | one pod of Deployment `deepseek-2ae88f90--v2-lite-prefill` (ScaledObject `deepseek-2ae88f90--v2-lite-prefill`, 2 to 4) or `deepseek-2ae88f90--v2-lite-decode` (`deepseek-2ae88f90--v2-lite-decode`, 2 to 6) |
| vLLM | `docker.io/vllm/vllm-openai@sha256:a4a4c0437bf7240089da5f08aa370c4aee17ae5290f7a3b468825ee26c4c3a6b` (`v0.31.0`) |
| EPP | `ghcr.io/llm-d/llm-d-router-endpoint-picker@sha256:024188e998f516879f68532016ca24fabca00afbdcc2af9a61b17634e197df2c` (`v1.0.0`) |
| Envoy | `docker.io/envoyproxy/envoy@sha256:0d8c8b3fc3250b5f664dd93ac305738f9c4e6ff38fcb8499088cca1b827f787e` (`distroless-v1.33.2`) |
| KEDA | OpenShift Custom Metrics Autoscaler 2.19.0 (`custom-metrics-autoscaler-rhel9@sha256:6e590046811987fe71c5a6565b347a542ad27bf9b293e32693127c3429fda518`) |
| Prometheus | OpenShift Thanos Querier, bearer auth; KEDA's token in the `prometheus-auth` Secret expires 2026-12-01 22:44 UTC |
| SLO | TTFT ≤ 2 s, TPOT ≤ 0.05 s (the protocol's example SLO; the scenario names none); X = 0.95 |
| Mix set M | 8192:256, 2048:2048, 256:4096; blend B draws each request's mix from M with equal weight |
| Profiles | as `gen_load.py` writes them, except `report.request_lifecycle.summary: false` and `per_request_fields.computed_metrics: false` (the `npd-fcoff` step 5 lesson: inference-perf re-tokenizes every streamed chunk once per report). TTFT and TPOT are derived from each record's token times |

## Decisions of the coordinator

The evaluation's owner was not available. The coordinator of this task decided,
and this evaluation follows:

- The same model and the same ScaledObjects throughout: the scenario's
  constants run as written (blis-calibrated for DeepSeek-V2-Lite on H100). The
  knees (run 1, per role, the other role pinned) are run, and the GPU μ_SLO and
  the constants the scenario's rules would give are reported next to blis's,
  but the live ScaledObjects are not patched with them. The loads of runs 2 to
  10 are derived from the GPU knees, as the protocol requires.
- No change to metrics, formulas, behavior blocks or caps. Where the protocol
  would ask the owner, the conservative choice is taken and recorded.
- If the free GPUs do not cover the caps (prefill 4 + decode 6), wait and
  retry; if still blocked, run what fits and mark the rest not run.

## μ_SLO

Pending.

## Runs

| # | Run | Status | Outcome | A | Errors | GPU-s (prefill + decode) | Report |
|---|---|---|---|---|---|---|---|
| 1a | knee decode 8192:256 | pending | | | | | |
| 1b | knee decode 2048:2048 | pending | | | | | |
| 1c | knee decode 256:4096 | pending | | | | | |
| 1d | knee decode blend | pending | | | | | |
| 1e | knee prefill 8192:256 | pending | | | | | |
| 1f | knee prefill blend | pending | | | | | |
| 2 | SO-active staircase | pending | | | | | |
| 3 | mix-shift | pending | | | | | |
| 4a | overload under the cap | pending | | | | | |
| 4b | overload over the cap | pending | | | | | |
| 5 | agentic | pending | | | | | |
| 8 | bursty | pending | | | | | |
| 9 | short spikes | pending | | | | | |
| 10 | scale-down | pending | | | | | |
| 6 | static-replica baseline | pending | | | | | |
| 7 | scale from zero | not run | `minReplicaCount` is 2 for both roles (run-set.md §2: only with `minReplicaCount: 0`) | | | | |

## Discarded attempts

None.

## Conclusions

Pending: no run is done.

## Log

- 2026-11-24 22:36–22:41 UTC: standup (session `villardl-20261124-173459-361`),
  2 prefill and 2 decode pods Ready 22:39:12–22:39:34 UTC, with the GLM-5.3
  constants in the ScaledObjects.
- 2026-11-24 23:04 UTC: both ScaledObjects re-applied from the `2e607e4a`
  render; `READY=True`, both HPAs read `0/1 (avg)`. The harness ServiceAccount
  `inference-perf-runner` can list Deployments, HPAs and ScaledObjects.
- 2026-11-24 23:07–23:09 UTC: smoke load (`sanity_random.yaml`, 30 requests).
  The triggers left 0: `offered` max 370 tok/s, `comp` and `done` 39.7 tok/s
  (5 m rate), `lam` 0.6 req/s, `gen` 5.1 tok/s, `ok` 0.105 req/s, `itl`
  0.009 s, `pods` 2. `conc` and `kv` read 0 at every 15 s sample: requests of
  50 output tokens finish between scrapes. Both series exist (the `conc` query
  has no `or vector(0)` and returned 0, not an empty result); their first
  non-zero reading is checked in run 1a. The harness writes `metrics/processed/`
  only inside `workspace.tar.zst`; it is extracted into each results
  directory after the run.
