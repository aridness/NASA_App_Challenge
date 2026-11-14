import json
import pandas as pd

df = pd.read_json(r"C:\Users\Ariele\Desktop\NASA\data\psi_solid_flammability.json")
print("Total rows:", len(df))
print("\nNull counts per column:\n", df.isna().sum())
print("\nLow-O2 (<18%) runs (check if any extinguished):\n",
      df[df["o2_percent"] < 18.0][["test_id", "material", "thickness_mm", "o2_percent", "airflow_cm_s", "outcome"]].to_string())