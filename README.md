# IDX 1% Ownership Dashboard

Dashboard transparansi kepemilikan saham Bursa Efek Indonesia (IDX) — menampilkan seluruh investor yang memegang **≥1% saham** di setiap emiten, berdasarkan laporan resmi **KSEI** (Kustodian Sentral Efek Indonesia). Diperkaya dengan skor konsentrasi kepemilikan, pemetaan grup konglomerat, dan penandaan tokoh politik (PEP).

🔗 **Live:** [ksei-ownership-dashboard.vercel.app](https://ksei-ownership-dashboard.vercel.app/)

> Proyek riset & transparansi publik. Bukan rekomendasi jual/beli — selalu cek ulang ke sumber resmi ([ksei.co.id](https://www.ksei.co.id)) sebelum mengambil keputusan investasi.

---

## Fitur Utama

| Tab | Isi |
|---|---|
| 📊 **Ringkasan Saham** | Kartu per emiten: daftar pemegang saham 1%+, skor **CCS** (konsentrasi kepemilikan 0–100), free float, filter (lokal/asing, free float, sektor), search, mode bandingkan hingga 6 saham, graph jaringan koneksi investor, export CSV |
| 👤 **Per Investor** | Kebalikan dari Ringkasan Saham — satu investor, semua saham yang dipegang, estimasi nilai (AUM), filter tipe/asal/label PEP-Konglo |
| 🏢 **Konglo Stocks** | Saham dikelompokkan per grup konglomerat besar Indonesia (kategori Main / Small-Micro / Investor-Sharing) |
| 📈 **Metrik** | Belasan chart analitik: lokal vs asing, tipe investor, top investor, sebaran negara, distribusi CCS, CCS rata-rata per sektor, jejak kepemilikan PEP & Konglo |
| 🕒 **Changelog** | Perbandingan otomatis dua periode terakhir — saham baru/dihapus, investor masuk/keluar, perubahan jumlah kepemilikan |

## Sumber Data

- **Kepemilikan saham** — laporan bulanan KSEI *"Kepemilikan Investor di atas 1%"* (format Excel/PDF)
- **Harga & sektor** — Yahoo Finance (opsional, per emiten)
- **PEP & Konglomerat** — kurasi manual dari sumber publik, untuk tujuan riset, bukan tuduhan

## Struktur Proyek

```
ksei-ownership-dashboard/
├── data/
│   ├── fakta.csv             # tabel fakta gabungan SEMUA periode — sumber kebenaran utama
│   ├── changelog.json        # perbandingan 2 periode terbaru
│   ├── metrik.json           # metrik konsentrasi per emiten per periode
│   ├── pemetaan_tipe.json    # pemetaan klasifikasi investor KSEI -> 9 kode tipe situs
│   └── emiten.json           # (opsional) harga & sektor dari Yahoo Finance
├── docs/                     # di-serve GitHub Pages — INI yang live
│   ├── index.html
│   ├── data.js / changelog_data.js / sector_data.js / price_data.js
│   ├── pep_data.js / konglo_data.js     # kurasi manual, disalin apa adanya saat build
│   └── .nojekyll
├── scripts/
│   ├── parse_1pct.py          # Tahap 1 — parser PDF
│   ├── parse_1pct_xlsx.py     # Tahap 1 — parser Excel (disarankan, jauh lebih stabil)
│   ├── merge_fakta.py         # Tahap 2 — gabung ke fakta.csv (idempoten per periode)
│   ├── fetch_yfinance.py      # Tahap 3 — ambil harga & sektor
│   ├── hitung_metrik.py       # Tahap 4 — hitung CCS/CR1/CR3 & changelog
│   ├── build_site.py          # Tahap 5 — rakit semuanya jadi docs/
│   └── update_periode.py      # Orkestrator — jalankan Tahap 1→5 dari SATU perintah
├── requirements.txt
└── README.md
```

> **Catatan:** `source.html` (template asli aplikasi, dibutuhkan `build_site.py`) sengaja **tidak** disimpan di repo ini — simpan salinannya di tempat aman lokal Anda.

## Cara Kerja: Pipeline 5 Tahap

```
Excel/PDF KSEI ──▶ 1·Parse ──▶ 2·Gabung fakta ──▶ 4·Hitung metrik ──▶ 5·Build situs ──▶ docs/
                                     │
                                     └──▶ 3·Harga & sektor (yfinance) ──▶┘
```

1. **Parse** — baca file laporan KSEI mentah → CSV 12 kolom terstandar (tanggal, kode, nama investor, tipe, jumlah saham, persentase, dst).
2. **Gabung fakta** — masukkan ke `data/fakta.csv` multi-periode; klasifikasi investor dipetakan otomatis via `data/pemetaan_tipe.json` (belajar dari data historis, label baru yang belum pernah muncul akan ditandai untuk keputusan manual).
3. **Harga & sektor** *(opsional)* — perkaya dengan data Yahoo Finance.
4. **Hitung metrik** — CR1/CR3/HHI/CCS per emiten, plus changelog dua periode terbaru.
5. **Build situs** — tempel semua data ke template, hasil akhir masuk `docs/`.

## Setup Awal

```bash
git clone https://github.com/<username-anda>/ksei-ownership-dashboard.git
cd ksei-ownership-dashboard
pip install -r requirements.txt
```

## 🔄 Update Data Bulanan

Setiap KSEI merilis laporan baru:

1. **Unduh** file laporan "1% \<tanggal\> \<bulan\> \<tahun\>" (format `.xlsx` disarankan; `.pdf` juga didukung).
2. **Jalankan satu perintah:**
   ```bash
   python scripts/update_periode.py "1% 31 Agustus 2026.xlsx"
   ```
   Ini otomatis menjalankan Tahap 1 → 2 → 4 → 3 → 5 secara berurutan, berhenti kalau ada tahap yang gagal.
   - Ketinggalan lebih dari satu bulan? Masukkan **semua file sekaligus** dalam satu perintah (bukan satu per satu), supaya pemetaan tipe investor konsisten:
     ```bash
     python scripts/update_periode.py "1% 30 Sep 2026.xlsx" "1% 31 Okt 2026.xlsx"
     ```
   - Mau lewati pengambilan harga (lebih cepat, tanpa internet)? tambahkan `--skip-harga`.
   - Tahap 5 (build situs) hanya jalan kalau `source.html` ada di root folder.
3. **Cek laporan** yang tercetak di terminal. Kalau ada klasifikasi investor baru yang belum punya pemetaan ("tanpa-bukti"), buka `data/pemetaan_tipe.json` dan isi manual kode tipenya (`CP`/`ID`/`IB`/`IS`/`OT`/`MF`/`PF`/`SC`/`FD`), lalu jalankan ulang langkah 2 (aman, idempoten).
4. **Review** `git diff` / buka `docs/index.html` di browser untuk memastikan tampilannya benar.
5. **Commit & push:**
   ```bash
   git add -A
   git commit -m "Update periode <bulan> <tahun>"
   git push
   ```

## Catatan & Keterbatasan

- Tahap 3 (harga/sektor) butuh koneksi internet aktif ke Yahoo Finance saat dijalankan — kalau dilewati, badge harga/sektor sederhananya tidak muncul (bukan error).
- Data PEP & grup konglomerat dikurasi independen dari sumber publik untuk tujuan riset dan edukasi, bukan tuduhan hukum atau saran finansial.
- Free float di sini = 100% dikurangi total kepemilikan tercatat 1%+; ini indikator konsentrasi, bukan definisi *free float* yang presisi secara regulasi.

## Tech Stack

- **Pipeline data:** Python (`pdfplumber`, `pandas`, `openpyxl`, `yfinance`)
- **Frontend:** HTML/CSS/JavaScript murni (tanpa build step) + [Chart.js](https://www.chartjs.org/) untuk grafik + [D3.js](https://d3js.org/) untuk graph jaringan
- **Hosting:** GitHub Pages

## Kredit

- Sumber data: **KSEI** (Kustodian Sentral Efek Indonesia)
- Harga & sektor: **Yahoo Finance**
- Dibangun oleh [@alphamarett](https://www.threads.com/@alphamarett) — [dukung update di sini](https://sawerin.vercel.app/)

## Disclaimer

Dashboard ini dibuat untuk tujuan riset dan transparansi publik. Data disajikan apa adanya dari sumber resmi tanpa jaminan akurasi 100%. Selalu verifikasi ke sumber resmi sebelum mengambil keputusan finansial apa pun.
