from __future__ import annotations
import sys

print("Python executable:", sys.executable)
print("Python version:", sys.version)
try:
    import numpy as np
    print("NumPy:", np.__version__, np.__file__)
except Exception as e:
    print("NumPy import error:", repr(e))
try:
    import pandas as pd
    print("Pandas:", pd.__version__, pd.__file__)
except Exception as e:
    print("Pandas import error:", repr(e))
try:
    import streamlit as st
    print("Streamlit:", st.__version__)
except Exception as e:
    print("Streamlit import error:", repr(e))
