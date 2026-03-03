# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PreTxT."""

import os
import importlib

block_cipher = None

# Locate packages that carry static/JS assets Dash needs at runtime
def pkg_dir(name):
    return os.path.dirname(importlib.import_module(name).__file__)

dash_dir = pkg_dir("dash")
dcc_dir = pkg_dir("dash.dcc")
html_dir = pkg_dir("dash.html")
dt_dir = pkg_dir("dash.dash_table")
dbc_dir = pkg_dir("dash_bootstrap_components")
plotly_dir = pkg_dir("plotly")

datas = [
    # Dash renderer + core component bundles
    (os.path.join(dash_dir, "dash-renderer"), "dash/dash-renderer"),
    (os.path.join(dash_dir, "deps"), "dash/deps"),
    (dcc_dir, "dash/dcc"),
    (html_dir, "dash/html"),
    (dt_dir, "dash/dash_table"),
    (dbc_dir, "dash_bootstrap_components"),
    # Plotly.js bundle
    (os.path.join(plotly_dir, "package_data"), "plotly/package_data"),
    # Our own assets and data
    ("assets", "assets"),
    ("r_scripts", "r_scripts"),
    ("naplan_example", "naplan_example"),
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "dash",
        "dash.dcc",
        "dash.html",
        "dash.dash_table",
        "dash_bootstrap_components",
        "plotly",
        "pandas",
        "numpy",
        "scipy",
        "scipy.interpolate",
        "scipy.integrate",
        "scipy.ndimage",
        "choix",
        "anthropic",
        "openpyxl",
        "xlrd",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "IPython", "notebook", "pytest",
        "torch", "torchvision", "torchaudio",
        "sklearn", "scikit-learn",
        "cv2", "opencv-python",
        "transformers", "huggingface_hub",
        "nltk", "statsmodels", "altair",
        "sqlalchemy", "zmq", "pyzmq",
        "lxml", "kaleido", "pyarrow",
        "PIL", "Pillow",
        "tensorflow", "keras",
        "pygments",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                   # not one-file — speeds up launch and avoids temp extraction
    exclude_binaries=True,
    name="PreTxT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # keep console so user sees the URL to open
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PreTxT",
)
