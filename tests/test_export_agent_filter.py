"""Tests for agent-based building filter in export_report.py."""

from datetime import datetime
from main_app import ESGEntry, session
from export_report import get_esg_data_for_export


def _add_entry(client, agent, building):
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
        timestamp=datetime.utcnow(),
    )
    session.add(entry)
    session.commit()
    return entry


def test_get_esg_data_filtered_by_agent():
    """Filtering by agent returns only that agent's buildings."""
    # Insert two agents managing different buildings
    e1 = _add_entry("ClientA", "AgentX", "Building Alpha")
    e2 = _add_entry("ClientA", "AgentY", "Building Beta")

    try:
        df = get_esg_data_for_export(agent="AgentX")
        assert "Building Alpha" in df["Building"].values
        assert "Building Beta" not in df["Building"].values
    finally:
        session.delete(e1)
        session.delete(e2)
        session.commit()


def test_get_esg_data_agent_all_buildings():
    """Filtering by agent with no building filter returns all their buildings."""
    e1 = _add_entry("ClientB", "AgentZ", "Building One")
    e2 = _add_entry("ClientB", "AgentZ", "Building Two")

    try:
        df = get_esg_data_for_export(agent="AgentZ")
        buildings = set(df["Building"].values)
        assert "Building One" in buildings
        assert "Building Two" in buildings
    finally:
        session.delete(e1)
        session.delete(e2)
        session.commit()


def test_get_esg_data_agent_specific_building():
    """Filtering by agent and specific building returns only that building."""
    e1 = _add_entry("ClientC", "AgentW", "Site North")
    e2 = _add_entry("ClientC", "AgentW", "Site South")

    try:
        df = get_esg_data_for_export(agent="AgentW", building="Site North")
        assert len(df) >= 1
        assert all(df["Building"] == "Site North")
    finally:
        session.delete(e1)
        session.delete(e2)
        session.commit()
