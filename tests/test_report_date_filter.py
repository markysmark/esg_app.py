"""Tests for date filtering in export_report.get_esg_data_for_export."""

from datetime import date, datetime, timedelta
from main_app import ESGEntry, session
from export_report import get_esg_data_for_export


def _add_entry_at(client, agent, building, ts):
    entry = ESGEntry(
        client=client,
        agent=agent,
        building=building,
        waste_tonnes=5.0,
        energy_kwh=10000.0,
        chem_litres=50.0,
        eco_chem_pct=80.0,
        employee_count=100,
        hours_worked=4000.0,
        timestamp=ts,
    )
    session.add(entry)
    session.commit()
    return entry


def test_historical_record_included_with_default_range():
    """A record from 6 months ago should appear when start_date is 1 year ago."""
    six_months_ago = datetime.now() - timedelta(days=180)
    entry = _add_entry_at("HistClient", "HistAgent", "HistBuilding", six_months_ago)

    try:
        start = date.today() - timedelta(days=365)
        end = date.today()
        df = get_esg_data_for_export(
            client="HistClient",
            start_date=start,
            end_date=end,
        )
        assert len(df) >= 1, "Historical record should be included in a 1-year date range"
        assert "HistBuilding" in df["Building"].values
    finally:
        session.delete(entry)
        session.commit()


def test_end_date_includes_full_day():
    """A record created today with a non-zero time should be included when end_date is today."""
    # Use a time well into the day to simulate a late-day record
    today_with_time = datetime.combine(date.today(), datetime.min.time()).replace(hour=18, minute=30)
    entry = _add_entry_at("TodayClient", "TodayAgent", "TodayBuilding", today_with_time)

    try:
        start = date.today()
        end = date.today()
        df = get_esg_data_for_export(
            client="TodayClient",
            start_date=start,
            end_date=end,
        )
        assert len(df) >= 1, "Record from today (with non-zero time) should be included when end_date is today"
        assert "TodayBuilding" in df["Building"].values
    finally:
        session.delete(entry)
        session.commit()


def test_record_outside_date_range_excluded():
    """A record from 2 years ago should NOT appear when start_date is 1 year ago."""
    two_years_ago = datetime.now() - timedelta(days=730)
    entry = _add_entry_at("OldClient", "OldAgent", "OldBuilding", two_years_ago)

    try:
        start = date.today() - timedelta(days=365)
        end = date.today()
        df = get_esg_data_for_export(
            client="OldClient",
            start_date=start,
            end_date=end,
        )
        assert df.empty or "OldBuilding" not in df["Building"].values, (
            "Record older than 1 year should not appear in a 1-year date range"
        )
    finally:
        session.delete(entry)
        session.commit()
