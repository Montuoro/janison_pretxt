"""Parse CSV/Excel files into a standardised item DataFrame."""

import io
import base64
import pandas as pd

REQUIRED_COLS = {"item_id", "stem", "correct_answer"}
OPTIONAL_COLS = {"option_a", "option_b", "option_c", "option_d", "max_score", "item_type"}


def parse_upload(contents: str, filename: str) -> tuple[pd.DataFrame | None, str | None]:
    """Parse uploaded file contents into a DataFrame.

    Args:
        contents: base64 data URI from dcc.Upload.
        filename: original filename.

    Returns:
        (DataFrame, None) on success, (None, error_message) on failure.
    """
    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
    except Exception:
        return None, "Could not decode file."

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None, "Unsupported file type. Please upload CSV or Excel."
    except Exception as e:
        return None, f"Error reading file: {e}"

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        return None, f"Missing required columns: {', '.join(sorted(missing))}"

    if len(df) < 3:
        return None, "Need at least 3 items."

    # Fill optional columns
    for col in OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = ""

    # Ensure item_id is string
    df["item_id"] = df["item_id"].astype(str)

    # Default max_score
    df["max_score"] = pd.to_numeric(df["max_score"], errors="coerce").fillna(1).astype(int)

    return df, None


def load_sample_items() -> pd.DataFrame:
    """Load the built-in NAPLAN sample items."""
    import os, sys
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), "..")
    sample_path = os.path.join(base, "naplan_example", "sample_items.csv")
    return pd.read_csv(sample_path)
