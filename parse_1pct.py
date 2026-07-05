#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_1pct.py — Parser laporan KSEI "Kepemilikan Investor di atas 1%" (PDF ekspor Excel)
Tahap 1 pipeline KSEI Ownership Dashboard.

Cara pakai:
    python parse_1pct.py "1% 2 Juni 2026.pdf" -o ksei_1pct.csv \
        [--meta meta.json] [--report laporan.md] [--baseline-csv ksei_saham_20260703.csv]

Keluaran CSV (12 kolom, urutan sama dengan PDF):
    date, share_code, issuer_name, investor_name, investor_classification,
    local_foreign, nationality, domicile, holdings_scripless, holdings_scrip,
    total_holding_shares, percentage

Nilai numerik dinormalkan untuk mesin (int polos; percentage float titik-desimal).
Kolom teks dipertahankan apa adanya dari PDF (local_foreign tetap L/F —
normalisasi L→D dilakukan di tahap merge, bukan di parser).

Teknik:
- Batas kolom diambil dari garis grid vertikal PDF (rects tipis), bukan posisi
  header (header rata-tengah sehingga menyesatkan).
- Kata diekstrak dengan use_text_flow=True agar sel yang tulisannya
  tumpang-tindih secara visual (emiten bernama panjang, mis. CARS) tetap
  terpisah sesuai urutan penulisan di content stream.
- Baris direkonstruksi dengan pengelompokan koordinat vertikal (toleransi 1.2pt).
- Validasi bawaan per baris: pola tanggal/kode, 4 kolom angka, dan
  TOTAL == SCRIPLESS + SCRIP.
