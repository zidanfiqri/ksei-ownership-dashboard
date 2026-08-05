# debug_pdf2.py — taruh di scripts/, jalankan dari ROOT: python3 scripts/debug_pdf2.py
import parse_1pct as p
import pdfplumber

if not hasattr(p, "DATE_CODE_FUSED_RE"):
    print("BELUM ADA: DATE_CODE_FUSED_RE tidak ditemukan di parse_1pct.py")
    print("-> edit Langkah 1 sebelumnya belum tersimpan di file ini.")
    raise SystemExit(1)
print("OK: DATE_CODE_FUSED_RE sudah ada di modul.\n")

path = "1% 30 Juni 2026.pdf"
with pdfplumber.open(path) as pdf:
    page = pdf.pages[0]
    bounds, _ = p.page_boundaries(page, None)
    print("bounds halaman 1:", bounds)

    words = page.extract_words(use_text_flow=True, x_tolerance=1.0, keep_blank_chars=False)
    rows = p.rows_from_words(words)
    print("jumlah baris halaman 1 (setelah dikelompokkan):", len(rows))
    print()
    for i, row in enumerate(rows[:6]):
        ws = row["words"]
        first = ws[0]["text"]
        md = bool(p.DATE_RE.match(first))
        mf = p.DATE_CODE_FUSED_RE.match(first)
        print(f"baris {i} (top={row['top']:.1f}): kata_pertama={first!r}")
        print(f"   DATE_RE={md}  FUSED={bool(mf)}" + (f" groups={mf.groups()}" if mf else ""))