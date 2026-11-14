import os
import re
import docx

base = r"C:\Users\Ariele\Desktop\NASA\data"
docx_files = [
    os.path.join(base, "BASS", "US National Meeting-070HE-0218-Final.docx"),
    os.path.join(base, "BASS-II", "BASS-II data FAQ.docx"),
    os.path.join(base, "BASS-II", "BASS-II Procedure.docx"),
]

# Search paragraphs and tables in .docx files for spread rate numbers (mm/s or cm/s)
for path in docx_files:
    if not os.path.exists(path):
        continue
    doc = docx.Document(path)
    print(f"\n=== {os.path.basename(path)} ===")
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            joined = " | ".join(cells)
            if any(k in joined.lower() for k in ["mm/s", "cm/s", "spread", "147", "155", "227", "144"]):
                print("  TABLE:", joined[:160])