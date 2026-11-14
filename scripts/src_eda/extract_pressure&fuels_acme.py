import os
import docx
from pypdf import PdfReader

acme_dir = r"C:\Users\Ariele\Desktop\NASA\data\ACME_BRE"

doc = docx.Document(os.path.join(acme_dir, "ACME-BRE_Test_Summary.docx"))
print("=== ACME-BRE_Test_Summary.docx ===")
for p in doc.paragraphs:
    if p.text.strip():
        print(" ", p.text.strip()[:220])

for pdf_name in ["BRE_data_interpretation_20220804.pdf", "ACME_non-imaging_data_file_description.pdf"]:
    pdf_path = os.path.join(acme_dir, pdf_name)
    if os.path.exists(pdf_path):
        reader = PdfReader(pdf_path)
        print(f"\n=== {pdf_name} ({len(reader.pages)} pages) ===")
        for i, page in enumerate(reader.pages[:6]):
            txt = page.extract_text() or ""
            for line in txt.splitlines():
                if any(k in line.lower() for k in ["psi", "atm", "kpa", "pressure", "pmma", "nomex", "cotton", "cel", "26.5", "34", "40"]):
                    print(f"  [p.{i+1}] {line.strip()[:160]}")