import os
import pandas as pd
import docx

acme_dir = r"C:\Users\Ariele\Desktop\NASA\data\ACME_BRE"
csv_path = os.path.join(acme_dir, "PSI-20_Experimental table_ACME BRE.csv")

df = pd.read_csv(csv_path)
print("COLS:", list(df.columns))
print("SHAPE:", df.shape)
print(df.to_string())

doc_path = os.path.join(acme_dir, "ACME-BRE_Test_Summary.docx")
if os.path.exists(doc_path):
    doc = docx.Document(doc_path)
    print("\n=== ACME-BRE_Test_Summary.docx Tables ===")
    for t in doc.tables:
        for row in t.rows[:10]:
            print(" | ".join(c.text.strip().replace("\n", " ") for c in row.cells))