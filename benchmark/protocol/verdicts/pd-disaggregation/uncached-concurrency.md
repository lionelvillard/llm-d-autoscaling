# Static signal analysis: pd-disaggregation/uncached-concurrency

Step 1 of the [evaluation protocol](../../README.md), produced with the
`static-signal-analysis` skill. Properties P1–P11 are defined in
[step 1](../../1-static-signal-analysis.md) §1.2. Cited `27_keda-scaledobjects.yaml`,
`12_router-values.yaml`, `13_ms-values.yaml` and `18_podmonitor.yaml` are from
the rendered plan (namespace `ssa-0551`, a placeholder).

The ScaledObjects come from llm-d-autoscaling-research task 0545
(`experiments/pd-scaledobjects-glm53/manifests/`, findings
`findings/derived/system/pd/pd-scaledobjects-glm53.md`), with the model
switched from GLM-5.3 to DeepSeek-V2-Lite. The task owner fixed the metrics,
formulas and behavior; this analysis changed only label selectors and the
ScaledObject names (see Label fixes).

**Revision (2e607e4a).** The first version of this verdict (`d21170d0`)
analyzed task 0545's GLM-5.3 TP8 H200 constants. Commit `2e607e4a` replaced
them with DeepSeek-V2-Lite H100 values taken from the step 3 blis knees
([`uncached-concurrency-step3.md`](uncached-concurrency-step3.md),
"Calibration"), with task 0545's rules: prefill divisor 10850 → 37540
(0.7 × 53,628 tok/s), `conc / 4` → `conc / 510` (1.3 × 392), 0.39 → 8.4
(1.3 × 6.461 req/s), 700 → 2133 (the blend's mean OSL, both places), ITL SLO
0.075 → 0.05. Metrics, labels and behavior are unchanged. P3, the decode
cross-over, the predictions and the verdict below are redone for these
values. Every capacity number from step 3 is a simulator number (tag `sim`):
blis priced this plant, and step 5 must confirm it on the GPU.

Source references:

- **V** = `vllm-project/vllm@db9527a4` (tag `v0.31.0`), the overlay's image.
- **E** = `llm-d/llm-d-router@b9393d1a` (tag `v1.0.0`), the EPP and router chart.
- **B** = `llm-d/llm-d-benchmark@0fb187fb`, the renderer.

| | |
|---|---|
| Scenario | `benchmark/config/scenarios/staging/pd-disaggregation/uncached-concurrency.yaml` at `2e607e4a` (constants); label fixes from `d21170d0` |
| Backend overlay | `benchmark/config/cluster-configs/ocp/vllm.yaml` (target: OpenShift `pokprod001`, H100 80GB, 1 GPU per pod, TP1) |
| Rendered with | `llmdbenchmark standup --dry-run`, llm-d-benchmark@`0fb187fb`, through a temporary spec pointing at the scenario (the repo has no `specification/staging/pd-disaggregation/uncached-concurrency.yaml.j2`). The Jinja plan rendered; the helmfile step failed offline, so the modelservice values were read from `13_ms-values.yaml` before chart rendering |
| Load | The scenario's `sanity_random.yaml` (B): open loop, `constant` at `q` = 1 req/s for 30 s; random prompts, mean ISL 384, OSL 50, `ignore_eos`. `λ_in = 1 × 384 = 384`, `λ_out = 1 × 50 = 50` tokens/s; no prefix reuse. Steps 3/5 use the run set (`run-set.md` §1): 8192:256, 2048:2048, 256:4096 and their blend, random prompts (agentic run aside), so `comp / done ≈ 1` on every run but the agentic one |
| Date | 2026-11-24; revised the same day for the constants of `2e607e4a` |
| Verdict | **Accepted with conditions** |

**Accepted with conditions.** Each pool has a proportional driver: offered
prompt tokens at the router times the measured uncached share on prefill
(arrival-side, open-loop, so it passes P1, P2 and P5), and requests in progress
on decode, backed by an offered-output-token term. After the label fixes below,
every selector picks one stack's pool and every EPP series has exactly one
producer in the effective configuration (P10, P11). With the blis-calibrated
constants, prefill's 37540 sets a 0.7 target on the blend (0.75 on 8192:256)
and passes P3 in the simulator. Three conditions remain:

- Decode's two proportional terms target 1.3 × the blend's μ_SLO knee, so the
  pool settles at about 1.1 × μ_SLO per pod, past the knee, with no headroom
  (P3).
- Across the mixes their reading at a pod's knee varies about threefold (0.29
  on 8192:256, 0.91 on 256:4096). On 8192:256 the KV guard, not the driver,
  sizes decode.
- The prefill numerator counts the EPP's 4-bytes-per-token estimate, not
  engine tokens (`e`). All constants are blis values that step 5 must confirm
  on the GPU.

**Predicted:** under the scenario's own sanity load, both pools hold at
`minReplicaCount: 2`. Under the run set, decode tracks load but settles at
about 7.0–7.3 blend req/s per pod against a μ_SLO of 6.461. Below the knee the
offered term decides, past it `conc`; the KV guard decides on 8192:256.
Prefill stays at 2 until the offered uncached work exceeds 82,588 tok/s for
15 minutes, then grows one pod per 5 minutes and holds each pod for at least
an hour.

vLLM v0.31.0 is enough: every vLLM series read here is in v0.31.0 with the same
labels and write points. `git diff v0.31.0 v0.32.0 -- vllm/v1/metrics/{loggers,stats}.py`
adds only `num_requests_kv_fetch_by_stage`, `watermark_requests`,
`prompt_tokens_cached_by_source` and `admission_rejections`, none of which is
read. The "vLLM ≥ 0.32" in task 0545 reflects that catalog's version window, not
a dependency of these queries. No `images.vllm.tag` change is needed.

## Label fixes made in the scenario

