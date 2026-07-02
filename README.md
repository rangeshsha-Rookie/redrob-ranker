# Redrob Ranker — India Runs Data & AI Challenge

> **Track 1 — Data & AI Challenge** | Redrob × Hack2skill 2026

## What I Built
A deterministic, CPU-only candidate ranking system that scores 100,000 candidates against the Redrob AI Engineer JD using multi-signal weighted scoring — skills match, years of experience, seniority, location, notice period, and all 23 redrob behavioral signals.

## Why This Approach
- **No ML model needed** — rule-based scoring is fast, transparent, and fully reproducible
- **Behavioral signals** prevent keyword stuffers from gaming the ranking
- **Honeypot detection** via profile consistency checks
- **Runs in under 5 minutes, CPU only, no network** — satisfies all compute constraints

## How It Works
```
1. Load candidates.jsonl (local only — not in repo)
2. Score each candidate across 6 signal groups
3. Apply JD-priority weights to produce a final score
4. Output top 100 ranked candidates as submission.csv with reasoning
```

## Repo Files
| File | Purpose |
|---|---|
| `rank.py` | Main ranking script |
| `sample_candidates.json` | 50-candidate sample for sandbox testing |
| `submission.csv` | Final ranked output (top 100) |
| `submission_metadata.yaml` | Submission metadata |
| `validate_submission.py` | Format validator |
| `requirements.txt` | Dependencies (stdlib only) |
| `.gitignore` | Excludes large local dataset files |

## Setup & Run
```powershell
# Python 3.11+ required
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

> `candidates.jsonl` is kept **local only** and is not committed to GitHub.

## Convert Output to XLSX
```powershell
pip install openpyxl pandas
python -c "import pandas as pd; pd.read_csv('submission.csv').to_excel('submission.xlsx', index=False); print('Done!')"
```

## Constraints Met
- CPU only ✅
- No network during ranking ✅
- Runs in under 5 minutes ✅
- 100 ranked candidates with reasoning ✅
- Score monotonically non-increasing ✅

## Sandbox Demo
[Run on Colab](https://colab.research.google.com/drive/1l_xRxQj8hkYATMzuDAzCwyWkaNIJ4rRi?usp=sharing) — uses `sample_candidates.json` (50 candidates)

## GitHub Repo
https://github.com/rangeshsha-Rookie/redrob-ranker
