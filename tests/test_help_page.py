import io
import builtins
import streamlit as st
from main_app import page_help

def test_page_help_reads_readme(monkeypatch, tmp_path):
    # create a temporary README and point cwd to tmp_path
    sample = "# Hello Help"
    readme_file = tmp_path / "README.md"
    readme_file.write_text(sample, encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    captured = {}
    def fake_markdown(text, **kwargs):
        captured['text'] = text
        captured['kwargs'] = kwargs
    monkeypatch.setattr(st, 'markdown', fake_markdown)

    # call the help page - should not raise and should read our sample
    page_help()
    assert 'text' in captured
    assert sample in captured['text']
    assert captured['kwargs'].get('unsafe_allow_html') is False
