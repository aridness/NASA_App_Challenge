import os
import re
import docx
from pypdf import PdfReader

base = r"C:\Users\Ariele\Desktop\NASA\data"

# 1. Dump all tables from US National Meeting-070HE-0218-Final.docx
meeting_doc = os.path.join(base, "BASS", "US National Meeting-070HE-0218-Final.docx")
doc = docx.Document(meeting_doc)
print("=== US National Meeting Tables ===")
for t_idx, table in enumerate(doc.tables):
    print(f"\n--- Table {t_idx} ---")
    for row in table.rows:
        print(" | ".join(c.text.strip().replace("\n", " ") for c in row.cells))

# 2. Search paragraphs in FAQ / Procedure / Meeting docs for spread rates
for rel_path in [
    os.path.join("BASS", "US National Meeting-070HE-0218-Final.docx"),
    os.path.join("BASS-II", "BASS-II data FAQ.docx"),
    os.path.join("BASS-II", "BASS-II Procedure.docx"),
]:
    full_path = os.path.join(base, rel_path)
    if os.path.exists(full_path):
        d = docx.Document(full_path)
        print(f"\n=== Text matches in {os.path.basename(full_path)} ===")
        for p in d.paragraphs:
            txt = p.text.strip()
            if re.search(r"(\d+\.?\d*\s*(mm/s|cm/s)|spread rate|1-g|1g)", txt, re.I):
                print("  ", txt[:200])

# 3. Scan SRD PDFs for spread rates and 1g baselines
for rel_pdf in [
    os.path.join("BASS", "SRD_BASS.pdf"),
    os.path.join("BASS-II", "SRD_BASS-II.pdf"),
    os.path.join("BASS", "SLICE ED-04 SLICE_BASS_SAR-1_FINAL.pdf"),
]:
    pdf_path = os.path.join(base, rel_pdf)
    if os.path.exists(pdf_path):
        reader = PdfReader(pdf_path)
        print(f"\n=== PDF matches in {os.path.basename(pdf_path)} ({len(reader.pages)} pages) ===")
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            for line in txt.splitlines():
                if re.search(r"(\d+\.?\d*\s*(mm/s|cm/s)|spread rate|baseline)", line, re.I):
                    print(f"  [p.{i+1}] {line.strip()[:160]}")