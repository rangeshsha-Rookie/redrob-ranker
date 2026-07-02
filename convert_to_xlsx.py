"""
convert_to_xlsx.py
------------------
Converts submission.csv to submission.xlsx for upload.

Usage:
    python convert_to_xlsx.py

Outputs submission.xlsx in the same folder as this script.
"""
import os
import sys

try:
    import pandas as pd
except ImportError:
    print("pandas not found. Run: pip install pandas openpyxl")
    sys.exit(1)

script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path   = os.path.join(script_dir, "submission.csv")
xlsx_path  = os.path.join(script_dir, "submission.xlsx")

if not os.path.exists(csv_path):
    print(f"ERROR: {csv_path} not found. Run rank.py first.")
    sys.exit(1)

df = pd.read_csv(csv_path)
df.to_excel(xlsx_path, index=False)
print(f"Done! submission.xlsx saved to:\n{xlsx_path}")
