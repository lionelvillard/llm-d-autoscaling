# Step 3, run 1c: knee 256:4096, decode pool (pd-disaggregation/uncached-concurrency)

Part of the [step 3 summary](../../../uncached-concurrency-step3.md). Simulator numbers: blis priced this plant; they are not GPU measurements.

| | |
|---|---|
| Plant | blis-signal-lab `25f2dfb` (branch `signals-hpa`) plus task 0545's counter patch; blis-substrate `v0.14.0` catalog entry `deepseek-v2-lite` |
| BLIS scenario | [`deepseek-v2-lite-h100-pd.yaml`](../../deepseek-v2-lite-h100-pd.yaml): a `prefill` and a `decode` pool, H100, bf16, TP1 (1 GPU per replica), block size 128, gpu-memory-utilization 0.90, max-model-len 32768, prefix caching on, as the overlay; router [`router/pd-always.yaml`](../../router/pd-always.yaml) (always-disagg decider) |
| Cold start | 120 s (`loading_delay`): the protocol's default; this overlay has no GPU measurement |
| Metrics | scrape 15 s (the rendered PodMonitors), `metrics_delay_s` 0 (raw series), HPA sync 15 s, `pollingInterval` 15 s |
| Seed | blis's default (no `--seed`); the load's seed is `schedule.seed` in `blis-run.json` |
| Scenario | `benchmark/config/scenarios/staging/pd-disaggregation/uncached-concurrency.yaml`, rendered with `standup --dry-run`; policy [`policy.json`](policy.json) (the as-rendered GLM-5.3 constants; the pool is pinned, so only the HPA log reads them; [`scaledobjects.json`](../../policy-glm-constants/scaledobjects.json)), translated from it ([`terms.json`](../../terms.json)) |
| Model | `deepseek-ai/DeepSeek-V2-Lite`, 1 H100 per replica (TP1), both roles |
| SLO | TTFT <= 2 s, TPOT <= 0.05 s; X = 0.95 |
| Run | 1c, knee 256:4096, decode pool |
| Load | four 300 s stages at 0.6, 0.8, 1.0 and 1.25 x an estimate of 3.9 req/s ([`knee-index.json`](knee-index.json)) |
| Arm | pinned: decode 1, prefill 6 |
| Gaps exposed | see the summary |
| Memory | peak RSS 4.52 GiB of a 29.61 GiB budget; not killed |
| Raw results | `benchmark/results/step3-uncached-concurrency-20261124/decode-256x4096-e3.9/` (not committed) |

![load vs supply, decode pool](load-vs-supply-decode.svg)

256:4096 at four rates (2.340, 3.120, 3.900, 4.875 req/s) on one pinned decode pod. A per stage: 100.0 %, 100.0 %, 100.0 %, 52.2 %; it crosses 0.95 between stages 3 and 4, at μ_SLO = 4.002 req/s. The trigger panels are the HPA's own reading at each sync, from blis's decision log, not a Prometheus query. Every number is a simulator number. Each run is one sample (n = 1).

## Per stage, decode pool

| stage | s | set req/s | offered req/s | λ_in tok/s | λ_out tok/s | sent | errors | A | TTFT p50/p90/p99 s | TPOT p50/p90/p99 ms | Ready | need | requested replica-s | Ready replica-s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 2.340 | 2.340 | 599 | 9,585 | 702 | 0 | 100.0 % | 0.10/0.11/0.12 | 19.4/20.8/21.2 | 1–1 | – | 300 | 300 |
| 2 | 300 | 3.120 | 3.120 | 799 | 12,780 | 936 | 0 | 100.0 % | 0.11/0.12/0.13 | 23.8/24.0/24.4 | 1–1 | – | 300 | 300 |
| 3 | 300 | 3.900 | 3.900 | 998 | 15,974 | 1,170 | 0 | 100.0 % | 0.12/0.13/0.14 | 27.4/28.2/29.5 | 1–1 | – | 300 | 300 |
| 4 | 300 | 4.875 | 4.877 | 1,248 | 19,975 | 1,463 | 0 | 52.2 % | 0.15/46.23/76.47 | 35.9/42.6/44.0 | 1–1 | – | 300 | 300 |

- run: 4,271 sent, A 83.6 %, errors 0, requested 1,200 replica-s = 1,200 GPU-s at 1 GPU per replica
- placement: 0 request(s) before the first stage, 0 after the last; stages more than 3 sd off their set rate: none: ok
- knee: μ_SLO = 4.002 req/s (A crosses 0.95 between stages 3 and 4)

## What the run shows

The run shows a problem when stage 1 fails or stage 4 passes (the crossing is outside the stages). Stage 1 passed (A 100.0 %) and stage 4 failed (A 52.2 %), so the crossing is inside them: μ_SLO(256:4096, decode) = 4.002 req/s (A crosses 0.95 between stages 3 and 4, linear interpolation). The mix's requests last about 100 s at the TPOT limit, a third of a 300 s stage, so μ_SLO is an upper bound (run-set.md §2).

**Outcome: as expected; μ_SLO = 4.002 req/s.**

## Amendments

None.
