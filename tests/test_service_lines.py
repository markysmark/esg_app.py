"""Tests for the service_lines module."""

import pytest
import sys
import os

# Ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from service_lines import (
    SERVICE_LINES,
    normalised_weight,
    compute_normalised_service_score,
    compute_contribution_score,
    rag_static,
    rag_trend,
    get_rag_status,
    generate_recommendations,
)


# ---------------------------------------------------------------------------
# Service line definitions
# ---------------------------------------------------------------------------

def test_service_lines_weights_sum_to_one():
    """All service line weights should sum to exactly 1.0."""
    total = sum(v["weight"] for v in SERVICE_LINES.values())
    assert abs(total - 1.0) < 1e-9


def test_all_service_lines_have_domains():
    for name, meta in SERVICE_LINES.items():
        assert "domains" in meta, f"{name} missing 'domains'"
        assert len(meta["domains"]) > 0


# ---------------------------------------------------------------------------
# Weight normalisation
# ---------------------------------------------------------------------------

def test_normalised_weight_single_active():
    """When only one service is active its normalised weight should be 1.0."""
    w = normalised_weight("Cleaning", ["Cleaning"])
    assert abs(w - 1.0) < 1e-9


def test_normalised_weight_all_active():
    """When all services are active, normalised weight equals raw weight."""
    all_lines = list(SERVICE_LINES.keys())
    for line in all_lines:
        expected = SERVICE_LINES[line]["weight"]
        assert abs(normalised_weight(line, all_lines) - expected) < 1e-9


def test_normalised_weight_inactive_returns_zero():
    w = normalised_weight("Security", ["Cleaning", "Waste Management"])
    assert w == 0.0


def test_normalised_weight_empty_active():
    w = normalised_weight("Cleaning", [])
    assert w == 0.0


