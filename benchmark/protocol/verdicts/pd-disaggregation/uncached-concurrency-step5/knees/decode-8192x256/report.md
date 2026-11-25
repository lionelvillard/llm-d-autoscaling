# Step 5, run 1a: knee 8192:256, decode pool (pd-disaggregation/uncached-concurrency)

Part of the [step 5 summary](../../../uncached-concurrency-step5.md).

| | |
|---|---|
| Namespace | `step5-uncached-concurrency-20261125`, Kubernetes v1.32.9 (OpenShift) |
| Scenario / overlay | `staging/pd-disaggregation/uncached-concurrency.yaml` at `2e607e4a` / `ocp/vllm-rdma.yaml` (the `--set` flags are in the summary) |
| Model / GPU | deepseek-ai/DeepSeek-V2-Lite bf16 / 1 × NVIDIA H100 80GB HBM3 per replica, both roles |
| Images, KEDA | as in the summary header |
| SLO | TTFT ≤ 2 s, TPOT ≤ 0.05 s; X = 0.95 |
| Profile / load | [`profile.yaml`](profile.yaml); `knee-decode-8192x256.csv` (10,409 requests, seed 1; `gen_load.py knee --mix 8192:256 --estimate 9.5`), client timeout 60 s; schedule in [`load.json`](load.json) |
| Arm | pinned (`paused-replicas`): decode 1, prefill 4 |
| Session | `villardl-20261124-223310-750` |
| Start / end (UTC) | 2026-11-25 03:34:10 / 2026-11-25 03:55:10 (inference-perf stage 0, with the drain) |
| Raw results | `benchmark/results/villardl-20261124-223310-750/results/inference-perf-1795577636-ctpfen_1/` (not committed) |

![load vs supply, decode pool](load-vs-supply-decode.svg)

Four 300 s stages of 8192:256 at 5.7 to 11.9 req/s against one pinned decode
pod, with four prefill pods. A is 0.982 and 0.979 in stages 1 and 2, then
0.061 and 0.000: TPOT p50 jumps from 46.7 to 70.3 ms and the decode pod's KV
fills (mean 0.994 in stage 3). The decode composite reads 0.95 in stages 1 and
2, set by the `itl` term, and 1.46 past the knee. The prefill pool's figure is
the second one.

![load vs supply, prefill pool](load-vs-supply-prefill.svg)

## Per stage, decode pool

| stage | s | set req/s | offered req/s | λ_in tok/s | λ_out tok/s | sent | errors | A | TTFT p50/p90/p99 s | TPOT p50/p90/p99 ms | Ready | need | requested replica-s | Ready replica-s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 5.700 | 5.600 | 45,875 | 1,607 | 1,680 | 0 | 98.2 % | 0.47/0.72/1.11 | 37.1/42.8/62.9 | 1–1 | – | 300 | 300 |
| 2 | 300 | 7.600 | 7.640 | 62,587 | 2,314 | 2,292 | 0 | 97.9 % | 0.52/0.79/1.24 | 46.7/47.7/70.7 | 1–1 | – | 300 | 300 |
| 3 | 300 | 9.500 | 9.397 | 76,977 | 2,867 | 2,819 | 0 | 6.1 % | 11.37/23.60/25.88 | 70.3/71.2/105.8 | 1–1 | – | 300 | 300 |
| 4 | 300 | 11.875 | 12.060 | 13,926 | 431 | 3,618 | 3108 error | 0.0 % | 31.90/39.33/49.29 | 70.3/70.7/105.0 | 1–1 | – | 300 | 300 |

- run: 10,409 sent, A 39.1 %, errors {'error': 3108}, requested 1,200 replica-s = 1,200 GPU-s at 1 GPU per replica
- placement: 0 request(s) before the first stage, 0 after the last; stages more than 3 sd off their set rate: none: ok
- knee: μ_SLO = 7.696 req/s (A crosses 0.95 between stages 2 and 3)

## Per stage, prefill pool

| stage | s | set req/s | offered req/s | λ_in tok/s | λ_out tok/s | sent | errors | A | TTFT p50/p90/p99 s | TPOT p50/p90/p99 ms | Ready | need | requested replica-s | Ready replica-s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 5.700 | 5.600 | 45,875 | 1,607 | 1,680 | 0 | 98.2 % | 0.47/0.72/1.11 | 37.1/42.8/62.9 | 4–4 | – | 1,200 | 1,200 |
| 2 | 300 | 7.600 | 7.640 | 62,587 | 2,314 | 2,292 | 0 | 97.9 % | 0.52/0.79/1.24 | 46.7/47.7/70.7 | 4–4 | – | 1,200 | 1,200 |
| 3 | 300 | 9.500 | 9.397 | 76,977 | 2,867 | 2,819 | 0 | 6.1 % | 11.37/23.60/25.88 | 70.3/71.2/105.8 | 4–4 | – | 1,200 | 1,200 |
| 4 | 300 | 11.875 | 12.060 | 13,926 | 431 | 3,618 | 3108 error | 0.0 % | 31.90/39.33/49.29 | 70.3/70.7/105.0 | 4–4 | – | 1,200 | 1,200 |

