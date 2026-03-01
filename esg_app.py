"""Entrypoint compatibility shim for the ESG application.

The original codebase defines the main application in `main_app.py`, but various
configuration files (DevContainer, Quickstart, etc.) reference `esg_app.py` as the
module to run.  This stub simply forwards execution to the real application so that
those workflows continue working without requiring large-scale renaming or imports
throughout the codebase.

When executed by Streamlit (e.g. `streamlit run esg_app.py`), this module imports
and invokes `main()` from `main_app.py`.
"""

from main_app import main


if __name__ == "__main__":
    main()
