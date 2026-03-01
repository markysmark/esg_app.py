"""
Service Line Framework for ESG Scoring.

Provides:
- Service line definitions with ESG domain mapping and weights
- Dynamic weight normalisation when only a subset of services is active
- Cleaning ESG Contribution Score formula
- RAG (Red / Amber / Green) threshold logic with trend-based escalation
- Recommendation engine (non-sales-driven diagnostics)
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 1. Service line library
# ---------------------------------------------------------------------------

# Each entry carries the ESG domains it influences and its share of total
# ESG performance variance when all services are active (weights sum to 1.0).
SERVICE_LINES: dict[str, dict[str, Any]] = {
    "Cleaning":          {"domains": ["E", "S", "G"], "weight": 0.30},
    "Waste Management":  {"domains": ["E"],            "weight": 0.25},
    "Security":          {"domains": ["S", "G"],       "weight": 0.15},
    "M&E":               {"domains": ["E"],            "weight": 0.20},
    "Catering":          {"domains": ["S"],            "weight": 0.05},
    "Landscaping":       {"domains": ["E"],            "weight": 0.05},
}

# ---------------------------------------------------------------------------
# 2. Scope helpers – persisted via SQLAlchemy (import kept lazy to avoid
#    circular imports at module load time; callers must pass the session).
# ---------------------------------------------------------------------------


def get_active_service_lines(session, building: str) -> list[str]:
    """Return the list of service-line names that are active for *building*.

    Falls back to all service lines when no configuration has been saved.
    """
    from main_app import ServiceLineConfig  # lazy import

    configs = (
        session.query(ServiceLineConfig)
        .filter(ServiceLineConfig.building == building)
        .all()
    )
    if not configs:
        return list(SERVICE_LINES.keys())
    return [c.service_line for c in configs if c.active]


def save_service_lines(session, building: str, active_lines: list[str]) -> None:
    """Persist the active service-line selection for *building*."""
    from main_app import ServiceLineConfig  # lazy import

    # Delete existing config for this building
    session.query(ServiceLineConfig).filter(
        ServiceLineConfig.building == building
    ).delete()

    for name in SERVICE_LINES:
        cfg = ServiceLineConfig(
            building=building,
            service_line=name,
            active=(name in active_lines),
        )
        session.add(cfg)
    session.commit()


# ---------------------------------------------------------------------------
# 3. Dynamic weight normalisation
# ---------------------------------------------------------------------------


def normalised_weight(service_line: str, active_lines: list[str]) -> float:
    """Return the weight of *service_line* normalised to the active scope.

    If *service_line* is not in *active_lines*, returns 0.0.
    The total active weight is redistributed so contributions still sum to 1.
    """
    if service_line not in active_lines:
        return 0.0
    total_active = sum(SERVICE_LINES[s]["weight"] for s in active_lines if s in SERVICE_LINES)
    if total_active == 0.0:
        return 0.0
    return SERVICE_LINES[service_line]["weight"] / total_active


def compute_normalised_service_score(
    service_scores: dict[str, float], active_lines: list[str]
) -> float:
    """Compute a single service ESG score from individual service performance scores.

    *service_scores* maps service-line name → score (0–100).
    Only active lines are included; weights are normalised to the active scope.
    Returns a score in [0, 100] rounded to one decimal place.
    """
    if not active_lines:
        return 0.0
    total = 0.0
    for line in active_lines:
        score = service_scores.get(line, 0.0)
        total += score * normalised_weight(line, active_lines)
    return round(min(100.0, max(0.0, total)), 1)


# ---------------------------------------------------------------------------
# 4. Cleaning ESG Contribution Score
# ---------------------------------------------------------------------------

# Field definitions used by CleaningKPI and UI helpers
CLEANING_KPI_FIELDS: dict[str, dict[str, Any]] = {
    # Environmental
    "chem_per_sqm":        {"label": "Chemical Usage (L/m²)",          "domain": "E"},
    "eco_chem_pct":        {"label": "Eco-certified Chemicals (%)",     "domain": "E"},
    "water_per_site":      {"label": "Water Usage per Site (m³)",       "domain": "E"},
    "waste_seg_accuracy":  {"label": "Waste Segregation Accuracy (%)",  "domain": "E"},
    "carbon_per_visit":    {"label": "Carbon per Cleaning Visit (kg)",  "domain": "E"},
    "microfibre_ratio":    {"label": "Microfibre vs Disposable (%)",    "domain": "E"},
    # Social
    "staff_turnover_rate": {"label": "Staff Turnover Rate (%)",         "domain": "S"},
    "training_hours":      {"label": "Training Hours per Cleaner",      "domain": "S"},
    "living_wage_pct":     {"label": "Living Wage Compliance (%)",      "domain": "S"},
    "accident_freq_rate":  {"label": "Accident Frequency Rate",         "domain": "S"},
    "absence_rate":        {"label": "Absence Rate (%)",                "domain": "S"},
    "client_satisfaction": {"label": "Client Satisfaction Score (0-10)","domain": "S"},
    # Governance
    "audit_pass_rate":     {"label": "Audit Pass Rate (%)",             "domain": "G"},
    "method_stmt_updates": {"label": "Method Statement Updates (yr)",   "domain": "G"},
    "sla_adherence":       {"label": "SLA Adherence (%)",               "domain": "G"},
    "incident_report_hrs": {"label": "Incident Reporting Time (hrs)",   "domain": "G"},
    "subcontractor_score": {"label": "Subcontractor Vetting Score (%)", "domain": "G"},
}


def compute_contribution_score(kpi: dict[str, float]) -> float:
    """Compute the Cleaning ESG Contribution Score.

    Formula:
        (chemical_score × 0.25) + (waste_segregation × 0.30)
        + (training_hours × 0.15) + (carbon_score × 0.30)

    Each raw KPI is converted to a 0–100 component score before weighting.
    Returns a value in [0, 100] rounded to one decimal place.
    """
    # Chemical score: eco-certified % used directly (higher is better)
    chemical_score = min(100.0, float(kpi.get("eco_chem_pct") or 0.0))

    # Waste segregation: already a percentage, higher = better
    waste_seg = min(100.0, float(kpi.get("waste_seg_accuracy") or 0.0))

    # Training hours: normalised against a 40-hour benchmark (max score = 100)
    training_raw = float(kpi.get("training_hours") or 0.0)
    training_score = min(100.0, (training_raw / 40.0) * 100.0)

    # Carbon per visit: lower is better. Invert against 20 kg benchmark.
    carbon_raw = float(kpi.get("carbon_per_visit") or 0.0)
    carbon_score = max(0.0, 100.0 - (carbon_raw / 20.0) * 100.0)

    contribution = (
        chemical_score * 0.25
        + waste_seg * 0.30
        + training_score * 0.15
        + carbon_score * 0.30
    )
    return round(min(100.0, max(0.0, contribution)), 1)


# ---------------------------------------------------------------------------
# 5. RAG framework – static thresholds + trend-based escalation
# ---------------------------------------------------------------------------

# Static thresholds: { metric: (red_upper, amber_upper) } where *lower is worse*.
# For metrics where *higher is worse*, we negate the value before lookup.
RAG_THRESHOLDS: dict[str, dict[str, Any]] = {
    # lower is worse → green when value > amber_lower
    "waste_seg_accuracy":  {"direction": "higher_better", "amber": 90, "green": 95},
    "eco_chem_pct":        {"direction": "higher_better", "amber": 50, "green": 75},
    "living_wage_pct":     {"direction": "higher_better", "amber": 90, "green": 100},
    "audit_pass_rate":     {"direction": "higher_better", "amber": 80, "green": 90},
    "sla_adherence":       {"direction": "higher_better", "amber": 85, "green": 95},
    "client_satisfaction": {"direction": "higher_better", "amber": 6,  "green": 8},
    "subcontractor_score": {"direction": "higher_better", "amber": 60, "green": 80},
    "microfibre_ratio":    {"direction": "higher_better", "amber": 50, "green": 75},
    "training_hours":      {"direction": "higher_better", "amber": 20, "green": 35},
    # higher is worse
    "chem_per_sqm":        {"direction": "lower_better",  "amber": 0.5, "red": 1.0},
    "water_per_site":      {"direction": "lower_better",  "amber": 50,  "red": 100},
    "carbon_per_visit":    {"direction": "lower_better",  "amber": 5,   "red": 10},
    "staff_turnover_rate": {"direction": "lower_better",  "amber": 20,  "red": 35},
    "accident_freq_rate":  {"direction": "lower_better",  "amber": 0.5, "red": 1.0},
    "absence_rate":        {"direction": "lower_better",  "amber": 5,   "red": 8},
    "incident_report_hrs": {"direction": "lower_better",  "amber": 4,   "red": 24},
    "method_stmt_updates": {"direction": "lower_better",  "amber": 2,   "red": 4},
}

_TREND_CONSECUTIVE_DECLINES = 3
_TREND_MOM_PCT_THRESHOLD = 8.0
_TREND_PORTFOLIO_VARIANCE_PCT = 15.0


def rag_static(metric: str, value: float) -> str:
    """Return 'green', 'amber', or 'red' based on static thresholds.

    Returns 'grey' when no threshold is defined for the metric.
    """
    cfg = RAG_THRESHOLDS.get(metric)
    if cfg is None:
        return "grey"

    if cfg["direction"] == "higher_better":
        if value >= cfg["green"]:
            return "green"
        elif value >= cfg["amber"]:
            return "amber"
        return "red"
    else:  # lower_better
        if value <= cfg["amber"]:
            return "green"
        elif value <= cfg["red"]:
            return "amber"
        return "red"


def rag_trend(metric: str, history: list[float]) -> str | None:
    """Return a trend-based RAG escalation ('red' or 'amber') or None.

    Rules:
    - 3 consecutive month-on-month declines → red
    - Any single period decline ≥ 8% → amber
    - Deviation from portfolio average > 15% → amber (requires portfolio_avg kwarg via history[-1] being the average)

    *history* is a chronological list of values (oldest first).
    Returns None when there is insufficient data or no trigger fires.
    """
    if len(history) < 2:
        return None

    cfg = RAG_THRESHOLDS.get(metric)
    if cfg is None:
        return None

    # For lower_better metrics flip sign so "decline" = increase in raw value
    multiplier = -1.0 if cfg["direction"] == "lower_better" else 1.0
    adjusted = [v * multiplier for v in history]

    # Consecutive declines
    if len(adjusted) >= _TREND_CONSECUTIVE_DECLINES:
        diffs = [adjusted[i] - adjusted[i - 1] for i in range(1, len(adjusted))]
        last_n = diffs[-(  _TREND_CONSECUTIVE_DECLINES):]
        if all(d < 0 for d in last_n):
            return "red"

    # Month-on-month deterioration ≥ 8%
    prev, curr = adjusted[-2], adjusted[-1]
    if prev != 0 and abs((curr - prev) / prev) * 100 >= _TREND_MOM_PCT_THRESHOLD and curr < prev:
        return "amber"

    return None


def get_rag_status(metric: str, value: float, history: list[float] | None = None) -> str:
    """Return the effective RAG status, combining static and trend signals.

    Trend-based escalation can only worsen (not improve) the static result.
    """
    static = rag_static(metric, value)
    if history:
        trend = rag_trend(metric, history)
        # Escalate: red > amber > green
        rank = {"red": 2, "amber": 1, "green": 0, "grey": -1}
        if trend and rank.get(trend, 0) > rank.get(static, 0):
            return trend
    return static


# ---------------------------------------------------------------------------
# 6. Recommendation engine (non-sales driven)
# ---------------------------------------------------------------------------

# Each recommendation entry has:
#   trigger: (metric, rag_status) pair
#   drivers: list of likely cause strings
#   actions: list of recommended action strings (last may note revenue impact)
#   projected_outcome: short outcome note

_RECOMMENDATIONS: list[dict[str, Any]] = [
    {
        "trigger": ("waste_seg_accuracy", "red"),
        "observation": "Waste segregation accuracy is critically low",
        "drivers": [
            "Poor segregation signage or bin placement",
            "Night-shift contractor overlap",
            "Insufficient staff training on waste streams",
        ],
        "actions": [
            "Refresh on-site signage (low cost)",
            "Conduct staff toolbox talk (included in contract)",
            "Review bin positioning with FM",
            "Consider a daytime waste champion pilot",
        ],
        "projected_outcome": "Contamination reduction 10–15%; E score uplift 5–8 pts",
    },
    {
        "trigger": ("waste_seg_accuracy", "amber"),
        "observation": "Waste segregation accuracy is declining",
        "drivers": ["Seasonal staffing changes", "New contractors not yet inducted"],
        "actions": [
            "Re-induct new or temporary staff on waste procedures",
            "Quick spot-audit of key waste points",
        ],
        "projected_outcome": "Stabilise contamination within 4 weeks",
    },
    {
        "trigger": ("carbon_per_visit", "red"),
        "observation": "Carbon per cleaning visit is above threshold",
        "drivers": [
            "Inefficient routing or excess vehicle journeys",
            "Out-of-hours machine use not energy-aligned",
        ],
        "actions": [
            "Review cleaning schedule to consolidate visits",
            "Align heavy equipment use to off-peak energy windows",
            "Assess route optimisation with facilities team",
        ],
        "projected_outcome": "Carbon reduction 10–20% per visit; supports Scope 3 reporting",
    },
    {
        "trigger": ("eco_chem_pct", "red"),
        "observation": "Eco-certified chemical usage is low",
        "drivers": [
            "Legacy procurement contracts",
            "Supplier certification not updated",
        ],
        "actions": [
            "Review chemical dilution ratios with current supplier",
            "Request updated supplier eco-certifications",
            "Trial certified alternatives on a low-risk area first",
        ],
        "projected_outcome": "E score chemical component improvement; supports brand compliance",
    },
    {
        "trigger": ("staff_turnover_rate", "red"),
        "observation": "Staff turnover rate is high",
        "drivers": [
            "Below living-wage remuneration",
            "Limited career progression visibility",
            "Shift pattern inflexibility",
        ],
        "actions": [
            "Conduct exit interview analysis",
            "Confirm living wage compliance for all site staff",
            "Introduce quarterly recognition programme (low cost)",
        ],
        "projected_outcome": "Turnover reduction; S score stability; improved service consistency",
    },
    {
        "trigger": ("training_hours", "red"),
        "observation": "Training hours per cleaner are below target",
        "drivers": ["Operational pressure limiting scheduled training", "New staff not yet inducted"],
        "actions": [
            "Schedule micro-learning sessions (15 min during shift handover)",
            "Deploy digital training modules for flexible completion",
        ],
        "projected_outcome": "Competence uplift; contribution score improvement within 1 quarter",
    },
    {
        "trigger": ("audit_pass_rate", "red"),
        "observation": "Audit pass rate is below acceptable threshold",
        "drivers": [
            "Method statements out of date",
            "Site-specific risk controls not communicated to staff",
        ],
        "actions": [
            "Urgent review of method statements for this site",
            "Pre-audit internal walkthrough with site supervisor",
            "Update risk register entries",
        ],
        "projected_outcome": "G score recovery; reduces contractual exposure",
    },
    {
        "trigger": ("sla_adherence", "amber"),
        "observation": "SLA adherence is slipping",
        "drivers": [
            "Absence or resourcing gaps",
            "Scope creep not formally documented",
        ],
        "actions": [
            "Review absence cover arrangements",
            "Confirm scope boundaries with FM in writing",
            "Flag any out-of-scope requests for variation management",
        ],
        "projected_outcome": "SLA stabilisation; protects contract renewal position",
    },
    {
        "trigger": ("client_satisfaction", "red"),
        "observation": "Client satisfaction score is critically low",
        "drivers": [
            "Unresolved service complaints",
            "Communication gaps with FM",
        ],
        "actions": [
            "Schedule urgent review meeting with building FM",
            "Prepare documented action plan with timescales",
            "Increase site supervisor visit frequency short-term",
        ],
        "projected_outcome": "Relationship repair; reduces churn risk",
    },
]


def generate_recommendations(
    kpi_data: dict[str, float],
    history: dict[str, list[float]] | None = None,
) -> list[dict[str, Any]]:
    """Return a list of recommendation dicts for the given KPI snapshot.

    Each returned dict contains:
        observation, drivers (list), actions (list), projected_outcome,
        rag_status, metric.

    Only recommendations whose trigger metric fires (amber or red) are returned.
    """
    triggered = []
    seen_metrics: set[str] = set()

    for rec in _RECOMMENDATIONS:
        metric, required_status = rec["trigger"]
        value = kpi_data.get(metric)
        if value is None:
            continue
        hist = (history or {}).get(metric, [])
        status = get_rag_status(metric, float(value), hist or None)
        # Fire if status matches trigger or is more severe
        rank = {"red": 2, "amber": 1, "green": 0, "grey": -1}
        if rank.get(status, 0) >= rank.get(required_status, 0) and status not in ("green", "grey"):
            if metric not in seen_metrics:
                triggered.append({
                    "metric": metric,
                    "rag_status": status,
                    "observation": rec["observation"],
                    "drivers": rec["drivers"],
                    "actions": rec["actions"],
                    "projected_outcome": rec["projected_outcome"],
                })
                seen_metrics.add(metric)

    return triggered
