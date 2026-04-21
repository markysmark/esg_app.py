import os
from main_app import EvidenceRegister, session, _utcnow


def test_evidence_register_create_and_query():
    # create a fake record
    now = _utcnow()
    ref = os.path.join('evidence', f'test_{now.strftime("%Y%m%dT%H%M%S")}.txt')
    os.makedirs('evidence', exist_ok=True)
    with open(ref, 'w') as f:
        f.write('test')

    er = EvidenceRegister(building='Test Building', item_type='text/plain', reference=ref)
    session.add(er)
    session.commit()

    fetched = session.query(EvidenceRegister).filter(EvidenceRegister.building == 'Test Building').order_by(EvidenceRegister.uploaded_at.desc()).first()
    assert fetched is not None
    assert os.path.exists(fetched.reference)

    # cleanup record
    session.delete(fetched)
    session.commit()
    try:
        os.remove(ref)
    except Exception:
        pass
