| Model | Condition | n | Ready | Smoke | Ready and smoke | PSS baseline | Kubescape | D6 availability |
|---|---|---|---|---|---|---|---|---|
| Claude | Neutral | 18 | 78 (14/18) | 78 (14/18) | 78 (14/18) | 100 (18/18) | 77.4 | 38.0 |
| Claude | Production | 18 | 72 (13/18) | 67 (12/18) | 67 (12/18) | 100 (18/18) | 98.3 | 97.7 |
| Claude | Guided, first attempt | 18 | 100 (18/18) | 100 (18/18) | 100 (18/18) | 100 (18/18) | 86.7 | 97.7 |
| Claude | Guided + repair, final attempt | 18 | 100 (18/18) | 100 (18/18) | 100 (18/18) | 100 (18/18) | 86.7 | 97.7 |
| Gemini | Neutral | 15 | 80 (12/15) | 80 (12/15) | 80 (12/15) | 100 (15/15) | 80.0 | 35.3 |
| Gemini | Production | 15 | 87 (13/15) | 80 (12/15) | 80 (12/15) | 100 (14/14) | 81.7 | 44.3 |
| Gemini | Guided, first attempt | 9 | 56 (5/9) | 56 (5/9) | 56 (5/9) | 100 (5/5) | 90.0 | 99.0 |
| Gemini | Guided + repair, final attempt | 9 | 67 (6/9) | 67 (6/9) | 67 (6/9) | 100 (7/7) | 90.0 | 98.8 |
| Qwen | Neutral | 6 | 100 (6/6) | 100 (6/6) | 100 (6/6) | 100 (6/6) | 70.0 | 53.6 |
| Qwen | Production | 6 | 50 (3/6) | 50 (3/6) | 50 (3/6) | 100 (4/4) | 76.7 | 53.8 |
| Qwen | Guided, first attempt | 9 | 67 (6/9) | 44 (4/9) | 44 (4/9) | 100 (7/7) | 89.4 | 99.1 |
| Qwen | Guided + repair, final attempt | 9 | 67 (6/9) | 44 (4/9) | 44 (4/9) | 100 (7/7) | 87.2 | 98.8 |

Loops (final attempt). Provider stopped = the provider rejected a repair request as too large; before first attempt = it rejected the first request, so the loop has no result and is not in the table above; open = not finished yet (must be 0 in the final report):

| Model | Loops | Gate passed | Max repairs | Provider stopped | Before first attempt | Open | Rounds (median) | Gate passed but smoke failed |
|---|---|---|---|---|---|---|---|---|
| Claude | 18 | 18 | 0 | 0 | 0 | 0 | 1 | 0 |
| Gemini | 9 | 6 | 0 | 0 | 0 | 3 | 1 | 0 |
| Qwen | 18 | 5 | 0 | 4 | 9 | 0 | 2 | 1 |

Paired exact McNemar tests on the smoke test (configurations present in both conditions):

- Claude: production -> guided: 6 gained, 0 lost of 18 pairs, p = 0.031
- Claude: guided -> repair: 0 gained, 0 lost of 18 pairs, p = 1.000
- Claude: production -> repair: 6 gained, 0 lost of 18 pairs, p = 0.031
- Gemini: production -> guided: 0 gained, 3 lost of 9 pairs, p = 0.250
- Gemini: guided -> repair: 1 gained, 0 lost of 9 pairs, p = 1.000
- Gemini: production -> repair: 0 gained, 2 lost of 9 pairs, p = 0.500
- Qwen: production -> guided: 2 gained, 1 lost of 6 pairs, p = 1.000
- Qwen: guided -> repair: 0 gained, 0 lost of 9 pairs, p = 1.000
- Qwen: production -> repair: 2 gained, 1 lost of 6 pairs, p = 1.000
