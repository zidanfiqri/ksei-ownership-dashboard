#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_fakta.py — Tahap 2 pipeline KSEI Ownership Dashboard.

Membangun/memperbarui TABEL FAKTA multi-periode dari:
  1. Baseline situs lama (data.js, label periode diberikan lewat argumen), dan
  2. Satu atau lebih CSV hasil parse_1pct.py (periode diambil dari kolom date).

Sekaligus menurunkan PEMETAAN TIPE INVESTOR: PDF KSEI memakai puluhan
klasifikasi granular, sedangkan situs memakai 9 kode (CP/ID/IB/IS/OT/MF/PF/
SC/FD). Pemetaan diturunkan secara EMPIRIS dari irisan pasangan
(kode, investor) antara periode PDF dan baseline; label tanpa bukti dibiarkan
kosong dan dilaporkan untuk diputuskan manusia. Hasil pemetaan disimpan ke
JSON agar bulan-bulan berikutnya konsisten dan bisa disunting manual.

Cara pakai:
    python merge_fakta.py \
        --data-js data.js --periode-baseline 2026-03-12 \
        --parsed ksei_1pct_20260529.csv \
        --mapping data/pemetaan_tipe.json \
        --out data/fakta.csv --report LAPORAN_TAHAP2.md

Aturan merge:
- Idempoten per periode: jika --out sudah ada, seluruh baris periode yang
  sedang diimpor dibuang dulu lalu diganti (aman dijalankan ulang di Actions).
- Baris TIDAK dipaksa unik per (periode, kode, investor): KSEI bisa memuat
  investor yang sama lewat dua jenis rekening (kasus ICON di baseline).
- Normalisasi: lokal_asing L->D (PDF memakai L/F, situs D/F); angka int;
  persentase float titik-desimal. Selain itu data dipertahankan apa adanya.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

FAKTA_COLS = [
    "periode", "kode", "emiten", "investor", "tipe", "klasifikasi",
    "lokal_asing", "nasionalitas", "domisili",
    "scripless", "scrip", "total_lembar", "persentase", "sumber",
]

KODE_TIPE_SAH = {"CP", "ID", "IB", "IS", "OT", "MF", "PF", "SC", "FD", ""}


def date_to_iso(d):
    dd, mon, yy = d.split("-")
    return f"{yy}-{MONTHS[mon]:02d}-{int(dd):02d}"


def fmt_pct(v):
    return f"{v:g}"


def load_baseline(path, periode):
    raw = open(path, encoding="utf-8").read()
    data = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
    rows = []
    for r in data:
        rows.append({
            "periode": periode,
            "kode": r["share_code"],
            "emiten": r["issuer_name"],
            "investor": r["investor_name"],
            "tipe": r.get("investor_type") or "",
            "klasifikasi": "",
            "lokal_asing": r.get("local_foreign") or "",
            "nasionalitas": r.get("nationality") or "",
            "domisili": r.get("domicile") or "",
            "scripless": int(r.get("holdings_scripless") or 0),
            "scrip": int(r.get("holdings_scrip") or 0),
            "total_lembar": int(r.get("total_holding_shares") or 0),
            "persentase": float(r.get("percentage") or 0),
            "sumber": "data.js",
        })
    return rows


