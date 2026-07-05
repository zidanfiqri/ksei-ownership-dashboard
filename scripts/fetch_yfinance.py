#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_yfinance.py — Tahap 3 pipeline KSEI Ownership Dashboard.

Mengambil HARGA, MARKET CAP, SEKTOR, dan INDUSTRI untuk seluruh kode emiten
di tabel fakta, dari Yahoo Finance (ticker IDX = KODE + ".JK"), lalu
menyimpannya ke data/emiten.json.

Cara pakai:
    python fetch_yfinance.py --fakta data/fakta.csv --out data/emiten.json \
        [--report LAPORAN_YFINANCE.md] [--sleep 0.6] [--retries 3] \
        [--refresh-sector] [--limit N] [--dry-run]

Perilaku penting:
- INKREMENTAL: sektor/industri jarang berubah, jadi hanya diambil untuk kode
  yang belum punya (atau semua bila --refresh-sector). Harga & mcap selalu
  disegarkan. Run pertama berat (±956 kode), run berikutnya ringan.
- TAHAN GAGAL: kegagalan per kode dicatat di kolom "error" dan tidak
  menghentikan proses; nilai lama (bila ada) dipertahankan. Skrip keluar
  dengan kode 0 selama ada minimal sebagian hasil — kegagalan total saja
  yang mengembalikan kode 1, supaya GitHub Actions tidak gagal hanya karena
  Yahoo cegukan pada sebagian ticker.
- --dry-run: tidak menyentuh jaringan sama sekali; menghasilkan kerangka
  emiten.json (semua nilai null, error="dry-run") untuk menguji alur I/O.

