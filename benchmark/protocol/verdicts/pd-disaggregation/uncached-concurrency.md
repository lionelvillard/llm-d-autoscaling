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

Source references:

- **V** = `vllm-project/vllm@db9527a4` (tag `v0.31.0`), the overlay's image.
- **E** = `llm-d/llm-d-router@b9393d1a` (tag `v1.0.0`), the EPP and router chart.
- **B** = `llm-d/llm-d-benchmark@0fb187fb`, the renderer.

| | |
|---|---|
| Scenario | `benchmark/config/scenarios/staging/pd-disaggregation/uncached-concurrency.yaml` |
| Backend overlay | `benchmark/config/cluster-configs/ocp/vllm.yaml` (target: OpenShift `pokprod001`, H100 80GB, 1 GPU per pod, TP1) |
| Rendered with | `llmdbenchmark standup --dry-run`, llm-d-benchmark@`0fb187fb`, through a temporary spec pointing at the scenario (the repo has no `specification/staging/pd-disaggregation/uncached-concurrency.yaml.j2`). The Jinja plan rendered; the helmfile step failed offline, so the modelservice values were read from `13_ms-values.yaml` before chart rendering |
| Load | The scenario's `sanity_random.yaml` (B): open loop, `constant` at `q` = 1 req/s for 30 s; random prompts, mean ISL 384, OSL 50, `ignore_eos`. `λ_in = 1 × 384 = 384`, `λ_out = 1 × 50 = 50` tokens/s; no prefix reuse. Steps 3/5 use the run set (`run-set.md` §1): 8192:256, 2048:2048, 256:4096 and their blend, random prompts (agentic run aside), so `comp / done ≈ 1` on every run but the agentic one |
| Date | 2026-11-24 |
| Verdict | **Accepted with conditions** |

**Accepted with conditions.** Each pool has a proportional driver: offered
prompt tokens at the router times the measured uncached share on prefill
(arrival-side, open-loop, so it passes P1, P2 and P5), and requests in progress
on decode, backed by an offered-output-token guard. After the label fixes below,
every selector picks one stack's pool and every EPP series has exactly one
producer in the effective configuration (P10, P11). The conditions are
calibration, not structure. The five constants (10850, 4, 0.39, 700, 0.075) are
GLM-5.3 TP8 H200 values (BLIS). The two decode constants put the offered guard
above the driver whenever decode ITL is below 14.65 ms. The prefill driver
counts the EPP's 4-bytes-per-token estimate, not engine tokens.
**Predicted:** under the scenario's own sanity load, both pools hold at
`minReplicaCount: 2`. Under the run set, until the knee runs re-measure the
constants, decode reaches its cap of 6 at loads one DeepSeek-V2-Lite pod can
probably carry. Prefill grows by one pod at a time, only after 15 minutes of
sustained demand, and holds each pod for at least an hour.

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
- `scalingModifiers`: `max(done > 0 ? offered * comp / done : offered, comp) / 10850`, `target: "1"`, `AverageValue` (`:79-82`). Per-trigger thresholds are parsed but do not reach the HPA; `desired = ceil(formula)`.

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
| P3 fixed busyness | fail (constant) / measure | the unit is EPP pseudo-tokens (bytes / 4), while the divisor 10850 is in engine-computed tokens/s. The ask scales by `e = offered / rate(vllm:prompt_tokens_total{prefill})`, unknown for random DeepSeek-tokenizer text. 10850 = 0.7 × 15,500 tok/s for one TP8 GLM-5.3 H200 pod (BLIS), not this plant (formula below). Mix sensitivity of μ_P across 256- and 8192-token prompts also unmeasured | source |
| P4 metric type | pass | `sum(rate(...))` is extensive; composite `AverageValue`, target 1 (`:79-82`) | config |
| P5 bounds | pass | not capped (arrivals are counted, not service), not integrating; at 2× capacity it asks 2× | source |
| P6 defined at zero | pass | `minReplicaCount: 2`. With no prefill pod, `PredictionTarget` attributes requests to `decode` (E `metrics.go#L185-L187`), so this selector would read nothing and the scaler errors, not 0 | source |
| P7 fails visibly | pass | no `or vector(0)`, `ignoreNullValues: "false"`. Lost EPP series → error → fallback holds `max(N, 2)`. Side effect: the histogram series only appears with the first request, so after every EPP start the prefill ScaledObject errors until traffic arrives, and fallback holds the current size (PF2) | config, source |
| P8 lag and noise | fail (by design) | lag `10 + 30 + 15 = 55 s` (EPP scrape, ½ of `[1m]`, polling), plus the 900 s scale-up stabilization: ≈ 955 s against a cold start of a few minutes (measure). Task 0545 chose 900 s to absorb a GLM agentic session-cache fill (≈ 650 s there). The run set's random prompts have no such fill. Noise: `1/√(q × 60)`, 13 % at q = 1 req/s, 6 % at 5 req/s; the scale-up window takes the minimum over 900 s, so noise does not trigger scale-up | config |
| P9 measures what it claims | pass, with the estimate | arrival-side prompt tokens of requests routed to prefill; T8 (counted after scheduling) is harmless with the gate off and `minReplicas: 2`. The count is an estimate (P3) | source |
| P10 selects its own pool | pass (after fix) | N1: `job` pins this stack's EPP. N2: `namespace`. N3: `endpoint_role="prefill"`. N4: one ServiceMonitor, and `29_epp-keda-saturation-epp-monitoring.yaml` renders empty. Step 2 confirms `count by (job, plugin_name, endpoint_role, modality)` returns one series | config |
| P11 router configuration | pass | `approx-prefix-cache-producer` is listed explicitly (`12_router-values.yaml:32`), one instance, so `plugin_name` = its type. The prompt tokens come from the loader's `estimate` `token-producer` (T18), hence P3's `e`. No parameter changes the count. The `utilization-detector` filter (T19) does not touch it | source |

