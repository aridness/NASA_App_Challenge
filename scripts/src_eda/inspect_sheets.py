import glob
import os
import pandas as pd

base_dir = r"C:\Users\Ariele\Desktop\NASA\data"
excel_files = [
    os.path.join(base_dir, "BASS", "BASS test matrix.xlsx"),
    os.path.join(base_dir, "BASS", "BASS Test Matrix 050213.xlsx"),
    os.path.join(base_dir, "BASS-II", "BASS-II Test Matrix by PI Final.xlsx"),
]

for f in excel_files:
    if os.path.exists(f):
        xl = pd.ExcelFile(f)
        print(f"\n=== {os.path.basename(f)} | Sheets: {xl.sheet_names} ===")
        for sheet in xl.sheet_names[:3]:  # Check first 3 sheets
            df = xl.parse(sheet, nrows=5)
            print(f"  [{sheet}] -> {list(df.columns)}")