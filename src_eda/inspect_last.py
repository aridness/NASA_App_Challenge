import os
import pandas as pd

base = r"C:\Users\Ariele\Desktop\NASA\data"

# 1. Check remaining columns (12+) of BASS 'as run matrix'
bass_xl = os.path.join(base, "BASS", "BASS test matrix.xlsx")
bass_df = pd.read_excel(bass_xl, sheet_name="as run matrix", header=2)
print("=== BASS All Columns ===")
print(list(bass_df.columns))
print(bass_df.iloc[:3, 12:].to_string())

# 2. Print all Saffire rows (only 21 total)
for folder, fname in [
    ("SAFFIRE-I", "PSI-98_Experimental table_SAFFIRE-1.csv"),
    ("SAFFIRE-II", "PSI-99_Experimental table_SAFFIRE-2.csv"),
    ("SAFFIRE-III", "PSI-100_Experimental table_SAFFIRE-3.csv"),
]:
    print(f"\n=== {folder} ===")
    print(pd.read_csv(os.path.join(base, folder, fname)).to_string())