- run: 10,409 sent, A 39.1 %, errors {'error': 3108}, requested 4,800 replica-s = 4,800 GPU-s at 1 GPU per replica
- placement: 0 request(s) before the first stage, 0 after the last; stages more than 3 sd off their set rate: none: ok
- knee: μ_SLO = 7.696 req/s (A crosses 0.95 between stages 2 and 3)

- the generator kept up: `schedule_delay_seconds` max 0.241 s, p99 0.138 s.
- no eviction, OOM kill or image pull failure of a serving pod during the run ([`events.txt`](events.txt)).

## Triggers per stage

Means over the last 120 s of each stage or phase ([`terms.json`](terms.json), from `triggers/`). `term_*` are the decode formula's four terms; `composite` is each formula evaluated on the exported series (`triggers/<pool>/composite.json`).

| phase | req/s | decode.conc | decode.kv | decode.itl | decode.lam | decode.gen_over_ok | decode.term_conc | decode.term_lam | decode.term_kv | decode.term_itl | decode.composite | prefill.offered | prefill.comp | prefill.done | prefill.composite |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5.7 | 55.4 | 0.349 | 0.0475 | 5.57 | 262 | 0.109 | 0.0813 | 0.436 | 0.95 | 0.95 | 73,859 | 38,237 | 38,237 | 1.97 |
| 2 | 7.6 | 91 | 0.573 | 0.0475 | 7.57 | 258 | 0.178 | 0.109 | 0.716 | 0.951 | 0.951 | 100,397 | 59,931 | 59,931 | 2.67 |
| 3 | 9.5 | 332 | 0.994 | 0.073 | 9.53 | 259 | 0.65 | 0.138 | 1.24 | 1.46 | 1.46 | 126,466 | 74,827 | 74,827 | 3.37 |
| 4 | 11.9 | 712 | 0.992 | 0.0728 | 12 | 475 | 1.4 | 0.317 | 1.24 | 1.46 | 1.46 | 158,668 | 94,686 | 94,686 | 4.23 |

## What the run shows

The run shows a problem when stage 1 fails or stage 4 passes. Stage 1 passed
(A 0.982) and stage 4 failed (A 0.000), so μ_SLO(8192:256, decode) =
**7.696 req/s**: 0.38 × blis's 20.267 req/s, and 5.8 × the first (TCP)
plant's 1.328 req/s.

- **TPOT binds, then KV.** TPOT p50 is 37.1 and 46.7 ms in stages 1 and 2
  (p90 42.8 and 47.7 ms) and 70.3 ms past the knee, where the mean KV usage
  reads 0.994 with 332 requests running or waiting. TTFT p90 stays at or
  below 0.79 s until the knee: the KV transfer no longer binds.
- **The `itl` guard decides at this knee.** ITL p90 reads 0.0475 s in stages 1
  and 2, so `pods × itl / 0.05` = 0.95, against 0.109 to 0.178 for `conc / 510`,
  0.08 to 0.11 for the offered-output term and 0.44 to 0.72 for `kv`. Step 1
  predicted that `itl` reads about 0.58 per pod at a knee and never wins below
  1.25 × μ_SLO (PF8); on this plant it is the largest term at the knee, and it
  reads 1.46 (ceil 2 pods) once the knee is passed.
- **PF10 holds on the drivers.** `conc / 510` and the offered-output term
  read 0.11 to 0.18 of a pod at 0.74 to 0.99 × μ_SLO; without the `kv` and
  `itl` guards the formula would not size decode for this mix.
- **The EPP counts 1.6 × the client's prompt tokens** (PF3): prefill
  `offered` over the client's λ_in reads 73,859 / 45,875 = 1.61, then 1.60,
  1.64. The prefill composite reads 1.97 at 45,875 client prompt tokens/s:
  the prefill ScaledObject would ask for 2 pods where 37,540 engine tokens/s
  per pod would ask for 1.22.
- Errors: 3,108, all `TimeoutError` (60 s client timeout), all in stage 4.

**Outcome: as expected; μ_SLO = 7.696 req/s** (the crossing is inside the
stages).

## Amendments

None.