**Failure case (P3):** 8192:256 at `q` = 4 req/s, random prompts, so
`comp / done = 1`. Then `λ_in = 32,768` tok/s, and the ask is
`ceil(e × 32,768 / 10,850) = ceil(3.02 e)`, which is 4 (the cap) for `e = 1`.
One pod meets that load at ρ = 0.7 if its knee μ_P is
`32,768 / 0.7 = 46,811` tok/s. Generally the pool runs `μ_P / 15,500 × e` times
larger than the 0.7 target means. A 2.4B-active MoE on a whole H100 likely
computes well above the 15,500 tok/s of a TP8 GLM-5.3 pod (*needs
measurement*).

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

### The driver term, `max(offered × comp / done, comp) / 10850`

- P1, P2, P5: as `offered`. The share is 1 on random prompts, and on the
  agentic run it is measured rather than assumed. It moves with `R`, since a
  new pod is cold, but that is a capacity effect (§1.2, P1 note), not a P2
  failure.
- P3: **fail** as configured. 10850 is not this plant's knee, and `offered` is
  in estimated tokens (above). The scenario marks 10850 CALIBRATE.
- P4: `AverageValue`, target 1, an absolute replica count: pass.

## ScaledObject `deepseek-886595ad--v2-lite-decode`

- `minReplicaCount: 2`, `maxReplicaCount: 6`, `pollingInterval: 15` (`:97-99`).
- `fallback`: 3 failures, 2 replicas, `currentReplicasIfHigher` (`:190-193`).
- Scale-up: no stabilization, `max(+4 pods, +100 %)` per 15 s. Scale-down: 300 s window, 1 pod / 120 s (`:194-213`).
- `scalingModifiers`: `max(conc / 4, (ok > 0 ? lam * gen / ok : lam * 700) / (0.39 * 700), pods * kv / 0.8, pods * itl / 0.075)`, `target: "1"`, `AverageValue` (`:214-217`).

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
| P3 fixed busyness | fail (constant) / measure | 4 = 1.3 × the knee concurrency of a TP8 GLM-5.3 H200 pod (BLIS, knee 3.1). Per the KV arithmetic below, a TP1 H100 DeepSeek-V2-Lite pod holds hundreds of sequences, and its knee concurrency for each mix in M is unmeasured. `V` across 8192:256, 2048:2048, 256:4096 is also unmeasured: the knee is set by attention cost and KV per sequence, which differ across the mixes | config, measure |
| P4 metric type | pass | extensive sums; composite `AverageValue` | config |
| P5 bounds | pass | `running ≤ max_num_seqs` = 1024 on an H100 (V `vllm/engine/arg_utils.py#L2868-L2877`; the overlay sets none), far above `4 × 1.1`; `waiting` integrates under overload, bounded by `maxReplicaCount: 6` and +4 pods / 15 s | source, config |
| P6 defined at zero | pass | `minReplicaCount: 2`; with no decode pod both gauges vanish → scaler error → fallback, not 0 | config |
| P7 fails visibly | pass | no default, `ignoreNullValues: "false"`; either sum empty → error | config |
| P8 lag and noise | pass | lag `15 + 0 + 15 = 30 s`; one request moves the ask by `1 / 4 = 0.25` pod, below one pod but above 10 % of a 2-pod target. The 300 s scale-down window absorbs it | config |
| P9 measures what it claims | pass | counts decode residency, including the KV-pull wait. It does not count requests still queued on prefill: the sidecar sends the decode leg after prefill, so `conc` lags demand while prefill is short. The `lam` guard covers that | source |
| P10 selects its own pool | pass (after fix) | as `comp`, decode side; `role` removes the T14 duplicate, so the sums are not doubled | config |
| P11 router configuration | pass | flow control off, so T4 and T20 do not apply. The default `utilization-detector` filters decode pods at `waiting ≥ 5` or KV ≥ 0.8 while another is below (T19): this levels per-pod values but leaves the sum unchanged | source |

