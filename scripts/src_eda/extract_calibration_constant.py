import os
import docx

base = r"C:\Users\Ariele\Desktop\NASA\data"
docs = [
    os.path.join(base, "BASS-II", "BASS-II Procedure.docx"),
    os.path.join(base, "BASS-II", "BASS-II data FAQ.docx"),
    os.path.join(base, "SAFFIRE-I", "SAFFIRE-I and SAFFIRE-III DoD.docx"),
]

for path in docs:
    if not os.path.exists(path):
        continue
    doc = docx.Document(path)
    print(f"\n=== {os.path.basename(path)} ===")
    for t in doc.tables:
        for row in t.rows:
            txt = " | ".join(c.text.strip().replace("\n", " ") for c in row.cells)
            if any(k in txt.lower() for k in ["restrictor", "cm/s", "mm/s", "spread", "s1", "s2"]):
                print("  TABLE:", txt[:160])
    for p in doc.paragraphs:
        txt = p.text.strip()
        if any(k in txt.lower() for k in ["restrictor", "spread rate", "mm/s"]):
            print("  PARA:", txt[:180])