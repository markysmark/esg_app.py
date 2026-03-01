# tests/conftest.py
# Ensure the project root is on sys.path so tests can import modules such as
# `main_app` even if pytest changes the working directory during collection.

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