| Trigger(s) | Before | After | Why |
|---|---|---|---|
| `offered` | `{namespace, endpoint_role="prefill"}` | `+ job="${model.idLabel}-router-epp", plugin_name="approx-prefix-cache-producer"` | `prefix_prompt_tokens` has no pool label (E `prefixmetrics/metrics.go#L78-L88`: `plugin_name, plugin_type, endpoint_role, modality`); a second stack's EPP in the namespace (N1) was summed in. `plugin_name` keeps the selector on one producer if a second prefix producer is ever configured (P11) |
| `lam` (both selectors) | `{namespace}` | `+ job="${model.idLabel}-router-epp"` | EPP `request_*` carry no pool label (trap T15): N1 |
| `comp`, `done` | `{namespace, role="prefill"}` | `+ pod=~"${model.idLabel}-prefill-.*"` | `role` is a static relabel every modelservice stack in the namespace stamps: N1 |
| `conc`, `gen`, `ok`, `pods`, `kv`, `itl` | `{namespace, role="decode"}` | `+ pod=~"${model.idLabel}-decode-.*"` | same, decode |
| both ScaledObjects | `name: pd-disaggregation-{prefill,decode}` | `name: ${model.idLabel}-{prefill,decode}` | trap T17: a second stack inheriting the block would overwrite the object |

`role` is kept: it is what removes the duplicate series of the second,
unrelabelled PodMonitor (trap T14; `18_podmonitor.yaml:1-15` renders
`vllm-deepseek-886595ad--v2-lite` at 30 s, while `13_ms-values.yaml:328-331` and
`:626-629` relabel `role` only on the modelservice PodMonitors). Rendered values:
`job="deepseek-886595ad--v2-lite-router-epp"`. That is the router chart's
`<release>-epp`, with the release name truncated to 40 characters
(E `config/charts/routerlib/templates/_helpers.tpl#L14-L17`). The release here is
33 characters, so the pin matches. An `idLabel` longer than 33 characters would
break it.

## Deployed versions

| Component | Version | Source of the version |
|---|---|---|
| vLLM (both roles) | `docker.io/vllm/vllm-openai:v0.31.0` (`db9527a4`) | overlay `ocp/vllm.yaml:82`; `13_ms-values.yaml:158,454` |
| EPP | `ghcr.io/llm-d/llm-d-router-endpoint-picker:v1.0.0` (`b9393d1a`) | B `config/templates/values/defaults.yaml:119`; `12_router-values.yaml:16-20` |
| EPP configuration | `pd-config.yaml`: `always-disagg-pd-decider`, `disagg-profile-handler`, `approx-prefix-cache-producer` (no parameters), `prefill-filter`, `decode-filter`, `prefix-cache-scorer`, `queue-scorer`, `kv-cache-utilization-scorer`, `active-request-scorer`. No `featureGates`, no `flowControl`. Loader adds (trap T18): `utilization-detector` (defaults 5 / 0.8, filter in both profiles, T19), the metrics data source and vLLM extractor, `inflight-load-producer` (for `active-request-scorer`), `token-producer` with the `estimate` backend (`router.tokenizer.enabled: false`) | `12_router-values.yaml:21-55`, `:99-100` |
| Routing sidecar | `llm-d-router-disagg-sidecar:v1.0.0`, connector `nixlv2` | `13_ms-values.yaml:29`; scenario `routing.connector` |
| Router chart / modelservice chart | `v1.0.0` / `v0.4.16` | B `defaults.yaml:115,117` |
| Scrape intervals | vLLM 15 s (scenario PodMonitors; the extra `vllm-<model>` PodMonitor 30 s); EPP 10 s | `13_ms-values.yaml:327,621`; `18_podmonitor.yaml:15`; `12_router-values.yaml:84` |
| Prometheus endpoint | OpenShift Thanos querier, bearer auth | `27_keda-scaledobjects.yaml:25-26` |
| KEDA | not known for `pokprod001` (OpenShift may run the Custom Metrics Autoscaler); `benchmark/README.md` requires 2.20+ | *needs measurement*; trap T7 is *unverified* on a release |

Note on the template: llm-d-benchmark@`0fb187fb` renders `fallback`,
`ignoreNullValues` and `scalingModifiers`
(`27_keda-scaledobjects.yaml:31,58-61,79-82`). The defaults table in
[`1-per-trigger-how-to.md`](../../1-per-trigger-how-to.md) §1, written at `bd7d768`, says
it drops them. That table is out of date.

## ScaledObject `deepseek-886595ad--v2-lite-prefill`

- `minReplicaCount: 2`, `maxReplicaCount: 4`, `pollingInterval: 15` (`27_keda-scaledobjects.yaml:15-17`).
- `fallback`: 3 failures, 2 replicas, `currentReplicasIfHigher` (`:58-61`); valid, since the composite target `"1"` parses as a positive integer.
- Scale-up: stabilization 900 s, 1 pod / 300 s. Scale-down: stabilization 3600 s, 1 pod / 600 s (`:62-78`).
- `scalingModifiers`: `max(done > 0 ? offered * comp / done : offered, comp) / 37540`, `target: "1"`, `AverageValue` (`:79-82`). Per-trigger thresholds are parsed but do not reach the HPA; `desired = ceil(formula)`.

### Trigger `offered`

```promql
sum(rate(llm_d_epp_prefix_prompt_tokens_sum{namespace="ssa-0551",job="deepseek-886595ad--v2-lite-router-epp",plugin_name="approx-prefix-cache-producer",endpoint_role="prefill"}[1m]))
```

`metricType: AverageValue`, `threshold: "1"`, `activationThreshold: "0"`,
`ignoreNullValues: "false"` (`27_keda-scaledobjects.yaml:19-31`).