def test_normalised_weights_sum_to_one_for_subset():
    """Normalised weights for an active subset should sum to 1.0."""
    active = ["Cleaning", "M&E"]
    total = sum(normalised_weight(line, active) for line in active)
    assert abs(total - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Normalised service score
# ---------------------------------------------------------------------------

def test_compute_normalised_service_score_all_perfect():
    active = list(SERVICE_LINES.keys())
    scores = {line: 100.0 for line in active}
    result = compute_normalised_service_score(scores, active)
    assert result == 100.0


def test_compute_normalised_service_score_empty_active():
    result = compute_normalised_service_score({"Cleaning": 80}, [])
    assert result == 0.0


def test_compute_normalised_service_score_subset():
    """Partial scope: only Cleaning at 80 and M&E at 60 active."""
    active = ["Cleaning", "M&E"]
    scores = {"Cleaning": 80.0, "M&E": 60.0}
    result = compute_normalised_service_score(scores, active)
    # Verify it is within [0, 100] and better than 60
    assert 60.0 < result < 80.0


def test_compute_normalised_service_score_clamped():
    """Score should never exceed 100."""
    active = list(SERVICE_LINES.keys())
    scores = {line: 120.0 for line in active}
    result = compute_normalised_service_score(scores, active)
    assert result <= 100.0


# ---------------------------------------------------------------------------
# Contribution score
# ---------------------------------------------------------------------------

def test_contribution_score_all_perfect():
    kpi = {
        "eco_chem_pct": 100.0,
        "waste_seg_accuracy": 100.0,
        "training_hours": 40.0,
        "carbon_per_visit": 0.0,
    }
    assert compute_contribution_score(kpi) == 100.0


def test_contribution_score_all_zero():
    # carbon_per_visit = 0 is ideal → max carbon_score = 100
    # all others = 0 → chemical, waste_seg, training each = 0
    # result = 0*0.25 + 0*0.30 + 0*0.15 + 100*0.30 = 30.0
    score = compute_contribution_score({})
    assert score == 30.0


def test_contribution_score_partial():
    kpi = {
        "eco_chem_pct": 80.0,
        "waste_seg_accuracy": 90.0,
        "training_hours": 20.0,
        "carbon_per_visit": 5.0,
    }
    score = compute_contribution_score(kpi)
    assert 0.0 < score < 100.0


def test_contribution_score_bounds():
    kpi = {
        "eco_chem_pct": 50.0,
        "waste_seg_accuracy": 75.0,
        "training_hours": 30.0,
        "carbon_per_visit": 10.0,
    }
    score = compute_contribution_score(kpi)
    assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# RAG – static thresholds
# ---------------------------------------------------------------------------

def test_rag_static_green_higher_better():
    assert rag_static("waste_seg_accuracy", 96.0) == "green"


def test_rag_static_amber_higher_better():
    assert rag_static("waste_seg_accuracy", 92.0) == "amber"


def test_rag_static_red_higher_better():
    assert rag_static("waste_seg_accuracy", 80.0) == "red"


def test_rag_static_green_lower_better():
    assert rag_static("carbon_per_visit", 3.0) == "green"


def test_rag_static_amber_lower_better():
    assert rag_static("carbon_per_visit", 7.0) == "amber"


def test_rag_static_red_lower_better():
    assert rag_static("carbon_per_visit", 15.0) == "red"


def test_rag_static_unknown_metric():
    assert rag_static("not_a_metric", 50.0) == "grey"


# ---------------------------------------------------------------------------
# RAG – trend-based escalation
# ---------------------------------------------------------------------------

def test_rag_trend_no_escalation_stable():
    # Stable values – no escalation
    result = rag_trend("waste_seg_accuracy", [90.0, 91.0, 92.0])
    assert result is None


def test_rag_trend_consecutive_declines_triggers_red():
    # Three consecutive declines
    result = rag_trend("waste_seg_accuracy", [95.0, 93.0, 91.0, 89.0])
    assert result == "red"


def test_rag_trend_mom_decline_triggers_amber():
    # Single 10% decline > 8% threshold
    result = rag_trend("waste_seg_accuracy", [90.0, 81.0])
    assert result == "amber"


def test_rag_trend_insufficient_data():
    result = rag_trend("waste_seg_accuracy", [90.0])
    assert result is None


def test_rag_trend_lower_better_metric():
    # For lower_better metric, consecutive *increases* = declines
    result = rag_trend("carbon_per_visit", [4.0, 5.0, 6.0, 7.0])
    assert result == "red"


# ---------------------------------------------------------------------------
# get_rag_status – combined
# ---------------------------------------------------------------------------

def test_get_rag_status_trend_escalates():
    # Static = amber (92%), but 3 consecutive declines → escalate to red
    status = get_rag_status(
        "waste_seg_accuracy", 92.0,
        history=[98.0, 96.0, 94.0, 92.0]
    )
    assert status == "red"


def test_get_rag_status_no_history():
    status = get_rag_status("waste_seg_accuracy", 98.0)
    assert status == "green"


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------

def test_generate_recommendations_red_fires():
    kpi = {"waste_seg_accuracy": 75.0}  # < amber threshold of 90 → red
    recs = generate_recommendations(kpi)
    assert any(r["metric"] == "waste_seg_accuracy" for r in recs)


def test_generate_recommendations_green_does_not_fire():
    kpi = {"waste_seg_accuracy": 98.0}  # clearly green
    recs = generate_recommendations(kpi)
    assert not any(r["metric"] == "waste_seg_accuracy" for r in recs)


def test_generate_recommendations_structure():
    kpi = {"audit_pass_rate": 60.0}  # below amber=80 → red
    recs = generate_recommendations(kpi)
    for rec in recs:
        assert "observation" in rec
        assert "drivers" in rec
        assert "actions" in rec
        assert "projected_outcome" in rec
        assert "rag_status" in rec
        assert "metric" in rec


def test_generate_recommendations_empty_kpi():
    recs = generate_recommendations({})
    assert recs == []


def test_generate_recommendations_no_duplicate_metrics():
    kpi = {
        "waste_seg_accuracy": 75.0,  # red
        "carbon_per_visit": 15.0,    # red
        "staff_turnover_rate": 40.0, # red
    }
    recs = generate_recommendations(kpi)
    metrics = [r["metric"] for r in recs]
    assert len(metrics) == len(set(metrics))
