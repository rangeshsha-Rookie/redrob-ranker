# Redrob Hackathon — Deck Outline
> Copy this into Google Slides → File → Download → PDF Document

---

## Slide 1 — Title
**India Runs Data & AI Challenge**
Intelligent Candidate Discovery & Ranking

Team: Rangesh Gupta (Solo)
Track: Data & AI Challenge
Hack2skill × Redrob AI — 2026

---

## Slide 2 — What I Built
A **deterministic, CPU-only candidate ranking system** that:
- Reads 100,000 candidates from `candidates.jsonl`
- Scores every candidate against the Redrob AI Engineer JD
- Outputs the **top 100 ranked candidates** as a CSV with 1-2 sentence reasoning per candidate
- Runs in under 3 minutes, no GPU, no internet

---

## Slide 3 — Why This Approach
- **Rule-based scoring = transparent + reproducible** — every score can be explained
- **Multi-signal design** prevents keyword stuffers from ranking high
- Uses all **23 redrob behavioral signals** for realistic candidate evaluation
- **Honeypot detection** built in — filters ~80 subtly impossible profiles
- Satisfies all compute constraints: CPU-only, no network, ≤5 min

---

## Slide 4 — How It Works
```
Step 1: Load candidates.jsonl
Step 2: Extract 6 signal groups per candidate
        └ Skills match (token overlap with JD)
        └ Years of experience
        └ Seniority level
        └ Bangalore location bonus
        └ Notice period penalty
        └ Behavioral signal score (23 signals)
Step 3: Apply JD-priority weights → final_score
Step 4: Sort descending, take top 100
Step 5: Write submission.csv with rank, score, reasoning
```

---

## Slide 5 — Results & Links
- **100 candidates ranked** | Rank 1 = best fit
- Score range: 0.0 – 1.0 | Monotonically non-increasing ✔
- All candidate_ids verified against dataset ✔
- Format validated with `validate_submission.py` ✔

🔗 GitHub: https://github.com/rangeshsha-Rookie/redrob-ranker
📳 Sandbox: https://colab.research.google.com/drive/1l_xRxQj8hkYATMzuDAzCwyWkaNIJ4rRi?usp=sharing
