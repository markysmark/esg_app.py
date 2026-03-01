import os
import json
import tempfile
import pytest
from data_upload import (
    load_mapping_profiles,
    save_mapping_profiles,
    PROFILE_FILE,
    profile_option_index,
)


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


def test_profile_option_index_returns_correct_indices():
    columns = ["Building", "Waste", "Energy"]
    profile = {"building": "Waste", "missing": "Nope"}

    # Offsets by one because of the leading None choice
    assert profile_option_index(profile, "building", columns) == 2
    # Missing or unknown keys fall back to the default option
    assert profile_option_index(profile, "missing", columns) == 0
    assert profile_option_index({}, "building", columns) == 0
