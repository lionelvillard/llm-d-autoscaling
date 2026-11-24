# Step 3, run 1a: knee 8192:256, decode pool (pd-disaggregation/uncached-concurrency)

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
| Run | 1a, knee 8192:256, decode pool |
| Load | four 300 s stages at 0.6, 0.8, 1.0 and 1.25 x an estimate of 20 req/s ([`knee-index.json`](knee-index.json)) |
| Arm | pinned: decode 1, prefill 8 (the other pool large enough not to bind) |
| Gaps exposed | see the summary |
| Memory | peak RSS 7.89 GiB of a 29.43 GiB budget; not killed |
| Raw results | `benchmark/results/step3-uncached-concurrency-20261124/decode-8192x256-e20/` (not committed) |

![load vs supply, decode pool](load-vs-supply-decode.svg)

8192:256 at four rates (12.000, 16.000, 20.000, 25.000 req/s) on one pinned decode pod. A per stage: 100.0 %, 100.0 %, 100.0 %, 6.2 %; it crosses 0.95 between stages 3 and 4, at μ_SLO = 20.267 req/s. The trigger panels are the HPA's own reading at each sync, from blis's decision log, not a Prometheus query. Every number is a simulator number. Each run is one sample (n = 1).

## Per stage, decode pool

| stage | s | set req/s | offered req/s | λ_in tok/s | λ_out tok/s | sent | errors | A | TTFT p50/p90/p99 s | TPOT p50/p90/p99 ms | Ready | need | requested replica-s | Ready replica-s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 12.000 | 12.000 | 98,304 | 3,072 | 3,600 | 0 | 100.0 % | 0.24/0.31/0.43 | 20.5/21.5/22.0 | 1–1 | – | 300 | 300 |
| 2 | 300 | 16.000 | 16.000 | 131,072 | 4,096 | 4,800 | 0 | 100.0 % | 0.25/0.34/0.46 | 24.0/25.8/27.6 | 1–1 | – | 300 | 300 |
| 3 | 300 | 20.000 | 20.000 | 163,840 | 5,120 | 6,000 | 0 | 100.0 % | 0.27/0.63/1.08 | 29.3/30.7/30.7 | 1–1 | – | 300 | 300 |
| 4 | 300 | 25.000 | 25.000 | 204,800 | 6,400 | 7,500 | 941 timeout | 6.2 % | 25.14/47.40/51.68 | 30.7/30.7/30.7 | 1–1 | – | 300 | 300 |

- run: 21,900 sent, A 67.9 %, errors {'timeout': 941}, requested 1,200 replica-s = 1,200 GPU-s at 1 GPU per replica
- placement: 0 request(s) before the first stage, 0 after the last; stages more than 3 sd off their set rate: none: ok
- knee: μ_SLO = 20.267 req/s (A crosses 0.95 between stages 3 and 4)

## What the run shows

The run shows a problem when stage 1 fails or stage 4 passes (the crossing is outside the stages). Stage 1 passed (A 100.0 %) and stage 4 failed (A 6.2 %), so the crossing is inside them: μ_SLO(8192:256, decode) = 20.267 req/s (A crosses 0.95 between stages 3 and 4, linear interpolation).

**Outcome: as expected; μ_SLO = 20.267 req/s.**

## Amendments

None.
