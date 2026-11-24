# Step 3, run 1b: knee 2048:2048, decode pool (pd-disaggregation/uncached-concurrency)

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
| Run | 1b, knee 2048:2048, decode pool |
| Load | four 300 s stages at 0.6, 0.8, 1.0 and 1.25 x an estimate of 5.5 req/s ([`knee-index.json`](knee-index.json)) |
| Arm | pinned: decode 1, prefill 6 |
| Gaps exposed | see the summary |
| Memory | peak RSS 3.85 GiB of a 30.41 GiB budget; not killed |
| Raw results | `benchmark/results/step3-uncached-concurrency-20261124/decode-2048x2048-e5.5/` (not committed) |

![load vs supply, decode pool](load-vs-supply-decode.svg)

2048:2048 at four rates (3.300, 4.400, 5.500, 6.875 req/s) on one pinned decode pod. A per stage: 100.0 %, 100.0 %, 100.0 %, 53.0 %; it crosses 0.95 between stages 3 and 4, at μ_SLO = 5.647 req/s. The trigger panels are the HPA's own reading at each sync, from blis's decision log, not a Prometheus query. Every number is a simulator number. Each run is one sample (n = 1).

## Per stage, decode pool

| stage | s | set req/s | offered req/s | λ_in tok/s | λ_out tok/s | sent | errors | A | TTFT p50/p90/p99 s | TPOT p50/p90/p99 ms | Ready | need | requested replica-s | Ready replica-s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 3.300 | 3.300 | 6,758 | 6,758 | 990 | 0 | 100.0 % | 0.12/0.13/0.13 | 19.4/19.8/20.1 | 1–1 | – | 300 | 300 |
| 2 | 300 | 4.400 | 4.400 | 9,011 | 9,011 | 1,320 | 0 | 100.0 % | 0.13/0.14/0.14 | 22.0/22.7/22.8 | 1–1 | – | 300 | 300 |
| 3 | 300 | 5.500 | 5.500 | 11,264 | 11,264 | 1,650 | 0 | 100.0 % | 0.14/0.15/0.16 | 25.5/26.2/27.2 | 1–1 | – | 300 | 300 |
| 4 | 300 | 6.875 | 6.877 | 14,083 | 14,083 | 2,063 | 0 | 53.0 % | 0.59/17.28/25.34 | 32.9/35.6/36.0 | 1–1 | – | 300 | 300 |

- run: 6,023 sent, A 83.9 %, errors 0, requested 1,200 replica-s = 1,200 GPU-s at 1 GPU per replica
- placement: 0 request(s) before the first stage, 0 after the last; stages more than 3 sd off their set rate: none: ok
- knee: μ_SLO = 5.647 req/s (A crosses 0.95 between stages 3 and 4)

## What the run shows

The run shows a problem when stage 1 fails or stage 4 passes (the crossing is outside the stages). Stage 1 passed (A 100.0 %) and stage 4 failed (A 53.0 %), so the crossing is inside them: μ_SLO(2048:2048, decode) = 5.647 req/s (A crosses 0.95 between stages 3 and 4, linear interpolation).

**Outcome: as expected; μ_SLO = 5.647 req/s.**

## Amendments

None.