Struktur keluaran (data/emiten.json):
{
  "_meta": {"dibuat": "...", "mode": "...", "jumlah_kode": N, ...},
  "AADI": {"harga": 2410.0, "mcap": 18760000000000, "sektor": "Energy",
            "industri": "Thermal Coal", "harga_tanggal": "2026-07-05",
            "error": null},
  ...
}
Catatan: tidak semua emiten kecil tersedia di Yahoo; cakupan sektor situs
asli pun hanya 907/955. Kode tanpa data tampil tanpa pill harga/sektor —
perilaku yang sama dengan situs asli.
"""

import argparse
import csv
import datetime as dt
import json
import sys
import time


def read_codes(fakta_path):
    with open(fakta_path, encoding="utf-8") as f:
        return sorted({r["kode"] for r in csv.DictReader(f)})


def load_existing(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.pop("_meta", None)
        return data
    except FileNotFoundError:
        return {}


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def _get(obj, *keys):
    """Ambil nilai dari fast_info/info lintas versi yfinance (atribut/kunci)."""
    for k in keys:
        try:
            v = getattr(obj, k)
            if v is not None:
                return v
        except Exception:
            pass
        try:
            v = obj[k]
            if v is not None:
                return v
        except Exception:
            pass
        try:
            v = obj.get(k)
            if v is not None:
                return v
        except Exception:
            pass
    return None


def fetch_one(kode, need_sector, sleep_s, retries):
    import yfinance as yf

    last_err = None
    for attempt in range(retries):
        errs = []
        try:
            t = yf.Ticker(f"{kode}.JK")
            harga = mcap = None
            try:
                fi = t.fast_info
                harga = _first(_get(fi, "last_price", "lastPrice"),
                               _get(fi, "regular_market_price",
                                    "regularMarketPrice"))
                mcap = _get(fi, "market_cap", "marketCap")
            except Exception as e:
                errs.append(f"fast_info: {type(e).__name__}")
            if harga is None:
                try:
                    h = t.history(period="5d")
                    if len(h) and "Close" in h:
                        harga = float(h["Close"].dropna().iloc[-1])
                except Exception as e:
                    errs.append(f"history: {type(e).__name__}")

            sektor = industri = None
            if need_sector or (harga is None and mcap is None):
                try:
                    info = t.get_info()
                except Exception as e:
                    errs.append(f"get_info: {type(e).__name__}")
                    info = {}
                if info:
                    sektor = _get(info, "sector")
                    industri = _get(info, "industry")
                    if harga is None:
                        harga = _first(_get(info, "currentPrice"),
                                       _get(info, "regularMarketPrice"))
                    if mcap is None:
                        mcap = _get(info, "marketCap")

            if harga is None and mcap is None and sektor is None:
                # tidak ada satu pun data — anggap gagal agar retry & tercatat
                raise RuntimeError("; ".join(errs) or "tidak ada data dari Yahoo")

            return {
                "harga": float(harga) if harga is not None else None,
                "mcap": int(mcap) if mcap else None,
                "sektor": sektor,
                "industri": industri,
                "error": ("; ".join(errs) or None),
            }
        except Exception as e:  # jaringan/limit/format
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(sleep_s * (2 ** attempt))
    return {"harga": None, "mcap": None, "sektor": None, "industri": None,
            "error": last_err or "gagal tanpa pesan"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fakta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    ap.add_argument("--sleep", type=float, default=0.6,
                    help="jeda antar kode (detik), hormati rate limit Yahoo")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--refresh-sector", action="store_true",
                    help="paksa ambil ulang sektor/industri semua kode")
    ap.add_argument("--limit", type=int, default=0,
                    help="proses N kode pertama saja (untuk uji coba)")
    ap.add_argument("--dry-run", action="store_true",
                    help="tanpa jaringan: hasilkan kerangka keluaran saja")
    args = ap.parse_args(argv)

    codes = read_codes(args.fakta)
    if args.limit:
        codes = codes[: args.limit]
    existing = load_existing(args.out)
    today = dt.date.today().isoformat()
    t0 = time.time()

    out = dict(existing)
    n_ok_harga = n_ok_sektor = 0
    gagal = []

    for i, kode in enumerate(codes, 1):
        prev = existing.get(kode, {})
        if args.dry_run:
            entry = {"harga": None, "mcap": None,
                     "sektor": prev.get("sektor"),
                     "industri": prev.get("industri"),
                     "error": "dry-run"}
        else:
            need_sector = args.refresh_sector or not prev.get("sektor")
            entry = fetch_one(kode, need_sector, args.sleep, args.retries)
            # pertahankan nilai lama bila pengambilan baru gagal/kosong
            if entry["sektor"] is None:
                entry["sektor"] = prev.get("sektor")
                entry["industri"] = entry["industri"] or prev.get("industri")
            if entry["harga"] is None and prev.get("harga") is not None:
                entry["harga"] = prev["harga"]
                entry["mcap"] = entry["mcap"] or prev.get("mcap")
                entry["error"] = (entry["error"] or "") + " | pakai harga lama"
            time.sleep(args.sleep)

        entry["harga_tanggal"] = today if entry["harga"] is not None else \
            prev.get("harga_tanggal")
        out[kode] = entry
        if entry["harga"] is not None:
            n_ok_harga += 1
        if entry["sektor"]:
            n_ok_sektor += 1
        if entry["error"] and entry["error"] != "dry-run":
            gagal.append((kode, entry["error"]))
        if i % 50 == 0:
            print(f"  {i}/{len(codes)} kode diproses...", file=sys.stderr)

    meta = {
        "dibuat": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "dry-run" if args.dry_run else "live",
        "jumlah_kode": len(codes),
        "harga_terisi": n_ok_harga,
        "sektor_terisi": n_ok_sektor,
        "durasi_detik": round(time.time() - t0, 1),
    }
    payload = {"_meta": meta}
    payload.update({k: out[k] for k in sorted(out)})
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    lines = [
        "# Laporan Pengambilan Data Emiten (yfinance)",
        "",
        f"- Mode: **{meta['mode']}** | Waktu: {meta['dibuat']} | "
        f"Durasi: {meta['durasi_detik']} dtk",
        f"- Kode diproses: {len(codes)}",
        f"- Harga terisi: {n_ok_harga} | Sektor terisi: {n_ok_sektor}",
        f"- Gagal: {len(gagal)}",
    ]
    for k, e in gagal[:30]:
        lines.append(f"    - {k}: {e}")
    if len(gagal) > 30:
        lines.append(f"    - ... (+{len(gagal)-30} lagi)")
    report = "\n".join(lines)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    print(report)

    if not args.dry_run and n_ok_harga == 0:
        print("FATAL: tidak satu pun harga terambil — cek jaringan/limit.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