def load_parsed(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lf = r["local_foreign"]
            rows.append({
                "periode": date_to_iso(r["date"]),
                "kode": r["share_code"],
                "emiten": r["issuer_name"],
                "investor": r["investor_name"],
                "tipe": None,  # diisi lewat pemetaan
                "klasifikasi": r["investor_classification"],
                "lokal_asing": "D" if lf == "L" else lf,
                "nasionalitas": r["nationality"],
                "domisili": r["domicile"],
                "scripless": int(r["holdings_scripless"]),
                "scrip": int(r["holdings_scrip"]),
                "total_lembar": int(r["total_holding_shares"]),
                "persentase": float(r["percentage"]),
                "sumber": "pdf_1pct",
            })
    return rows


def derive_mapping(parsed_rows, baseline_rows, existing):
    """label klasifikasi -> kode tipe, berdasarkan irisan (kode, investor)."""
    base_tipe = {}
    for r in baseline_rows:
        base_tipe[(r["kode"], r["investor"])] = r["tipe"]

    evidence = defaultdict(Counter)
    for r in parsed_rows:
        key = (r["kode"], r["investor"])
        if key in base_tipe:
            evidence[r["klasifikasi"]][base_tipe[key]] += 1

    mapping = dict(existing) if existing else {}
    labels = sorted({r["klasifikasi"] for r in parsed_rows})
    for label in labels:
        if label in mapping and mapping[label].get("kode") in KODE_TIPE_SAH \
                and mapping[label].get("kode") is not None:
            continue
        if label == "":
            mapping[label] = {"kode": "", "dasar": "definisi",
                              "catatan": "rekening warkat khusus tanpa klasifikasi"}
            continue
        ev = evidence.get(label)
        if ev:
            kode, n = ev.most_common(1)[0]
            total = sum(ev.values())
            mapping[label] = {
                "kode": kode, "dasar": "empiris",
                "sampel": total, "akurasi": round(n / total, 4),
                "rincian": dict(ev.most_common()),
            }
        else:
            mapping[label] = {"kode": None, "dasar": "tanpa-bukti",
                              "catatan": "perlu keputusan manual"}
    return mapping, evidence


def apply_mapping(parsed_rows, mapping):
    unmapped = Counter()
    for r in parsed_rows:
        m = mapping.get(r["klasifikasi"], {})
        kode = m.get("kode")
        if kode is None:
            r["tipe"] = ""
            unmapped[r["klasifikasi"]] += 1
        else:
            r["tipe"] = kode
    return unmapped


def load_existing_fakta(path):
    try:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def validate(all_rows, known_anomalies):
    issues = defaultdict(list)
    for r in all_rows:
        if r["scripless"] + r["scrip"] != r["total_lembar"]:
            key = (r["periode"], r["kode"], r["investor"])
            tag = " (anomali sumber terdokumentasi)" if key in known_anomalies else ""
            issues["total_tak_konsisten"].append(
                f"{r['periode']} {r['kode']} {r['investor']!r}{tag}")
        if not (0 < r["persentase"] <= 100):
            issues["pct_di_luar_batas"].append(
                f"{r['periode']} {r['kode']} {r['persentase']}")
        if r["lokal_asing"] not in ("D", "F", ""):
            issues["lf_tidak_valid"].append(
                f"{r['periode']} {r['kode']} {r['lokal_asing']!r}")
        if r["tipe"] not in KODE_TIPE_SAH:
            issues["tipe_tidak_sah"].append(
                f"{r['periode']} {r['kode']} {r['tipe']!r}")
    dup = Counter((r["periode"], r["kode"], r["investor"]) for r in all_rows)
    for key, n in dup.items():
        if n > 1 and key not in known_anomalies:
            issues["duplikat_tak_terduga"].append(f"{key} x{n}")
    return issues


def build_report(all_rows, mapping, evidence, unmapped, issues, renames,
                 known_anomalies):
    lines = []
    add = lines.append
    add("# Laporan Tahap 2 — Tabel Fakta, Baseline, dan Pemetaan Tipe Investor")
    add("")
    periods = sorted({r["periode"] for r in all_rows})
    add("## Isi tabel fakta")
    for p in periods:
        rows = [r for r in all_rows if r["periode"] == p]
        add(f"- Periode **{p}** ({rows[0]['sumber']}): {len(rows)} baris, "
            f"{len({r['kode'] for r in rows})} emiten, "
            f"{len({r['investor'] for r in rows})} investor unik, "
            f"baris ber-scrip: {sum(1 for r in rows if r['scrip'] > 0)}")
    add(f"- Total baris: **{len(all_rows)}**")
    add("")

    add("## Pemetaan klasifikasi PDF -> kode tipe situs")
    add("")
    add("| Klasifikasi PDF | Kode | Dasar | Sampel | Akurasi |")
    add("|---|---|---|---|---|")
    label_use = Counter(r["klasifikasi"] for r in all_rows if r["sumber"] == "pdf_1pct")
    for label, _n in label_use.most_common():
        m = mapping.get(label, {})
        nm = "(kosong)" if label == "" else label
        kode = m.get("kode")
        kode_s = "**?**" if kode is None else (kode or "(kosong)")
        add(f"| {nm} | {kode_s} | {m.get('dasar','-')} | "
            f"{m.get('sampel','-')} | "
            f"{'' if 'akurasi' not in m else format(m['akurasi']*100, '.1f') + '%'} |")
    add("")
    if unmapped:
        add("### Label TANPA BUKTI — perlu keputusanmu")
        add("")
        for label, n in unmapped.most_common():
            add(f"- **{label}**: {n} baris — usulan saya lihat bagian Catatan di bawah")
        add("")

    kualitas_n = kualitas_ok = 0
    base_tipe = {(r["kode"], r["investor"]): r["tipe"]
                 for r in all_rows if r["sumber"] == "data.js"}
    for r in all_rows:
        if r["sumber"] != "pdf_1pct":
            continue
        key = (r["kode"], r["investor"])
        if key in base_tipe and r["tipe"]:
            kualitas_n += 1
            if r["tipe"] == base_tipe[key]:
                kualitas_ok += 1
    if kualitas_n:
        add(f"Kualitas pemetaan (baris PDF beririsan baseline dgn tipe terisi): "
            f"**{kualitas_ok}/{kualitas_n} = {kualitas_ok/kualitas_n*100:.2f}%** "
            f"kode tipe identik dengan baseline.")
    add("")

    add("## Emiten ganti nama antar-periode (informasional, bahan changelog)")
    if renames:
        for k, was, now in renames:
            add(f"- {k}: {was!r} -> {now!r}")
    else:
        add("- tidak ada")
    add("")

    add("## Pemeriksaan integritas")
    ok = True
    for key, label in [
        ("total_tak_konsisten", "TOTAL != SCRIPLESS + SCRIP"),
        ("pct_di_luar_batas", "Persentase di luar (0, 100]"),
        ("lf_tidak_valid", "Lokal/Asing tak dikenal"),
        ("tipe_tidak_sah", "Kode tipe di luar daftar sah"),
        ("duplikat_tak_terduga", "Duplikat (periode,kode,investor) tak terduga"),
    ]:
        msgs = issues.get(key, [])
        hard = [m for m in msgs if "terdokumentasi" not in m]
        status = "OK" if not msgs else (
            f"{len(msgs)} (semua anomali terdokumentasi)" if not hard
            else f"**{len(hard)} masalah**")
        add(f"- {label}: {status}")
        for m in msgs[:5]:
            add(f"    - {m}")
        if hard:
            ok = False
    add("")
    add("## Catatan & anomali terdokumentasi")
    add("- Baseline ICON memuat 'ISLAND REGENCY GROUP LIMITED' dua baris "
        "(rekening scripless + warkat khusus) — dipertahankan, kunci fakta tidak unik.")
    add("- Baseline MAYA 'MAYAPADA KARUNIA PT': 0+6.323.076.332 != 6.023.326.332 "
        "— salah ketik di sumber asli, diimpor apa adanya.")
    add("- lokal_asing PDF dinormalkan L->D agar konsisten dengan situs.")
    add("- Nama emiten disimpan per periode; tampilan situs memakai periode terbaru.")
    add("")
    add(f"## Kesimpulan: {'LULUS' if ok else 'ADA MASALAH'}"
        + (" — tinjau label tanpa-bukti di atas" if unmapped else ""))
    return "\n".join(lines), ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-js")
    ap.add_argument("--periode-baseline")
    ap.add_argument("--parsed", nargs="*", default=[])
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    args = ap.parse_args(argv)

    baseline_rows = []
    if args.data_js:
        if not args.periode_baseline:
            print("FATAL: --periode-baseline wajib bila --data-js dipakai",
                  file=sys.stderr)
            return 2
        baseline_rows = load_baseline(args.data_js, args.periode_baseline)

    parsed_rows = []
    for p in args.parsed:
        parsed_rows.extend(load_parsed(p))

    try:
        with open(args.mapping, encoding="utf-8") as f:
            existing_map = json.load(f)
    except FileNotFoundError:
        existing_map = {}

    mapping, evidence = derive_mapping(parsed_rows, baseline_rows, existing_map)
    unmapped = apply_mapping(parsed_rows, mapping)

    with open(args.mapping, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)

    new_rows = baseline_rows + parsed_rows
    new_periods = {r["periode"] for r in new_rows}
    old = [r for r in load_existing_fakta(args.out)
           if r["periode"] not in new_periods]
    for r in old:  # tipe data dari CSV lama
        for k in ("scripless", "scrip", "total_lembar"):
            r[k] = int(r[k])
        r["persentase"] = float(r["persentase"])

    all_rows = old + new_rows
    all_rows.sort(key=lambda r: (r["periode"], r["kode"], -r["persentase"],
                                 r["investor"]))

    known_anomalies = set()
    if args.periode_baseline:
        known_anomalies = {
            (args.periode_baseline, "ICON", "ISLAND REGENCY GROUP LIMITED"),
            (args.periode_baseline, "MAYA", "MAYAPADA KARUNIA PT"),
        }
    issues = validate(all_rows, known_anomalies)

    per_code = defaultdict(dict)
    for r in all_rows:
        per_code[r["kode"]][r["periode"]] = r["emiten"]
    renames = []
    for k, d in sorted(per_code.items()):
        ps = sorted(d)
        if len(ps) > 1 and d[ps[0]] != d[ps[-1]]:
            renames.append((k, d[ps[0]], d[ps[-1]]))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FAKTA_COLS)
        w.writeheader()
        for r in all_rows:
            row = dict(r)
            row["persentase"] = fmt_pct(row["persentase"])
            w.writerow({k: row[k] for k in FAKTA_COLS})

    report, ok = build_report(all_rows, mapping, evidence, unmapped, issues,
                              renames, known_anomalies)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
