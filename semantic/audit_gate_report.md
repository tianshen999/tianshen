# Release Gate Report (ADR-029)

- Start: 2026-09-09 00:27:59  End: 2026-09-09 00:37:26
- Verdict: **PASS - release allowed** (failed steps: 0 / 11)

| Step | Result |
|---|---|
| Unit tests | PASS |
| Calibrate F/P certs | PASS |
| Calibrate S certs | PASS |
| Rebuild word planes | PASS |
| Data consistency | PASS |
| Full-system audit | PASS |
| E2E integration | PASS |
| Eval polyphone | PASS |
| Eval semantic | PASS |
| Eval token economy | PASS |
| Threshold gate | PASS |

Thresholds (tools/gate_check.py; changes require ADR-029 revision):
- Independence: deep-layer R2(F+P explains S) < 0.3
- Semantic retrieval: S2 Hit@10 >= 0.19
- Polyphone accuracy >= 99.9%
- Rank criterion: every plane measured rank >= 0.8 x nominal
- E2E integration: one text through tokenize -> pinyin -> 3D retrieval -> plug routing (exit 0)
