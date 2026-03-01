from datetime import datetime, timedelta
from main_app import (
    grade_data_quality, log_action, session,
    ESGEntry, EvidenceRegister, ActionLog
)


def test_grade_data_quality_empty():
    result = grade_data_quality("NoClient")
    assert result["grade"] == "F"
    assert result["current_data_pct"] == 0
    assert result["avg_confidence"] == 0.0

    # overall portfolio grade should not error when called with None
    portfolio = grade_data_quality(None)
    assert "grade" in portfolio


def test_grade_data_quality_with_data():
    # insert a dummy entry and evidence
    e = ESGEntry(
        client="C1", agent="A1", building="B1",
        waste_tonnes=1, energy_kwh=100, chem_litres=10,
        eco_chem_pct=50, employee_count=10, hours_worked=1000
    )
    session.add(e)
    session.commit()
    session.add(EvidenceRegister(building="B1", item_type="doc", reference="r1"))
    session.commit()

    result = grade_data_quality("C1", agent="A1", building="B1")
    assert 0 <= result["current_data_pct"] <= 100
    assert result["obligations_with_evidence_pct"] >= 20
    assert 0.0 <= result["avg_confidence"] <= 1.0
    # simulate a perfect fresh record
    session.query(ESGEntry).delete()
    session.add(ESGEntry(client="C1", agent="A1", building="B1",
                         waste_tonnes=0, energy_kwh=0, chem_litres=1,
                         eco_chem_pct=100, employee_count=10, hours_worked=400,
                         timestamp=datetime.utcnow()))
    session.add(EvidenceRegister(building="B1", item_type="doc", reference="r2"))
    session.commit()
    res2 = grade_data_quality("C1", agent="A1", building="B1")
    # with more complete recent data the grade should at least improve above an F
    assert res2["grade"] in ("A","B","C")

    # cleanup
    session.query(ESGEntry).filter(ESGEntry.building == "B1").delete()
    session.query(EvidenceRegister).filter(EvidenceRegister.building == "B1").delete()
    session.commit()


def test_log_action():
    before = session.query(ActionLog).count()
    log_action("B1", "tester", "did something")
    after = session.query(ActionLog).count()
    assert after == before + 1