"""

import argparse
import bisect
import csv
import json
import re
import sys
from collections import Counter, defaultdict

import pdfplumber

DATE_RE = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$")
CODE_RE = re.compile(r"^[A-Z0-9]{4}$")
NUM_RE = re.compile(r"^(?:\d{1,3}(?:\.\d{3})*|0)$")
PCT_RE = re.compile(r"^\d{1,3},\d{1,2}$")

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

COLS = [
    "date", "share_code", "issuer_name", "investor_name",
    "investor_classification", "local_foreign", "nationality", "domicile",
    "holdings_scripless", "holdings_scrip", "total_holding_shares", "percentage",
]

Y_TOL = 1.2          # toleransi pengelompokan baris (pt)
X_CLUSTER_TOL = 2.0  # toleransi klaster garis grid (pt)
N_BOUNDS = 13        # 13 batas = 12 kolom


def date_to_iso(d):
    """'29-May-2026' -> '2026-05-29'"""
    dd, mon, yy = d.split("-")
    return f"{yy}-{MONTHS[mon]:02d}-{int(dd):02d}"


def to_int(s):
    return int(s.replace(".", ""))


def to_pct(s):
    return float(s.replace(",", "."))


def page_boundaries(page, prev_bounds):
    """Batas kolom dari rects tipis (grid vertikal). Fallback: halaman sebelumnya."""
    thin = [r for r in page.rects if r["width"] < 1.0]
    xs = sorted((r["x0"] + r["x1"]) / 2 for r in thin)
    clusters = []
    for x in xs:
        if clusters and x - clusters[-1][-1] < X_CLUSTER_TOL:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    bounds = [sum(c) / len(c) for c in clusters]
    if len(bounds) == N_BOUNDS:
        return bounds, False
    if prev_bounds is not None:
        return prev_bounds, True
    raise RuntimeError(
        f"Grid kolom tidak ditemukan di halaman pertama "
        f"(ditemukan {len(bounds)} batas, butuh {N_BOUNDS})."
    )


def rows_from_words(words):
    """Kelompokkan kata menjadi baris berdasarkan koordinat top.

    Urutan kata di dalam baris mengikuti urutan kemunculan di `words`
    (= urutan content stream bila use_text_flow=True).
    """
    order = {id(w): i for i, w in enumerate(words)}
    rows = []
    for w in sorted(words, key=lambda w: w["top"]):
        if rows and abs(w["top"] - rows[-1]["top"]) <= Y_TOL:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: order[id(w)])
    return rows


def assign_columns(ws, bounds, repair_log=None):
    """Tempatkan tiap kata ke kolomnya.

    Kolom teks (0-7, rata-kiri): ditentukan TEPI KIRI kata (x0) — teks
    rata-kiri hanya bisa meluber ke kanan, jadi x0 jujur menunjukkan kolom
    asal. Kolom angka (8-11, rata-kanan): ditentukan titik tengah.

    Di batas emiten->investor, glyph 'Tbk' emiten panjang bisa meluber/
    menempel ke kata pertama investor. Karena glyph dua sel saling
    tumpang-tindih pada ruang x yang sama, pemisahan geometris mustahil;
    yang pasti benar adalah POLA: tidak ada nama investor yang berawalan
    'Tbk'. Tangga perbaikan di bawah mengembalikan fragmen T/b/k ke emiten.
    """
    EPS = 0.7
    cols = [[] for _ in range(N_BOUNDS - 1)]
    for w in ws:
        center = (w["x0"] + w["x1"]) / 2
        if center < bounds[8]:
            idx = 0
            for i in range(1, 8):
                if w["x0"] >= bounds[i] - EPS:
                    idx = i
                else:
                    break
        else:
            idx = 8
            for i in range(9, N_BOUNDS - 1):
                if center >= bounds[i]:
                    idx = i
                else:
                    break
        cols[idx].append(w["text"])

    # --- tangga perbaikan batas emiten->investor ---
    # Kasus cermin lebih dulu: token gabungan jatuh di SISI EMITEN
    # ('...TbkFURUKAWA' -> emiten '...Tbk' + investor 'FURUKAWA').
    # Syarat sisa berawalan huruf kapital/angka agar 'Tbk,' / 'Tbk.' yang sah
    # (bagian nama resmi seperti '... Tbk, PT') tidak ikut terbelah.
    if cols[2]:
        m = re.match(r"^Tbk([A-Z0-9].*)$", cols[2][-1])
        if m:
            cols[2][-1] = "Tbk"
            cols[3].insert(0, m.group(1))
            if repair_log is not None:
                repair_log.append("Tbk|" + m.group(1))
    if cols[3]:
        issuer = " ".join(cols[2])
        inv0 = cols[3][0]
        moved = None
        if inv0 in ("Tbk", "Tbk.", "Tbk,"):
            cols[2].append(cols[3].pop(0)); moved = inv0
        elif inv0.startswith("Tbk") and len(inv0) > 3:
            cols[2].append("Tbk"); cols[3][0] = inv0[3:]; moved = "Tbk<-" + inv0
        elif issuer.endswith("Tb") and inv0 == "k":
            cols[2][-1] += cols[3].pop(0); moved = "k"
        elif issuer.endswith("Tb") and inv0.startswith("k") and len(inv0) > 1:
            cols[2][-1] += "k"; cols[3][0] = inv0[1:]; moved = "k<-" + inv0
        elif issuer.endswith("T") and inv0 == "bk":
            cols[2][-1] += cols[3].pop(0); moved = "bk"
        elif issuer.endswith("T") and inv0.startswith("bk") and len(inv0) > 2:
            cols[2][-1] += "bk"; cols[3][0] = inv0[2:]; moved = "bk<-" + inv0
        if moved and repair_log is not None:
            repair_log.append(moved)

    return [" ".join(c).strip() for c in cols]


def parse_pdf(pdf_path):
    records = []
    issues = defaultdict(list)   # kategori -> daftar pesan
    stats = {
        "pages": 0,
        "skipped_header": 0,
        "skipped_footer": 0,
        "skipped_other": 0,
        "bounds_fallback_pages": [],
        "splits": [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        stats["pages"] = len(pdf.pages)
        bounds = None
        for pageno, page in enumerate(pdf.pages, start=1):
            bounds, used_fallback = page_boundaries(page, bounds)
            if used_fallback:
                stats["bounds_fallback_pages"].append(pageno)

            words = page.extract_words(
                use_text_flow=True, x_tolerance=1.0, keep_blank_chars=False
            )
            for row in rows_from_words(words):
                ws = row["words"]
                first = ws[0]["text"]
                if not DATE_RE.match(first):
                    joined = " ".join(w["text"] for w in ws)
                    if "DATE" in joined and "SHARE_CODE" in joined:
                        stats["skipped_header"] += 1
                    elif joined.startswith("#") or "Kode A" in joined:
                        stats["skipped_footer"] += 1
                    else:
                        stats["skipped_other"] += 1
                    continue

                vals = assign_columns(ws, bounds, stats["splits"])
                loc = f"hal.{pageno} y={row['top']:.1f}"

                date_s, code = vals[0], vals[1]
                if not CODE_RE.match(code):
                    issues["kode_tidak_valid"].append(f"{loc}: {code!r} | {vals}")
                    continue
                num_raw = vals[8:11]
                pct_raw = vals[11]
                if not all(NUM_RE.match(n) for n in num_raw) or not PCT_RE.match(pct_raw):
                    issues["angka_tidak_valid"].append(f"{loc}: {vals[8:12]}")
                    continue
                if vals[5] not in ("L", "F", ""):
                    issues["lf_tidak_valid"].append(f"{loc}: {vals[5]!r}")

                scripless, scrip, total = (to_int(n) for n in num_raw)
                pct = to_pct(pct_raw)
                if scripless + scrip != total:
                    issues["total_tak_konsisten"].append(
                        f"{loc}: {code} {vals[3]!r}: {scripless}+{scrip}!={total}"
                    )
                if not (0 < pct <= 100):
                    issues["pct_di_luar_batas"].append(f"{loc}: {code} {pct}")
                if not vals[2]:
                    issues["emiten_kosong"].append(f"{loc}: {code}")
                if not vals[3]:
                    issues["investor_kosong"].append(f"{loc}: {code}")

                records.append({
                    "date": date_s,
                    "share_code": code,
                    "issuer_name": vals[2],
                    "investor_name": vals[3],
                    "investor_classification": vals[4],
                    "local_foreign": vals[5],
                    "nationality": vals[6],
                    "domicile": vals[7],
                    "holdings_scripless": scripless,
                    "holdings_scrip": scrip,
                    "total_holding_shares": total,
                    "percentage": pct,
                    "_page": pageno,
                })
    by_code = {}
    for r in records:
        by_code.setdefault(r["share_code"], set()).add(r["issuer_name"])
    for k, v in sorted(by_code.items()):
        if len(v) > 1:
            issues["emiten_tidak_seragam"].append(f"{k}: {sorted(v)}")
    return records, issues, stats


def build_report(records, issues, stats, pdf_path, baseline_rows=None):
    lines = []
    add = lines.append
    dates = Counter(r["date"] for r in records)
    codes = sorted({r["share_code"] for r in records})
    classif = Counter(r["investor_classification"] for r in records)
    lf = Counter(r["local_foreign"] or "(kosong)" for r in records)
    pair_counts = Counter((r["share_code"], r["investor_name"]) for r in records)
    dup_pairs = {p: c for p, c in pair_counts.items() if c > 1}
    scrip_pos = sum(1 for r in records if r["holdings_scrip"] > 0)

    add(f"# Laporan Validasi Tahap 1 — Parser PDF KSEI 1%")
    add("")
    add(f"Sumber: `{pdf_path}` ({stats['pages']} halaman)")
    add("")
    add("## Hasil ekstraksi")
    add(f"- Baris data: **{len(records)}**")
    add(f"- Emiten unik: **{len(codes)}**")
    add(f"- Investor unik: **{len({r['investor_name'] for r in records})}**")
    add(f"- Tanggal periode: **{dict(dates)}**")
    add(f"- Baris ber-scrip (>0): {scrip_pos}")
    add(f"- Baris dilewati — header: {stats['skipped_header']}, footer: {stats['skipped_footer']}, lainnya (disklaimer dsb.): {stats['skipped_other']}")
    if stats["splits"]:
        add(f"- Perbaikan batas emiten->investor (fragmen Tbk dikembalikan): {len(stats['splits'])} -> {stats['splits'][:6]}")
    if stats["bounds_fallback_pages"]:
        add(f"- Halaman memakai grid fallback: {stats['bounds_fallback_pages']}")
    add("")
    add("## Distribusi nilai")
    add(f"- Lokal/Asing: {dict(lf.most_common())}")
    add(f"- Klasifikasi investor ({len(classif)} jenis): {dict(classif.most_common())}")
    add(f"- Pasangan (kode, investor) muncul >1×: {len(dup_pairs)}"
        + (f" -> {list(dup_pairs.items())[:10]}" if dup_pairs else ""))
    add("")
    add("## Pemeriksaan integritas")
    ok = True
    for key, label in [
        ("kode_tidak_valid", "Kode emiten tidak valid"),
        ("angka_tidak_valid", "Kolom angka tidak valid"),
        ("lf_tidak_valid", "Nilai Lokal/Asing tak dikenal"),
        ("total_tak_konsisten", "TOTAL != SCRIPLESS + SCRIP"),
        ("pct_di_luar_batas", "Persentase di luar (0, 100]"),
        ("emiten_kosong", "Nama emiten kosong"),
        ("emiten_tidak_seragam", "Nama emiten tidak seragam antar-baris satu kode"),
        ("investor_kosong", "Nama investor kosong"),
    ]:
        n = len(issues.get(key, []))
        status = "OK" if n == 0 else f"**{n} masalah**"
        add(f"- {label}: {status}")
        if n:
            ok = False
            for msg in issues[key][:5]:
                add(f"    - {msg}")
            if n > 5:
                add(f"    - ... (+{n-5} lagi)")
    add("")

    if baseline_rows is not None:
        base_codes = {r["Kode"] for r in baseline_rows}
        new_codes = sorted(set(codes) - base_codes)
        gone_codes = sorted(base_codes - set(codes))
        add("## Perbandingan dengan CSV baseline (situs, 12 Mar 2026)")
        add(f"- Emiten baseline: {len(base_codes)} | PDF: {len(codes)}")
        add(f"- Emiten baru di PDF: {new_codes or 'tidak ada'}")
        add(f"- Emiten hilang dari PDF: {gone_codes or 'tidak ada'}")
        base_pair = {}
        for r in baseline_rows:
            base_pair[(r["Kode"], r["Investor"])] = (
                int(r["Lembar Saham"]),
                float(r["Persentase"].replace(",", ".")) if r["Persentase"] else None,
            )
        overlap = same = 0
        for r in records:
            key = (r["share_code"], r["investor_name"])
            if key in base_pair:
                overlap += 1
                if base_pair[key][0] == r["total_holding_shares"]:
                    same += 1
        add(f"- Pasangan (kode, investor) yang ada di kedua periode: {overlap}")
        add(f"  - lembar saham tidak berubah: {same} | berubah: {overlap - same} (wajar antar-periode)")
        base_issuer = {r["Kode"]: r["Emiten"] for r in baseline_rows}
        pdf_issuer = {}
        for r in records:
            pdf_issuer.setdefault(r["share_code"], r["issuer_name"])
        mismatch = [
            (k, v, base_issuer[k]) for k, v in sorted(pdf_issuer.items())
            if k in base_issuer and v != base_issuer[k]
        ]
        add(f"- Nama emiten berbeda dari baseline (informasional — kemungkinan ganti "
            f"nama resmi/beda penulisan, bukan error parse): {len(mismatch)}")
        for k, now, was in mismatch:
            add(f"    - {k}: {was!r} -> {now!r}")
        spot = next((r for r in records
                     if r["share_code"] == "AADI" and "GARIBALDI" in r["investor_name"]), None)
        if spot:
            exp = base_pair.get(("AADI", spot["investor_name"]))
            add(f"- Spot-check AADI/GARIBALDI: PDF {spot['total_holding_shares']} / {spot['percentage']}"
                f" vs baseline {exp} -> {'COCOK' if exp and exp[0]==spot['total_holding_shares'] else 'BEDA'}")
        add("")

    add(f"## Kesimpulan: {'LULUS — siap dipakai Tahap 2' if ok else 'ADA MASALAH — lihat rincian di atas'}")
    return "\n".join(lines), ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="Parser PDF KSEI kepemilikan 1%")
    ap.add_argument("pdf", help="path PDF laporan 1%")
    ap.add_argument("-o", "--output", required=True, help="path CSV keluaran")
    ap.add_argument("--meta", help="path JSON metadata keluaran")
    ap.add_argument("--report", help="path laporan validasi (markdown)")
    ap.add_argument("--baseline-csv", help="CSV baseline situs untuk cross-check")
    args = ap.parse_args(argv)

    records, issues, stats = parse_pdf(args.pdf)
    if not records:
        print("FATAL: tidak ada baris data terbaca.", file=sys.stderr)
        return 2

    dates = sorted({r["date"] for r in records})
    periode_iso = date_to_iso(dates[0]) if len(dates) == 1 else None

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in records:
            w.writerow({k: r[k] for k in COLS})

    if args.meta:
        meta = {
            "sumber_pdf": args.pdf,
            "periode": periode_iso,
            "tanggal_mentah": dates,
            "jumlah_baris": len(records),
            "jumlah_emiten": len({r["share_code"] for r in records}),
            "halaman": stats["pages"],
        }
        with open(args.meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    baseline_rows = None
    if args.baseline_csv:
        with open(args.baseline_csv, encoding="utf-8-sig") as f:
            baseline_rows = list(csv.DictReader(f))

    report, ok = build_report(records, issues, stats, args.pdf, baseline_rows)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