- **What it counts:** the `_sum` of a histogram observed once per request in the
  approximate prefix producer's `PreRequest`, after scheduling and before the
  request is sent. The value is the request's prompt token count.
  `endpoint_role` is `prefill` whenever the prefill profile picked an endpoint.
  `source`: E `…/dataproducer/prefixmetrics/metrics.go#L78-L88` (definition),
  `#L153-L158` (`RecordPrediction`), `#L178-L189` (`PredictionTarget`);
  `…/dataproducer/approximateprefix/plugin.go#L284-L345` (`PreRequest`,
  `PromptTokens: request.Body.TokenizedRequest.TokenCount()` at `#L341`).
  The token count comes from the auto-created `estimate` backend:
  "tokenizer-free byte-packing … ≈4 bytes/token; its token IDs do not
  correspond to engine tokens" (E `…/dataproducer/tokenizer/README.md#L20,L144-L147`;
  `BytesPerToken = 4`, E `pkg/epp/framework/interface/requesthandling/types.go#L202-L206`).
- **Kind:** offered work rate, counted before any queue: flow control is off, so
  the EPP dispatches at arrival. **Role it can play:** driver. **Role it plays
  here:** the driver's numerator.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P1 proportional | pass | a rate of arrivals × prompt size; no queue wait in it; `ε = 1` at a fixed mix | source |
| P2 coupled to actuation | pass | open loop: arrivals at the router do not depend on prefill `R` | config |
| P3 fixed busyness | pass (sim) / measure | 37540 = 0.7 × 53,628 computed tok/s, one V2-Lite H100 prefill pod's knee on the blend (step 3 run 1f, `sim`). At the 8192:256 knee (49,930 tok/s, run 1e) the target is `37,540 / 49,930 = 0.75`: `V = 53,628 / 49,930 = 1.07` over the mixes where prefill binds (2048:2048 and 256:4096 never bound prefill up to 50 req/s). Open: the numerator is EPP pseudo-tokens (bytes / 4), the divisor engine-computed tokens, so the ask scales by `e = offered / rate(vllm:prompt_tokens_total{prefill})`, which blis does not model (its `offered` counts engine tokens). The knee is a blis number until step 5 | source, sim |
| P4 metric type | pass | `sum(rate(...))` is extensive; composite `AverageValue`, target 1 (`:79-82`) | config |
| P5 bounds | pass | not capped (arrivals are counted, not service), not integrating; at 2× capacity it asks 2× | source |
| P6 defined at zero | pass | `minReplicaCount: 2`. With no prefill pod, `PredictionTarget` attributes requests to `decode` (E `metrics.go#L185-L187`), so this selector would read nothing and the scaler errors, not 0 | source |
| P7 fails visibly | pass | no `or vector(0)`, `ignoreNullValues: "false"`. Lost EPP series → error → fallback holds `max(N, 2)`. Side effect: the histogram series only appears with the first request, so after every EPP start the prefill ScaledObject errors until traffic arrives, and fallback holds the current size (PF2) | config, source |
| P8 lag and noise | fail (by design) | lag `10 + 30 + 15 = 55 s` (EPP scrape, ½ of `[1m]`, polling), plus the 900 s scale-up stabilization: ≈ 955 s against a cold start of a few minutes (measure). Task 0545 chose 900 s to absorb a GLM agentic session-cache fill (≈ 650 s there). The run set's random prompts have no such fill. Noise: `1/√(q × 60)`, 13 % at q = 1 req/s, 6 % at 5 req/s; the scale-up window takes the minimum over 900 s, so noise does not trigger scale-up | config |
| P9 measures what it claims | pass, with the estimate | arrival-side prompt tokens of requests routed to prefill; T8 (counted after scheduling) is harmless with the gate off and `minReplicas: 2`. The count is an estimate (P3) | source |
| P10 selects its own pool | pass (after fix) | N1: `job` pins this stack's EPP. N2: `namespace`. N3: `endpoint_role="prefill"`. N4: one ServiceMonitor, and `29_epp-keda-saturation-epp-monitoring.yaml` renders empty. Step 2 confirms `count by (job, plugin_name, endpoint_role, modality)` returns one series | config |
| P11 router configuration | pass | `approx-prefix-cache-producer` is listed explicitly (`12_router-values.yaml:32`), one instance, so `plugin_name` = its type. The prompt tokens come from the loader's `estimate` `token-producer` (T18), hence P3's `e`. No parameter changes the count. The `utilization-detector` filter (T19) does not touch it | source |

**Failure case (P3, `e`):** 8192:256 at `q` = 8 req/s, random prompts, so
`comp / done = 1` and `λ_in = 65,536` tok/s. With `e = 1` the ask is
`ceil(65,536 / 37,540) = ceil(1.75) = 2`: each pod at
`32,768 / 49,930 = 0.66` of its knee, as intended. With `e = 1.3` it is
`ceil(2.27) = 3`, 30 % more pods than the target means. With `e = 0.8` it
reads 1.40, so the pool stays at 2 up to `2 × 1.1 × 37,540 / 0.8 = 103,235`
tok/s, which is 12.6 req/s or `1.03 ×` two pods' knee: no headroom left.

### Trigger `comp`

```promql
sum(rate(vllm:prompt_tokens_by_source_total{namespace="ssa-0551",role="prefill",pod=~"deepseek-886595ad--v2-lite-prefill-.*",source="local_compute"}[5m]))
```

`AverageValue`, `threshold: "1"`, `activationThreshold: "0"`, `ignoreNullValues: "false"` (`:32-44`).

- **What it counts:** a counter of prompt tokens the engine computed: prompt
  minus local prefix-cache hits minus external KV transfer. It is incremented
  when the request's first output is processed, from the same `PrefillStats` as
  `vllm:prompt_tokens`. `source`: V `vllm/v1/metrics/loggers.py#L695-L708`
  (definition, labels `model_name, engine, source`; series pre-created per
  source), `#L1126-L1132` (inc), `vllm/v1/metrics/stats.py#L281-L295`
  (`computed = prompt − cached`), `#L408-L415`, `#L469-L471` (only while
  `is_prefilling`).
- **Kind:** completed work rate. **Role it can play:** guard (floor), and the
  numerator of the uncached share. **Role it plays here:** both.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P4 metric type | pass | extensive `sum(rate)` | config |
