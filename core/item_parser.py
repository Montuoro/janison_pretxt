"""Parse CSV/Excel files into a standardised item DataFrame."""

import io
import base64
import pandas as pd

REQUIRED_COLS = {"item_id", "stem", "correct_answer"}
OPTIONAL_COLS = {"option_a", "option_b", "option_c", "option_d", "max_score", "item_type"}
OPTION_COLS = ["option_a", "option_b", "option_c", "option_d"]


def parse_upload(contents: str, filename: str) -> tuple[pd.DataFrame | None, str | None]:
    """Parse uploaded file contents into a DataFrame."""
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

    return _clean_items(df), None


def load_sample_items() -> pd.DataFrame:
    """Load the built-in NAPLAN sample items."""
    import os, sys
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), "..")
    sample_path = os.path.join(base, "naplan_example", "sample_items.csv")
    df = pd.read_csv(sample_path)
    return _clean_items(df)


def _clean_items(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise item DataFrame: fill optional cols, detect types, fix SA items."""
    # Fill optional columns
    for col in OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = ""

    # Ensure item_id is string
    df["item_id"] = df["item_id"].astype(str)

    # ── Fix column-shift for SA items ───────────────────────────────────
    # Some CSV layouts have SA rows where the answer ends up in option_d,
    # correct_answer gets max_score ("1"), and max_score gets item_type ("SA").
    # Detect: max_score contains a type string like "SA"/"MC" → row is shifted.
    shifted = (
        df["max_score"].astype(str).str.strip().str.upper().isin(["SA", "MC", "CR"])
        & df["item_type"].isna()
    )
    if shifted.any():
        df.loc[shifted, "item_type"] = df.loc[shifted, "max_score"].astype(str).str.strip().str.upper()
        df.loc[shifted, "max_score"] = df.loc[shifted, "correct_answer"]
        # Move last non-empty option into correct_answer
        for idx in df.index[shifted]:
            for opt in reversed(OPTION_COLS):
                val = df.at[idx, opt]
                if pd.notna(val) and str(val).strip() != "":
                    df.at[idx, "correct_answer"] = val
                    df.at[idx, opt] = ""
                    break

    # Default max_score
    df["max_score"] = pd.to_numeric(df["max_score"], errors="coerce").fillna(1).astype(int)

    # ── Detect and fix item types ────────────────────────────────────────
    opt_filled = df[OPTION_COLS].apply(
        lambda col: col.notna() & (col.astype(str).str.strip() != "")
    )
    n_options_filled = opt_filled.sum(axis=1)

    needs_type = df["item_type"].isna() | (df["item_type"].astype(str).str.strip() == "")
    # Need at least 2 non-empty options to be MC; otherwise SA
    df.loc[needs_type & (n_options_filled >= 2), "item_type"] = "MC"
    df.loc[needs_type & (n_options_filled < 2), "item_type"] = "SA"

    # Normalise item_type to uppercase
    df["item_type"] = df["item_type"].astype(str).str.strip().str.upper()

    # ── Also reclassify explicitly-typed MC items that have < 2 options ──
    mc_mask = df["item_type"] == "MC"
    mc_too_few = mc_mask & (n_options_filled < 2)
    df.loc[mc_too_few, "item_type"] = "SA"

    # ── Fix SA items: extract answer from option column if needed ────────
    sa_mask = df["item_type"] == "SA"
    for idx in df.index[sa_mask]:
        ca = df.at[idx, "correct_answer"]
        # If correct_answer is a letter (A-D) pointing to an option, resolve it
        if pd.notna(ca) and str(ca).strip().upper() in ("A", "B", "C", "D"):
            letter = str(ca).strip().upper()
            opt_col = f"option_{letter.lower()}"
            opt_val = df.at[idx, opt_col]
            if pd.notna(opt_val) and str(opt_val).strip() != "":
                df.at[idx, "correct_answer"] = opt_val

    # Clear option columns for SA items
    for opt in OPTION_COLS:
        df.loc[sa_mask, opt] = ""

    return df
