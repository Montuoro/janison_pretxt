"""Build PreTxT .exe with PyInstaller.

Run:  python build_exe.py
"""

import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "pretxt.spec",
    "--noconfirm",
    "--clean",
]

print("Building PreTxT .exe ...")
print(f"Command: {' '.join(cmd)}\n")
subprocess.run(cmd, check=True)

print("\nBuild complete!")
print("  Output: dist/PreTxT/PreTxT.exe")
print("  To run: dist\\PreTxT\\PreTxT.exe")
print("  Then open http://127.0.0.1:8050 in your browser.")
