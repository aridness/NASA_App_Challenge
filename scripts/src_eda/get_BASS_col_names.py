import os
import pandas as pd

base = r"C:\Users\Ariele\Desktop\NASA\data"

# 1. Find real header row in BASS test matrix.xlsx
bass_xl = os.path.join(base, "BASS", "BASS test matrix.xlsx")
raw = pd.read_excel(bass_xl, sheet_name="as run matrix", header=None, nrows=10)
print("=== BASS 'as run matrix' first 6 rows ===")
for i, row in raw.head(6).iterrows():
    print(f"Row {i}: {[x for x in row.tolist() if pd.notna(x)][:12]}")

# 2. Sample rows from BASS-II CSV (updated path to BASS-II folder)
bass2 = pd.read_csv(os.path.join(base, "BASS-II", "PSI-25_Experimental table_BASS-II.csv"))
o2_col = [c for c in bass2.columns if "initial O2" in c][0]
print("\n=== BASS-II Sample Rows ===")
print(bass2[['PI', 'Test #', 'Sample #', 'Fuel Sample Material', 'Flow restrictor', 'Fan display', o2_col]].head(5).to_string())

# 3. Sample rows from SAFFIRE-2 CSV
saf2 = pd.read_csv(os.path.join(base, "SAFFIRE-II", "PSI-99_Experimental table_SAFFIRE-2.csv"))
print("\n=== SAFFIRE-2 Sample Rows ===")
print(saf2[['Sample Number', 'Material', 'Samle Thickness ', 'Air Flow (cm/s)', 'Percent O2 (Note 1)', 'Burn Time (s)', 'Flow Direction', '?-g Spread Length', '1-g Spread Rate']].head(5).to_string())