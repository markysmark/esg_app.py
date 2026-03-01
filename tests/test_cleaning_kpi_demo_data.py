"""Tests for CleaningKPI demo data seeded by load_savills_demo_data and load_test_client_data."""

from main_app import (
    load_savills_demo_data,
    clear_savills_demo_data,
    load_test_client_data,
    clear_test_client_data,
    CleaningKPI,
    ESGEntry,
    session,
)
from service_lines import compute_contribution_score, get_rag_status, CLEANING_KPI_FIELDS


_SAVILLS_BUILDINGS = [
    'The Leadenhall Building',
    'Broadgate Tower',
    'Centre Point',
    'St Pauls House',
]

_TEST_CLIENT_BUILDINGS = [
    'Tech Hub Downtown',
    'Innovation Plaza',
    'Green Heights Tower',
    'Commerce Center East',
    'Sustainable Park West',
    'Executive Plaza South',
    'Urban Living Complex',
    'Corporate Crown',
]

_HEADLINE_METRICS = ['waste_seg_accuracy', 'carbon_per_visit', 'audit_pass_rate', 'sla_adherence']


def teardown_module(module):
    for building in _SAVILLS_BUILDINGS + _TEST_CLIENT_BUILDINGS:
        session.query(CleaningKPI).filter(CleaningKPI.building == building).delete()
    session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').delete()
    session.query(ESGEntry).filter(ESGEntry.client == 'Test Client').delete()
    session.commit()


# ---------------------------------------------------------------------------
# Savills CleaningKPI demo data
# ---------------------------------------------------------------------------

def test_load_savills_demo_data_creates_cleaning_kpis():
    """Each Savills building should have a CleaningKPI record after loading demo data."""
    for building in _SAVILLS_BUILDINGS:
        session.query(CleaningKPI).filter(CleaningKPI.building == building).delete()
    session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').delete()
    session.commit()

    load_savills_demo_data()

    for building in _SAVILLS_BUILDINGS:
        kpi = session.query(CleaningKPI).filter(CleaningKPI.building == building).first()
        assert kpi is not None, f"Expected CleaningKPI record for {building}"


def test_savills_cleaning_kpi_shows_good_performance():
    """Savills buildings' CleaningKPI headline metrics should all be green."""
    for building in _SAVILLS_BUILDINGS:
        kpi = session.query(CleaningKPI).filter(CleaningKPI.building == building).first()
        assert kpi is not None
        for metric in _HEADLINE_METRICS:
            value = float(getattr(kpi, metric, 0.0) or 0.0)
            status = get_rag_status(metric, value)
            assert status == 'green', (
                f"{building} metric '{metric}' = {value} expected green, got {status}"
            )


def test_savills_cleaning_contribution_score_is_high():
    """Contribution scores for Savills buildings should be well above 70."""
    for building in _SAVILLS_BUILDINGS:
        kpi = session.query(CleaningKPI).filter(CleaningKPI.building == building).first()
        assert kpi is not None
        kpi_dict = {f: float(getattr(kpi, f, 0.0) or 0.0) for f in CLEANING_KPI_FIELDS}
        score = compute_contribution_score(kpi_dict)
        assert score >= 70.0, f"{building} contribution score {score} is below 70"


def test_clear_savills_demo_data_removes_cleaning_kpis():
    """clear_savills_demo_data should also remove CleaningKPI records."""
    clear_savills_demo_data()
    for building in _SAVILLS_BUILDINGS:
        count = session.query(CleaningKPI).filter(CleaningKPI.building == building).count()
        assert count == 0, f"Expected CleaningKPI records for {building} to be cleared"


# ---------------------------------------------------------------------------
# Test Client CleaningKPI demo data
# ---------------------------------------------------------------------------

def test_load_test_client_data_creates_cleaning_kpis():
    """Each Test Client building should have a CleaningKPI record after loading demo data."""
    for building in _TEST_CLIENT_BUILDINGS:
        session.query(CleaningKPI).filter(CleaningKPI.building == building).delete()
    session.query(ESGEntry).filter(ESGEntry.client == 'Test Client').delete()
    session.commit()

    load_test_client_data()

    for building in _TEST_CLIENT_BUILDINGS:
        kpi = session.query(CleaningKPI).filter(CleaningKPI.building == building).first()
        assert kpi is not None, f"Expected CleaningKPI record for {building}"


def test_test_client_cleaning_kpi_shows_good_performance():
    """Test Client buildings' CleaningKPI headline metrics should all be green."""
    for building in _TEST_CLIENT_BUILDINGS:
        kpi = session.query(CleaningKPI).filter(CleaningKPI.building == building).first()
        assert kpi is not None
        for metric in _HEADLINE_METRICS:
            value = float(getattr(kpi, metric, 0.0) or 0.0)
            status = get_rag_status(metric, value)
            assert status == 'green', (
                f"{building} metric '{metric}' = {value} expected green, got {status}"
            )


def test_load_test_client_data_idempotent_cleaning_kpis():
    """Calling load again should not add duplicate CleaningKPI records."""
    count_before = {b: session.query(CleaningKPI).filter(CleaningKPI.building == b).count()
                    for b in _TEST_CLIENT_BUILDINGS}
    load_test_client_data()
    count_after = {b: session.query(CleaningKPI).filter(CleaningKPI.building == b).count()
                   for b in _TEST_CLIENT_BUILDINGS}
    for building in _TEST_CLIENT_BUILDINGS:
        assert count_after[building] == count_before[building], (
            f"Duplicate CleaningKPI records created for {building}"
        )


def test_clear_test_client_data_removes_cleaning_kpis():
    """clear_test_client_data should also remove CleaningKPI records."""
    clear_test_client_data()
    for building in _TEST_CLIENT_BUILDINGS:
        count = session.query(CleaningKPI).filter(CleaningKPI.building == building).count()
        assert count == 0, f"Expected CleaningKPI records for {building} to be cleared"
