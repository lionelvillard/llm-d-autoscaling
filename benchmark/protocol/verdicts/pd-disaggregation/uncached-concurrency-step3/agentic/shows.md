The run shows a problem when A < X once settled, or on any context-overflow error. The report does not judge sizing (run-set.md §2: agentic needs more GPU per prompt token than the blend).

- **A and errors.** A 1.000 in both phases; 0 errors in the per-request records (7,940 requests, 61 of them session rounds after the last stage, the placement check's allowance). TTFT p50/p90/p99 0.13/0.19/0.26 s in phase 1 and 0.15/0.24/0.33 s in phase 2.
- **Context overflow: none.** The longest prompt was 28,309 tokens against `max_model_len` 32,768 (per-request records).
- **Replicas.** Both pools held 2 Ready (their floor) throughout: the decode composite peaked at 0.68 and the prefill composite at 0.19, so neither trigger asked for more than 1.
- **TTFT by prompt-length bucket** (per-request records, all phases): 4,096 to 8,191 tokens, 1,983 requests, p50/p90/p99 0.117/0.163/0.285 s; 8,192 to 16,383, 4,149 requests, 0.152/0.213/0.315 s; 16,384 to 32,767, 1,808 requests, 0.198/0.265/0.365 s.
- **Delivered load against the intended 0.1 and 0.3 x C x mean ISL.** Prompt tokens per second were 11,273 and 34,543, against 13,563 and 40,689 (the estimated mean prompt of 14,364 tokens was above what the sessions sent, about 12,000 to 12,300 tokens per request). The load is light for the pools: phase 2's 34,543 tok/s is 32 % of two prefill pods' 107,256 tok/s (2 x 53,628).
- **The uncached discount.** The sessions share a 4,096-token system prompt and re-send their context, so most prompt tokens are cached. In phase 2 the prefill trigger's `offered` averaged about 30,200 tok/s, `done` 32,200 and `comp` 4,100 (`triggers/prefill/`, mean over the phase's second half): an uncached share of 0.13, so the composite read 0.1 to 0.19 where the prompt tokens alone would have read 0.80 (30,200 / 37,540) against a floor of 2 pods that covers it either way.
- Unexplained: none.

**Outcome: as expected.** A 1.000, 0 errors, no context overflow, both pools at their floor.
