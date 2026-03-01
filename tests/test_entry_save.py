from main_app import session, ESGEntry


def test_manual_agent_entry():
    # clean up any previous test entries
    session.query(ESGEntry).filter(ESGEntry.client == "TestClient").delete()
    session.commit()

    # simulate saving an entry with a manual agent name
    entry = ESGEntry(client="TestClient", agent="ManualAgent", building="TestBuilding",
                     waste_tonnes=5.0, employee_count=10, hours_worked=100, chem_litres=2.0,
                     eco_chem_pct=50.0, energy_kwh=1000.0)
    session.add(entry)
    session.commit()

    # verify persisted correctly
    fetched = session.query(ESGEntry).filter(ESGEntry.client == "TestClient").all()
    assert len(fetched) == 1
    assert fetched[0].agent == "ManualAgent"

    # cleanup
    session.query(ESGEntry).filter(ESGEntry.client == "TestClient").delete()
    session.commit()