| P5 bounds | pass | capped at served supply `R × μ_P`. As a floor it never exceeds the driver below saturation (`comp ≤ offered × comp / done` while every offered prefill completes) | source |
| P7 fails visibly | pass | no default; `ignoreNullValues: "false"` | config |
| P8 lag | pass | `15 + 150 + 15 = 180 s` for the share; it multiplies a 1 m rate, so a hit-rate change reaches the ask 3 min late | config |
| P9 measures what it claims | pass | on prefill pods `external_kv_transfer` is 0, so `local_compute` is the prefill compute; the share `comp / done` is taken from two counters written in the same call (V `loggers.py#L1126-L1132`), so saturation does not bias it | source |
| P10 selects its own pool | pass (after fix) | N1: `pod` regex. N2: `namespace`. N3: `role` and `pod`. N4: `role` excludes the unrelabelled `vllm-<model>` scrape (T14); `engine` summed. Labels at V `loggers.py#L480` | config |
| P11 router configuration | pass | not an EPP series; the router's prefix scorer and `queue-scorer` change where tokens are computed, not the pool total; with random prompts the hit rate is 0 whatever the routing | source |

### Trigger `done`

```promql
sum(rate(vllm:prompt_tokens_total{namespace="ssa-0551",role="prefill",pod=~"deepseek-886595ad--v2-lite-prefill-.*"}[5m]))
```

`AverageValue`, `threshold: "1"`, `activationThreshold: "0"`, `ignoreNullValues: "false"` (`:45-57`).

- **What it counts:** a counter of all prompt tokens of prefills that produced
  their first output, cached or not. `source`: V `loggers.py#L685-L693`,
  `#L1126`; `stats.py#L412`.
- **Kind:** completed work rate. **Role:** denominator of the uncached share.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P7 fails visibly | pass | no default; `ignoreNullValues: "false"`; `done > 0 ?` guards the division at idle | config |
| P8 lag | pass | as `comp` | config |
| P9 measures what it claims | pass | same requests and same moment as `comp`; prefill requests always produce one token, so every finished prefill counts | source |
| P10 selects its own pool | pass (after fix) | as `comp` | config |
| P11 router configuration | pass | as `comp` | source |

### The driver term, `max(offered × comp / done, comp) / 37540`

- P1, P2, P5: as `offered`. The share is 1 on random prompts, and on the
  agentic run it is measured rather than assumed. It moves with `R`, since a
  new pod is cold, but that is a capacity effect (§1.2, P1 note), not a P2
  failure.
