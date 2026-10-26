#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_periode.py: orkestrator update bulanan KSEI Ownership Dashboard.

Menjalankan semua tahap berurutan dari satu perintah:
  1. parse_1pct_excel.py  file Excel KSEI/BEI "1% ..." -> ksei_1pct_YYYYMMDD.csv
  2. merge_fakta.py       gabung ke data/fakta.csv (aman dijalankan ulang per periode)
  3. hitung_metrik.py     data/metrik.json dan data/changelog.json
  4. fetch_yfinance.py    harga dan sektor (lewati dengan --skip-harga)
  5. build_site.py        rakit docs/ (tanpa source.html pun bisa)

Cara pakai (dari folder utama repo):
    python scripts/update_periode.py "1% 31 Agustus 2026.xlsx" "1% 30 September 2026.xlsx"
    python scripts/update_periode.py "1% 31 Oktober 2026.xlsx" --skip-harga

Masukkan SEMUA bulan yang tertinggal dalam satu perintah, urutan bebas. Tanggal periode
dibaca dari isi file, bukan dari nama file. Skrip berhenti di tahap pertama yang gagal.
"""
import argparse
import csv
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "scripts")
PY = sys.executable


def jalan(judul, args):
    print(f"\n=== {judul} ===", flush=True)
    r = subprocess.run([PY] + args, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"\nBERHENTI: tahap '{judul}' gagal (kode {r.returncode}). Perbaiki lalu jalankan ulang; "
                 f"tahap yang sudah selesai aman diulang.")


def tanggal_csv(path):
    with open(path, encoding="utf-8") as f:
        baris = next(csv.DictReader(f))
    return datetime.strptime(baris["date"], "%d-%b-%Y").strftime("%Y%m%d")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("excel", nargs="+", help="file Excel laporan pemegang saham di atas 1%%")
    ap.add_argument("--skip-harga", action="store_true", help="lewati pengambilan harga dan sektor dari Yahoo Finance")
    a = ap.parse_args()

    csvs = []
    for x in a.excel:
        src = x if os.path.isabs(x) else os.path.join(ROOT, x)
        if not os.path.exists(src):
            sys.exit(f"File tidak ditemukan: {x}")
        tmp = os.path.join(ROOT, "ksei_1pct_tmp.csv")
        jalan(f"1. Parse {os.path.basename(src)}", [os.path.join(S, "parse_1pct_excel.py"), src, "-o", tmp])
        tujuan = os.path.join(ROOT, f"ksei_1pct_{tanggal_csv(tmp)}.csv")
        os.replace(tmp, tujuan)
        print(f"-> {os.path.basename(tujuan)}")
        csvs.append(tujuan)

    jalan("2. Gabung ke data/fakta.csv",
          [os.path.join(S, "merge_fakta.py"), "--parsed", *csvs, "--mapping", "data/pemetaan_tipe.json",
           "--out", "data/fakta.csv"])
    jalan("3. Hitung metrik dan changelog",
          [os.path.join(S, "hitung_metrik.py"), "--fakta", "data/fakta.csv",
           "--out-metrik", "data/metrik.json", "--out-changelog", "data/changelog.json"])
    if not a.skip_harga:
        jalan("4. Harga dan sektor (Yahoo Finance)",
              [os.path.join(S, "fetch_yfinance.py"), "--fakta", "data/fakta.csv", "--out", "data/emiten.json"])
    else:
        print("\n=== 4. Harga dan sektor: dilewati (--skip-harga) ===")
    jalan("5. Build situs ke docs/",
          [os.path.join(S, "build_site.py"), "--source", "source.html", "--fakta", "data/fakta.csv",
           "--changelog", "data/changelog.json", "--emiten", "data/emiten.json",
           "--pep", "docs/pep_data.js", "--konglo", "docs/konglo_data.js", "--docs", "docs"])
    print("\nSELESAI. Cek tampilan docs/index.html, lalu:\n"
          "    git add -A && git commit -m \"Update periode\" && git push")


if __name__ == "__main__":
    main()
