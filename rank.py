#!/usr/bin/env python3
"""Deterministic candidate ranker for the Redrob hackathon.

The scorer is intentionally simple and fast:
- strong positive weight for retrieval / ranking / Python / evaluation / product signals
- behavioral and logistics signals as modifiers
- penalties for obvious mismatch patterns called out in the JD

The script reads a JSONL file, scores every candidate in one pass, and writes
the top 100 rows to a CSV with the exact submission schema.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


REFERENCE_DATE = date(2026, 7, 2)
TOP_K = 100

CONSULTING_COMPANIES = {
    "tcs",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "mindtree",
    "hcl",
    "tech mahindra",
    "persistent",
    "ltimindtree",
    "deloitte",
    "ey",
    "pwc",
    "kpmg",
    "bain",
    "bcg",
    "mckinsey",
}

PREFERRED_INDIAN_CITIES = {
    "noida",
    "pune",
    "mumbai",
    "delhi",
    "delhi ncr",
    "gurgaon",
    "gurugram",
    "hyderabad",
    "bengaluru",
    "bangalore",
    "chennai",
    "ahmedabad",
    "kolkata",
}

CORE_SKILLS = {
    "python": 4.5,
    "pytorch": 4.0,
    "tensorflow": 3.5,
    "sklearn": 3.0,
    "scikit": 3.0,
    "pandas": 2.5,
    "numpy": 1.5,
    "embeddings": 5.0,
    "embedding": 5.0,
    "vector": 4.5,
    "retrieval": 5.0,
    "ranking": 5.0,
    "ranker": 4.5,
    "search": 4.5,
    "recommendation": 4.0,
    "recommender": 4.0,
    "hybrid search": 4.5,
    "dense retrieval": 4.5,
    "learning to rank": 4.5,
    "ltr": 3.5,
    "evaluation": 4.5,
    "ndcg": 5.0,
    "mrr": 4.0,
    "map": 3.5,
    "precision@k": 3.0,
    "recall@k": 3.0,
    "cross encoder": 3.5,
    "sentence-transformers": 4.5,
    "sentence transformers": 4.5,
    "bge": 4.0,
    "e5": 4.0,
    "milvus": 4.0,
    "qdrant": 4.0,
    "pinecone": 4.0,
    "weaviate": 4.0,
    "faiss": 4.0,
    "opensearch": 4.0,
    "elasticsearch": 4.0,
    "bm25": 3.5,
    "hnsw": 2.5,
    "llm": 2.5,
    "fine tuning": 3.5,
    "fine-tuning": 3.5,
    "lora": 2.5,
    "qlora": 2.5,
    "peft": 2.5,
    "rag": 2.5,
    "fastapi": 2.0,
    "flask": 1.5,
    "production": 3.5,
    "deployed": 3.0,
    "shipped": 3.0,
    "experiment": 2.5,
    "ab test": 2.5,
    "a/b": 2.5,
}

DOMAIN_SKILLS = {
    "hr": 2.5,
    "recruiting": 3.5,
    "recruiter": 3.5,
    "talent": 2.5,
    "marketplace": 2.5,
    "ats": 2.5,
    "candidate": 1.5,
    "sourcing": 2.0,
    "talent intelligence": 3.0,
}

PRODUCT_SIGNALS = {
    "product company": 4.0,
    "product": 1.5,
    "startup": 2.5,
    "saas": 2.5,
    "user facing": 2.5,
    "real-time": 2.0,
    "realtime": 2.0,
    "on-call": 1.5,
    "monitoring": 1.5,
    "roadmap": 1.5,
    "production": 2.5,
    "shipped": 2.0,
    "deployed": 2.0,
    "scale": 1.5,
    "latency": 1.5,
    "experimentation": 1.5,
    "analytics": 1.0,
}

RESEARCH_PENALTIES = {
    "research": 4.0,
    "researcher": 4.0,
    "academic": 3.5,
    "phd": 5.0,
    "thesis": 3.0,
    "publication": 3.0,
    "papers": 3.0,
    "professor": 4.0,
    "postdoc": 4.0,
    "lab": 2.0,
}

FRAMEWORK_PENALTIES = {
    "langchain": 4.5,
    "llamaindex": 3.5,
    "crewai": 2.5,
    "autogen": 2.5,
    "prompt engineering": 1.5,
    "tutorial": 1.5,
    "demo": 1.0,
}

CV_SPEECH_ROBOTICS_PENALTIES = {
    "computer vision": 4.0,
    "cv": 2.5,
    "speech recognition": 4.0,
    "asr": 3.0,
    "tts": 3.0,
    "robotics": 4.0,
    "image classification": 3.0,
    "object detection": 3.0,
    "mechanical": 2.0,
}

TITLE_HINTS = {
    "ml engineer": 4.0,
    "machine learning": 4.0,
    "data scientist": 3.5,
    "data engineer": 2.5,
    "backend engineer": 2.0,
    "software engineer": 2.5,
    "search engineer": 5.0,
    "ranking": 5.0,
    "recommendation": 4.5,
    "applied scientist": 3.0,
    "ai engineer": 4.0,
    "nlp engineer": 4.0,
}

SERVICES_JOB_TITLES = {
    "consultant",
    "business analyst",
    "operations manager",
    "customer support",
    "marketing manager",
    "hr manager",
    "sales executive",
    "accountant",
    "graphic designer",
    "project manager",
}

TOKEN_RE = re.compile(r"[a-z0-9@#+/.&-]+")
MULTISPACE_RE = re.compile(r"\s+")


@dataclass
class ScoredCandidate:
    candidate_id: str
    score: float
    reasoning: str


def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower()
    text = text.replace("/", " ").replace("+", " ").replace("_", " ").replace("|", " ")
    text = text.replace("&", " & ")
    text = MULTISPACE_RE.sub(" ", text)
    return text.strip()


def token_set(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def log1p_scaled(value: float, scale: float, cap: float) -> float:
    if value <= 0:
        return 0.0
    return min(cap, math.log1p(value) * scale)


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def years_experience_score(years: float) -> float:
    if years < 0:
        return 0.0
    center = 7.0
    width = 3.0
    return 8.0 * math.exp(-((years - center) ** 2) / (2.0 * width * width))


def count_hits(text: str, tokens: set[str], weighted_terms: Dict[str, float]) -> Tuple[float, List[str]]:
    score = 0.0
    matched: List[str] = []
    for term, weight in weighted_terms.items():
        if " " in term or "/" in term or "-" in term or "+" in term or "@" in term or "." in term:
            present = term in text
        else:
            present = term in tokens
        if present:
            score += weight
            matched.append(term)
    return score, matched


def skill_list_text(candidate: Dict[str, Any]) -> Tuple[str, set[str]]:
    skill_entries = candidate.get("skills") or []
    names: List[str] = []
    for skill in skill_entries:
        if isinstance(skill, dict):
            name = skill.get("name")
            if name:
                names.append(str(name))
    text = normalize_text(" ".join(names))
    return text, token_set(text)


def build_candidate_text(candidate: Dict[str, Any]) -> str:
    parts: List[str] = []
    profile = candidate.get("profile") or {}
    for key in ("headline", "summary", "current_title", "current_company", "current_industry", "location", "country"):
        parts.append(str(profile.get(key, "")))

    for history in candidate.get("career_history") or []:
        if isinstance(history, dict):
            for key in ("company", "title", "industry", "company_size", "description"):
                parts.append(str(history.get(key, "")))

    for education in candidate.get("education") or []:
        if isinstance(education, dict):
            for key in ("institution", "degree", "field_of_study", "grade", "tier"):
                parts.append(str(education.get(key, "")))

    for cert in candidate.get("certifications") or []:
        if isinstance(cert, dict):
            for key in ("name", "issuer"):
                parts.append(str(cert.get(key, "")))

    return normalize_text(" ".join(parts))


def product_company_signal(candidate: Dict[str, Any], text: str) -> Tuple[float, List[str]]:
    score = 0.0
    matched: List[str] = []
    if any(term in text for term in ("startup", "saas", "product company", "user facing", "platform")):
        score += 2.5
        matched.append("product")

    companies = []
    for history in candidate.get("career_history") or []:
        if isinstance(history, dict):
            company = normalize_text(history.get("company", ""))
            title = normalize_text(history.get("title", ""))
            description = normalize_text(history.get("description", ""))
            companies.append(company)
            if any(term in description for term in ("shipped", "deployed", "production", "user-facing", "real-time", "latency", "monitoring")):
                score += 1.0
                matched.append("shipped")
            if any(term in title for term in ("engineer", "scientist", "analyst", "architect")):
                score += 0.3

    if companies and all(any(service in company for service in CONSULTING_COMPANIES) for company in companies):
        score -= 1.0
        matched.append("services")

    return score, matched


def experience_shape_score(years: float) -> Tuple[float, str]:
    if years < 0:
        return 0.0, ""
    if 5.0 <= years <= 9.0:
        return 4.5, "ideal experience band"
    if 4.0 <= years < 5.0 or 9.0 < years <= 11.0:
        return 2.5, "near target experience"
    if years < 2.0:
        return -4.0, "under target experience"
    if years > 15.0:
        return -2.0, "senior-experience mismatch"
    return 0.0, ""


def location_score(profile: Dict[str, Any], signals: Dict[str, Any], text: str) -> Tuple[float, List[str]]:
    location = normalize_text(profile.get("location", ""))
    country = normalize_text(profile.get("country", ""))
    prefers = normalize_text(signals.get("preferred_work_mode", ""))
    willing = bool(signals.get("willing_to_relocate"))
    score = 0.0
    reasons: List[str] = []

    if country == "india" or any(city in location for city in PREFERRED_INDIAN_CITIES):
        if any(city in location for city in ("noida", "pune", "mumbai", "delhi", "gurgaon", "gurugram", "hyderabad")):
            score += 4.5
            reasons.append("preferred location")
        else:
            score += 2.0
            reasons.append("India location")
    elif country:
        score -= 1.0
        reasons.append("outside India")

    if willing and not any(city in location for city in ("noida", "pune")):
        score += 1.5
        reasons.append("relocation")

    if prefers in {"hybrid", "flexible"}:
        score += 1.5
        reasons.append("work mode match")
    elif prefers == "onsite":
        score += 0.8
    elif prefers == "remote" and not willing:
        score -= 0.8

    if "outside india" in text or "no visa" in text:
        score -= 0.5

    return score, reasons


def notice_period_score(signals: Dict[str, Any]) -> Tuple[float, str]:
    notice = signals.get("notice_period_days")
    if notice is None:
        return 0.0, ""
    try:
        notice = int(notice)
    except (TypeError, ValueError):
        return 0.0, ""
    if notice <= 15:
        return 4.0, "quick notice"
    if notice <= 30:
        return 3.5, "sub-30 notice"
    if notice <= 60:
        return 1.5, "moderate notice"
    if notice <= 90:
        return -0.5, "long notice"
    return -2.5, "very long notice"


def salary_score(signals: Dict[str, Any]) -> float:
    salary = signals.get("expected_salary_range_inr_lpa") or {}
    try:
        min_salary = float(salary.get("min", 0.0))
        max_salary = float(salary.get("max", 0.0))
    except (TypeError, ValueError):
        return 0.0
    if min_salary <= 0 and max_salary <= 0:
        return 0.0
    if min_salary <= 25 and max_salary <= 35:
        return 1.5
    if min_salary <= 35 and max_salary <= 45:
        return 1.0
    if min_salary > 50:
        return -2.0
    if min_salary > 35:
        return -1.0
    return 0.0


def activity_score(signals: Dict[str, Any]) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    completeness = float(signals.get("profile_completeness_score") or 0.0)
    score += clamp(completeness / 100.0 * 3.0, 0.0, 3.0)
    if completeness >= 80:
        reasons.append("complete profile")

    if signals.get("open_to_work_flag"):
        score += 2.5
        reasons.append("open to work")

    views = int(signals.get("profile_views_received_30d") or 0)
    saves = int(signals.get("saved_by_recruiters_30d") or 0)
    search_appearance = int(signals.get("search_appearance_30d") or 0)
    score += log1p_scaled(views, 0.8, 2.0)
    score += log1p_scaled(saves, 1.0, 2.5)
    score += log1p_scaled(search_appearance, 0.3, 1.8)
    if saves:
        reasons.append("recruiter interest")

    response_rate = float(signals.get("recruiter_response_rate") or 0.0)
    score += clamp(response_rate * 7.0, 0.0, 7.0)
    if response_rate >= 0.5:
        reasons.append("good response rate")

    response_hours = float(signals.get("avg_response_time_hours") or 0.0)
    if response_hours > 0:
        score += clamp(4.0 - math.log1p(response_hours), -1.5, 4.0)

    interview_rate = float(signals.get("interview_completion_rate") or 0.0)
    score += clamp(interview_rate * 5.0, 0.0, 5.0)
    if interview_rate >= 0.8:
        reasons.append("high interview completion")

    offer_rate = float(signals.get("offer_acceptance_rate") or -1.0)
    if offer_rate >= 0:
        score += clamp(offer_rate * 2.0, 0.0, 2.0)

    github = float(signals.get("github_activity_score") or -1.0)
    if github >= 0:
        score += clamp(github / 20.0, 0.0, 5.0)
        reasons.append("GitHub activity")

    if bool(signals.get("verified_email")):
        score += 1.0
    if bool(signals.get("verified_phone")):
        score += 1.5
    if bool(signals.get("linkedin_connected")):
        score += 0.8

    connections = int(signals.get("connection_count") or 0)
    endorsements = int(signals.get("endorsements_received") or 0)
    score += log1p_scaled(connections, 0.35, 2.0)
    score += log1p_scaled(endorsements, 0.22, 1.8)

    applications = int(signals.get("applications_submitted_30d") or 0)
    score += log1p_scaled(applications, 0.25, 0.8)

    last_active = parse_date(signals.get("last_active_date"))
    if last_active is not None:
        days_since = (REFERENCE_DATE - last_active).days
        if days_since <= 14:
            score += 2.5
            reasons.append("recently active")
        elif days_since <= 45:
            score += 1.5
        elif days_since <= 90:
            score += 0.2
        elif days_since <= 180:
            score -= 2.0
        else:
            score -= 4.0
            reasons.append("inactive")

    signup_date = parse_date(signals.get("signup_date"))
    if signup_date is not None:
        tenure_days = (REFERENCE_DATE - signup_date).days
        if tenure_days >= 120:
            score += 0.5

    return score, reasons


def skill_match_score(candidate: Dict[str, Any], text: str, tokens: set[str]) -> Tuple[float, List[str]]:
    skill_text, skill_tokens = skill_list_text(candidate)
    combined_text = f"{text} {skill_text}"
    combined_tokens = tokens | skill_tokens

    score = 0.0
    reasons: List[str] = []

    core_score, core_hits = count_hits(combined_text, combined_tokens, CORE_SKILLS)
    score += min(core_score, 24.0)
    if core_hits:
        reasons.extend(core_hits[:3])

    domain_score, domain_hits = count_hits(combined_text, combined_tokens, DOMAIN_SKILLS)
    score += min(domain_score, 8.0)
    if domain_hits:
        reasons.extend(domain_hits[:2])

    product_score, product_hits = count_hits(combined_text, combined_tokens, PRODUCT_SIGNALS)
    score += min(product_score, 6.0)
    if product_hits:
        reasons.extend(product_hits[:2])

    title = normalize_text(candidate.get("profile", {}).get("current_title", ""))
    title_score, title_hits = count_hits(title, token_set(title), TITLE_HINTS)
    score += min(title_score, 6.0)
    if title_hits:
        reasons.extend(title_hits[:2])

    years = float(candidate.get("profile", {}).get("years_of_experience") or 0.0)
    exp_score = years_experience_score(years)
    score += exp_score
    if 5.0 <= years <= 9.0:
        reasons.append(f"{years:.1f} yrs")

    profile = candidate.get("profile") or {}
    company = normalize_text(profile.get("current_company", ""))
    if any(service in company for service in CONSULTING_COMPANIES):
        score -= 1.5

    education = candidate.get("education") or []
    for item in education:
        if not isinstance(item, dict):
            continue
        tier = normalize_text(item.get("tier", ""))
        field = normalize_text(item.get("field_of_study", ""))
        if any(term in field for term in ("computer science", "information technology", "machine learning", "data")):
            score += 1.0
        if tier == "tier_1":
            score += 1.0
        elif tier == "tier_2":
            score += 0.5

    return score, reasons


def penalty_score(candidate: Dict[str, Any], text: str, tokens: set[str]) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    has_product_system_signal = any(term in text for term in ("production", "shipped", "deployed", "ranking", "retrieval", "search", "python", "evaluation", "milvus", "faiss"))

    research_hits = [term for term in RESEARCH_PENALTIES if term in text]
    if research_hits and not has_product_system_signal:
        score += min(12.0, sum(RESEARCH_PENALTIES[term] for term in research_hits))
        reasons.append("research heavy")

    framework_hits = [term for term in FRAMEWORK_PENALTIES if term in text]
    if framework_hits:
        framework_only = any(term in text for term in ("langchain", "llamaindex", "crewai", "autogen")) and not has_product_system_signal
        if framework_only:
            score += min(9.0, sum(FRAMEWORK_PENALTIES[term] for term in framework_hits))
            reasons.append("framework heavy")

    cv_hits = [term for term in CV_SPEECH_ROBOTICS_PENALTIES if term in text]
    if cv_hits:
        cv_only = any(term in text for term in ("computer vision", "speech recognition", "tts", "robotics", "image classification", "object detection")) and not any(term in text for term in ("retrieval", "ranking", "search", "nlp", "language", "ir"))
        if cv_only:
            score += min(10.0, sum(CV_SPEECH_ROBOTICS_PENALTIES[term] for term in cv_hits))
            reasons.append("cv/speech heavy")

    profile = candidate.get("profile") or {}
    title = normalize_text(profile.get("current_title", ""))
    summary = normalize_text(profile.get("summary", ""))

    service_job = any(term in title for term in SERVICES_JOB_TITLES)
    company_history = []
    for history in candidate.get("career_history") or []:
        if isinstance(history, dict):
            company_history.append(normalize_text(history.get("company", "")))
    all_service = company_history and all(any(service in company for service in CONSULTING_COMPANIES) for company in company_history)
    product_terms = any(term in text for term in ("product company", "startup", "saas", "shipped", "deployed", "production"))
    if (service_job or all_service) and not product_terms:
        score += 5.0
        reasons.append("services only")

    if any(term in summary for term in ("pure research", "research only", "academic")):
        score += 2.0

    return score, reasons


def normalize_final_score(raw_score: float) -> float:
    return clamp(raw_score / 80.0, 0.0, 1.0)


def build_reasoning(candidate: Dict[str, Any], fit_hits: Sequence[str], signal_hits: Sequence[str], penalty_hits: Sequence[str]) -> str:
    profile = candidate.get("profile") or {}
    years = profile.get("years_of_experience")
    current_title = str(profile.get("current_title", "role")).strip()
    current_company = str(profile.get("current_company", "")).strip()
    location = str(profile.get("location", "")).strip()

    fit_terms: List[str] = []
    for term in fit_hits:
        if term not in fit_terms:
            fit_terms.append(term)
        if len(fit_terms) >= 3:
            break

    signal_terms: List[str] = []
    for term in signal_hits:
        if term not in signal_terms:
            signal_terms.append(term)
        if len(signal_terms) >= 3:
            break

    fit_part = ", ".join(fit_terms[:3]) if fit_terms else "general JD fit"

    if signal_terms:
        signal_part = ", ".join(signal_terms[:3])
        second = f"Activity signals include {signal_part}."
    else:
        second = "Signals are broadly stable."

    if years is not None:
        company_bit = f" at {current_company}" if current_company else ""
        first = f"{current_title}{company_bit} with {float(years):.1f} yrs; fit on {fit_part}."
    else:
        company_bit = f" at {current_company}" if current_company else ""
        first = f"{current_title}{company_bit}; fit on {fit_part}."

    if penalty_hits:
        second = f"Penalty risks are {', '.join(penalty_hits[:2])}."
    elif location:
        second = f"Location signal: {location}. {second}"

    return f"{first} {second}"[:220].rstrip()


def score_candidate(candidate: Dict[str, Any]) -> ScoredCandidate:
    candidate_id = str(candidate.get("candidate_id", ""))
    profile = candidate.get("profile") or {}
    signals = candidate.get("redrob_signals") or {}

    text = build_candidate_text(candidate)
    tokens = token_set(text)

    fit_score, fit_hits = skill_match_score(candidate, text, tokens)
    product_score, product_hits = product_company_signal(candidate, text)
    activity, signal_hits = activity_score(signals)
    location, location_hits = location_score(profile, signals, text)
    notice, notice_hit = notice_period_score(signals)
    salary = salary_score(signals)
    experience_bonus, experience_reason = experience_shape_score(float(profile.get("years_of_experience") or 0.0))
    penalties, penalty_hits = penalty_score(candidate, text, tokens)

    raw_score = (
        fit_score
        + product_score
        + activity
        + location
        + notice
        + salary
        + experience_bonus
        - penalties
    )

    score = normalize_final_score(raw_score)

    fit_reason_terms = list(fit_hits)
    if experience_reason:
        fit_reason_terms.append(experience_reason)

    signal_reason_terms = list(signal_hits)
    signal_reason_terms.extend(location_hits)
    if notice_hit:
        signal_reason_terms.append(notice_hit)

    reasoning = build_reasoning(candidate, fit_reason_terms, signal_reason_terms, penalty_hits)

    epsilon = (10000000 - int(candidate_id.split("_")[-1])) * 1e-12 if candidate_id.startswith("CAND_") else 0.0
    score = clamp(score + epsilon, 0.0, 1.0)

    return ScoredCandidate(candidate_id=candidate_id, score=score, reasoning=reasoning)


def write_submission(rows: Sequence[ScoredCandidate], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, item in enumerate(rows, start=1):
            writer.writerow([item.candidate_id, rank, f"{item.score:.12f}", item.reasoning])


def validate_output(out_path: Path) -> int:
    try:
        from validate_submission import validate_submission as validate_fn
    except Exception:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("validate_submission.py")), str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    errors = validate_fn(str(out_path))
    if errors:
        print(f"Validation failed ({len(errors)} issue(s)):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Submission is valid.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic Redrob candidate ranker")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to output CSV")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Number of rows to emit (default: 100)")
    parser.add_argument("--validate", action="store_true", help="Run the challenge validator after writing the CSV")
    args = parser.parse_args(argv)

    candidates_path = Path(args.candidates)
    out_path = Path(args.out)

    scored: List[ScoredCandidate] = []
    for candidate in load_jsonl(candidates_path):
        scored.append(score_candidate(candidate))

    scored.sort(key=lambda item: (-item.score, item.candidate_id))

    if len(scored) < args.top_k:
        raise SystemExit(f"Need at least {args.top_k} candidates, found {len(scored)}.")

    selected = scored[: args.top_k]
    write_submission(selected, out_path)

    if args.validate:
        return validate_output(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())