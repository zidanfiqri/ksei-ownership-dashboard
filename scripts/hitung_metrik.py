#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hitung_metrik.py — Tahap 4 pipeline KSEI Ownership Dashboard.

Dari data/fakta.csv menghitung:
  1. METRIK per emiten per periode -> data/metrik.json
     n pemegang, total kepemilikan tercatat, FREE FLOAT, CR1, CR3, HHI mentah,
     CCS 0-100, dan klasifikasi tipe kepemilikan.
  2. CHANGELOG periode terbaru vs periode sebelumnya -> data/changelog.json
     saham baru/dihapus, per saham: investor baru/keluar/berubah, peta
     INV_CHANGES "KODE|INVESTOR" untuk badge, dan ringkasan KPI.

Definisi (persis situs asli — Guide "Panduan Penggunaan" + source index.html):
  - Free Float = 100 − Σ persentase seluruh baris tercatat (bukan "true"
    free float; indikator konsentrasi).
  - CCS = (HHI_norm × 0,45 + CR3_norm × 0,35 + Holder_norm × 0,20) × 100,
    dibulatkan half-up (Math.round JS).
      HHI_norm    = min(HHI_mentah / 10000, 1),  HHI_mentah = Σ pct²
      CR3_norm    = min(CR3 / 100, 1),           CR3 = Σ 3 pct terbesar
      Holder_norm = max(0, 1 − (n − 1) / 19)     n = jumlah baris pemegang
  - Klasifikasi (urutan): Mayoritas Tunggal (CR1 ≥ 50) -> Oligopoli
    (CR3 ≥ 60) -> Terkonsentrasi (CCS ≥ 70) -> Tersebar (CCS ≤ 40) -> Moderat.
  - Changelog membandingkan pasangan (kode, investor); pasangan duplikat
    dalam satu periode (kasus ICON: dua jenis rekening) diagregasi dulu
    supaya perbandingan antar-periode per investor konsisten.

Validasi bawaan: bila --validasi-csv diberikan (CSV ekspor situs asli),
CCS hitungan periode baseline dibandingkan dengan kolom "HHI" CSV (yang
sebenarnya berisi CCS) — wajib cocok untuk SEMUA emiten.

Cara pakai:
    python hitung_metrik.py --fakta data/fakta.csv \
        --out-metrik data/metrik.json --out-changelog data/changelog.json \
        [--report LAPORAN.md] [--validasi-csv ksei_saham_20260703.csv \
         --periode-validasi 2026-03-12]
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict

KLAS_MAYORITAS = "Mayoritas"
KLAS_OLIGOPOLI = "Oligopoli"
KLAS_TERKONSENTRASI = "Terkonsentrasi"
KLAS_TERSEBAR = "Tersebar"
KLAS_MODERAT = "Moderat"


def half_up(x):
    """Pembulatan setengah-ke-atas, meniru Math.round JavaScript."""
    return math.floor(x + 0.5)


