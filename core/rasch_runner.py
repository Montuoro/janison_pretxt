"""R subprocess: write CSV, call Rscript, read JSON."""

import json
import os
import subprocess
import tempfile
import pandas as pd


def find_rscript() -> str:
    """Find Rscript.exe on Windows."""
    # Try common paths
    candidates = [
        r"C:\Program Files\R\R-4.4.2\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.3.3\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.4.1\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.4.0\bin\Rscript.exe",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p

    # Try PATH
    try:
        result = subprocess.run(["where", "Rscript"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass

    # Search Program Files
    r_base = r"C:\Program Files\R"
    if os.path.isdir(r_base):
        versions = sorted(os.listdir(r_base), reverse=True)
        for v in versions:
            candidate = os.path.join(r_base, v, "bin", "Rscript.exe")
            if os.path.isfile(candidate):
                return candidate

    raise FileNotFoundError("Cannot find Rscript.exe. Please ensure R is installed.")


def run_tam_analysis(response_matrix: pd.DataFrame, item_ids: list[str] = None,
                     output_dir: str = None) -> dict:
    """Run TAM Rasch analysis via R subprocess.

    Args:
        response_matrix: DataFrame of 0/1 responses (persons x items).
        item_ids: optional item ID labels.
        output_dir: directory for temp files (default: system temp).

    Returns:
        dict with TAM results (item params, fit stats, person params, reliability).
    """
    import sys
    rscript = find_rscript()
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), "..")
    r_script_path = os.path.join(base, "r_scripts", "run_tam.R")
    r_script_path = os.path.abspath(r_script_path)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="pretxt_tam_")

    # Write response CSV
    input_csv = os.path.join(output_dir, "responses.csv")
    df = response_matrix.copy()
    if item_ids:
        df.columns = item_ids
    else:
        df.columns = [f"item_{i+1}" for i in range(df.shape[1])]
    df.to_csv(input_csv, index=False)

    # Run R
    result = subprocess.run(
        [rscript, r_script_path, input_csv, output_dir],
        capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"R script failed:\nSTDERR: {result.stderr}\nSTDOUT: {result.stdout}")

    # Read results
    output_json = os.path.join(output_dir, "tam_results.json")
    if not os.path.isfile(output_json):
        raise FileNotFoundError(f"TAM output not found at {output_json}.\nR stdout: {result.stdout}\nR stderr: {result.stderr}")

    with open(output_json, "r") as f:
        tam_results = json.load(f)

    return tam_results