- P3: **pass in the simulator** (0.70 of the blend's knee, 0.75 of
  8192:256's), conditional on `e = 1` and on step 5 confirming the blis knee.
- P4: `AverageValue`, target 1, an absolute replica count: pass.

## ScaledObject `deepseek-886595ad--v2-lite-decode`

- `minReplicaCount: 2`, `maxReplicaCount: 6`, `pollingInterval: 15` (`:97-99`).
- `fallback`: 3 failures, 2 replicas, `currentReplicasIfHigher` (`:190-193`).
- Scale-up: no stabilization, `max(+4 pods, +100 %)` per 15 s. Scale-down: 300 s window, 1 pod / 120 s (`:194-213`).
- `scalingModifiers`: `max(conc / 510, (ok > 0 ? lam * gen / ok : lam * 2133) / (8.4 * 2133), pods * kv / 0.8, pods * itl / 0.05)`, `target: "1"`, `AverageValue` (`:214-217`).

### Trigger `conc`

```promql
sum(vllm:num_requests_running{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"})
+ sum(vllm:num_requests_waiting{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"})
```

`AverageValue`, `threshold: "1"`, `ignoreNullValues: "false"` (`:100-114`).

- **What it counts:** two gauges set every engine step: `running`, the requests
  in the batch, and `waiting`, which is `num_waiting_reqs + num_skipped_waiting_reqs`
  and so includes requests deferred for a KV transfer. On the decode pod a
  request enters when the sidecar sends its decode leg (after prefill) and
  leaves at its last token. `source`: V `loggers.py#L508-L526` (definitions),
  `#L1036-L1043` (`set`, waiting includes skipped); the deferred reason
  includes the KV transfer (`#L529-L536`).
- **Kind:** requests in progress (send to last token), with a backlog part
  (`waiting`). **Role it can play:** driver for a stable output-length mix.
  **Role it plays here:** driver.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P1 proportional | pass below saturation | Little: `conc = λ × W_d`, with `W_d` = KV pull + OSL × ITL, mildly load-dependent until the batch is compute-bound (§1.3: `ε` 1.0–1.24). Past the knee `waiting` integrates | source |
| P2 coupled to actuation | pass below saturation | the total `λ × W_d` does not depend on `R` except through ITL; after an overload, draining `waiting` drops it to `λ × W_d`, not below | source |
| P3 fixed busyness | fail (target past the knee; mix) | 510 = 1.3 × 392, the running + waiting one pod holds at the blend's μ_SLO knee (6.461 req/s, step 3 run 1d, `sim`). The protocol's knee is the SLO edge (A = 0.95), so 1.3 × it is past capacity. Interpolating run 1d's stages (359 at 6.3 req/s, 683 at 7.88), a pod reads 510 at 7.04 req/s and `510 × 1.1 = 561` (where the HPA adds a pod) at 7.29 req/s: 1.09–1.13 × μ_SLO, where run 1d's stage 4 (7.88 req/s) had A = 0.509. Mix: by Little with run 1a–1c's stage-3 TPOT, a pod at its mix's knee holds ≈ 152 (8192:256), 295 (2048:2048), 449 (256:4096), so the term reads 0.30, 0.58, 0.88: `V ≈ 2.9` | config, sim |
| P4 metric type | pass | extensive sums; composite `AverageValue` | config |
| P5 bounds | pass | `running ≤ max_num_seqs` = 1024 on an H100 (V `vllm/engine/arg_utils.py#L2868-L2877`; the overlay sets none), above `510 × 1.1 = 561`; `waiting` integrates under overload, bounded by `maxReplicaCount: 6` and +4 pods / 15 s | source, config |
| P6 defined at zero | pass | `minReplicaCount: 2`; with no decode pod both gauges vanish → scaler error → fallback, not 0 | config |
| P7 fails visibly | pass | no default, `ignoreNullValues: "false"`; either sum empty → error | config |
| P8 lag and noise | pass | lag `15 + 0 + 15 = 30 s`; one request moves the ask by `1 / 510 = 0.002` pod, far below the tolerance | config |
| P9 measures what it claims | pass | counts decode residency, including the KV-pull wait. It does not count requests still queued on prefill: the sidecar sends the decode leg after prefill, so `conc` lags demand while prefill is short. The `lam` guard covers that | source |
| P10 selects its own pool | pass (after fix) | as `comp`, decode side; `role` removes the T14 duplicate, so the sums are not doubled | config |
| P11 router configuration | pass | flow control off, so T4 and T20 do not apply. The default `utilization-detector` filters decode pods at `waiting ≥ 5` or KV ≥ 0.8 while another is below (T19): this levels per-pod values but leaves the sum unchanged | source |

The KV arithmetic agrees with blis on the order of magnitude. DeepSeek-V2-Lite
MLA caches `576 × 27 × 2 = 31,104` bytes per token, and about 35 GB is left for
KV on an 80 GB H100 at 0.90, so a pod holds about 1.1 M tokens. That is about
480 sequences of 256:4096's mean 2,300-token context. Run 1d's KV reads 0.74
at 359 requests and 1.00 at 683, so KV binds the blend.

**Failure case (P3, past the knee):** blend at 14.0 req/s on 2 pods,
`7.0 / 6.461 = 1.08 ×` μ_SLO per pod. By the interpolation above, `conc ≈ 1,010`,
which reads `1,010 / 510 = 1.98`. The offered term reads `14.0 / 8.4 = 1.67`.
The ratio to the 2 current pods is 0.99, inside the 10 % tolerance, so the HPA
holds 2 pods where `ceil(14.0 / 6.461) = 3` meet the SLO. Only the KV guard can
add the third pod, once the mean KV passes 0.88, at about 7.15 req/s per pod.

**Failure case (P3, mix):** 8192:256 at 40 req/s, about two pods' knee
(`2 × 20.267 = 40.5`). `conc ≈ 2 × 152 = 304` reads 0.60, and the offered term
reads `40 × 256 / 17,917 = 0.57`, so both drivers ask for 1 pod, below
`minReplicaCount`. The pool is sized by `minReplicaCount` and the KV guard:
8192:256 sequences hold about 8.4 k tokens each, so 152 of them fill a pod's KV
(PF10).

### Trigger `lam`

```promql
sum(rate(llm_d_epp_request_total{namespace="ssa-0551",job="deepseek-886595ad--v2-lite-router-epp"}[1m]))
+ (sum(rate(llm_d_epp_request_error_total{namespace="ssa-0551",job="deepseek-886595ad--v2-lite-router-epp",error_code="ServiceUnavailable"}[1m])) or vector(0))
```

`AverageValue`, `threshold: "1"`, `ignoreNullValues: "false"` (`:115-128`).

- **What it counts:** `request_total` is incremented once per request after
  scheduling, when the request is sent (E `pkg/epp/handlers/server.go#L644-L652`).
  A request that fails scheduling for lack of endpoints is counted instead in
  `request_error_total{error_code="ServiceUnavailable"}`
  (E `server.go#L459-L464`; `pkg/epp/requestcontrol/admission.go#L291`;
  `pkg/common/error/error.go#L74`). A model-server error after dispatch is
  recorded as `ModelServerError` (`server.go#L679`), not double-counted. One
  scheduling covers both P/D legs, so each request counts once.
- **Kind:** offered request rate. **Role it can play:** driver, mix-sensitive as
  a request rate. **Role it plays here:** multiplied by `gen / ok`, offered
  output tokens/s ÷ `8.4 × 2133 = 17,917` tok/s per pod, meant as a guard at
  the driver's operating point.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P1 proportional | pass | arrival rate, open loop; `λ × OSL` is `λ_out` | source |
| P2 coupled to actuation | pass | independent of decode `R` | config |
| P3 fixed busyness | fail (target past the knee; mix) | 8.4 req/s = 1.3 × μ_SLO(B, decode) 6.461 (step 3, `sim`): the term reads 1 per pod at 130 % of the blend's knee, and the HPA adds a pod only past `1.1 × 8.4 = 9.24` req/s per pod (143 %). Mix: at each mix's knee a pod reads `μ × OSL / 17,917` = 0.29 (8192:256), 0.65 (2048:2048), 0.91 (256:4096), 0.77 (blend): `V = 0.915 / 0.290 = 3.2`, a token-weighted request rate. Cross-over with `conc` (PF4): the ratio of the two terms is `(λ W_d / 510) / (λ OSL / 17,917) = 35.1 × W_d / OSL`, so they are equal at a decode residency of `510 / 17,917 = 28.46 ms` per output token, the blend knee's own (`392 / 6.461 / 2133 = 28.4 ms`, as built). Below the knee (run 1d's stage 1–3 TPOT p50 19.7–27.4 ms) this term is the larger and decides; past it `conc` is | config, sim |
| P4 metric type | pass | extensive | config |
| P5 bounds | pass | not capped | source |
| P6 defined at zero | pass | the EPP series exist with no decode pod, but `request_total` is created on the first request (CounterVec) | source |
| P7 fails visibly | pass | the `request_total` side has no default, and `ignoreNullValues: "false"`. Before the first request after an EPP start the series is absent: error, then fallback holds the current size (as PF2) | config, source |
| P8 lag and noise | pass | `10 + 30 + 15 = 55 s`; noise `1/√(60 q)`: 13 % at 1 req/s | config |
| P9 measures what it claims | pass | T8 (after scheduling) is harmless with the gate off: no EPP queue, and the 503s are added back. Requests shed as `ResourceExhausted` by the detector (priority < 0 only, T19) are not counted; inference-perf sends priority 0 | source |
| P10 selects its own pool | pass (after fix) | N1: `job` (T15). N2: `namespace`. N3: n/a, the router counts requests, not roles. N4: one ServiceMonitor | config |
| P11 router configuration | pass | `request_*` are always written (how-to P11 table); no parameter changes them with flow control off | source |