**KV arithmetic behind P3 (illustration, not a measurement):** DeepSeek-V2-Lite
MLA caches `512 + 64 = 576` values per layer per token. At 27 layers and 2 bytes
each, that is `576 × 27 × 2 = 31,104` bytes per token. With
`gpuMemoryUtilization: 0.90` on 80 GB (72 GB), minus about 31 GB of weights and a
few GB of activations, roughly 35 GB is left for KV, about 1.1 M tokens. A
256:4096 request averages about 2,300 tokens of context, so about 480 such
sequences fit. A target of 4 per pod is two orders of magnitude below that.

**Failure case (P3):** 2048:2048 at `q` = 1 req/s with an assumed decode ITL of
12 ms: `W_d ≈ 2048 × 0.012 = 24.6 s`, so `conc ≈ 24.6`, and `conc / 4 = 6.1`
asks for 7, capped at 6. If one pod's knee concurrency is in the tens to
hundreds, as the KV arithmetic suggests, one or two pods carry this load. The
pool runs at its cap at a fraction of its capacity.

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
  output tokens/s ÷ 273, meant as a guard at the driver's operating point.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P1 proportional | pass | arrival rate, open loop; `λ × OSL` is `λ_out` | source |
| P2 coupled to actuation | pass | independent of decode `R` | config |
| P3 fixed busyness | fail (constant) | `0.39 × 700 = 273` output tok/s per pod is GLM-5.3 TP8 H200's operating point. The guard sits at the driver's point only if `4 / 0.39 = 10.26 s` is the decode residency of a 700-token answer, which means 14.65 ms per token. For ITL `t`, the ratio of the two terms is `(λ OSL t / 4) / (λ OSL / 273) = 68.25 t`. Below `t = 14.65 ms` the "guard" is the larger term, so it decides at steady state (PF4) | config |
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
| P7 fails visibly | n/a (guard) | `or vector(0)`: an outage reads 0, `ok > 0 ?` then falls back to `lam × 700`. Safe while `conc` runs | config |
| P8 lag | pass, with a bias | 5 m windows: after an OSL shift the ratio takes ≈ 150 s (½ window) plus one answer's duration to follow. 256:4096 answers take ≈ 4096 × ITL ≈ 60 s at 15 ms. Before the first completion the prior 700 applies: for 256:4096 that under-reads by `4096 / 700 = 5.9×`. For 8192:256 it over-reads by `700 / 256 = 2.7×`, which lifts the guard term to `λ × 700 / 273 = 2.56 λ` pods for the first minutes | config |
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

(`:177-189`). Term `pods × itl / 0.075`.

- **What it counts:** a histogram of the gap between consecutive outputs of a
  request (not per token), observed on every output after the first. The
  buckets include 0.075 (V `vllm/v1/metrics/buckets.py#L83-L87`), so the SLO
  edge is resolved. `source`: V `loggers.py#L831-L838`, `#L1150-L1151`;
  `stats.py#L500-L506`.
- **Kind:** latency outcome. **Role it can play:** scale-in veto. **Role it
  plays here:** guard: it adds pods in proportion to `itl / 0.075`.

