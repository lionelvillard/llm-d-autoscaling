# blis evaluation: pd-disaggregation/uncached-concurrency

Step 3 of the [evaluation protocol](../../README.md)
([`3-blis-evaluation.md`](../../3-blis-evaluation.md)), produced with the
`blis-evaluation` skill. No step 1 or step 2 verdict exists for this scenario.

Every number here is a simulator number, for the plant blis priced. None is a
GPU measurement, and none is given to step 5.

| | |
|---|---|
| Plant | blis-signal-lab `25f2dfb` (branch `signals-hpa`), built with Go 1.27.2, plus task 0545's patch (`blis-signal-lab-25f2dfb.patch`, in llm-d-autoscaling-research `experiments/pd-scaledobjects-glm53/patches/`), which adds the prefill counters `prefill_computed_tokens` and `prefill_done_prompt_tokens` the `comp` and `done` triggers read. Without the patch those two triggers have no translation |
| Catalog | blis-substrate `v0.14.0` (the lab's `go.mod`): `blis catalog resolve --model deepseek-ai/DeepSeek-V2-Lite` gives identity `deepseek-v2-lite` ("the entry's model.yaml names this source repository"). A short probe (run 1e) simulated the model on `h100` at TP1 with no error |
| BLIS scenario | [`deepseek-v2-lite-h100-pd.yaml`](uncached-concurrency-step3/deepseek-v2-lite-h100-pd.yaml), written for the evaluation from the kit's `glm-5-h200-pd-autoscale.yaml`: a `prefill` pool of 8 and a `decode` pool of 16 H100 pods (1 node x 8 GPUs / TP1, and 2 nodes), each pod one TP1 engine on one GPU, as the overlay's `accelerator.count: 1`. Engine as the overlay and scenario: block size 128, `gpu_memory_utilization` 0.90, `max_model_len` 32768, prefix caching on; bf16 weights (the overlay passes no quantization), the rest as vLLM 0.32.0 resolves it. The pools are larger than the ScaledObjects' caps (4 and 6) so a knee can pin the other role high. The overlay runs vLLM 0.31.0 and blis models 0.32.0. The fabric is `roce-200g`, the catalog's nominal rate and the only one used for an H100 P/D scenario in the lab: the overlay states no NIC. Router [`router/pd-always.yaml`](uncached-concurrency-step3/router/pd-always.yaml): the kit's, with `always-disagg-pd-decider`, as the scenario's EPP config |
| Scenario | `benchmark/config/scenarios/staging/pd-disaggregation/uncached-concurrency.yaml` at commit `c6510478`, with backend overlay `benchmark/config/cluster-configs/ocp/vllm.yaml`, rendered by `llmdbenchmark standup --dry-run` (the repository has no `specification/` entry for this scenario; the render used a scratch spec that points at the scenario file). Rendered ScaledObjects: [`scaledobjects-rendered.yaml`](uncached-concurrency-step3/scaledobjects-rendered.yaml) |
| ScaledObjects | [`scaledobjects.json`](uncached-concurrency-step3/scaledobjects.json): `pd-disaggregation-prefill` -> `deepseek-78616ec3--v2-lite-prefill` (2 to 4), `pd-disaggregation-decode` -> `deepseek-78616ec3--v2-lite-decode` (2 to 6). Both have `scalingModifiers` and an HPA `behavior`. `so_to_policy.py` printed no note |
| Model | `deepseek-ai/DeepSeek-V2-Lite`, 1 H100 per replica (TP1), both roles. The scenario and the BLIS plant agree on GPU type and parallelism |
| SLO | TTFT <= 2 s, TPOT <= 0.05 s; X = 0.95 (the protocol's example SLO; the scenario names none) |
| Mix set M | 8192:256, 2048:2048, 256:4096; blend B draws each request's mix from M with equal weight (mean ISL 3,499, mean OSL 2,133 tokens) |
| Cold start | 120 s (`loading_delay`): the protocol's default; no GPU measurement exists for this overlay |
| Metrics pipeline | scrape 15 s: the rendered model-service PodMonitors (`13_ms-values.yaml`, `interval: "15s"`). `metrics_delay_s` 0: the triggers query raw series. HPA sync 15 s, `pollingInterval` 15 s |
| Seed | blis's default (no `--seed`); each load's seed is in [`index.json`](uncached-concurrency-step3/index.json) |
| Loads | written by `gen_load.py --target blis`: the knees from the estimates in the run reports, runs 2 to 10 from the knees ([`index.json`](uncached-concurrency-step3/index.json); [`index-prefill.json`](uncached-concurrency-step3/index-prefill.json) holds the same loads with the prefill pool's capacities, for the prefill tables' `need`). Client timeout 311 s for the blend and the 256:4096 mix (the run set's rule) |
| Lengths | see "Lengths" below |
| Memory | `blis_run.py`'s guard on every run, one at a time |

## Translation of the triggers

Prefill ScaledObject (formula `max(done > 0 ? offered * comp / done : offered, comp) / <threshold>`):

| Trigger | Query (namespace label omitted) | blis terms | Fidelity |
|---|---|---|---|
| `offered` | `sum(rate(llm_d_epp_prefix_prompt_tokens_sum{endpoint_role="prefill"}[1m]))` | `prefill_prompt_tokens`, `rate`, 60 s | approximated: the prompt tokens of requests dispatched to a prefill pod, counted at dispatch (the EPP series counts when its prefix producer runs); with `always-disagg-pd-decider` every request is dispatched to prefill, so the two agree up to the scrape timing |
| `comp` | `sum(rate(vllm:prompt_tokens_by_source_total{role="prefill",source="local_compute"}[5m]))` | `prefill_computed_tokens`, `rate`, 300 s (task 0545's patch) | approximated: the prompt tokens the engine ran in its steps, minus prefix-cache hits, offload and transfers, counted by blis when the leg's work is booked, not step by step |
| `done` | `sum(rate(vllm:prompt_tokens_total{role="prefill"}[5m]))` | `prefill_done_prompt_tokens`, `rate`, 300 s (task 0545's patch) | approximated: the whole prompt of each prefill leg that finished on a prefill pod, as vLLM counts it at the end of the prefill |

Decode ScaledObject (formula `max(conc / <n>, (ok > 0 ? lam * gen / ok : lam * <L>) / (<mu> * <L>), pods * kv / 0.8, pods * itl / <slo>)`):

| Trigger | Query (namespace label omitted) | blis terms | Fidelity |
|---|---|---|---|
| `conc` | `sum(vllm:num_requests_running{role="decode"}) + sum(vllm:num_requests_waiting{role="decode"})` | `running` `sum` + `waiting` `sum`, `role: decode` | exact |
| `lam` | `sum(rate(llm_d_epp_request_total[1m])) + (sum(rate(llm_d_epp_request_error_total{error_code="ServiceUnavailable"}[1m])) or vector(0))` | `arrivals`, `rate`, 60 s | exact |
| `gen` | `sum(rate(vllm:generation_tokens_total{role="decode"}[5m])) or vector(0)` | `generated_tokens`, `rate`, 300 s | approximated: blis counts a request's tokens when it completes, vLLM at each step. `gen / ok` is the mean output length of completions, so both counters lag together |
| `ok` | `sum(rate(vllm:request_success_total{role="decode"}[5m])) or vector(0)` | `completions`, `rate`, 300 s | pool-wide in blis; for P/D one completion per request, so it equals decode's |
| `pods` | `count(count by (pod) (vllm:num_requests_running{role="decode"})) or vector(0)` | `ready_pods`, `role: decode` | exact |
| `kv` | `avg(vllm:kv_cache_usage_perc{role="decode"}) or vector(0)` | `kv_usage`, `avg`, `role: decode` | exact |
| `itl` | `(histogram_quantile(0.9, sum by (le) (rate(vllm:inter_token_latency_seconds_bucket{role="decode"}[2m]))) > 0) or vector(0)` | `itl`, `quantile` 0.9, 120 s | approximated: exact quantile over the window's samples, not over histogram buckets |

The `or vector(0)` and `> 0` guards are dropped (blis rates and quantiles read 0
without traffic). The role filter of the prefill triggers is not needed: blis's
counters for them count prefill pods only.

## Simulator gaps that apply

From 3-blis-evaluation.md §3.2:

- **No Coordinator or flow control**: not part of this scenario. The router is the
  scenario's `always-disagg-pd-decider` chain; blis's router fork runs the same
  plugin set.
- **Requests past the client timeout keep running** (inference-sim#2291). They
  hold engine capacity a cluster would free. It slows recovery after overload
  (runs 4 and 10).
- **A draining pod finishes its work.** No request can fail at a scale-down;
  that half of the criteria of runs 8 to 10 cannot show.
- **Scrapes and syncs on the same instants**: the dead time after a load change
  is the shortest the phases allow.
- **The prefill and decode counters** of the table above are approximated.
- **Scale from zero** is not run (`minReplicaCount` is 2 for both roles).

## Calibration of the GLM-5.3 constants

The ScaledObjects' constants are GLM-5.3 TP8 H200 values. Run 1 measured each
role's knee on this plant, and the policy for runs 2 to 10 uses constants
rewritten from them (the formulas' structure and every metric are unchanged).
The calibrated ScaledObjects are
[`scaledobjects-calibrated.yaml`](uncached-concurrency-step3/scaledobjects-calibrated.yaml);
the knee runs ran the as-rendered constants
([`policy-glm-constants/`](uncached-concurrency-step3/policy-glm-constants/)),
which cannot matter because the knees pin the pool.

After run 1, the scenario file `uncached-concurrency.yaml` was updated to these calibrated values (commit `2e607e4a`: 37540; 510, 8.4, 2133, 0.05), so the policy of runs 2 to 10 matches the scenario as written. The knees ran the GLM-5.3 constants, which do not matter under pinning.

| Constant | GLM-5.3 TP8 H200 | This plant | Rule and source |
|---|---|---|---|
| prefill divisor (`10850`) | 10,850 uncached tok/s per pod | **37,540** | 0.7 x one prefill pod's knee. The knee is the blend's (run-set.md §1: a rule that names no mix takes the blend's): μ_SLO(B, prefill) 15.328 req/s x 3,498.7 tok (mean ISL of B) = 53,628 tok/s (run 1f). The 8192:256 knee, 6.095 req/s = 49,930 tok/s (run 1e), is 6.9 % lower; 0.7 x it would be 34,950 |
| decode concurrency per pod (`4`) | 4 requests | **510** | 1.3 x the requests (running + waiting) one decode pod holds at the blend's knee: 392 at 6.461 req/s, interpolated between stage 3 (359 at 6.3 req/s) and stage 4 (683 at 7.88 req/s) of run 1d's `conc` series (mean over each stage's last 120 s) |
| decode completions per pod (`0.39`) | 0.39 req/s | **8.4** | 1.3 x μ_SLO(B, decode) = 1.3 x 6.461 req/s (run 1d) |
| output length before the first completion (`700`, twice) | 700 tokens | **2,133** | the blend's mean OSL, (256 + 2,048 + 4,096) / 3; the measured `gen / ok` at the knee is 2,035 to 2,081 (it is biased to the short requests that complete first) |
| ITL SLO (`0.075`) | 0.075 s | **0.05** | the run set's TPOT limit; the knee's decode ITL p90 reads 0.029 s at 6.461 req/s |
| KV guard (`0.8`), `minReplicas`, `maxReplicas`, behaviors | | unchanged | not capacity constants; the KV guard sits near the knee's own reading (0.77) |

## μ_SLO

Knee estimates (inputs to run 1, not measurements) and the pins are in each
run's report. Each knee pins its pool at 1 and the other at 6 to 12.

| Pool | Mix | μ_SLO (req/s) | Source |
|---|---|---|---|
| decode | 8192:256 | 20.267 | [run 1a](uncached-concurrency-step3/knees/decode-8192x256/report.md) |
| decode | 2048:2048 | 5.647 | [run 1b](uncached-concurrency-step3/knees/decode-2048x2048/report.md) |
| decode | 256:4096 | 4.002 | [run 1c](uncached-concurrency-step3/knees/decode-256x4096/report.md); an upper bound (300 s stages, about 100 s requests) |
| decode | blend | 6.461 | [run 1d](uncached-concurrency-step3/knees/decode-blend/report.md); the per-mix estimate was 6.30 |
| prefill | 8192:256 | 6.095 | [run 1e](uncached-concurrency-step3/knees/prefill-8192x256/report.md); 49,930 uncached tok/s per pod |
| prefill | blend | 15.328 | [run 1f](uncached-concurrency-step3/knees/prefill-blend/report.md); 53,628 uncached tok/s per pod |
| prefill | 2048:2048, 256:4096 | not reached | A stayed at 1.000 up to 50 req/s (2048:2048, 4 pinned stages, decode pinned at 16; attempts below). Their prompts are short and prefill is cheap; decode binds long before. `index-prefill.json` gives them an infinite capacity, so their prefill need is `minReplicaCount` |

C = min over pools of maxReplicaCount x μ_SLO(B): prefill 4 x 15.328 = 61.31
req/s, decode 6 x 6.461 = 38.77 req/s. **C = 38.77 req/s, set by the decode
pool.**

## Lengths

From the policy's behavior and the cold start (run-set.md §2), taking the
slower role of each quantity. Prefill is the slower role throughout: its
scale-up needs 900 s of sustained demand and adds 1 pod per 300 s, its
scale-down waits 3,600 s and removes 1 pod per 600 s.

| Quantity | Value | From |
|---|---|---|
| T | 600 s | `1 x 300 + 120 + 15 + 120 = 555`, prefill; decode needs 300; rounded up |
| phases | 1,200 s | `max(600, 2 T)` |
| R | 1,035 s | 15 + 900 + 120, prefill (decode: 135) |
| Q | 4,320 s | 3,600 + 600 + 120, prefill (decode: 540) |
| spike (run 9) | 517 s | R / 2 |
| G | 1,800 s | `min(2 R, 3,600 / 2)` |
| H | 1,755 s | `(4 - 2) x 300 + 1,035 + 120`, prefill (decode: 315) |
| D | 4,320 s | `1 x 600 + 3,600 + 120`, prefill (decode: 660) |

## Runs

GPU-seconds are requested replica-seconds x 1 GPU, both pools. Run 7 is not run
because `minReplicaCount` is 2 (run-set.md §2).

| # | Run | Status | Outcome | A | Errors | GPU-s (prefill + decode) | Report |
|---|---|---|---|---|---|---|---|
| 1a | knee decode 8192:256 | done | as expected; μ_SLO 20.267 req/s | | 0 | 1,200 | [report](uncached-concurrency-step3/knees/decode-8192x256/report.md) |
| 1b | knee decode 2048:2048 | done | as expected; μ_SLO 5.647 req/s | | 0 | 1,200 | [report](uncached-concurrency-step3/knees/decode-2048x2048/report.md) |
| 1c | knee decode 256:4096 | done | as expected; μ_SLO 4.002 req/s | | 0 | 1,200 | [report](uncached-concurrency-step3/knees/decode-256x4096/report.md) |
| 1d | knee decode blend | done | as expected; μ_SLO 6.461 req/s | | 0 | 1,200 | [report](uncached-concurrency-step3/knees/decode-blend/report.md) |
| 1e | knee prefill 8192:256 | done | as expected; μ_SLO 6.095 req/s | | 0 | 1,200 | [report](uncached-concurrency-step3/knees/prefill-8192x256/report.md) |
| 1f | knee prefill blend | done | as expected; μ_SLO 15.328 req/s | | 0 | 1,200 | [report](uncached-concurrency-step3/knees/prefill-blend/report.md) |
| 2 | SO-active staircase | done | problem shown: decode lagged the step into stage 3 (A 0.697; 4 Ready 270 s after it); prefill's 900 s window held 2 pods for 885 s after its trigger asked for 3 (stage 5 A 0.966) | 0.929 | 0 | 17,430 (6,270 + 11,160) |
| 3 | mix-shift | done | problem shown: phase 3 (256:4096) A 0.840, decode 2 to 6 Ready in 570 s, A 0.36 at the worst bin; a third prefill pod held 2,580 s above the floor; phase 2 decode 2 against a need of 3 with A 1.000 | 0.947 | 0 | 19,950 (9,900 + 10,050) |
| 4a | overload under the cap | done (second attempt, lab patch) | problem shown: A 0.039 in the 31.0 req/s phase after decode reached its cap of 6 and prefill 3; prefill's 900 s window left it at 2 pods for 1,035 s after the step; 24,459 timeouts and 10,792 unfinished | 0.231 | 24,459 timeout | 13,110 (5,085 + 8,025) |
| 4b | overload over the cap | done (lab patch from the start) | as expected for the cap, no trigger fault: decode at 6 from t = 1,365 s with its trigger at or above 6; prefill reached its cap of 4 only at t = 2,520 s, after the load; A 0.003 in the 58.1 req/s phase (62,008 timeouts, 37,165 unfinished) | 0.120 | 62,008 timeout | 14,580 (5,100 + 9,480) |
| 5 | agentic | pending | | | | | |
| 8 | bursty | pending | | | | | |
| 9 | short spikes | pending | | | | | |
| 10 | scale-down | pending | | | | | |
| 6 | static-replica baseline | pending | | | | | |
| 7 | scale from zero | not run | `minReplicaCount` is 2 (run-set.md §2: only with `minReplicaCount: 0`) | | | | |

## Discarded attempts

Knee attempts whose crossing fell outside the stages (the protocol's rule:
move the estimate and rerun). They are not reports; the raw runs are under
`benchmark/results/` (not committed).

| Attempt | Reason | Rerun |
|---|---|---|
| decode 2048:2048, estimate 4 req/s | A 1.000 in all four stages (2.4 to 5.0 req/s) | estimate 5.5 (run 1b) |
| decode 256:4096, estimate 2.5 req/s | A 1.000 in all four stages (1.5 to 3.1 req/s) | estimate 4.5, then 3.9 (run 1c) |
| decode 256:4096, estimate 4.5 req/s | crossing between stages 2 and 3 (A 1.000 to 0.835): inside the stages, but 3.87 req/s was an interpolation across a 0.8 req/s span, so the estimate was recentered | estimate 3.9 (run 1c: 4.002) |
| prefill 2048:2048, estimates 22 and 40 req/s | A 1.000 in all stages up to 50 req/s (102,400 tok/s) | none: the pool's capacity for this mix is above what the decode pool (16 pods) can feed |
| 4a, overload under the cap (1.2 x μ_SLO(B), then 0.8 x C = 31.013 req/s), first attempt | blis exited 1: `the emitted Result does not validate against blis-schemas`, with `request_rows[15129].e2e_us: is 197718867, less than ttft_us 197828060` and a negative `tpot_us`, on 1 row. Memory was not the cause (peak 25.2 of a 37.5 GiB budget, not killed). The same simulator defect as in `coordinator-kv`'s run 4b: a decode sub-request preempted after its first token has its TTFT rebuilt from a scheduling delay re-stamped at re-admission. Outside the configuration | rerun on the lab with the TTFT projection of inference-sim `dfa8987` (#2237) applied ([`lab-patch.diff`](uncached-concurrency-step3/overload-under/lab-patch.diff)): it changes the reported TTFT of disaggregated requests, not what the HPAs read. Used for runs 4a and 4b (4b ran on it from the start); the other runs ran without it unless they fail the same way |

## Conclusions

Pending: no run after the knees is done.

## Amendments

None.