### Triggers `gen` and `ok` (mean output length `gen / ok`)

```promql
sum(rate(vllm:generation_tokens_total{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"}[5m])) or vector(0)
sum(rate(vllm:request_success_total{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"}[5m])) or vector(0)
```

`AverageValue`, threshold 1, `ignoreNullValues` not set: KEDA's default `true` (`:129-152`).

- **What they count:** `generation_tokens` counts output tokens at each engine
  output. `request_success` counts finished requests by `finished_reason`
  (`stop|length|abort|error|repetition`), summed here. `source`: V
  `loggers.py#L719-L726`, `#L728-L740`, `#L1134`, `#L1153-L1156`.
- **Kind:** completed work rates. **Role:** their ratio is a mix estimate
  (mean OSL) for the guard.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P7 fails visibly | n/a (guard) | `or vector(0)`: an outage reads 0, `ok > 0 ?` then falls back to `lam × 2133`. Safe while `conc` runs | config |
| P8 lag | pass, with a bias | 5 m windows: after an OSL shift the ratio takes ≈ 150 s (½ window) plus one answer's duration to follow. 256:4096 answers take ≈ `4096 × 0.027 ≈ 110 s` (run 1c's TPOT). Before the first completion the prior 2133 applies, and the term reads `λ / 8.4`: for 256:4096 that under-reads by `4096 / 2133 = 1.9×`, for 8192:256 it over-reads by `2133 / 256 = 8.3×` (at 20 req/s it asks `ceil(2.4) = 3` pods for the first minutes instead of 2) | config |
| P9 measures what it claims | pass | the ratio is mean OSL of finished decode requests; aborts (scale-in, PF9) count with their short length and pull it down | source |
| P10 selects its own pool | pass (after fix) | as `conc` | config |
| P11 router configuration | pass | vLLM series; the router does not change them | source |

### Trigger `pods`

```promql
count(count by (pod) (vllm:num_requests_running{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"})) or vector(0)
```

(`:153-164`). The number of decode pods exporting metrics: from vLLM API server
start to the last scrape, close to Ready. **Role:** the pod count that turns the
two intensive guards into totals.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P4 metric type | pass | `pods × avg` = a sum; `pods × p90` is the `Value` rule written into the formula | config |
| P7 fails visibly | n/a (guard input) | `or vector(0)` zeroes both guards on an outage; safe while `conc` runs | config |
| P8 lag | pass | 15 s scrape; a deleted pod's series goes stale within one scrape | config |
| P9 measures what it claims | pass | `count by (pod)` is immune to T14's duplicate scrape even without `role` | config |
| P10 selects its own pool | pass (after fix) | `pod` regex | config |
| P11 router configuration | pass | vLLM series | source |

### Trigger `kv`

```promql
avg(vllm:kv_cache_usage_perc{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"}) or vector(0)
```

(`:165-176`). Term `pods × kv / 0.8`.

- **What it counts:** a gauge set each step to `1 − free / (num_gpu_blocks − 1)`.
  Idle prefix-cached blocks count as free. `source`: V `loggers.py#L576-L583`, `#L1050`.
- **Kind:** capped saturation, ceiling 1. **Role:** guard (KV).

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P4 metric type | pass | `pods × avg = sum`, under the composite `AverageValue` | config |
| P5 bounds | pass | `1 / 0.8 = 1.25 > 1.1`; to add a pod the mean must exceed `0.8 × 1.1 = 0.88` | config |
| P8 lag | pass | `15 + 0 + 15 = 30 s` | config |
| P9 measures what it claims | pass | live sequences' KV, including blocks reserved for an in-flight NIXL pull | source |
| P10 selects its own pool | pass (after fix) | as `conc` | config |
| P11 router configuration | pass, noted | `kvCacheUtilThreshold` 0.8 (T19): while any decode pod is under 0.8, none above it gets a new request, so the pool fills evenly toward 0.8 and the guard adds a pod once all pods pass 0.88 (PF7) | source |

### Trigger `itl`

```promql
(histogram_quantile(0.9, sum by (le) (rate(vllm:inter_token_latency_seconds_bucket{namespace="ssa-0551",role="decode",pod=~"deepseek-886595ad--v2-lite-decode-.*"}[2m]))) > 0)
or vector(0)
```

(`:177-189`). Term `pods × itl / 0.05`.

- **What it counts:** a histogram of the gap between consecutive outputs of a
  request (not per token), observed on every output after the first. The
  buckets include 0.05 (V `vllm/v1/metrics/buckets.py#L83-L87`), so the SLO
  edge is resolved. `source`: V `loggers.py#L831-L838`, `#L1150-L1151`;
  `stats.py#L500-L506`.
- **Kind:** latency outcome. **Role it can play:** scale-in veto. **Role it
  plays here:** guard: it adds pods in proportion to `itl / 0.05`.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P1 proportional | fail (role mismatch) | flat until the batch is compute- or KV-bound, then steep. As a veto it would only hold the count; here it adds pods. Kept because ITL above its SLO is always a decode shortage (task 0545 §2). In blis the knee's ITL p90 is 0.029 s (run 1d), so the term reads `0.029 / 0.05 = 0.58` per pod; it adds a pod past `0.05 × 1.1 = 0.055 s`, above every stage-4 TPOT p90 of runs 1a–1d (30.7–42.6 ms, at 1.22–1.25 × μ_SLO). It fires only in deeper overload or under preemption (PF8) | source, sim |
| P4 metric type | pass | `pods × quantile` is the `Value` rule; composite `AverageValue` | config |
| P5 bounds | pass | not capped; `maxReplicaCount: 6` bounds it | config |
| P8 lag | pass | `15 + 60 + 15 = 90 s` | config |
| P9 measures what it claims | pass | decode-side inter-output gaps, which on a decode pod cover the decode batch and preemption stalls | source |
| P10 selects its own pool | pass (after fix) | as `conc`; `sum by (le)` over the `role`-pinned series, so the T14 duplicate does not skew the quantile | config |
| P11 router configuration | pass | vLLM series; the T19 filter reduces hot spots | source |

