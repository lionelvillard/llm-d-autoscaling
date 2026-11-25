Run 6 is not a pass/fail run: it is the cost reference for run 3 (same load, same seed 103, pools pinned at run 3's peak Ready counts: prefill 3, decode 6; the HPAs still read and log every trigger but cannot move the pools).

- **A per phase:** 1.000, 1.000, 1.000 (run 3: 1.000, 1.000, 0.840). No errors.
- **TTFT p90 and TPOT p90 in the phases:** 0.39 s and 9.5 ms, 0.12 s and 17.2 ms, 0.11 s and 19.3 ms; run 3's phase 3 had TTFT p90 67.3 s.
- **GPU-seconds:** 32,400 (prefill 10,800 + decode 21,600), against run 3's 19,950 (prefill 9,900 + decode 10,050): run 3 / run 6 = 0.62. The comparison table is in the summary.

**Outcome: as expected (cost reference).** The static fleet met the SLO in every phase at 62 % more GPU-seconds than run 3; run 3 lost attainment only in phase 3 (A 0.840), while its decode pool went from 2 to 6.
