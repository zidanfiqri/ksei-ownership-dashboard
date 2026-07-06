#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_site.py — Tahap 5 pipeline KSEI Ownership Dashboard.

Merakit situs statis (folder docs/, disajikan GitHub Pages) dari:
  - source.html        : aplikasi index.html ASLI (View frame source) — tidak
                         diubah kecuali patch label tanggal header & guide.
  - data/fakta.csv     : sumber KSEI_DATA (periode terbaru).
  - data/changelog.json: sumber CHANGELOG_DATA / INV_CHANGES / label periode.
  - data/emiten.json   : (opsional) sumber SECTOR_DATA & PRICE_DATA — bila
                         belum ada, keduanya kosong dan pill tidak tampil,
                         persis perilaku situs asli saat data tak tersedia.
  - pep_data.js, konglo_data.js : kurasi manual — disalin apa adanya.

Keluaran docs/: index.html, data.js, changelog_data.js, sector_data.js,
price_data.js, pep_data.js, konglo_data.js, .nojekyll

Kontrak data (diekstrak dari kode inline source.html — JANGAN diubah tanpa
memeriksa konsumennya):
  KSEI_DATA        : [{share_code, issuer_name, investor_name, investor_type,
                       local_foreign, nationality, domicile,
                       holdings_scripless, holdings_scrip,
                       total_holding_shares, percentage}]
  SECTOR_DATA      : {KODE: {sector, industry}}
  PRICE_DATA       : {KODE: {p, mc}}
  CHANGELOG_DATA   : {new_stocks:[{share_code, issuer_name,
                        investors:[{investor_name, shares, percentage}]}],
                      removed_stocks:[{share_code, issuer_name}],
                      changes:[{share_code, issuer_name,
                        new_investors:[{investor_name, shares, percentage}],
                        removed_investors:[{investor_name, shares, percentage}],
                        share_changes:[{investor_name, old_shares, new_shares,
                                        share_diff, pct_diff}]}]}
  INV_CHANGES      : {"KODE|INVESTOR": {is_new, shares, percentage} |
                      {share_diff, pct_diff}}
  CHANGELOG_DATA_DATE / CHANGELOG_PREV_DATE : label periode (string).

Cara pakai:
    python scripts/build_site.py --source source.html --fakta data/fakta.csv \
        --changelog data/changelog.json --emiten data/emiten.json \
        --pep pep_data.js --konglo konglo_data.js --docs docs \
        [--periode 2026-05-29] [--report LAPORAN.md]
