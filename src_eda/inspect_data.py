import glob
import json
import os
import pandas as pd

base_dir = r"C:\Users\Ariele\Desktop\NASA\data"
csv_files = glob.glob(os.path.join(base_dir, "**", "PSI-*.csv"), recursive=True)

# Step 1: Inspect exact column names across all downloaded PSI tables
for f in csv_files:
    df = pd.read_csv(f)
    print(f"\n--- {os.path.basename(f)} ({len(df)} rows) ---")
    print(list(df.columns))