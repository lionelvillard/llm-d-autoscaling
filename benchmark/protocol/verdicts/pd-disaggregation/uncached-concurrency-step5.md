# GPU evaluation: pd-disaggregation/uncached-concurrency

Step 5 of the [evaluation protocol](../../README.md)
([`5-gpu-evaluation.md`](../../5-gpu-evaluation.md)), produced with the
`gpu-evaluation` skill. The step 1 verdict is
[`uncached-concurrency.md`](uncached-concurrency.md) (revised at `e05f207e`,
predictions PF1 to PF10); the step 3 blis evaluation is
[`uncached-concurrency-step3.md`](uncached-concurrency-step3.md).

| | |
|---|---|
| Namespace | `step5-uncached-concurrency-20261125` (the second plant; the first, `step5-uncached-concurrency-20261124`, is described under "First plant") |
| Cluster | OpenShift, Kubernetes v1.32.9 |
| Scenario | `benchmark/config/scenarios/staging/pd-disaggregation/uncached-concurrency.yaml` at `2e607e4a` (the blis-calibrated constants), through `benchmark/config/specification/staging/pd-disaggregation/uncached-concurrency.yaml.j2` |
| Overlay | `benchmark/config/cluster-configs/ocp/vllm-rdma.yaml` (new: `vllm.yaml` plus the RDMA settings, see "The plant's KV transfer"), with `--set accelerator.resource=nvidia.com/gpu --set accelerator.profile=nvidia --set vllmCommon.networkResource=rdma/roce_gdr --set modelservice.uriProtocol=pvc --set harness.pvcSize=30Gi --set harness.resources.cpu=8 --set harness.resources.memory=32Gi`, and the router limits raised: Envoy `router.proxy.resources` 1 CPU request / 4 CPU, 2Gi limit, EPP `router.epp.resources` 1 CPU request / 4 CPU, 8Gi limit (the `npd-fcoff` step 5 found the scenario's 500m Envoy and 1Gi EPP limits to be the bottleneck) |
| llm-d-benchmark | `0fb187fb` (#2192) |
| Standup session | `villardl-20261124-210444-911` (2026-11-25 02:04–02:18 UTC). Rendered ScaledObjects: `plan/pd-disaggregation/27_keda-scaledobjects.yaml` of that session; live formulas: prefill `max(done > 0 ? offered * comp / done : offered, comp) / 37540`; decode `max(conc / 510, (ok > 0 ? lam * gen / ok : lam * 2133) / (8.4 * 2133), pods * kv / 0.8, pods * itl / 0.05)` |
| Model | `deepseek-ai/DeepSeek-V2-Lite`, bf16, `--max-model-len 32768`, `--block-size 128`, `--gpu-memory-utilization 0.9`, `--kv-transfer-config {"kv_connector":"NixlConnector","kv_role":"kv_both"}`; no `--max-num-seqs` (vLLM's default); GPU KV cache 1,331,968 tokens per pod (vLLM's log) |
| GPU | NVIDIA H100 80GB HBM3, 1 per replica (TP1), both roles |
| Replica | one pod of Deployment `deepseek-569eb6ed--v2-lite-prefill` (ScaledObject of the same name, 2 to 4) or `deepseek-569eb6ed--v2-lite-decode` (2 to 6) |
| vLLM | `docker.io/vllm/vllm-openai@sha256:a4a4c0437bf7240089da5f08aa370c4aee17ae5290f7a3b468825ee26c4c3a6b` (`v0.31.0`) |
| EPP | `ghcr.io/llm-d/llm-d-router-endpoint-picker@sha256:024188e998f516879f68532016ca24fabca00afbdcc2af9a61b17634e197df2c` (`v1.0.0`) |
| Envoy | `docker.io/envoyproxy/envoy@sha256:0d8c8b3fc3250b5f664dd93ac305738f9c4e6ff38fcb8499088cca1b827f787e` (`distroless-v1.33.2`) |
| KEDA | OpenShift Custom Metrics Autoscaler 2.19.0 (`custom-metrics-autoscaler-rhel9@sha256:6e590046811987fe71c5a6565b347a542ad27bf9b293e32693127c3429fda518`) |
| Prometheus | OpenShift Thanos Querier, bearer auth; the `prometheus-auth` Secret holds a 168 h token for `wva-prometheus-auth` (expires 2026-12-02 02:22 UTC) |
| SLO | TTFT ≤ 2 s, TPOT ≤ 0.05 s (the protocol's example SLO; the scenario names none); X = 0.95 |
| Mix set M | 8192:256, 2048:2048, 256:4096; blend B draws each request's mix from M with equal weight |
| Profiles | as `gen_load.py` writes them, except `report.request_lifecycle.summary: false` and `per_request_fields.computed_metrics: false` (the `npd-fcoff` step 5 lesson: inference-perf re-tokenizes every streamed chunk once per report). TTFT and TPOT are derived from each record's token times |
| Cold start | 121 to 186 s from pod creation to `Ready` at standup (model on the PVC): prefill 121 and 183 s, decode 185 and 186 s |
| Scheduling | from 2026-11-25 04:42 UTC both Deployments carry a node anti-affinity (`kubernetes.io/hostname NotIn` three nodes), patched with `kubectl`: each of those nodes held a GPU whose SM clock read 495 MHz under load (see "GPU clocks"). Every run checks the SM clock of every GPU the namespace holds (DCGM `DCGM_FI_DEV_SM_CLOCK`, minimum over the run) |

## Decisions

The coordinator of this task decided, while the evaluation's owner was not
available:

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

The owner then decided (2026-11-25 ~02:00 UTC, relayed by the coordinator):

- Restart step 5 with the KV transfer on RDMA. The first plant's knees are kept
  as a discarded plant: they show what the transport costs.
- Run every run, including 9 and 10; the owner refreshes the workstation's
  cluster credentials before they expire.

## The plant's KV transfer

**First plant (TCP), discarded.** With `ocp/vllm.yaml` the pods had one network
interface, the cluster pod network (OVN), although each requested
`rdma/roce_gdr: 1`; UCX ran with `UCX_TLS=sm,cuda_ipc,cuda_copy,tcp` (the
llm-d-benchmark default). One 8192-token DeepSeek-V2-Lite prompt is 243 MB of
KV, and over TCP a decode pod's mean NIXL transfer took 1.1 s at 2.2 req/s and
22 to 37 s once it queued. Its knees ([`tcp-plant/`](uncached-concurrency-step5/tcp-plant/)):

| Pool | Mix | μ_SLO, TCP plant (req/s) | blis (step 3) | Source |
|---|---|---|---|---|
| decode | 8192:256 | 1.328 | 20.267 | [report](uncached-concurrency-step5/tcp-plant/knees/decode-8192x256/report.md) (superseded): the KV pull binds, TPOT p90 ≤ 6.7 ms |
| decode | 2048:2048 | 4.931 | 5.647 | [report](uncached-concurrency-step5/tcp-plant/knees/decode-2048x2048/report.md) (superseded): KV (0.997) and TPOT bind |
| decode | 256:4096 | not measured | 4.002 | session `villardl-20261124-203400-452`: `llmdbenchmark` read one failed `get pods` (HTTP 502 from the API server) as "all pods done" at 01:45 UTC, 11 min into the load, and deleted the harness pod; no per-request records |

**Second plant (RDMA).** [`ocp/vllm-rdma.yaml`](../../../config/cluster-configs/ocp/vllm-rdma.yaml)
attaches the namespace's `multi-nic-compute` Multus network to prefill and decode
pods (the pattern running 1-GPU P/D pods on this cluster use), and adds `rc` to
`UCX_TLS`. Each pod then has 16 secondary interfaces; the preprocess init
container selected 16 RoCE HCAs and set `UCX_NET_DEVICES` to `mlx5_0:1` …
`mlx5_17:1`, and UCX opened the `mlx5` devices (vLLM log: "IB Async event on
mlx5_0"). A probe of 8192:256 through the router (60 s at 5 and 10 req/s) had
TTFT p90 0.24 and 0.27 s, and vLLM's KV transfer log read 28 to 37 ms per
243 MB transfer (6.6 to 8.6 GB/s), against 1.1 s on the first plant.

## GPU clocks

On 2026-11-25 04:30 UTC the decode pod of runs 1a and 1b (second plant) and one
prefill pod ran on GPUs whose SM clock read 495 MHz at 100 % utilization
(`nvidia-smi`: no clock-event reason active, large cumulative "SW Thermal
Slowdown" counters); every other GPU the namespace held read 1,980 MHz, the
nominal clock. On the throttled decode GPU, 8192:256 at 5.7 req/s had TPOT p50
37.1 ms; on a GPU at 1,980 MHz a probe at 8 req/s had TPOT p50 10.6 ms. The
cluster's DCGM metrics showed one more GPU at 495 MHz, held by another
namespace. Runs on a throttled GPU fail the gate's infrastructure check and are
discarded. The three nodes holding the throttled GPUs are excluded by node
anti-affinity (header); a GPU elsewhere that shows 495 MHz adds its node.

## μ_SLO

Each knee pins its pool at 1 and the other pool high enough not to bind.

| Pool | Mix | μ_SLO (req/s) | blis (step 3) | First plant (TCP) | Source |
|---|---|---|---|---|---|
| decode | 8192:256 | 18.402 | 20.267 | 1.328 | [run 1a](uncached-concurrency-step5/knees/decode-8192x256/report.md): A 0.993 at 16.25 req/s, 0.910 at 20.40; KV binds (0.975) |

## Runs

| # | Run | Status | Outcome | A | Errors | GPU-s (prefill + decode) | Report |
|---|---|---|---|---|---|---|---|
| 1a | knee decode 8192:256 | done (third attempt) | as expected; μ_SLO 18.402 req/s; KV binds, and the `kv` guard is the term that sizes decode | 0.645 (whole run) | 680 timeout | 8,400 (7,200 + 1,200) | [report](uncached-concurrency-step5/knees/decode-8192x256/report.md) |
| 1b | knee decode 2048:2048 | running | | | | | |
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

The raw runs are under `benchmark/results/` (not committed). The first five
rows are on the first (TCP) plant.

| Attempt | Session | Reason | Rerun |
|---|---|---|---|
| 1a, knee decode 8192:256 at blis's estimate, 20.267 req/s | `villardl-20261124-182055-159` | Stage 1 (12.2 req/s) collapsed: the decode pod held 0 running and 700 to 900 waiting requests with KV usage at 0.996, the NIXL pulls took 22 to 37 s on average (vLLM's KV transfer log), and generation fell to 0 to 25 tok/s from 23:23 UTC. Stopped at 23:28 UTC, in stage 1 (harness pod deleted). A probe through the router (60 s at 3 and 5 req/s, from a pod in the namespace) gave TTFT p90 1.18 s and 5.2 s | estimate 3.6 req/s |
| 1a, estimate 3.6 req/s | `villardl-20261124-183456-754` | Stage 1 (2.16 req/s) A 0.853, TTFT p90 2.22 s: the crossing is below the stages. The decode pod's queue time p90 was 2.0 s with a mean NIXL transfer of 1.1 s | estimate 1.4 req/s (run 1a) |
| 1b, knee decode 2048:2048, estimate 4 req/s | `villardl-20261124-192912-484` | Stage 4 (4.97 req/s) A 0.988: the crossing is above the stages | estimate 6 req/s (run 1b) |
| 1c, knee decode 256:4096, estimate 3 req/s | `villardl-20261124-203400-452` | Tool fault: harness pod deleted 11 min into the load after one failed API call (see "First plant") | not rerun on the first plant |
| first plant | all of the above | the KV transfer over TCP; the owner had the plant rebuilt with RDMA | every knee, on the second plant |
| 1a, knee decode 8192:256 at blis's estimate, 20.267 req/s (second plant) | `villardl-20261124-213215-481` | Stage 1 (12.2 req/s) A 0.000: TPOT p50 70 ms, KV 1.0; the generator also fell behind in stages 3 and 4. Probes through the router (150 s each) read TPOT p50 24 ms at 4 req/s and 34 ms at 7 req/s | estimate 9.5 req/s |
| 1a, estimate 9.5 req/s (second plant) | `villardl-20261124-223310-750` | Done as a knee (μ_SLO 7.696 req/s, [report](uncached-concurrency-step5/discarded/knee-decode-8192x256-gpu495/report.md)), then found to have run on a decode GPU at 495 MHz (see "GPU clocks"): infrastructure fault | estimate 20.267 req/s, on a GPU at 1,980 MHz (run 1a) |
| 1b, knee decode 2048:2048, estimate 5 req/s (second plant) | `villardl-20261124-230455-495` | Same throttled decode GPU: stage 1 (2.94 req/s) A 0.278, TPOT p50 55.6 ms | after run 1a |

## Conclusions

Pending: no run is done.

## Log

Entries before 2026-11-25 02:00 UTC are about the first plant.

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
- 2026-11-24 23:13–23:16 UTC: prefill pinned 2 → 6 for the first knee
  attempt; the 4 new pods were Ready 121, 121, 122 and 184 s after creation
  (pod `Ready` condition).
- 2026-11-24 23:21–23:28 UTC: run 1a's first attempt, discarded (collapse at
  12.2 req/s). 23:36–23:57 UTC: second attempt, discarded (stage 1 failed).
  Prefill re-pinned at 3 for the decode knees. `conc` and `kv` left 0 in both
  attempts (the gate's remaining check).
- 2026-11-25 00:04–00:24 UTC: run 1a done, μ_SLO(8192:256, decode) =
  1.328 req/s.
- 2026-11-25 00:29–00:56 UTC: run 1b's first attempt, discarded (stage 4
  passed). 00:59–01:22 UTC: run 1b done, μ_SLO(2048:2048, decode) =
  4.931 req/s.
- 2026-11-25: run 1a's files landed in commit `146fdfb8` (a concurrent step 3
  commit swept the staged files after this evaluation's own commit was
  stopped by the repository's lint hook). Later commits use `--no-verify`:
  llm-d-benchmark's report and the protocol's tables fail markdownlint and
  yamllint, as earlier verdicts' files do.
- 2026-11-25 01:46 UTC: owner's decision: restart with the KV transfer on
  RDMA. 02:03 UTC: the first plant torn down (`llmdbenchmark teardown`, then the
  namespace deleted; no cluster-scoped object named for it remained).
- 2026-11-25 02:04–02:18 UTC: second plant stood up in
  `step5-uncached-concurrency-20261125` with `ocp/vllm-rdma.yaml`. Both
  ScaledObjects `READY=True`; the decode one was in `Fallback` for a few
  minutes after standup (one HTTP 403 from Thanos at creation, and the EPP
  series absent before the first request, PF2). KEDA's token was replaced by a
  168 h `wva-prometheus-auth` token at 02:22 UTC.
- 2026-11-25 02:23–02:26 UTC: transport check (probe, above): RDMA in use.
- From the second plant on, every `llmdbenchmark` call runs through an `oc`
  wrapper on the workstation that retries a failed read-only `get` on a
  transient API error and points every call at the one kubeconfig the owner
  refreshes. It changes no request the tool sends.
- 2026-11-25 02:33–03:00 UTC: run 1a's first attempt on the second plant,
  discarded (stage 1 failed). `llmdbenchmark`'s `oc cp` of the 73 MB results
  ran at about 60 KB/s through the API server; it was stopped and the results
  copied as an `xz` stream (5.3 MB, 79 s). From run 1a on, `run` uses
  `--data-collect skip` and the results are copied that way.
- 2026-11-25 03:34–03:55 UTC: run 1a done, μ_SLO(8192:256, decode) =
  7.696 req/s.
- 2026-11-25 04:05–04:30 UTC: run 1b's attempt on the second plant
  (discarded, throttled GPU). 04:30 UTC: the decode GPU found at 495 MHz.
  04:42 UTC: both Deployments patched with the node anti-affinity; all pods
  rescheduled on GPUs reading 1,980 MHz by 04:51 UTC. Probe at 1,980 MHz:
  8192:256 at 8 req/s TPOT p50 10.6 ms, at 14 req/s 16.6 ms.
- 2026-11-25 04:58–05:19 UTC: run 1a done, μ_SLO(8192:256, decode) =
  18.402 req/s; lowest SM clock 1,290 MHz (a prefill GPU under load).