| Property | Result | Evidence | Tag |
|---|---|---|---|
| P1 proportional | fail (role mismatch) | flat until the batch is compute- or KV-bound, then steep. As a veto it would only hold the count; here it adds pods. Kept because ITL above its SLO is always a decode shortage (task 0545 §2), and the 0.075 s SLO sits far above V2-Lite's per-token floor (measure), so it fires only in deep overload or under preemption | source |
| P4 metric type | pass | `pods × quantile` is the `Value` rule; composite `AverageValue` | config |
| P5 bounds | pass | not capped; `maxReplicaCount: 6` bounds it | config |
| P8 lag | pass | `15 + 60 + 15 = 90 s` | config |
| P9 measures what it claims | pass | decode-side inter-output gaps, which on a decode pod cover the decode batch and preemption stalls | source |
| P10 selects its own pool | pass (after fix) | as `conc`; `sum by (le)` over the `role`-pinned series, so the T14 duplicate does not skew the quantile | config |
| P11 router configuration | pass | vLLM series; the T19 filter reduces hot spots | source |

**Failure case (P1):** 3 decode pods, with ITL p90 held at 0.10 s by a cause that
more pods do not fix (for example KV preemption from one long context). The term
asks `ceil(3 × 0.10 / 0.075) = 4`, then `ceil(4 × 0.10 / 0.075) = 6`, which is
the cap, while ITL stays at 0.10. A veto would have held at 3.

## Combination

- **Driver in normal operation:** prefill, `offered × comp / done / 10850`.
  Decode, `conc / 4`, or the offered-output guard whenever decode ITL < 14.65 ms
  (PF4). Both are proportional, so the decode combination stays sound either
  way, but which term decides depends on a constant ratio set for another plant.
- **Who decides where:**
  - Prefill: the driver whenever requests complete; `comp` only if `done = 0`
    while `comp > 0` (never, both come from one write) or if the EPP's count
    runs low. The floor never decides at steady state.
  - Decode: `conc / 4` when ITL > 14.65 ms. The `lam` term when ITL is lower,
    and in any case while prefill is short (decode sees only what prefill
    passes). `kv` once the mean decode KV passes 0.88. `itl` once p90 passes
    `0.075 × 1.1 = 0.0825 s`. At the sanity load all four are below 1:
    `conc ≈ 1 × (50 × 0.012 + 0.05) ≈ 0.65` gives 0.16, and `lam` gives
    `50 / 273 = 0.18`, so the pool holds at 2.
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
  division guards; each branch passes on its range. The `lam × 700` branch only
  applies before the first completion in a 5 m window (`gen/ok` row).
- **`behavior` and bounds:** prefill's 900 s scale-up window delays every
  prefill scale-up by 15 min. No staircase stage shorter than about
  `900 + 55 + cold start` seconds can add a prefill pod (PF6), so `run-set.md`
  §2's T formula needs this window as the scale-up period. Decode's fast
  scale-up bounds nothing: with the current constants a sustained moderate load
  takes decode to its cap of 6 within one or two polls (PF5). That is harmless
  only if 6 pods are what the load needs, which the knee runs will show.
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

**Predicted behavior:** At low load (the sanity profile) both pools hold at 2.
Near one pod's real capacity, prefill is asked for about `e × μ_P / 10,850` pods
per pod of need. Decode reaches its cap of 6 once more than 20 requests are in
progress or more than `5 × 273 = 1,365` output tok/s are offered; both are
probably a fraction of one V2-Lite pod's capacity. Past capacity, prefill adds
one pod per 5 minutes after a 15-minute wait, up to 4; decode is already at 6.
At constant load neither pool oscillates: both drivers hold their totals as
pods are added.

## Predicted failures for step 2

