"""Tests for load_savills_demo_data historical data generation."""

from datetime import datetime
from main_app import load_savills_demo_data, clear_savills_demo_data, ESGEntry, session


def teardown_module(module):
    session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').delete()
    session.commit()


def test_load_savills_demo_data_creates_historical_records():
    """Each of the 4 Savills buildings should have 12 monthly records."""
    # Ensure a clean slate
    session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').delete()
    session.commit()

    load_savills_demo_data()

    buildings = ['The Leadenhall Building', 'Broadgate Tower', 'Centre Point', 'St Pauls House']
    for building in buildings:
        count = session.query(ESGEntry).filter(
            ESGEntry.building == building,
            ESGEntry.agent == 'Savills'
        ).count()
        assert count == 12, f"Expected 12 historical records for {building}, got {count}"


def test_load_savills_demo_data_timestamps_span_12_months():
    """The oldest and newest records should be roughly 11 months apart."""
    entries = session.query(ESGEntry).filter(
        ESGEntry.building == 'Centre Point',
        ESGEntry.agent == 'Savills'
    ).order_by(ESGEntry.timestamp).all()

    assert len(entries) == 12
    oldest = entries[0].timestamp
    newest = entries[-1].timestamp
    delta_days = (newest - oldest).days
    assert 325 <= delta_days <= 335, f"Expected ~330 days between oldest and newest, got {delta_days}"


def test_load_savills_demo_data_idempotent():
    """Calling load again should not add duplicate monthly records."""
    count_before = session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').count()
    load_savills_demo_data()
    count_after = session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').count()
    assert count_after == count_before


def test_load_savills_demo_data_trend():
    """Older records should have higher waste than the most recent record."""
    entries = session.query(ESGEntry).filter(
        ESGEntry.building == 'The Leadenhall Building',
        ESGEntry.agent == 'Savills'
    ).order_by(ESGEntry.timestamp).all()

    assert len(entries) == 12
    oldest_waste = entries[0].waste_tonnes
    newest_waste = entries[-1].waste_tonnes
    assert oldest_waste > newest_waste, (
        f"Expected oldest record to have more waste than newest: "
        f"{oldest_waste} vs {newest_waste}"
    )
