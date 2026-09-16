import os
import sys

# Ensure the project root (the directory containing ``src/``) is importable so
# tests can use ``from src...`` regardless of the invocation directory.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
