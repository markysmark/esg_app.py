from main_app import compute_esg_scores, ESGEntry


def test_compute_esg_scores_basic():
    # a moderate entry should return mid-to-high scores
    entry = ESGEntry()
    entry.waste_tonnes = 2.0
    entry.energy_kwh = 5000.0
    entry.employee_count = 25
    entry.hours_worked = 2000.0
    entry.eco_chem_pct = 85.0

    e, s, g, overall = compute_esg_scores(entry)
    # scores should lie within the normal range
    assert 0.0 <= e <= 100.0
    assert 0.0 <= s <= 100.0
    assert 0.0 <= g <= 100.0
    assert 0.0 <= overall <= 100.0


def test_compute_esg_scores_comparison():
    # higher waste or energy should reduce E score
    low = ESGEntry(waste_tonnes=1, energy_kwh=1000, employee_count=10, hours_worked=500, eco_chem_pct=90)
    high = ESGEntry(waste_tonnes=10, energy_kwh=15000, employee_count=10, hours_worked=500, eco_chem_pct=90)
    e_low, *_ = compute_esg_scores(low)
    e_high, *_ = compute_esg_scores(high)
    assert e_low > e_high


def test_compute_esg_scores_evidence_bonus():
    # create two entries with identical metrics but different evidence counts
    entry = ESGEntry(waste_tonnes=0, energy_kwh=0, employee_count=5, hours_worked=200, eco_chem_pct=50, building='Foo')
    # remove any existing evidence for 'Foo'
    from main_app import EvidenceRegister, session
    session.query(EvidenceRegister).filter(EvidenceRegister.building=='Foo').delete()
    session.commit()
    # score without evidence
    e1, s1, g1, o1 = compute_esg_scores(entry)
    # add two evidence records
    session.add_all([
        EvidenceRegister(building='Foo', item_type='doc', reference='x'),
        EvidenceRegister(building='Foo', item_type='doc', reference='y')
    ])
    session.commit()
    e2, s2, g2, o2 = compute_esg_scores(entry)
    assert g2 > g1


def test_compute_esg_scores_no_data():
    e, s, g, overall = compute_esg_scores(None)
    assert e == 0.0 and s == 0.0 and g == 0.0 and overall == 0.0