| Id | Prediction | How step 2 shows it |
|---|---|---|
| PF1 | Each selector returns exactly this stack's pool after the label fixes | `count by (namespace, job, pod, role, engine)` per vLLM selector returns one series per pool pod; `count by (job, plugin_name, endpoint_role, modality) (llm_d_epp_prefix_prompt_tokens_count{…})` returns one series; `count by (job) (llm_d_epp_request_total{namespace})` names `deepseek-886595ad--v2-lite-router-epp` |
| PF2 | `offered` (and `lam`) are absent after an EPP start until the first request. The ScaledObjects error, KEDA's fallback engages after 3 failures, and the replica count holds | ScaledObject `status.health` / conditions at idle after standup; replicas stay at 2 |
| PF3 | `offered` ≠ engine prompt tokens: `e = rate(llm_d_epp_prefix_prompt_tokens_sum{…}[5m]) / rate(vllm:prompt_tokens_total{role="prefill",…}[5m])` differs from 1 (bytes / 4 estimate) | steady random load; record `e` per mix |
| PF4 | Decode: `lam × gen / ok / 273 > conc / 4` whenever decode ITL < 14.65 ms, so the guard decides at steady state | read both terms and ITL at steady load |
| PF5 | Decode reaches `maxReplicaCount: 6` at `conc ≥ 21` (`ceil(conc / 4) > 5`) or `λ_out > 5 × 273 = 1,365` tok/s, whatever one pod can carry | step load; replicas against both terms |
| PF6 | Prefill adds no pod for demand above the ask that lasts less than ≈ 955 s plus cold start, and removes none for 3600 s after load drops | step above `2 × 1.1 × 10,850 = 23,870` tok/s for 10 min (no scale-up), then 20 min (one scale-up) |
| PF7 | Decode KV is levelled near 0.8 by the detector filter; `kv` adds a pod only when the mean exceeds 0.88 | long-context decode load; per-pod KV and the term |
| PF8 | `itl` reads 0 at idle (the `> 0` filter) and stays below the other terms under normal load | idle and steady samples of the term |
| PF9 | Each decode scale-in aborts in-flight requests (`--shutdown-timeout` 0) | `vllm:request_success_total{finished_reason="abort"}` and client errors at each scale-in |

## Needs measurement

1. Labels and producers on the cluster (PF1), needed by P10 and P11 of every trigger.
2. `e`, EPP estimated prompt tokens per engine prompt token, for random
   DeepSeek-tokenizer text and the agentic prompts. Needed by `offered` P3.
3. μ_P: computed prompt tokens/s of one DeepSeek-V2-Lite H100 prefill pod at its
   knee, per mix, with decode not binding. Needed to replace 10850 (= 0.7 μ_P).
4. Decode knee per mix: running + waiting per pod, completions/s per pod and ITL
   at that point. Needed to replace 4, 0.39 and 700 together, and to place the
   PF4 cross-over (`4 / (0.39 × 700)` s per token).
5. Decode ITL p90 floor and at the knee, against 0.075 s. Needed by `itl` P1.
6. Decode KV usage at the knee for 256:4096 and the agentic mix. Needed by `kv` P11.
7. Cold start of a prefill and of a decode pod, to size the prefill 900 s window
   and the run set's stage length T (PF6).
8. The KEDA (or Custom Metrics Autoscaler) release on `pokprod001`: support for
   `fallback.behavior: currentReplicasIfHigher` and `scalingModifiers`, and trap T7.

## Fixes

None of these was applied: the task owner fixed the metrics, formulas and
behavior. The constants are expected to come from the step 3/5 knee runs.

| Fails | Fix | Effect |
|---|---|---|
| prefill driver, P3 (10850) | `formula: "max(…) / (0.7 × μ_P)"` with μ_P from item 3 | prefill sized to the 0.7 target on this plant |
| `offered`, P3 (estimate) | `router.tokenizer.enabled: true` with a `vllm` `token-producer`, so `TokenizedRequest` holds engine tokens; or divide by `e` from item 2 | numerator and divisor in the same tokens |
| `conc`, P3 (4); `lam`, P3 (0.39, 700) | re-measure 4, 0.39 and the prior OSL from one decode knee run (item 4); keep `4 / 0.39` equal to the knee's per-request decode residency | decode sized to its knee; the offered guard returns to the driver's operating point and wins only while prefill is short |
| `offered`, P8 (900 s) | the scenario's CALIBRATE: for random prompts (no session-cache fill) 120–300 s, as task 0545 §2.1 advises where caches do not hold a shared working set; keep 900 s for the agentic run's design | prefill follows staircase stages within one cold start |
| `itl`, P1 (role) | keep as a guard with the SLO well above the ITL floor (item 5), or make it a veto: `min(pods × itl / 0.075, pods)` inside the `max` | it can no longer ratchet the pool on a cause more pods do not fix |
| decode scale-in (PF9) | add `--shutdown-timeout 45` to the decode vLLM command and `terminationGracePeriodSeconds` above it (task 0545 §1.3) | scale-in drains instead of aborting |
| `offered`, `lam`, P10 (N1); all vLLM triggers, P10 (N1); names, T17 | **applied**: see Label fixes | each selector reads this stack only |