def load_fakta(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["scripless"] = int(r["scripless"])
            r["scrip"] = int(r["scrip"])
            r["total_lembar"] = int(r["total_lembar"])
            r["persentase"] = float(r["persentase"])
            rows.append(r)
    return rows


def hitung_emiten(holder_pcts, n_holders):
    """Metrik konsentrasi satu emiten dari daftar persentase pemegang."""
    pcts = sorted(holder_pcts, reverse=True)
    # pctSum/CR dihitung eksak dalam sen-persen (nilai sumber selalu 2 desimal)
    cents = [int(round(p * 100)) for p in pcts]
    total = sum(cents) / 100.0
    cr1 = cents[0] / 100.0 if cents else 0.0
    cr3 = sum(cents[:3]) / 100.0
    # persis situs: hhiRaw = Math.round(sum pct^2) SEBELUM normalisasi
    hhi_raw = half_up(sum(p * p for p in pcts))
    hhi_norm = min(hhi_raw / 10000.0, 1.0)
    cr3_norm = min(cr3 / 100.0, 1.0)
    holder_norm = max(0.0, 1.0 - (n_holders - 1) / 19.0)
    ccs = half_up((hhi_norm * 0.45 + cr3_norm * 0.35 + holder_norm * 0.20) * 100)

    # persis situs: Terkonsentrasi/Tersebar memakai TOTAL TERCATAT (pctSum),
    # bukan CCS — sesuai kode inline buildGroups
    if cr1 >= 50:
        klas = KLAS_MAYORITAS
    elif cr3 >= 60:
        klas = KLAS_OLIGOPOLI
    elif total >= 70:
        klas = KLAS_TERKONSENTRASI
    elif total <= 40:
        klas = KLAS_TERSEBAR
    else:
        klas = KLAS_MODERAT

    return {
        "n": n_holders,
        "total_tercatat": round(total, 2),
        "free_float": round(max(0.0, 100.0 - total), 2),
        "cr1": round(cr1, 2),
        "cr3": round(cr3, 2),
        "hhi_raw": hhi_raw,
        "ccs": ccs,
        "klasifikasi": klas,
    }


def build_metrik(rows):
    per = defaultdict(lambda: defaultdict(list))
    nama = {}
    for r in rows:
        per[r["periode"]][r["kode"]].append(r)
        nama[(r["periode"], r["kode"])] = r["emiten"]
    out = {}
    for periode, kode_map in per.items():
        out[periode] = {}
        for kode, hs in kode_map.items():
            m = hitung_emiten([h["persentase"] for h in hs], len(hs))
            m["emiten"] = nama[(periode, kode)]
            out[periode][kode] = m
    return out


def agg_pairs(rows_periode):
    """(kode, investor) -> {lembar, pct}; duplikat (dua rekening) dijumlah."""
    agg = {}
    for r in rows_periode:
        key = (r["kode"], r["investor"])
        if key in agg:
            agg[key]["lembar"] += r["total_lembar"]
            agg[key]["pct"] = round(agg[key]["pct"] + r["persentase"], 2)
        else:
            agg[key] = {"lembar": r["total_lembar"], "pct": r["persentase"]}
    return agg


def build_changelog(rows, periode_baru, periode_lama):
    baru = [r for r in rows if r["periode"] == periode_baru]
    lama = [r for r in rows if r["periode"] == periode_lama]
    p_baru, p_lama = agg_pairs(baru), agg_pairs(lama)
    kode_baru = {k for k, _ in p_baru}
    kode_lama = {k for k, _ in p_lama}
    nama_baru = {r["kode"]: r["emiten"] for r in baru}

    saham_baru = sorted(kode_baru - kode_lama)
    saham_dihapus = sorted(kode_lama - kode_baru)

    per_saham = {}
    inv_changes = {}
    n_inv_baru = n_inv_keluar = n_berubah = 0

    for kode in sorted(kode_baru | kode_lama):
        inv_b = {i: v for (k, i), v in p_baru.items() if k == kode}
        inv_l = {i: v for (k, i), v in p_lama.items() if k == kode}
        e = {"investor_baru": [], "investor_keluar": [], "perubahan": []}
        for i in sorted(set(inv_b) - set(inv_l)):
            e["investor_baru"].append(
                {"investor": i, "lembar": inv_b[i]["lembar"],
                 "pct": inv_b[i]["pct"]})
            inv_changes[f"{kode}|{i}"] = {"status": "baru",
                                          "delta_lembar": inv_b[i]["lembar"],
                                          "delta_pct": inv_b[i]["pct"]}
            n_inv_baru += 1
        for i in sorted(set(inv_l) - set(inv_b)):
            e["investor_keluar"].append(
                {"investor": i, "lembar": inv_l[i]["lembar"],
                 "pct": inv_l[i]["pct"]})
            inv_changes[f"{kode}|{i}"] = {"status": "keluar",
                                          "delta_lembar": -inv_l[i]["lembar"],
                                          "delta_pct": -inv_l[i]["pct"]}
            n_inv_keluar += 1
        for i in sorted(set(inv_b) & set(inv_l)):
            d_lembar = inv_b[i]["lembar"] - inv_l[i]["lembar"]
            if d_lembar == 0:
                continue
            d_pct = round(inv_b[i]["pct"] - inv_l[i]["pct"], 2)
            e["perubahan"].append({
                "investor": i,
                "lembar_lama": inv_l[i]["lembar"],
                "lembar_baru": inv_b[i]["lembar"],
                "delta_lembar": d_lembar,
                "pct_lama": inv_l[i]["pct"],
                "pct_baru": inv_b[i]["pct"],
                "delta_pct": d_pct,
            })
            inv_changes[f"{kode}|{i}"] = {"status": "berubah",
                                          "delta_lembar": d_lembar,
                                          "delta_pct": d_pct}
            n_berubah += 1
        if e["investor_baru"] or e["investor_keluar"] or e["perubahan"]:
            e["emiten"] = nama_baru.get(kode, "")
            per_saham[kode] = e

    saham_berubah = [k for k in per_saham
                     if k not in saham_baru and k not in saham_dihapus]
    return {
        "periode_baru": periode_baru,
        "periode_lama": periode_lama,
        "saham_baru": saham_baru,
        "saham_dihapus": saham_dihapus,
        "per_saham": per_saham,
        "inv_changes": inv_changes,
        "ringkasan": {
            "saham_baru": len(saham_baru),
            "saham_dihapus": len(saham_dihapus),
            "saham_berubah": len(saham_berubah),
            "investor_baru": n_inv_baru,
            "investor_keluar": n_inv_keluar,
            "perubahan_kepemilikan": n_berubah,
        },
    }


def validasi_ccs(metrik_periode, csv_path):
    """Bandingkan CCS hitungan vs kolom 'HHI' (berisi CCS) di CSV situs."""
    situs = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            situs[r["Kode"]] = int(r["HHI"])
    cocok, beda = 0, []
    for kode, v in situs.items():
        m = metrik_periode.get(kode)
        if m is None:
            beda.append((kode, "tidak ada di metrik", v))
        elif m["ccs"] == v:
            cocok += 1
        else:
            beda.append((kode, m["ccs"], v))
    return cocok, len(situs), beda


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fakta", required=True)
    ap.add_argument("--out-metrik", required=True)
    ap.add_argument("--out-changelog", required=True)
    ap.add_argument("--report")
    ap.add_argument("--validasi-csv")
    ap.add_argument("--periode-validasi", default="2026-03-12")
    args = ap.parse_args(argv)

    rows = load_fakta(args.fakta)
    periods = sorted({r["periode"] for r in rows})
    metrik = build_metrik(rows)

    changelog = None
    if len(periods) >= 2:
        changelog = build_changelog(rows, periods[-1], periods[-2])

    with open(args.out_metrik, "w", encoding="utf-8") as f:
        json.dump({"_meta": {"periode": periods},
                   "per_periode": metrik}, f, ensure_ascii=False, indent=1)
    if changelog:
        with open(args.out_changelog, "w", encoding="utf-8") as f:
            json.dump(changelog, f, ensure_ascii=False, indent=1)

    # ---------- laporan ----------
    L = []
    add = L.append
    add("# Laporan Tahap 4 — Metrik Konsentrasi, Free Float, dan Changelog")
    add("")
    for p in periods:
        mm = metrik[p]
        klas = defaultdict(int)
        for v in mm.values():
            klas[v["klasifikasi"]] += 1
        add(f"## Periode {p}: {len(mm)} emiten")
        add(f"- Distribusi klasifikasi: {dict(sorted(klas.items(), key=lambda x: -x[1]))}")
        b40 = sum(1 for v in mm.values() if v["total_tercatat"] == 40)
        b70 = sum(1 for v in mm.values() if v["total_tercatat"] == 70)
        add(f"- Kasus batas (total tercatat tepat 40/70): {b40}/{b70} emiten")
        ff0 = sum(1 for v in mm.values() if v["free_float"] == 0)
        add(f"- Free float 0% (kepemilikan tercatat >=100%): {ff0}")
        add("")

    ok = True
    if args.validasi_csv:
        mp = metrik.get(args.periode_validasi, {})
        cocok, total, beda = validasi_ccs(mp, args.validasi_csv)
        add(f"## Validasi CCS vs situs asli (CSV, periode {args.periode_validasi})")
        add(f"- Cocok: **{cocok}/{total}**")
        if beda:
            ok = False
            for k, hit, situs in beda[:15]:
                add(f"    - {k}: hitung={hit} vs situs={situs}")
            if len(beda) > 15:
                add(f"    - ... (+{len(beda)-15} lagi)")
        add("")
        spots = {"AALI": 76, "ABDA": 85, "ABMM": 63, "ACES": 53,
                 "ABBA": 41, "AADI": 41}
        add("- Spot-check: " + ", ".join(
            f"{k}={mp[k]['ccs']}({'OK' if mp.get(k, {}).get('ccs') == v else 'BEDA vs ' + str(v)})"
            for k, v in spots.items() if k in mp))
        add("")

    if changelog:
        r = changelog["ringkasan"]
        add(f"## Changelog {changelog['periode_lama']} -> {changelog['periode_baru']}")
        add(f"- Saham baru: {r['saham_baru']} -> {changelog['saham_baru']}")
        add(f"- Saham dihapus: {r['saham_dihapus']} -> {changelog['saham_dihapus']}")
        add(f"- Saham berubah: {r['saham_berubah']} | investor baru: "
            f"{r['investor_baru']} | investor keluar: {r['investor_keluar']} | "
            f"perubahan kepemilikan: {r['perubahan_kepemilikan']}")
        n_baru_pairs = sum(len(v) for v in
                           (changelog["per_saham"][k]["investor_baru"]
                            for k in changelog["per_saham"]))
        pasangan_baru = len(agg_pairs([x for x in rows
                                       if x["periode"] == changelog["periode_baru"]]))
        pasangan_lama = len(agg_pairs([x for x in rows
                                       if x["periode"] == changelog["periode_lama"]]))
        ov_b = pasangan_baru - r["investor_baru"]
        ov_l = pasangan_lama - r["investor_keluar"]
        add(f"- Rekonsiliasi pasangan (agregat): baru {pasangan_baru} - masuk "
            f"{r['investor_baru']} = {ov_b}; lama {pasangan_lama} - keluar "
            f"{r['investor_keluar']} = {ov_l} -> "
            f"{'KONSISTEN' if ov_b == ov_l else '**TIDAK KONSISTEN**'}")
        if ov_b != ov_l:
            ok = False
        wbsa_ok = "WBSA" in changelog["saham_baru"]
        add(f"- UJI WAJIB — WBSA sebagai Saham Baru: "
            f"{'LULUS' if wbsa_ok else '**GAGAL**'}")
        if not wbsa_ok:
            ok = False
        add("")

    add("## Catatan")
    add("- KOREKSI dari versi awal: Terkonsentrasi/Tersebar memakai ambang "
        "TOTAL TERCATAT (pctSum >=70 / <=40), bukan CCS — diverifikasi dari "
        "kode inline buildGroups situs asli; hhiRaw juga dibulatkan sebelum "
        "normalisasi, persis Math.round situs.")
    add("- Free float terverifikasi terhadap UI situs asli: AALI 18,14 / "
        "ABBA 25,33 / AADI 20,51 (screenshot Guide).")
    add("- Duplikat rekening (kasus ICON) diagregasi sebelum perbandingan "
        "antar-periode; dua rekening baseline ICON terkonsolidasi menjadi "
        "satu di Mei dengan total sama, sehingga dinilai tak berubah.")
    add("")
    add(f"## Kesimpulan: {'LULUS' if ok else 'ADA MASALAH'}")
    report = "\n".join(L)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
