# Laporan Tahap 4 — Metrik Konsentrasi, Free Float, dan Changelog

## Periode 2026-03-12: 955 emiten
- Distribusi klasifikasi: {'Mayoritas': 522, 'Oligopoli': 230, 'Terkonsentrasi': 116, 'Moderat': 74, 'Tersebar': 13}
- Kasus batas (total tercatat tepat 40/70): 0/0 emiten
- Free float 0% (kepemilikan tercatat >=100%): 0

## Periode 2026-05-29: 956 emiten
- Distribusi klasifikasi: {'Mayoritas': 531, 'Oligopoli': 225, 'Terkonsentrasi': 115, 'Moderat': 71, 'Tersebar': 14}
- Kasus batas (total tercatat tepat 40/70): 0/0 emiten
- Free float 0% (kepemilikan tercatat >=100%): 0

## Periode 2026-06-30: 956 emiten
- Distribusi klasifikasi: {'Mayoritas': 532, 'Oligopoli': 223, 'Terkonsentrasi': 115, 'Moderat': 72, 'Tersebar': 14}
- Kasus batas (total tercatat tepat 40/70): 0/0 emiten
- Free float 0% (kepemilikan tercatat >=100%): 0

## Periode 2026-07-31: 961 emiten
- Distribusi klasifikasi: {'Mayoritas': 536, 'Oligopoli': 220, 'Terkonsentrasi': 116, 'Moderat': 75, 'Tersebar': 14}
- Kasus batas (total tercatat tepat 40/70): 0/1 emiten
- Free float 0% (kepemilikan tercatat >=100%): 0

## Changelog 2026-06-30 -> 2026-07-31
- Saham baru: 6 -> ['BACH', 'EMMI', 'JECX', 'JELI', 'PRDL', 'RANS']
- Saham dihapus: 1 -> ['CNTX']
- Saham berubah: 529 | investor baru: 361 | investor keluar: 365 | perubahan kepemilikan: 847
- Rekonsiliasi pasangan (agregat): baru 7193 - masuk 361 = 6832; lama 7197 - keluar 365 = 6832 -> KONSISTEN

## Catatan
- KOREKSI dari versi awal: Terkonsentrasi/Tersebar memakai ambang TOTAL TERCATAT (pctSum >=70 / <=40), bukan CCS — diverifikasi dari kode inline buildGroups situs asli; hhiRaw juga dibulatkan sebelum normalisasi, persis Math.round situs.
- Free float terverifikasi terhadap UI situs asli: AALI 18,14 / ABBA 25,33 / AADI 20,51 (screenshot Guide).
- Duplikat rekening (kasus ICON) diagregasi sebelum perbandingan antar-periode; dua rekening baseline ICON terkonsolidasi menjadi satu di Mei dengan total sama, sehingga dinilai tak berubah.

## Kesimpulan: LULUS
