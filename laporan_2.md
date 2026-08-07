# Laporan Tahap 2 — Tabel Fakta, Baseline, dan Pemetaan Tipe Investor

## Isi tabel fakta
- Periode **2026-03-12** (data.js): 7262 baris, 955 emiten, 5216 investor unik, baris ber-scrip: 1049
- Periode **2026-05-29** (pdf_1pct): 7161 baris, 956 emiten, 5144 investor unik, baris ber-scrip: 1043
- Periode **2026-06-30** (pdf_1pct): 7197 baris, 956 emiten, 5162 investor unik, baris ber-scrip: 1033
- Periode **2026-07-31** (pdf_1pct): 7193 baris, 961 emiten, 5177 investor unik, baris ber-scrip: 1035
- Total baris: **28813**

## Pemetaan klasifikasi PDF -> kode tipe situs

| Klasifikasi PDF | Kode | Dasar | Sampel | Akurasi |
|---|---|---|---|---|
| Individual | ID | empiris | 2319 | 99.8% |
| Corporate | CP | empiris | 1935 | 97.4% |
| Mutual Funds | MF | empiris | 281 | 96.4% |
| Securities Company | SC | empiris | 149 | 100.0% |
| (kosong) | (kosong) | definisi | - |  |
| Private Bank | IB | empiris | 187 | 75.4% |
| Investment Advisors | CP | empiris | 189 | 70.4% |
| Private Equity | CP | empiris | 206 | 72.3% |
| Firm | CP | empiris | 118 | 99.2% |
| Insurance | IS | empiris | 74 | 100.0% |
| Bank | IB | empiris | 106 | 99.1% |
| State Owned Enterprises | IS | empiris | 101 | 86.1% |
| Investment Manager | SC | empiris | 61 | 95.1% |
| Venture Capital | CP | empiris | 46 | 76.1% |
| Pension Funds | PF | empiris | 44 | 100.0% |
| Partnership | OT | empiris | 35 | 100.0% |
| Trustee Bank | IB | empiris | 26 | 65.4% |
| Sovereign Wealth Fund | OT | empiris | 26 | 100.0% |
| Sole Proprietorship | CP | empiris | 22 | 95.5% |
| Government | OT | empiris | 20 | 100.0% |
| Financial Institutional | IB | empiris | 18 | 100.0% |
| PermanentEstablishment | CP | empiris | 14 | 100.0% |
| Exchange Traded Funds | MF | empiris | 12 | 100.0% |
| Commanditaire Vennootschap (CV) Or Limited Partnership | CP | empiris | 9 | 100.0% |
| Capital Market Supporting Institutions And Professions | CP | empiris | 13 | 61.5% |
| Hedge Fund | MF | empiris | 10 | 70.0% |
| Brokerage Firms | CP | empiris | 3 | 100.0% |
| Cooperatives | OT | empiris | 10 | 100.0% |
| Investment Fund Selling Agent | CP | empiris | 8 | 100.0% |
| Foundation | FD | empiris | 6 | 100.0% |
| Peer To Peer Lending | CP | empiris | 2 | 100.0% |
| International Organization | OT | empiris | 3 | 66.7% |
| State Owned Company | CP | empiris | 2 | 100.0% |
| Educational Institution | FD | empiris | 1 | 100.0% |
| Diocese | OT | empiris | 1 | 100.0% |
| Association/Social Organizations | OT | manual | - |  |

Kualitas pemetaan (baris PDF beririsan baseline dgn tipe terisi): **16740/17571 = 95.27%** kode tipe identik dengan baseline.

## Emiten ganti nama antar-periode (informasional, bahan changelog)
- ANTM: 'ANEKA TAMBANG Tbk' -> 'ANEKA TAMBANG (PERSERO) Tbk'
- BMAS: 'BANK MASPION INDONESIA Tbk' -> 'BANK KASIKORN INDONESIA Tbk'
- BRIS: 'BANK SYARIAH INDONESIA Tbk' -> 'BANK SYARIAH INDONESIA (PERSERO) Tbk'
- BVIC: 'BANK VICTORIA INTERNATIONAL Tbk' -> 'BANK VICTORIA INTERNATIONAL  Tbk'
- CNTX: 'CENTEX Tbk' -> 'CENTEX Tbk SERI A PREFEREN'
- CTTH: 'CITATAH Tbk' -> 'CITATAH  Tbk'
- GOLD: 'VISI TELEKOMUNIKASI INFRASTRUKTUR Tbk' -> 'VISI TELEKOMUNIKASI INFRASTRUKTUR Tbk, PT'
- IATA: 'MNC ENERGY INVESTMENTS Tbk' -> 'KARYA PACIFIC ENERGY Tbk'
- KPIG: 'MNC LAND Tbk' -> 'MNC TOURISM INDONESIA Tbk'
- LPPF: 'MATAHARI DEPARTMENT STORE Tbk' -> 'MDS RETAILING Tbk'
- MORA: 'MORA TELEMATIKA INDONESIA Tbk' -> 'EKAMAS MORA REPUBLIK Tbk'
- MTSM: 'METRO REALTY Tbk' -> 'METRO REALTY Tbk, PT'
- NASA: 'ANDALAN PERKASA ABADI Tbk' -> 'ANDALAN PERKASA ABADI  Tbk'
- NATO: 'SURYA PERMATA ANDALAN Tbk' -> 'OLYMPUS STRATEGIC INDONESIA Tbk'
- PTBA: 'BUKIT ASAM Tbk' -> 'BUKIT ASAM (PERSERO) Tbk'
- SMBR: 'SEMEN BATURAJA Tbk' -> 'SEMEN BATURAJA (PERSERO) Tbk'
- SOSS: 'SHIELD ON SERVICE Tbk' -> 'ALSOK INDONESIA SERVICES Tbk'
- SRAJ: 'SEJAHTERARAYA ANUGRAHJAYA Tbk' -> 'SEJAHTERARAYA ANUGRAHJAYA Tbk, PT'
- STAR: 'BUANA ARTHA ANUGERAH Tbk' -> 'CALCULUS GLOBAL VENTURES Tbk'
- SUGI: 'SUGIH ENERGY Tbk' -> 'SUGIH ENERGY Tbk, PT'
- TINS: 'TIMAH Tbk' -> 'TIMAH (PERSERO) Tbk'

## Pemeriksaan integritas
- TOTAL != SCRIPLESS + SCRIP: 1 (semua anomali terdokumentasi)
    - 2026-03-12 MAYA 'MAYAPADA KARUNIA PT' (anomali sumber terdokumentasi)
- Persentase di luar (0, 100]: OK
- Lokal/Asing tak dikenal: OK
- Kode tipe di luar daftar sah: OK
- Duplikat (periode,kode,investor) tak terduga: OK

## Catatan & anomali terdokumentasi
- Baseline ICON memuat 'ISLAND REGENCY GROUP LIMITED' dua baris (rekening scripless + warkat khusus) — dipertahankan, kunci fakta tidak unik.
- Baseline MAYA 'MAYAPADA KARUNIA PT': 0+6.323.076.332 != 6.023.326.332 — salah ketik di sumber asli, diimpor apa adanya.
- lokal_asing PDF dinormalkan L->D agar konsisten dengan situs.
- Nama emiten disimpan per periode; tampilan situs memakai periode terbaru.

## Kesimpulan: LULUS
