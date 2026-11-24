# Step 3, run 1d: knee blend, decode pool (pd-disaggregation/uncached-concurrency)

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
| Run | 1d, knee blend, decode pool |
| Load | four 300 s stages at 0.6, 0.8, 1.0 and 1.25 x an estimate of 6.3 req/s ([`knee-index.json`](knee-index.json)) |
| Arm | pinned: decode 1, prefill 8 |
| Gaps exposed | see the summary |
| Memory | peak RSS 4.57 GiB of a 29.4 GiB budget; not killed |
| Raw results | `benchmark/results/step3-uncached-concurrency-20261124/decode-blend-e6.3/` (not committed) |

![load vs supply, decode pool](load-vs-supply-decode.svg)

blend at four rates (3.780, 5.040, 6.300, 7.875 req/s) on one pinned decode pod. A per stage: 100.0 %, 100.0 %, 100.0 %, 50.9 %; it crosses 0.95 between stages 3 and 4, at μ_SLO = 6.461 req/s. The trigger panels are the HPA's own reading at each sync, from blis's decision log, not a Prometheus query. Every number is a simulator number. Each run is one sample (n = 1).

## Per stage, decode pool

| stage | s | set req/s | offered req/s | λ_in tok/s | λ_out tok/s | sent | errors | A | TTFT p50/p90/p99 s | TPOT p50/p90/p99 ms | Ready | need | requested replica-s | Ready replica-s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 3.780 | 3.780 | 13,225 | 8,064 | 1,134 | 0 | 100.0 % | 0.12/0.24/0.25 | 19.7/20.5/20.9 | 1–1 | – | 300 | 300 |
| 2 | 300 | 5.040 | 5.040 | 17,633 | 10,752 | 1,512 | 0 | 100.0 % | 0.13/0.25/0.28 | 22.7/24.6/25.8 | 1–1 | – | 300 | 300 |
| 3 | 300 | 6.300 | 6.300 | 22,042 | 13,440 | 1,890 | 0 | 100.0 % | 0.14/0.26/0.30 | 27.4/28.5/29.9 | 1–1 | – | 300 | 300 |
| 4 | 300 | 7.875 | 7.880 | 27,569 | 16,811 | 2,364 | 0 | 50.9 % | 1.41/41.28/46.44 | 33.2/36.2/38.4 | 1–1 | – | 300 | 300 |

- run: 6,900 sent, A 83.2 %, errors 0, requested 1,200 replica-s = 1,200 GPU-s at 1 GPU per replica
- placement: 0 request(s) before the first stage, 0 after the last; stages more than 3 sd off their set rate: none: ok
- knee: μ_SLO = 6.461 req/s (A crosses 0.95 between stages 3 and 4)

## What the run shows

The run shows a problem when stage 1 fails or stage 4 passes (the crossing is outside the stages). Stage 1 passed (A 100.0 %) and stage 4 failed (A 50.9 %), so the crossing is inside them: μ_SLO(blend, decode) = 6.461 req/s (A crosses 0.95 between stages 3 and 4, linear interpolation). The decode pod's mean KV usage reads 0.74 in stage 3 and 1.00 in stage 4 (`kv`), and its running + waiting requests 359 and 683: KV binds the blend before the engine's sequence limit does.

**Outcome: as expected; μ_SLO = 6.461 req/s.**

## Amendments

None.
