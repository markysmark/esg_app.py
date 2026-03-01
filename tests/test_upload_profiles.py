import os
import json
import tempfile
import pytest
from data_upload import load_mapping_profiles, save_mapping_profiles, PROFILE_FILE


def test_profile_persistence(tmp_path, monkeypatch):
    # use temporary directory to avoid clobbering real file
    monkeypatch.chdir(tmp_path)
    # ensure no file exists
    assert not os.path.exists(PROFILE_FILE)

    profiles = load_mapping_profiles()
    assert profiles == {}

    profiles['foo'] = {'building': 'A', 'waste_tonnes': 'W'}
    save_mapping_profiles(profiles)

    assert os.path.exists(PROFILE_FILE)
    # read directly
    with open(PROFILE_FILE, 'r') as f:
        data = json.load(f)
    assert 'foo' in data
    assert data['foo']['building'] == 'A'

    # loading again should return same
    loaded = load_mapping_profiles()
    assert loaded == profiles

    # corrupt file should not raise
    with open(PROFILE_FILE, 'w') as f:
        f.write("notjson")
    assert load_mapping_profiles() == {}