**Failure case (P1):** 3 decode pods, with ITL p90 held at 0.07 s by a cause that
more pods do not fix (for example KV preemption from one long context). The term
asks `ceil(3 × 0.07 / 0.05) = 5`, then `ceil(5 × 0.07 / 0.05) = 7`, capped at 6,
while ITL stays at 0.07. A veto would have held at 3.

## Combination

- **Driver in normal operation:** prefill, `offered × comp / done / 37540`.
  Decode: the offered-output term below the blend's knee, where decode residency
  is under 28.46 ms per output token, and `conc / 510` past it (PF4). Both terms
  are proportional and were calibrated at one operating point, so they hand over
  at the knee by construction. That point is 1.3 × μ_SLO, so near the handover
  the KV guard decides too (PF5).
- **Who decides where:**
  - Prefill: the driver whenever requests complete; `comp` only if `done = 0`
    while `comp > 0` (never, both come from one write) or if the EPP's count
    runs low. The floor never decides at steady state.
  - Decode: the `lam` term below the knee, and in any case while prefill is
    short (decode sees only what prefill passes). `conc / 510` past the knee.
    `kv` once the mean decode KV passes 0.88: about 7.15 blend req/s per pod
    (run 1d interpolated), and on 8192:256 well before either driver (PF10).
    `itl` once p90 passes `0.05 × 1.1 = 0.055 s`, which blis never reached.
    At the sanity load all four are near 0: `conc ≈ 0.65` gives 0.0013,
    `lam` gives `50 / 17,917 = 0.003`, and prefill reads
    `384 / 37,540 = 0.010`, so both pools hold at 2.
- **Scale-in:** prefill's driver counts arrivals, so no backlog collapses after a
  scale-up and the pool cannot fall below need. Scale-in waits 3600 s, then 1 pod
  per 600 s. Decode: after an overload, `waiting` drains and `conc` falls to
  `λ × W_d`, the need at the configured constant, not below. Nothing stays high
  after load drops: the 5 m `gen/ok` windows and the 2 m ITL window decay within
  the 300 s window. Scale-in aborts in-flight decode requests: the overlay sets
  no `--shutdown-timeout`, and the default is 0 (V `vllm/config/vllm.py#L458`).
  Task 0545 lists decode drain as a prerequisite (PF9).
- **`scalingModifiers.formula`:** both formulas take a `max` of proportional
  terms and guards, with no `min` and no weighted sum. The ternaries are
  division guards; each branch passes on its range. The `lam × 2133` branch only
  applies before the first completion in a 5 m window (`gen/ok` row).
- **`behavior` and bounds:** prefill's 900 s scale-up window delays every
  prefill scale-up by 15 min. No staircase stage shorter than about
  `900 + 55 + cold start` seconds can add a prefill pod (PF6), so `run-set.md`
  §2's T formula needs this window as the scale-up period (step 3 run 2: 885 s
  at 2 pods after the trigger asked for 3, `sim`). Decode's fast scale-up
  reaches any ask within one or two polls. `maxReplicaCount: 6` caps decode at
  `6 × 6.461 = 38.77` blend req/s, which sets C (step 3). At C the drivers ask
  `ceil(38.77 / 8.4) = ceil(4.6) = 5`. Only the KV guard
  (`5 × 1.0 / 0.8 = 6.25`) takes decode to 6 (PF5).
- **Disaggregated pools:** prefill's driver reads the router's prefill-attributed
  arrivals and prefill pods' own compute, so it measures prefill work. Decode's
  `conc` counts decode residency only. A request still in prefill is not in it.
  The `lam` guard covers that, as designed. No trigger reads `inflight_tokens`.
- **Router configuration across both:** one EPP serves both pools, with flow
  control off. No plugin added for one trigger changes another's series. The
  injected `utilization-detector` levels decode `waiting` (at 5) and KV (at 0.8)
  across pods (T19). That affects only the `kv` guard's firing point.
- **Isolation:** N1: after the fixes every vLLM selector pins this stack's `pod`
  prefix, and every EPP selector pins its `job`. N2: `namespace` on every
  selector. N3: `role` and `pod` per role; `endpoint_role` on the EPP side. N4:
  `role` drops the `vllm-<model>` duplicate scrape, and `pods` is immune to it.
  Names and targets carry `${model.idLabel}` (`:5,14,87,96`).

**Predicted behavior (blis constants):** At low load (the sanity profile) both
pools hold at 2. Under the run set:

- **Prefill** stays at 2 until the offered uncached work exceeds
  `2 × 1.1 × 37,540 = 82,588` tok/s (× 1/`e`) for 15 minutes. That is 23.6
  blend req/s or 10.1 req/s of 8192:256. Prefill then adds one pod per
  5 minutes, up to 4 (`4 × 15.328 = 61.3` blend req/s).
- **Decode** tracks load but holds 1.09–1.13 × μ_SLO(B) per pod: 2 pods carry
  up to about 14.3–14.6 blend req/s, where 3 are needed above 12.9. Attainment dips
  just past each multiple of μ_SLO until `conc` or the KV guard adds the pod.
- **On 8192:256 phases**, decode's drivers read about a third of need, and
  `minReplicaCount` plus the KV guard size the pool.
- **At constant load** neither pool oscillates: both drivers hold their totals
  as pods are added. The KV guard decides near the knee, and KV as a sizing
  signal can cycle (task 0545 §2, D5a), which step 3/5 must check.

## Predicted failures for step 2

