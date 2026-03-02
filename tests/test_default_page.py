"""Tests to verify the app's default landing page is 'Home' on startup."""

import importlib
import sys


def test_module_level_default_page_is_home():
    """The module-level session-state initialisation must default to 'Home'.

    When main_app is first imported (before main() is called), the module-level
    code sets current_page in st.session_state.  That value must be 'Home' so
    that the user lands on the welcoming Home page rather than the empty
    Dashboard page on first launch.
    """
    # Re-import main_app with a fresh session_state so we can see what value
    # the module-level code would write.
    import streamlit as st

    # Patch session_state to capture what is written
    written = {}

    class FakeSessionState:
        def __contains__(self, key):
            return key in written

        def __setattr__(self, key, value):
            written[key] = value

        def __getattr__(self, key):
            return written.get(key)

    original_ss = st.session_state
    try:
        st.session_state = FakeSessionState()

        # Remove cached module so its top-level code re-executes
        sys.modules.pop('main_app', None)
        import main_app  # noqa: F401

        assert written.get('current_page') == 'Home', (
            f"Expected default current_page to be 'Home', got {written.get('current_page')!r}"
        )
    finally:
        st.session_state = original_ss
        # Remove the freshly-imported module so subsequent tests get a clean import
        sys.modules.pop('main_app', None)
