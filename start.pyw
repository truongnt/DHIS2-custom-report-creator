"""No-console launcher for Auto Report.

A `.pyw` file is opened by Windows with pythonw.exe (no console window), so
double-clicking this (or `pythonw start.pyw`) runs the GUI without a cmd window.
"""
import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))
runpy.run_path(os.path.join(_HERE, "main.py"), run_name="__main__")