| Id | Prediction | How step 2 shows it |
|---|---|---|
| PF1 | Each selector returns exactly this stack's pool after the label fixes | `count by (namespace, job, pod, role, engine)` per vLLM selector returns one series per pool pod; `count by (job, plugin_name, endpoint_role, modality) (llm_d_epp_prefix_prompt_tokens_count{…})` returns one series; `count by (job) (llm_d_epp_request_total{namespace})` names `deepseek-886595ad--v2-lite-router-epp` |
| PF2 | `offered` (and `lam`) are absent after an EPP start until the first request. The ScaledObjects error, KEDA's fallback engages after 3 failures, and the replica count holds | ScaledObject `status.health` / conditions at idle after standup; replicas stay at 2 |
| PF3 | `offered` ≠ engine prompt tokens: `e = rate(llm_d_epp_prefix_prompt_tokens_sum{…}[5m]) / rate(vllm:prompt_tokens_total{role="prefill",…}[5m])` differs from 1 (bytes / 4 estimate) | steady random load; record `e` per mix |
| PF4 | Decode: the offered term `lam × gen / ok / 17,917` exceeds `conc / 510` whenever decode residency per output token is below 28.46 ms (below the knee), and `conc / 510` is the larger past it | read both terms and `conc / λ / (gen / ok)` at several steady loads |
| PF5 | Decode holds about 1.1 × μ_SLO per pod: no pod is added until `conc > 561` per pod or `λ > 9.24` blend req/s per pod or mean KV > 0.88. At C (38.77 req/s) the drivers ask 5 and only the KV guard reaches 6 | staircase across `R × 6.461`; per-pod `conc`, KV and replicas against the terms |
| PF6 | Prefill adds no pod for demand above the ask that lasts less than ≈ 955 s plus cold start, and removes none for 3600 s after load drops | step above `2 × 1.1 × 37,540 = 82,588` offered tok/s for 10 min (no scale-up), then 20 min (one scale-up) |
| PF7 | Decode KV is levelled near 0.8 by the detector filter; `kv` adds a pod only when the mean exceeds 0.88 | long-context decode load; per-pod KV and the term |
| PF8 | `itl` reads 0 at idle (the `> 0` filter), about 0.58 per pod at the knee, and never wins below 1.25 × μ_SLO | idle and steady samples of the term |
| PF9 | Each decode scale-in aborts in-flight requests (`--shutdown-timeout` 0) | `vllm:request_success_total{finished_reason="abort"}` and client errors at each scale-in |
| PF10 | On 8192:256, decode's drivers read about 0.3 per pod at that mix's knee, so `minReplicaCount` and the KV guard size decode, not `conc` or `lam` | 8192:256 steady load near `2 × 20.267` req/s; all four terms |

## Needs measurement

1. Labels and producers on the cluster (PF1), needed by P10 and P11 of every trigger.
2. `e`, EPP estimated prompt tokens per engine prompt token, for random
   DeepSeek-tokenizer text and the agentic prompts. Needed by `offered` P3.
3. μ_P on the GPU: blis gives 53,628 (blend) and 49,930 (8192:256) computed tok/s
   per prefill pod. Step 5 confirms them, since 37540 rests on them.
4. Decode knee per mix on the GPU: running + waiting per pod, completions/s and
   per-token residency. blis gives 392 at 6.461 req/s (blend), 28.4 ms per
   token. Needed to confirm 510, 8.4 and 2133, the PF4 cross-over (28.46 ms) and
   the per-mix `V` (≈ 3, derived from blis's stage TPOT, not measured per mix).
5. Decode ITL p90 at and past the knee, against 0.05 s (blis: 0.029 at the knee).
   Needed by `itl` P1.
6. Decode KV usage at the knee per mix (blis blend: 0.74 at 6.3 req/s, 1.00 at
   7.88). Needed by `kv` P11, PF5 and PF10.
7. Cold start of a prefill and of a decode pod, to size the prefill 900 s window
   and the run set's stage length T (PF6).
8. The KEDA (or Custom Metrics Autoscaler) release on `pokprod001`: support for
   `fallback.behavior: currentReplicasIfHigher` and `scalingModifiers`, and trap T7.

## Fixes

None of these was applied: the task owner fixed the metrics, formulas and
behavior. The constants came from the step 3 knees (`2e607e4a`) and are to be
confirmed by step 5.

| Fails | Fix | Effect |
|---|---|---|
| prefill driver, P3 (10850) | **applied in `2e607e4a`**: `/ 37540` (0.7 × the blis blend knee) | prefill at 0.70–0.75 of its knee in blis; confirm in step 5 |
| `offered`, P3 (estimate) | `router.tokenizer.enabled: true` with a `vllm` `token-producer`, so `TokenizedRequest` holds engine tokens; or divide by `e` from item 2 | numerator and divisor in the same tokens |
| `conc`, `lam`, P3 (target 1.3 × the μ_SLO knee) | task 0545's 1.3 rule assumed a knee below the SLO edge; with this protocol's μ_SLO, use 0.7 × it as prefill does: `conc / 274` and `/ (4.52 * 2133)` (0.7 × 392, 0.7 × 6.461), keeping one operating point for both | decode at 0.7 of its knee, 43 % headroom; the cross-over stays at the same per-token residency |
| `conc`, `lam`, P3 (mix, V ≈ 3) | none within this formula; the KV guard covers 8192:256. A per-mix capacity (output tokens weighted by context) would be a metric change | — |
| `offered`, P8 (900 s) | the scenario's CALIBRATE: for random prompts (no session-cache fill) 120–300 s, as task 0545 §2.1 advises where caches do not hold a shared working set; keep 900 s for the agentic run's design | prefill follows staircase stages within one cold start |
| `itl`, P1 (role) | keep as a guard with the SLO well above the ITL floor (item 5), or make it a veto: `min(pods × itl / 0.05, pods)` inside the `max` | it can no longer ratchet the pool on a cause more pods do not fix |
| decode scale-in (PF9) | add `--shutdown-timeout 45` to the decode vLLM command and `terminationGracePeriodSeconds` above it (task 0545 §1.3) | scale-in drains instead of aborting |
| `offered`, `lam`, P10 (N1); all vLLM triggers, P10 (N1); names, T17 | **applied**: see Label fixes | each selector reads this stack only |
