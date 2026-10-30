# SOKA LLFD Monitoring Dashboard

Dashboard monitoring lokal untuk membaca hasil eksperimen LLFD dari folder
`realworld/results/sessions/`. Dashboard tidak mengubah algoritma scheduler,
topologi Docker/Kubernetes, maupun format hasil eksperimen.

## Fitur

- Ringkasan jumlah task, task selesai, predicted makespan, dan real execution time.
- Distribusi accumulated load setiap VM.
- Ringkasan topologi DC-1, host, dan empat VM.
- Metrik optimasi LLFD jika tersedia pada `summary.csv`.
- Tabel task assignment dari `mappings/llfd_mapping*.json`.
- Event log dari seluruh file `.log` pada session terbaru.
- Status container Docker jika perintah `docker ps` tersedia.
- Auto-refresh setiap 3 detik.

## Menjalankan

Dari root repository:

```bash
chmod +x dashboard/run_dashboard.sh
./dashboard/run_dashboard.sh
```

Buka browser:

```text
http://127.0.0.1:8080
```

Jalankan eksperimen di terminal lain:

```bash
./run.sh plan
```

atau untuk eksekusi pada Docker:

```bash
./run.sh docker
```

Untuk Kubernetes:

```bash
./run.sh kind
```

Dashboard membaca session terbaru dari `realworld/results/sessions/`.
Refresh otomatis berjalan setiap 3 detik. Dashboard dapat dibuka sebelum
eksperimen dimulai; data akan muncul setelah runner membuat session dan file
hasilnya.

## Mengubah port

```bash
DASHBOARD_PORT=8090 ./dashboard/run_dashboard.sh
```

Lalu buka `http://127.0.0.1:8090`.

## Struktur file

```text
dashboard/
├── server.py
├── index.html
├── run_dashboard.sh
└── static/
    ├── css/
    │   └── dashboard.css
    └── js/
        └── dashboard.js
```

## Catatan interpretasi

- `Predicted makespan` adalah estimasi scheduler berdasarkan `lengthMI / MIPS`.
- `Real execution` berasal dari `llfd-result.json`, yang dibuat pada mode
  eksekusi (Docker/Kind), bukan mode `plan`.
- Progress completed hanya dihitung dari hasil task aktual di `llfd-result.json`.
  Dashboard tidak menganggap task yang baru dialokasikan sebagai task selesai.
- Status worker pada panel infrastruktur dibaca dari Docker. Untuk Kubernetes,
  gunakan status Pod melalui `kubectl`; panel ini tidak mengklaim status Pod
  Kubernetes sebagai status Docker.
- Event log adalah tail dari file log session terbaru, bukan stream stdout
  langsung. File yang sedang bertambah akan terlihat pada refresh berikutnya.
- Dashboard ini ditujukan untuk penggunaan lokal/demo. Server tidak memiliki
  autentikasi dan sebaiknya tidak diekspos langsung ke internet.
- Grafik beban prediksi per VM (bar chart), distribusi jumlah task per VM
  (doughnut chart), dan estimasi durasi per task (line chart). Grafik dirender
  langsung menggunakan Canvas browser tanpa library eksternal.
