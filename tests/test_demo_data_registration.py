"""Tests that demo-data load functions register clients/buildings in clients_agents.json."""

import json
import os
import shutil

import pytest

from main_app import (
    load_savills_demo_data,
    load_test_client_data,
    clear_savills_demo_data,
    clear_test_client_data,
    CLIENTS_FILE,
    load_clients_data,
    save_clients_data,
    ESGEntry,
    CleaningKPI,
    session,
)

_BACKUP = CLIENTS_FILE + ".bak"

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


def setup_module(module):
    # Back up the real clients file so tests don't permanently alter it
    if os.path.exists(CLIENTS_FILE):
        shutil.copy(CLIENTS_FILE, _BACKUP)


def teardown_module(module):
    # Restore the original clients file
    if os.path.exists(_BACKUP):
        shutil.move(_BACKUP, CLIENTS_FILE)
    # Clean up any DB rows created during tests
    for building in _SAVILLS_BUILDINGS + _TEST_CLIENT_BUILDINGS:
        session.query(CleaningKPI).filter(CleaningKPI.building == building).delete()
    session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').delete()
    session.query(ESGEntry).filter(ESGEntry.client == 'Test Client').delete()
    session.commit()


# ---------------------------------------------------------------------------
# Savills registration
# ---------------------------------------------------------------------------

def test_load_savills_registers_st_pauls_house():
    """St Pauls House must be added to clients_agents.json after loading Savills data."""
    # Remove St Pauls House from the clients file to simulate a clean state
    data = load_clients_data()
    for client_data in data.values():
        buildings = client_data.get('Buildings', [])
        if 'St Pauls House' in buildings:
            buildings.remove('St Pauls House')
    save_clients_data(data)

    load_savills_demo_data()

    fresh = load_clients_data()
    all_buildings = [b for cd in fresh.values() for b in cd.get('Buildings', [])]
    assert 'St Pauls House' in all_buildings, (
        "St Pauls House should be registered in clients_agents.json after load_savills_demo_data()"
    )


def test_load_savills_registration_is_idempotent():
    """Calling load_savills_demo_data twice must not duplicate buildings."""
    load_savills_demo_data()
    load_savills_demo_data()
    data_after_second_load = load_clients_data()
    for client_data in data_after_second_load.values():
        for building in _SAVILLS_BUILDINGS:
            count = client_data.get('Buildings', []).count(building)
            assert count <= 1, f"Duplicate entry for '{building}' in clients_agents.json"


# ---------------------------------------------------------------------------
# Test Client registration
# ---------------------------------------------------------------------------

def test_load_test_client_registers_client():
    """'Test Client' must appear in clients_agents.json after loading test data."""
    # Remove Test Client entirely from the file
    data = load_clients_data()
    data.pop('Test Client', None)
    save_clients_data(data)

    load_test_client_data()

    fresh = load_clients_data()
    assert 'Test Client' in fresh, (
        "'Test Client' should be registered in clients_agents.json after load_test_client_data()"
    )


def test_load_test_client_registers_all_buildings():
    """All 8 Test Client buildings must appear in clients_agents.json."""
    data = load_clients_data()
    data.pop('Test Client', None)
    save_clients_data(data)

    load_test_client_data()

    fresh = load_clients_data()
    registered = fresh.get('Test Client', {}).get('Buildings', [])
    for building in _TEST_CLIENT_BUILDINGS:
        assert building in registered, (
            f"'{building}' should be in Test Client's buildings after load_test_client_data()"
        )


def test_load_test_client_registers_agents():
    """Agents CBRE, JLL, Knight Frank and Savills must appear for Test Client."""
    data = load_clients_data()
    data.pop('Test Client', None)
    save_clients_data(data)

    load_test_client_data()

    fresh = load_clients_data()
    agents = fresh.get('Test Client', {}).get('Agents', [])
    for expected_agent in ['CBRE', 'JLL', 'Knight Frank', 'Savills']:
        assert expected_agent in agents, (
            f"'{expected_agent}' should be registered as an agent for Test Client"
        )


def test_load_test_client_registration_is_idempotent():
    """Calling load_test_client_data twice must not duplicate entries."""
    load_test_client_data()
    load_test_client_data()
    data = load_clients_data()
    tc = data.get('Test Client', {})
    for building in _TEST_CLIENT_BUILDINGS:
        count = tc.get('Buildings', []).count(building)
        assert count <= 1, f"Duplicate entry for '{building}' in clients_agents.json"
