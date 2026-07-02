# Redrob Ranker

## Overview
Deterministic CPU-only ranker for the Redrob / India Runs Data & AI Challenge.
It reads candidate data, scores each candidate locally, and writes the required `submission.csv` output.

Place your own `candidates.jsonl` next to `rank.py` before running.

## Files in This Repo
- `rank.py` - main ranking script
- `sample_candidates.json` - small sample input file
- `submission.csv` - generated output example
- `submission_metadata.yaml` - submission metadata template
- `validate_submission.py` - local CSV validator
- `requirements.txt` - dependency list
- `.gitignore` - ignores local-only large files

## Setup
1. Use Python 3.11+.
2. Optional: create and activate a virtual environment.
3. Install dependencies only if `requirements.txt` contains any packages.
4. Put `candidates.jsonl` in this folder locally before running.

## Run the Ranker
```powershell
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

## Notes
- Ranking is CPU-only.
- No network access is used during ranking.
- `candidates.jsonl` stays local and is not committed to GitHub.

## Sandbox Demo
Colab link: https://colab.research.google.com/drive/1l_xRxQj8hkYATMzuDAzCwyWkaNIJ4rRi?usp=sharing
