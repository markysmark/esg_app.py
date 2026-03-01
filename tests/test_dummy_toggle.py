from main_app import (
    is_dummy_enabled, set_dummy_enabled, load_dummy_entries, session, ESGEntry, DUMMY_FILE
)
import os

def setup_module(module):
    # ensure toggle file removed
    if os.path.exists(DUMMY_FILE):
        os.remove(DUMMY_FILE)


def teardown_module(module):
    # cleanup any dummy entries created and remove toggle file
    session.query(ESGEntry).filter(ESGEntry.client.like('TestClient%')).delete()
    session.commit()
    if os.path.exists(DUMMY_FILE):
        os.remove(DUMMY_FILE)


def test_toggle_file_roundtrip():
    assert not is_dummy_enabled()
    set_dummy_enabled(True)
    assert is_dummy_enabled()
    set_dummy_enabled(False)
    assert not is_dummy_enabled()


def test_loading_dummy_entries():
    # ensure toggle logic doesn't prevent direct call
    before = session.query(ESGEntry).count()
    load_dummy_entries(client="TestClient", agent="TestAgent", count=3)
    after = session.query(ESGEntry).count()
    assert after == before + 3
    # verify entries have the expected agent label
    entries = session.query(ESGEntry).filter(ESGEntry.agent == "TestAgent").all()
    assert len(entries) >= 3
    # toggle should auto-disable after loading
    assert not is_dummy_enabled()

