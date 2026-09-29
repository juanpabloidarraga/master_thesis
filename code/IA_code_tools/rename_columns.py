#!/usr/bin/env python3
"""
Rename Columns in Catalog CSV Files
created by Antigravity (google)
====================================
This script renames the columns of a combined catalog CSV file such that:
  - All columns before `sobject_id` receive the suffix `_w` (Willet catalog).
  - The column `sobject_id` and all columns after it receive the suffix `_g` (GALAH catalog).

How to specify / modify the file to process:
-------------------------------------------
1. IN THIS SCRIPT:
   Simply change the `INPUT_FILE` (and optionally `OUTPUT_FILE`) variable below
   in the CONFIGURATION section.

2. FROM THE COMMAND LINE:
   Run with no arguments to use the defaults below:
       python code/rename_columns.py

   Or pass an input file:
       python code/rename_columns.py data/combine_catalogs/another_file.csv

   Or pass both input and output files (to keep the original file unchanged):
       python code/rename_columns.py input.csv output.csv

3. IN JUPYTER NOTEBOOKS OR PYTHON CODE:
       from rename_columns import rename_csv_file, rename_dataframe
       rename_csv_file("path/to/file.csv")
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

# ==============================================================================
# CONFIGURATION
# Modify these variables directly to change default files or parameters.
# ==============================================================================

# Input file path:
# You can change this to any file path (relative to repo root, code/, or absolute).
INPUT_FILE = "data/combine_catalogs/K2_GALAH_GALAH.csv"

# Output file path:
# - Set to None to update the INPUT_FILE in-place (safe & atomic).
# - Or set to a path (e.g., "data/combine_catalogs/K2_GALAH_GALAH_renamed.csv")
#   to save the result to a new file and keep the original file untouched.
OUTPUT_FILE = None

# Suffix rules:
PIVOT_COLUMN = "sobject_id"  # The pivot column separating the two catalogs
LEFT_SUFFIX = "_w"           # Suffix for columns before the pivot column (Willet)
RIGHT_SUFFIX = "_g"          # Suffix for the pivot column and columns after (GALAH)

# Create a backup (.bak) of the original file when modifying in-place:
CREATE_BACKUP = True

# ==============================================================================


def resolve_path(path_input: str | Path | None, base_dirs: list[Path] | None = None) -> Path | None:
    """
    Resolves a file path that may be relative to cwd, repo root, or the script folder,
    and tolerates common folder name typos (e.g. combine_catalog vs combine_catalogs).
    """
    if path_input is None:
        return None

    p = Path(path_input)
    if p.is_absolute():
        return p

    if base_dirs is None:
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        cwd = Path.cwd()
        base_dirs = [cwd, repo_root, script_dir]

    # Generate candidate variations for folder name differences
    path_variants = [p]
    str_p = str(p)
    if "combine_catalog/" in str_p and "combine_catalogs/" not in str_p:
        path_variants.append(Path(str_p.replace("combine_catalog/", "combine_catalogs/")))
    elif "combine_catalogs/" in str_p:
        path_variants.append(Path(str_p.replace("combine_catalogs/", "combine_catalog/")))

    for variant in path_variants:
        for base in base_dirs:
            candidate = (base / variant).resolve()
            if candidate.exists():
                return candidate

    # If file doesn't exist yet (e.g., for an output file), resolve relative to repo root or cwd
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / p).resolve()


def rename_column_names(
    columns: list[str],
    pivot_col: str = PIVOT_COLUMN,
    left_suffix: str = LEFT_SUFFIX,
    right_suffix: str = RIGHT_SUFFIX,
) -> tuple[list[str], int]:
    """
    Computes new column names:
      - Suffix `left_suffix` for columns before `pivot_col`.
      - Suffix `right_suffix` for `pivot_col` and columns after `pivot_col`.

    Returns:
      (new_columns, pivot_index)
    """
    if pivot_col not in columns:
        # Check if already renamed
        already_renamed_col = f"{pivot_col}{right_suffix}"
        if already_renamed_col in columns:
            raise ValueError(
                f"Pivot column '{pivot_col}' was not found, but '{already_renamed_col}' is already present. "
                "This file's columns appear to have already been renamed!"
            )
        raise ValueError(
            f"Pivot column '{pivot_col}' not found in the CSV header.\n"
            f"Total columns: {len(columns)}.\n"
            f"First 10 columns: {columns[:10]}"
        )

    pivot_idx = columns.index(pivot_col)
    new_columns = []
    for i, col in enumerate(columns):
        if i < pivot_idx:
            new_columns.append(f"{col}{left_suffix}")
        else:
            new_columns.append(f"{col}{right_suffix}")

    return new_columns, pivot_idx


def rename_csv_file(
    input_file: str | Path,
    output_file: str | Path | None = None,
    pivot_col: str = PIVOT_COLUMN,
    left_suffix: str = LEFT_SUFFIX,
    right_suffix: str = RIGHT_SUFFIX,
    create_backup: bool = CREATE_BACKUP,
) -> Path:
    """
    Reads `input_file`, renames columns in the header, and writes to `output_file`
    (or modifies `input_file` in place if `output_file` is None).

    Uses fast streaming: only the header line is modified, all data rows are streamed
    byte-by-byte without unneeded memory consumption or floating-point precision changes.
    """
    input_path = resolve_path(input_file)
    if input_path is None or not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file} (resolved to {input_path})")

    is_inplace = (output_file is None) or (resolve_path(output_file) == input_path)
    output_path = input_path if is_inplace else resolve_path(output_file)
    if output_path is None:
        output_path = input_path

    # Ensure parent output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use a temporary file in the same directory for atomic write
    temp_dir = output_path.parent
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=temp_dir,
        delete=False,
    )
    temp_path = Path(temp_file.name)

    try:
        with open(input_path, "r", newline="", encoding="utf-8") as f_in:
            reader = csv.reader(f_in)
            try:
                original_header = next(reader)
            except StopIteration:
                raise ValueError(f"Input file is empty: {input_path}")

            new_header, pivot_idx = rename_column_names(
                original_header,
                pivot_col=pivot_col,
                left_suffix=left_suffix,
                right_suffix=right_suffix,
            )

            writer = csv.writer(temp_file, lineterminator="\n")
            writer.writerow(new_header)
            temp_file.flush()

            # Fast stream copy of all data rows
            shutil.copyfileobj(f_in, temp_file)

        temp_file.close()

        # Handle backup if in-place update
        if is_inplace and create_backup:
            backup_path = input_path.with_name(f"{input_path.name}.bak")
            shutil.copy2(input_path, backup_path)
            print(f"📦 Backup created: {backup_path}")

        # Atomically replace or move into place
        os.replace(temp_path, output_path)

    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise

    left_count = pivot_idx
    right_count = len(new_header) - pivot_idx

    print(f"✅ Success! Renamed columns in {input_path.name}")
    print(f"   • Destination: {output_path}")
    print(f"   • Columns with '{left_suffix}' (before {pivot_col}): {left_count}")
    print(f"   • Columns with '{right_suffix}' (from {pivot_col} onward): {right_count}")
    print(f"   • Total columns: {len(new_header)}")
    print(f"   • First 3 renamed cols: {new_header[:3]}")
    print(f"   • Pivot column renamed: {new_header[pivot_idx]}")
    print(f"   • Last 3 renamed cols:  {new_header[-3:]}")

    return output_path


def rename_dataframe(
    df,
    pivot_col: str = PIVOT_COLUMN,
    left_suffix: str = LEFT_SUFFIX,
    right_suffix: str = RIGHT_SUFFIX,
):
    """
    Helper function to rename columns of a pandas DataFrame.
    Can be imported directly into notebooks or scripts:
        from rename_columns import rename_dataframe
        df_renamed = rename_dataframe(df)
    """
    cols = list(df.columns)
    new_cols, _ = rename_column_names(
        cols,
        pivot_col=pivot_col,
        left_suffix=left_suffix,
        right_suffix=right_suffix,
    )
    return df.rename(columns=dict(zip(cols, new_cols)))


def main():
    parser = argparse.ArgumentParser(
        description="Rename CSV columns with suffixes before and after a pivot column.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults from the CONFIGURATION section at the top of the script:
  python code/rename_columns.py

  # Process a different input file in-place:
  python code/rename_columns.py path/to/another_catalog.csv

  # Process a file and save to a new output file:
  python code/rename_columns.py path/to/input.csv path/to/output.csv

  # Specify a custom pivot column or suffixes:
  python code/rename_columns.py input.csv output.csv --pivot sobject_id --left-suffix _w --right-suffix _g
""",
    )

    parser.add_argument(
        "input",
        nargs="?",
        default=INPUT_FILE,
        help=f"Path to input CSV file. (Default from script config: '{INPUT_FILE}')",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=OUTPUT_FILE,
        help="Path to output CSV file. (If omitted or None, updates input file in-place).",
    )
    parser.add_argument(
        "-p", "--pivot",
        default=PIVOT_COLUMN,
        help=f"Pivot column name. (Default: '{PIVOT_COLUMN}')",
    )
    parser.add_argument(
        "--left-suffix",
        default=LEFT_SUFFIX,
        help=f"Suffix for columns before pivot. (Default: '{LEFT_SUFFIX}')",
    )
    parser.add_argument(
        "--right-suffix",
        default=RIGHT_SUFFIX,
        help=f"Suffix for pivot column and columns after it. (Default: '{RIGHT_SUFFIX}')",
    )
    parser.add_argument(
        "--backup",
        dest="backup",
        action="store_true",
        default=CREATE_BACKUP,
        help="Create a backup (.bak) of the original file when modifying in-place (default: enabled).",
    )
    parser.add_argument(
        "--no-backup",
        dest="backup",
        action="store_false",
        help="Do not create a backup when modifying in-place.",
    )

    args = parser.parse_args()

    start_time = time.time()
    try:
        rename_csv_file(
            input_file=args.input,
            output_file=args.output,
            pivot_col=args.pivot,
            left_suffix=args.left_suffix,
            right_suffix=args.right_suffix,
            create_backup=args.backup,
        )
    except (ValueError, FileNotFoundError) as err:
        print(f"❌ Error: {err}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"⏱️ Finished in {elapsed:.3f} seconds.")


if __name__ == "__main__":
    main()
