"""hanya untuk debuf"""

# debug_pdf.py
import pdfplumber

path = "1% 30 Juni 2026.pdf"
with pdfplumber.open(path) as pdf:
    print("jumlah halaman:", len(pdf.pages))
    p = pdf.pages[0]
    thin = [r for r in p.rects if r["width"] < 1.0]
    print("jumlah garis grid tipis di hal.1:", len(thin))
    words = p.extract_words(use_text_flow=True, x_tolerance=1.0, keep_blank_chars=False)
    print("jumlah kata di hal.1:", len(words))
    print("20 kata pertama:", [w["text"] for w in words[:20]])
    print("--- extract_text() 600 karakter pertama ---")
    txt = p.extract_text()
    print(txt[:600] if txt else "(KOSONG — tidak ada teks di halaman ini)")