"""

import argparse
import csv
import json
import os
import re
import shutil
import sys

BULAN_ID = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei",
            6: "Juni", 7: "Juli", 8: "Agustus", 9: "September",
            10: "Oktober", 11: "November", 12: "Desember"}

HEADER_LAMA = ("Per 27 Feb 2026 &nbsp;\u00b7&nbsp; Sumber: KSEI "
               "&nbsp;\u00b7&nbsp; Harga: 12 Mar 2026")
GUIDE_PERIODE_LAMA = "Per 12 Maret 2026"
GUIDE_PEMBANDING_LAMA = "3 Maret 2026"


def tgl_id(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {BULAN_ID[int(m)]} {y}"


def load_fakta(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def buat_ksei_data(rows, periode):
    rec = []
    for r in rows:
        if r["periode"] != periode:
            continue
        rec.append({
            "share_code": r["kode"],
            "issuer_name": r["emiten"],
            "investor_name": r["investor"],
            "investor_type": r["tipe"],
            "local_foreign": r["lokal_asing"],
            "nationality": r["nasionalitas"],
            "domicile": r["domisili"],
            "holdings_scripless": int(r["scripless"]),
            "holdings_scrip": int(r["scrip"]),
            "total_holding_shares": int(r["total_lembar"]),
            "percentage": float(r["persentase"]),
        })
    rec.sort(key=lambda x: (x["share_code"], -x["percentage"],
                            x["investor_name"]))
    return rec


def buat_changelog_js(cl, nama_baru, nama_lama):
    def inv_baru(items):
        return [{"investor_name": i["investor"], "shares": i["lembar"],
                 "percentage": i["pct"]} for i in items]

    new_stocks = []
    for kode in cl["saham_baru"]:
        e = cl["per_saham"].get(kode, {})
        new_stocks.append({
            "share_code": kode,
            "issuer_name": nama_baru.get(kode, ""),
            "investors": inv_baru(e.get("investor_baru", [])),
        })
    removed_stocks = [{"share_code": k, "issuer_name": nama_lama.get(k, "")}
                      for k in cl["saham_dihapus"]]

    changes = []
    for kode in sorted(cl["per_saham"]):
        if kode in cl["saham_baru"] or kode in cl["saham_dihapus"]:
            continue
        e = cl["per_saham"][kode]
        changes.append({
            "share_code": kode,
            "issuer_name": nama_baru.get(kode, e.get("emiten", "")),
            "new_investors": inv_baru(e.get("investor_baru", [])),
            "removed_investors": inv_baru(e.get("investor_keluar", [])),
            "share_changes": [{
                "investor_name": p["investor"],
                "old_shares": p["lembar_lama"],
                "new_shares": p["lembar_baru"],
                "share_diff": p["delta_lembar"],
                "pct_diff": p["delta_pct"],
            } for p in e.get("perubahan", [])],
        })

    inv_changes = {}
    for key, v in cl["inv_changes"].items():
        if v["status"] == "baru":
            inv_changes[key] = {"is_new": True,
                                "shares": v["delta_lembar"],
                                "percentage": v["delta_pct"]}
        elif v["status"] == "berubah":
            inv_changes[key] = {"share_diff": v["delta_lembar"],
                                "pct_diff": v["delta_pct"]}
        # status "keluar": tidak dikonsumsi kartu (investornya tak tampil)

    data = {"new_stocks": new_stocks, "removed_stocks": removed_stocks,
            "changes": changes}
    return data, inv_changes


def dump_js(nama, obj):
    return f"const {nama} = " + json.dumps(
        obj, ensure_ascii=False, separators=(",", ":")) + ";\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--fakta", required=True)
    ap.add_argument("--changelog", required=True)
    ap.add_argument("--emiten")
    ap.add_argument("--pep", required=True)
    ap.add_argument("--konglo", required=True)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--periode", help="default: periode terbaru di fakta")
    ap.add_argument("--report")
    args = ap.parse_args(argv)

    rows = load_fakta(args.fakta)
    periods = sorted({r["periode"] for r in rows})
    periode = args.periode or periods[-1]
    if periode not in periods:
        print(f"FATAL: periode {periode} tidak ada di fakta ({periods})",
              file=sys.stderr)
        return 2

    with open(args.changelog, encoding="utf-8") as f:
        cl = json.load(f)

    nama = {}
    for r in rows:
        nama.setdefault(r["periode"], {})[r["kode"]] = r["emiten"]
    nama_baru = nama.get(cl["periode_baru"], {})
    nama_lama = nama.get(cl["periode_lama"], {})

    ksei = buat_ksei_data(rows, periode)
    cl_data, inv_changes = buat_changelog_js(cl, nama_baru, nama_lama)

    sector, price = {}, {}
    harga_tanggal = None
    if args.emiten and os.path.exists(args.emiten):
        with open(args.emiten, encoding="utf-8") as f:
            em = json.load(f)
        meta = em.pop("_meta", {})
        if meta.get("mode") == "live":
            harga_tanggal = (meta.get("dibuat") or "")[:10] or None
            for k, v in em.items():
                if v.get("sektor"):
                    sector[k] = {"sector": v["sektor"],
                                 "industry": v.get("industri") or ""}
                if v.get("harga") is not None and v.get("mcap"):
                    price[k] = {"p": v["harga"], "mc": v["mcap"]}
                    if not harga_tanggal and v.get("harga_tanggal"):
                        harga_tanggal = v["harga_tanggal"]

    # ---------- index.html: patch label tanggal (wajib persis ketemu) ----------
    src = open(args.source, encoding="utf-8").read()
    disp_baru = tgl_id(periode)
    disp_lama = tgl_id(cl["periode_lama"]) if periode == cl["periode_baru"] \
        else "-"
    disp_harga = tgl_id(harga_tanggal) if harga_tanggal else disp_baru
    ganti = [
        (HEADER_LAMA,
         f"Per {disp_baru} &nbsp;\u00b7&nbsp; Sumber: KSEI "
         f"&nbsp;\u00b7&nbsp; Harga: {disp_harga}"),
        (GUIDE_PERIODE_LAMA, f"Per {disp_baru}"),
        (GUIDE_PEMBANDING_LAMA, disp_lama),
    ]
    # Dua fase agar hasil patch tidak menabrak literal berikutnya
    # (mis. build baseline membuat header berisi "Per 12 Maret 2026").
    n_ganti = []
    for i, (lama, _) in enumerate(ganti):
        n = src.count(lama)
        if n == 0:
            print(f"FATAL: literal patch tidak ditemukan: {lama!r}",
                  file=sys.stderr)
            return 2
        n_ganti.append(n)
        src = src.replace(lama, f"\x00PATCH{i}\x00")
    for i, (_, baru) in enumerate(ganti):
        src = src.replace(f"\x00PATCH{i}\x00", baru)

    # Dua tanggal changelog dideklarasikan INLINE di source asli
    # (const CHANGELOG_DATA_DATE / CHANGELOG_PREV_DATE) — patch nilainya di
    # tempat, JANGAN dideklarasikan lagi di changelog_data.js (menyebabkan
    # "Identifier ... has already been declared").
    for var, val in [("CHANGELOG_DATA_DATE", tgl_id(cl["periode_baru"])),
                     ("CHANGELOG_PREV_DATE", tgl_id(cl["periode_lama"]))]:
        pat = re.compile(r"const " + var + r" = '[^']*';")
        src, n = pat.subn(
            (lambda v: lambda m: f"const {var} = {json.dumps(v)};")(val),
            src, count=1)
        if n != 1:
            print(f"FATAL: deklarasi inline {var} tak ditemukan tepat 1x "
                  f"(n={n})", file=sys.stderr)
            return 2

    # ---------- tulis docs/ ----------
    os.makedirs(args.docs, exist_ok=True)
    out = {}
    out["index.html"] = src
    out["data.js"] = dump_js("KSEI_DATA", ksei)
    out["changelog_data.js"] = (
        dump_js("CHANGELOG_DATA", cl_data)
        + dump_js("INV_CHANGES", inv_changes))
    out["sector_data.js"] = dump_js("SECTOR_DATA", sector)
    out["price_data.js"] = dump_js("PRICE_DATA", price)
    for name, content in out.items():
        with open(os.path.join(args.docs, name), "w", encoding="utf-8") as f:
            f.write(content)
    shutil.copy(args.pep, os.path.join(args.docs, "pep_data.js"))
    shutil.copy(args.konglo, os.path.join(args.docs, "konglo_data.js"))
    open(os.path.join(args.docs, ".nojekyll"), "w").close()

    # ---------- laporan ----------
    L = [
        "# Laporan Build Situs (Tahap 5)",
        "",
        f"- Periode tampil: **{periode}** ({tgl_id(periode)}) | "
        f"pembanding: {cl['periode_lama']}",
        f"- KSEI_DATA: {len(ksei)} baris, "
        f"{len({r['share_code'] for r in ksei})} emiten",
        f"- CHANGELOG: baru {len(cl_data['new_stocks'])}, dihapus "
        f"{len(cl_data['removed_stocks'])}, berubah {len(cl_data['changes'])}; "
        f"INV_CHANGES: {len(inv_changes)} kunci",
        f"- SECTOR_DATA: {len(sector)} kode | PRICE_DATA: {len(price)} kode"
        + ("" if sector or price else
           "  (emiten.json belum ada/belum live -> pill tidak tampil dulu)"),
        f"- Patch label: header 'Per {disp_baru}', harga '{disp_harga}', "
        f"guide pembanding '{disp_lama}'",
    ]
    report = "\n".join(L)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
