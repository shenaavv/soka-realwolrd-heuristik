# LLFD Real-World Cloud

## Strategi Optimasi Komputasi Awan (SOKA)

Implementasi real-world cloud untuk penjadwalan task menggunakan algoritma
**Least-Loaded First-Fit Decreasing (LLFD)**. Infrastruktur dijalankan dengan
Docker dan Kubernetes, sedangkan hasil eksperimen disimpan dalam format
terstruktur seperti project simulator pada referensi.

## Anggota Tim

| No | Nama                   | NRP        |
| -- | ---------------------- | ---------- |
| 1  | Kanafira Vanesha Putri | 5027241010 |
| 2  | Tiara Putri Prasetya   | 5027241013 |
| 3  | Dina Rahmadani         | 5027241065 |
| 4  | Zahra Khaalishah       | 5027241070 |
| 5  | S. Farhan Baig         | 5027241097 |

## Daftar Isi

- [1. Pendahuluan](#1-pendahuluan)
- [2. Tujuan dan Ketentuan](#2-tujuan-dan-ketentuan)
- [3. Algoritma LLFD](#3-algoritma-llfd)
- [4. Arsitektur Datacenter](#4-arsitektur-datacenter)
- [5. Pemetaan Simulasi ke Real-World](#5-pemetaan-simulasi-ke-real-world)
- [6. Dataset dan Parameter](#6-dataset-dan-parameter)
- [7. Struktur Repository](#7-struktur-repository)
- [8. Format Hasil Eksperimen](#8-format-hasil-eksperimen)
- [9. Persyaratan Sistem](#9-persyaratan-sistem)
- [10. Cara Menjalankan](#10-cara-menjalankan)
- [11. Menjalankan Docker](#11-menjalankan-docker)
- [12. Menjalankan Kubernetes](#12-menjalankan-kubernetes)
- [13. Contoh Hasil](#13-contoh-hasil)
- [14. Verifikasi Topologi](#14-verifikasi-topologi)
- [15. Batasan Implementasi](#15-batasan-implementasi)
- [16. Kesimpulan](#16-kesimpulan)
- [17. Dataset Google Cluster Workload Trace](#17-dataset-google-cluster-workload-trace)

---

## 1. Pendahuluan

Pada lingkungan cloud, task dengan panjang dan kebutuhan pemrosesan yang
berbeda harus dialokasikan ke beberapa VM. Setiap VM memiliki jumlah PE dan
kecepatan MIPS yang berbeda. Penjadwal harus memilih VM yang sesuai tanpa
menumpuk seluruh task pada satu VM tercepat.

Project ini mengimplementasikan LLFD dalam lingkungan real-world:

1. Task dibaca dari dataset.
2. Task diurutkan menurun berdasarkan `lengthMI`.
3. Setiap task dialokasikan ke VM yang memenuhi kebutuhan PE dan memiliki
   accumulated load paling kecil.
4. Mapping disimpan ke file JSON dan CSV.
5. Pada mode Docker, task dikirim ke worker HTTP yang berjalan sebagai container.
6. Pada mode Kubernetes, worker dijalankan sebagai Pod pada node host yang
   sesuai.

---

## 2. Tujuan dan Ketentuan

Implementasi ini memenuhi ketentuan berikut:

| Ketentuan | Implementasi |
|---|---|
| Algoritma | Least-Loaded First-Fit Decreasing |
| Datacenter | 1 datacenter logis, `DC-1` |
| Host | Minimal 2 host, tersedia `host-1` dan `host-2` |
| VM per host | Minimal 2 VM per host |
| Total VM | 4 VM |
| Containerization | Docker Compose |
| Orchestration | Kubernetes Kind |
| Output | JSON mapping, CSV task, summary CSV, log |
| Entry point | `run.sh` |

Topologi yang digunakan:

```text
DC-1
├── host-1
│   ├── vm-1
│   └── vm-2
└── host-2
    ├── vm-3
    └── vm-4
```

---

## 3. Algoritma LLFD

LLFD menggabungkan dua strategi greedy:

### 3.1 First-Fit Decreasing

Seluruh task diurutkan berdasarkan `lengthMI` dari terbesar ke terkecil.
Task yang paling berat dialokasikan lebih dahulu agar beban besar tidak
terlambat diproses.

### 3.2 Least-Loaded

Untuk setiap task, scheduler membentuk daftar VM yang memenuhi:

```text
vm.PEs >= task.PEs
```

Dari VM yang feasible, dipilih VM dengan accumulated load terkecil.

Accumulated load dihitung dengan:

```text
vmLoad[j] += task.lengthMI / vm.MIPS
```

### 3.3 Pseudocode

```text
LLFD(tasks, vms):
    urutkan tasks menurun berdasarkan lengthMI
    vmLoad[j] = 0 untuk setiap VM

    untuk setiap task:
        feasible = semua VM dengan VM.PEs >= task.PEs

        jika feasible tidak kosong:
            bestVm = VM dengan vmLoad terkecil di feasible
        jika tidak:
            bestVm = VM dengan vmLoad terkecil dari semua VM

        assign task ke bestVm
        vmLoad[bestVm] += task.lengthMI / bestVm.MIPS

    kembalikan mapping dan vmLoad
```

### 3.4 Kompleksitas

Dengan `N` task dan `M` VM, kompleksitas implementasi adalah sekitar
`O(N log N + N x M)`: sorting task membutuhkan `O(N log N)` dan pencarian VM
untuk setiap task membutuhkan `O(M)`.

### 3.5 Implementasi Kode

Implementasi scheduler berada di
[realworld/llfd_scheduler.py](realworld/llfd_scheduler.py). Scheduler tidak
hanya menghasilkan dokumentasi, tetapi dipanggil langsung oleh
[realworld/llfd_runner.py](realworld/llfd_runner.py) sebelum task dikirim ke
worker.

---

## 4. Arsitektur Datacenter

### 4.1 Spesifikasi Topologi

| Datacenter | Host | VM | PE | MIPS per PE | Endpoint Docker |
|---|---|---|---:|---:|---|
| DC-1 | host-1 | vm-1 | 4 | 2.500 | `localhost:9101` |
| DC-1 | host-1 | vm-2 | 2 | 1.500 | `localhost:9102` |
| DC-1 | host-2 | vm-3 | 4 | 2.500 | `localhost:9103` |
| DC-1 | host-2 | vm-4 | 2 | 1.500 | `localhost:9104` |

Kapasitas teoritis VM dihitung dari:

```text
capacity = PE x MIPS
```

Sehingga:

| VM | Kapasitas |
|---|---:|
| vm-1 | 10.000 MIPS |
| vm-2 | 3.000 MIPS |
| vm-3 | 10.000 MIPS |
| vm-4 | 3.000 MIPS |

### 4.2 Representasi Docker

Pada Docker Compose:

- satu service = satu VM;
- satu container menjalankan satu worker;
- `cpu_quota` membatasi kapasitas CPU relatif VM;
- label `soka.datacenter`, `soka.host`, dan `soka.vm` menyimpan metadata
  topologi;
- satu network Docker bernama `llfd-dc-1` mewakili DC-1.

### 4.3 Representasi Kubernetes

Pada Kubernetes:

- namespace `dc-1` mewakili DC-1;
- dua node worker diberi label `soka.host=host-1` dan
  `soka.host=host-2`;
- setiap Deployment memiliki satu replica;
- `nodeSelector` memastikan VM berada pada host yang benar;
- empat Deployment menghasilkan empat Pod/VM;
- setiap VM memiliki Service internal.

Konfigurasi Kind berada di
[realworld/kind-config.yaml](realworld/kind-config.yaml), sedangkan resource
Kubernetes berada di [realworld/k8s-topology.yaml](realworld/k8s-topology.yaml).

---

## 5. Pemetaan Simulasi ke Real-World

| Konsep scheduler/cloud | Implementasi real-world |
|---|---|
| Datacenter | Docker network atau Kubernetes namespace |
| Host | Docker label atau Kubernetes worker node |
| VM | Docker container atau Kubernetes Pod |
| PE | Field `pes` pada konfigurasi VM |
| MIPS | Parameter scheduler dan CPU quota/limit |
| Cloudlet/task | Object task dari dataset |
| Broker | `llfd_runner.py` |
| Cloudlet scheduler | `llfd_scheduler.py` |
| Execution time | `lengthMI / MIPS` untuk prediksi |
| Worker execution | CPU-bound loop pada `worker.py` |
| Mapping | `mappings/llfd_mapping.json` |

Worker menyediakan endpoint:

```text
GET  /health
POST /batch
```

`/health` digunakan untuk memastikan worker hidup. `/batch` menerima daftar
task dan menjalankannya satu per satu secara FIFO.

---

## 6. Dataset dan Parameter

Dataset seed default berada di
[src/main/resources/dataset/google_cluster_trace_sample.txt](src/main/resources/dataset/google_cluster_trace_sample.txt).
Formatnya adalah satu nilai `lengthMI` per baris:

```text
900000
600000
450000
300000
150000
100000
75000
50000
```

Komentar dengan tanda `#` dan pemisah spasi, koma, atau titik koma dapat
digunakan oleh parser.

Dataset lain dapat digunakan tanpa mengubah kode:

```bash
DATASET=src/main/resources/dataset/dataset-lain.txt ./run.sh plan
```

Parameter yang digunakan:

| Parameter | Nilai default | Keterangan |
|---|---:|---|
| `iterations-per-mi` | 2 | Beban CPU worker per MI |
| jumlah task | 8 | Berdasarkan dataset default |
| jumlah host | 2 | `host-1`, `host-2` |
| jumlah VM | 4 | Dua VM per host |

---

## 7. Struktur Repository

```text
.
├── README.md
├── docs/
│   └── architecture.md
├── scripts/
│   ├── run_all.sh
│   └── run_llfd.sh
├── src/
│   └── main/
│       └── resources/
│           └── dataset/
│               └── google_cluster_trace_sample.txt
├── realworld/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── kind-config.yaml
│   ├── k8s-topology.yaml
│   ├── llfd_runner.py
│   ├── llfd_scheduler.py
│   ├── worker/
│   │   └── worker.py
│   └── results/
│       ├── README.md
│       └── sessions/
│           ├── README.md
│           └── <timestamp>/
│               ├── logs/
│               │   └── llfd.log
│               ├── mappings/
│               │   └── llfd_mapping.json
│               ├── parameters.txt
│               ├── summary.csv
│               └── tasks_LLFD_n<N>_run1.csv
├── run.sh
└── .gitignore
```

---

## 8. Format Hasil Eksperimen

Setiap eksekusi membuat folder baru:

```text
realworld/results/sessions/YYYYMMDD_HHMMSS/
```

### 8.1 `parameters.txt`

Menyimpan konfigurasi eksperimen:

```text
algorithm=LLFD
datacenter=DC-1
hosts=2
vms_per_host=2
dataset=...
mode=plan
```

### 8.2 `logs/llfd.log`

Menyimpan output terminal scheduler, termasuk jumlah task, makespan prediksi,
dan jumlah task yang dialokasikan ke setiap VM.

### 8.3 `mappings/llfd_mapping.json`

Menyimpan:

- daftar task;
- daftar VM;
- host setiap VM;
- assignment task ke VM;
- predicted execution time;
- accumulated load;
- predicted makespan.

### 8.4 `tasks_LLFD_n<N>_run1.csv`

Berisi mapping per task:

```csv
task_id,lengthMI,pes,vm,host,predicted_seconds
```

### 8.5 `summary.csv`

Berisi ringkasan:

```csv
algorithm,datacenter,hosts,vms,tasks,predicted_makespan_seconds
LLFD,DC-1,2,4,8,400.0
```

---

## 9. Persyaratan Sistem

### Mode plan

- Python 3.10 atau lebih baru
- Bash

### Mode Docker

- Docker Engine atau Docker Desktop
- Docker Compose v2
- Python 3.10 atau lebih baru

### Mode Kubernetes

- Docker
- Kind
- kubectl
- Python 3.10 atau lebih baru

Mode `plan` tidak membutuhkan Docker maupun Kubernetes.

---

## 10. Cara Menjalankan

Berikan izin eksekusi jika diperlukan:

```bash
chmod +x run.sh scripts/*.sh
```

### 10.1 Membuat Plan Saja

```bash
./run.sh plan
```

Perintah ini membaca dataset, menjalankan LLFD, dan membuat semua hasil
eksperimen tanpa menyalakan container.

### 10.2 Menggunakan Wrapper Script

```bash
./scripts/run_all.sh plan
./scripts/run_llfd.sh plan
```

### 10.3 Memilih Dataset

```bash
DATASET=src/main/resources/dataset/google_cluster_trace_sample.txt ./run.sh plan
```

### 10.4 Memilih Folder Hasil

```bash
RESULTS_DIR=realworld/results/sessions/manual-run ./run.sh plan
```

---

## 11. Menjalankan Docker

Mode Docker menjalankan proses berikut:

1. build image worker;
2. membuat satu network DC-1;
3. menjalankan empat container VM;
4. menjalankan scheduler LLFD;
5. mengirim task ke worker;
6. menyimpan hasil dan log;
7. mematikan container melalui cleanup otomatis.

Jalankan:

```bash
./run.sh docker
```

Periksa worker:

```bash
docker compose -f realworld/docker-compose.yml ps
docker logs llfd-vm-1
```

Jika Docker tidak tersedia, gunakan `./run.sh plan` untuk menghasilkan mapping
dan hasil analisis algoritma.

---

## 12. Menjalankan Kubernetes

### 12.1 Membuat Cluster

```bash
kind create cluster --config realworld/kind-config.yaml --name llfd
```

### 12.2 Build dan Load Image

```bash
docker build -t llfd-worker:1.0 realworld
kind load docker-image llfd-worker:1.0 --name llfd
```

### 12.3 Deploy Topologi

```bash
kubectl apply -f realworld/k8s-topology.yaml
kubectl -n dc-1 rollout status deployment --timeout=120s
kubectl -n dc-1 get pods -o wide
```

### 12.4 Port Forward

Buka empat terminal atau jalankan sebagai proses background:

```bash
kubectl -n dc-1 port-forward svc/vm-1 9101:8000
kubectl -n dc-1 port-forward svc/vm-2 9102:8000
kubectl -n dc-1 port-forward svc/vm-3 9103:8000
kubectl -n dc-1 port-forward svc/vm-4 9104:8000
```

Kemudian jalankan:

```bash
./run.sh plan
```

Untuk menutup resource:

```bash
kubectl delete -f realworld/k8s-topology.yaml
kind delete cluster --name llfd
```

Mode Kubernetes otomatis tersedia melalui:

```bash
./run.sh kind
```

Mode `kind` benar-benar menjalankan alur Kubernetes, bukan hanya membuat plan:

1. membuat cluster Kind dengan dua node worker;
2. memberi label `host-1` dan `host-2`;
3. build dan load image worker;
4. deploy satu namespace `dc-1` dengan empat Deployment/Pod;
5. menunggu seluruh Pod siap;
6. menjalankan empat port-forward service;
7. memeriksa endpoint health setiap VM;
8. menjalankan LLFD dan mengirim task ke worker Kubernetes;
9. menyimpan hasil task, mapping, summary, dan log;
10. menghapus port-forward, resource, dan cluster saat selesai.

---

## 13. Contoh Hasil

Perintah:

```bash
./run.sh plan
```

Contoh output lengkap di terminal:

```text
session=20261028_225126
algorithm=LLFD
datacenter=DC-1
hosts=2
vms_per_host=2
mode=plan

==============================================================================
LLFD REAL-WORLD EXPERIMENT
==============================================================================
algorithm       : LLFD (Least-Loaded First-Fit Decreasing)
mode            : plan
datacenter      : DC-1
hosts           : 2
vm per host     : 2
total VM        : 4
total task      : 8
total length MI : 2,625,000
------------------------------------------------------------------------------
TOPOLOGY
  DC-1/host-1
    vm-1: 4 PE x 2,500 MIPS -> http://127.0.0.1:9101
    vm-2: 2 PE x 1,500 MIPS -> http://127.0.0.1:9102
  DC-1/host-2
    vm-3: 4 PE x 2,500 MIPS -> http://127.0.0.1:9103
    vm-4: 2 PE x 1,500 MIPS -> http://127.0.0.1:9104
------------------------------------------------------------------------------
SCHEDULING TRACE (FFD order, then least accumulated load)
order  task     lengthMI     VM     host      exec(s)  fallback
    1     0      900,000   vm-1   host-1      360.000     False
    2     1      600,000   vm-2   host-1      400.000     False
    3     2      450,000   vm-3   host-2      180.000     False
    4     3      300,000   vm-4   host-2      200.000     False
    5     4      150,000   vm-3   host-2       60.000     False
    6     5      100,000   vm-4   host-2       66.667     False
    7     6       75,000   vm-3   host-2       30.000     False
    8     7       50,000   vm-4   host-2       33.333     False
------------------------------------------------------------------------------
VM LOAD SUMMARY
    VM     host   tasks        load(s)      share
  vm-1   host-1       1        360.000     90.0%
  vm-2   host-1       1        400.000    100.0%
  vm-3   host-2       3        270.000     67.5%
  vm-4   host-2       3        300.000     75.0%
------------------------------------------------------------------------------
METRICS
  predicted makespan : 400.000 s
  average VM load    : 332.500 s
  min VM load        : 270.000 s
  max VM load        : 400.000 s
==============================================================================
```

Contoh assignment:

| Task | Length MI | VM | Host | Prediksi |
|---:|---:|---|---|---:|
| 0 | 900.000 | vm-1 | host-1 | 360,00 s |
| 1 | 600.000 | vm-2 | host-1 | 400,00 s |
| 2 | 450.000 | vm-3 | host-2 | 180,00 s |
| 3 | 300.000 | vm-4 | host-2 | 200,00 s |
| 4 | 150.000 | vm-3 | host-2 | 60,00 s |
| 5 | 100.000 | vm-4 | host-2 | 66,67 s |
| 6 | 75.000 | vm-3 | host-2 | 30,00 s |
| 7 | 50.000 | vm-4 | host-2 | 33,33 s |

Predicted accumulated load:

| VM | Load |
|---|---:|
| vm-1 | 360,00 s |
| vm-2 | 400,00 s |
| vm-3 | 270,00 s |
| vm-4 | 300,00 s |

Predicted makespan adalah load maksimum, yaitu `400,00 s`.

### 13.1 Contoh File Log

Output terminal yang sama disimpan ke:

```text
realworld/results/sessions/20261028_225126/logs/llfd.log
```

Contoh isi awal file:

```text
==============================================================================
LLFD REAL-WORLD EXPERIMENT
==============================================================================
algorithm       : LLFD (Least-Loaded First-Fit Decreasing)
datacenter      : DC-1
hosts           : 2
vm per host     : 2
total VM        : 4
total task      : 8
------------------------------------------------------------------------------
TOPOLOGY
  DC-1/host-1
    vm-1: 4 PE x 2,500 MIPS -> http://127.0.0.1:9101
    vm-2: 2 PE x 1,500 MIPS -> http://127.0.0.1:9102
  DC-1/host-2
    vm-3: 4 PE x 2,500 MIPS -> http://127.0.0.1:9103
    vm-4: 2 PE x 1,500 MIPS -> http://127.0.0.1:9104
------------------------------------------------------------------------------
METRICS
  predicted makespan : 400.000 s
  average VM load    : 332.500 s
  min VM load        : 270.000 s
  max VM load        : 400.000 s
==============================================================================
```

### 13.2 Contoh File `summary.csv`

```csv
algorithm,datacenter,hosts,vms,tasks,total_length_mi,predicted_makespan_seconds,average_vm_load_seconds,min_vm_load_seconds,max_vm_load_seconds
LLFD,DC-1,2,4,8,2625000.0,400.0,332.5,270.0,400.0
```

### 13.3 Contoh File Assignment CSV

File `tasks_LLFD_n8_run1.csv` berisi assignment setiap task:

```csv
task_id,lengthMI,pes,vm,host,predicted_seconds
0,900000.0,1,vm-1,host-1,360.0
1,600000.0,1,vm-2,host-1,400.0
2,450000.0,1,vm-3,host-2,180.0
3,300000.0,1,vm-4,host-2,200.0
4,150000.0,1,vm-3,host-2,60.0
5,100000.0,1,vm-4,host-2,66.66666666666667
6,75000.0,1,vm-3,host-2,30.0
7,50000.0,1,vm-4,host-2,33.333333333333336
```

### 13.4 Contoh File `parameters.txt`

```text
session=20261028_225126
algorithm=LLFD
datacenter=DC-1
hosts=2
vms_per_host=2
dataset=src/main/resources/dataset/google_cluster_trace_sample.txt
mode=plan
```

### 13.5 Contoh Mapping JSON

Potongan `mappings/llfd_mapping.json`:

```json
{
  "algorithm": "LLFD",
  "tasks": [
    {"id": 0, "length_mi": 900000.0, "pes": 1}
  ],
  "assignments": [
    {
      "task_id": 0,
      "lengthMI": 900000.0,
      "pes": 1,
      "vm": "vm-1",
      "host": "host-1",
      "predicted_seconds": 360.0,
      "fallback": false
    }
  ],
  "loads": {
    "vm-1": 360.0,
    "vm-2": 400.0,
    "vm-3": 270.0,
    "vm-4": 300.0
  },
  "makespan_predicted_seconds": 400.0
}
```

### 13.6 Contoh Output Kubernetes

Saat Kind, kubectl, dan Docker tersedia, `./run.sh kind` juga menampilkan:

```text
Kubernetes worker siap; menjalankan LLFD pada 4 VM.
{"status": "ok", "vm": "vm-1", "vm_type": "V3"}
{"status": "ok", "vm": "vm-2", "vm_type": "V2"}
{"status": "ok", "vm": "vm-3", "vm_type": "V3"}
{"status": "ok", "vm": "vm-4", "vm_type": "V2"}

==============================================================================
LLFD REAL-WORLD EXPERIMENT
==============================================================================
mode            : real-world
datacenter      : DC-1
hosts           : 2
vm per host     : 2
total VM        : 4
total task      : 8
------------------------------------------------------------------------------
EXECUTION RESULT: 8 task selesai
real elapsed time : <durasi aktual> s
result file       : realworld/results/sessions/<timestamp>/llfd-result.json
```

---

## 14. Verifikasi Topologi

Verifikasi file Kubernetes:

```bash
grep -c "kind: Deployment" realworld/k8s-topology.yaml
```

Hasil yang diharapkan:

```text
4
```

Verifikasi node Kubernetes:

```bash
kubectl get nodes --show-labels
```

Verifikasi jumlah Pod per host:

```bash
kubectl -n dc-1 get pods -L soka.host -o wide
```

Hasil yang diharapkan:

```text
host-1: 2 Pod
host-2: 2 Pod
```

Verifikasi hasil scheduler tanpa infrastructure:

```bash
./run.sh plan
cat realworld/results/sessions/<timestamp>/summary.csv
cat realworld/results/sessions/<timestamp>/logs/llfd.log
```

---

## 15. Batasan Implementasi

1. Mode Docker menjalankan seluruh container pada mesin fisik yang sama.
   Label host merepresentasikan topologi logis, bukan server fisik terpisah.
2. Mode Kubernetes Kind berjalan sebagai cluster lokal untuk kebutuhan
   eksperimen, bukan cluster production multi-node.
3. MIPS merupakan model kapasitas untuk perhitungan scheduler. CPU nyata worker
   dipengaruhi oleh host, cgroup, scheduler OS, dan overhead container.
4. Worker menjalankan task secara FIFO di setiap VM.
5. Dataset default dibuat kecil agar validasi cepat. Dataset yang lebih besar
   dapat dimasukkan ke `src/main/resources/dataset/`.
6. Hasil `summary.csv` pada mode plan berisi predicted makespan. Waktu nyata
   hanya tersedia jika worker dijalankan pada mode Docker atau Kubernetes.

---

## 16. Kesimpulan

Project ini menyediakan implementasi LLFD end-to-end dengan struktur
eksperimen yang lengkap:

- satu datacenter;
- dua host;
- dua VM pada setiap host;
- scheduler LLFD yang benar-benar digunakan;
- worker Docker dan Kubernetes;
- dataset terpisah;
- script eksekusi tunggal;
- hasil mapping JSON;
- hasil per-task CSV;
- summary CSV;
- log output bertimestamp.

Perintah utama untuk menghasilkan eksperimen adalah:

```bash
./run.sh plan
```

Sedangkan deployment real-world dapat dijalankan dengan:

```bash
./run.sh docker
```

atau:

```bash
./run.sh kind
```

---

## 17. Dataset Google Cluster Workload Trace

Eksperimen skala menggunakan seed workload
`src/main/resources/dataset/google_cluster_trace_sample.txt`. Generator
memperluas workload trace tersebut secara deterministic menjadi:

```text
100, 1000, 2000, 3000, 4000, 5000,
6000, 7000, 8000, 9000, 10000 task
```

Nilai `lengthMI` diambil dari workload trace seed dengan bootstrap resampling
yang memiliki seed tetap, sehingga ukuran dataset dapat diulang dan hasilnya
konsisten. Generator dapat dipakai langsung:

```bash
python3 scripts/generate_google_trace_datasets.py \
  --source src/main/resources/dataset/google_cluster_trace_sample.txt \
  --output-dir src/main/resources/dataset/generated
```

Output generator:

```text
src/main/resources/dataset/generated/
├── GoogleClusterTrace_Dataset_100.txt
├── GoogleClusterTrace_Dataset_1000.txt
├── GoogleClusterTrace_Dataset_2000.txt
├── GoogleClusterTrace_Dataset_3000.txt
├── GoogleClusterTrace_Dataset_4000.txt
├── GoogleClusterTrace_Dataset_5000.txt
├── GoogleClusterTrace_Dataset_6000.txt
├── GoogleClusterTrace_Dataset_7000.txt
├── GoogleClusterTrace_Dataset_8000.txt
├── GoogleClusterTrace_Dataset_9000.txt
└── GoogleClusterTrace_Dataset_10000.txt
```

### 17.1 Plan Semua Skala

Untuk menguji LLFD pada seluruh skala tanpa infrastructure:

```bash
./run.sh scale-plan
```

Hasilnya disimpan ke session:

```text
realworld/results/sessions/<timestamp>/
├── logs/
│   ├── dataset-generation.log
│   ├── llfd_100.log
│   ├── llfd_1000.log
│   └── ... llfd_10000.log
├── mappings/
│   ├── llfd_mapping_100.json
│   └── ... llfd_mapping_10000.json
├── summary_100.csv
├── ...
├── summary_10000.csv
└── scale-summary.csv
```

### 17.2 Eksekusi Semua Skala di Kubernetes

Perintah utama untuk requirement real-world cloud:

```bash
./run.sh kind-scale
```

`kind-scale` melakukan hal berikut:

1. membuat cluster Kind;
2. membuat dua node worker berlabel `host-1` dan `host-2`;
3. deploy satu datacenter Kubernetes `dc-1`;
4. menjalankan empat VM sebagai Pod;
5. membuat port-forward ke seluruh VM;
6. melakukan health check seluruh worker;
7. menghasilkan dataset 100 sampai 10.000 task;
8. menjalankan LLFD pada setiap ukuran melalui endpoint Kubernetes;
9. menyimpan mapping, task CSV, result, summary, dan log per ukuran;
10. menggabungkan metrik ke `scale-summary.csv`;
11. membersihkan cluster setelah seluruh skala selesai.

Contoh output terminal:

```text
generated .../GoogleClusterTrace_Dataset_100.txt (100 tasks)
generated .../GoogleClusterTrace_Dataset_1000.txt (1000 tasks)
...
generated .../GoogleClusterTrace_Dataset_10000.txt (10000 tasks)
Kubernetes worker siap; menjalankan LLFD pada 4 VM.
{"status": "ok", "vm": "vm-1", "vm_type": "V3"}
{"status": "ok", "vm": "vm-2", "vm_type": "V2"}
{"status": "ok", "vm": "vm-3", "vm_type": "V3"}
{"status": "ok", "vm": "vm-4", "vm_type": "V2"}
LLFD dataset=GoogleClusterTrace_Dataset_100.txt tasks=100 makespan=...s loads=...
LLFD dataset=GoogleClusterTrace_Dataset_1000.txt tasks=1000 makespan=...s loads=...
...
LLFD dataset=GoogleClusterTrace_Dataset_10000.txt tasks=10000 makespan=...s loads=...
```

Contoh `scale-summary.csv`:

```csv
dataset,tasks,predicted_makespan_seconds,average_vm_load_seconds,min_vm_load_seconds,max_vm_load_seconds
GoogleClusterTrace_Dataset_100,100,4360.0,4352.5,4350.0,4360.0
GoogleClusterTrace_Dataset_1000,1000,41300.0,41292.5,41280.0,41300.0
GoogleClusterTrace_Dataset_2000,2000,82516.667,82504.167,82500.0,82516.667
...
GoogleClusterTrace_Dataset_10000,10000,408616.667,408606.667,408600.0,408616.667
```

Nilai aktual `scale-summary.csv` mengikuti hasil sampling deterministic dan
disimpan di folder session. Untuk menjalankan skala tertentu saja:

```bash
SIZES=100,1000,10000 ./run.sh kind-scale
```

Mode `kind-scale` memerlukan Docker, Kind, kubectl, dan resource CPU/RAM yang
cukup. Berbeda dari `scale-plan`, mode ini benar-benar mengirim task ke worker
Kubernetes.

Contoh hasil `scale-plan` yang telah dijalankan tersimpan di:

```text
realworld/results/sessions/20261028_225640/
├── logs/
│   ├── dataset-generation.log
│   ├── llfd_100.log
│   ├── llfd_1000.log
│   └── ... llfd_10000.log
├── mappings/
│   ├── llfd_mapping_100.json
│   └── ... llfd_mapping_10000.json
├── scale-summary.csv
├── summary_100.csv
└── tasks_GoogleClusterTrace_n10000_run1.csv
```

Contoh isi `logs/llfd_10000.log`:

```text
LLFD dataset=GoogleClusterTrace_Dataset_10000.txt tasks=10000 makespan=408616.667s loads={"vm-1": 408600.0, "vm-2": 408616.667, "vm-3": 408610.0, "vm-4": 408600.0}
```

### 17.3 Troubleshooting `kind-scale`

`run.sh` dan seluruh script di repository sudah diberi permission executable:

```bash
chmod +x run.sh scripts/*.sh scripts/*.py realworld/*.py realworld/worker/*.py
```

Error berikut **bukan** error permission:

```text
ERROR: command Kubernetes berikut belum tersedia di PATH: kind kubectl docker
```

Periksa prerequisite:

```bash
command -v kind
command -v kubectl
command -v docker
docker info
```

Jika menggunakan WSL2 dengan Docker Desktop:

1. Install `kind`, `kubectl`, dan Docker Desktop.
2. Buka Docker Desktop.
3. Aktifkan **Settings → Resources → WSL Integration**.
4. Aktifkan integrasi untuk distro WSL yang digunakan.
5. Tutup dan buka kembali terminal WSL.
6. Pastikan `docker info` berhasil sebelum menjalankan:

```bash
./run.sh kind-scale
```

Jika `./run.sh kind-scale` sudah menampilkan `session=...` lalu error
`kind/kubectl tidak ditemukan`, berarti `run.sh` berhasil dieksekusi. Yang belum
tersedia adalah runtime Kubernetes-nya, bukan permission file.

### 17.4 Bukti Eksekusi Terakhir

Pada eksekusi terakhir di WSL, Docker sudah berhasil terhubung:

```text
Context: default
Server:
 Containers: 3
 Running: 3
 Server Version: 29.6.2
 Operating System: Docker Desktop
 CPUs: 12
 Total Memory: 9.569GiB
```

Kind juga berhasil membuat cluster `llfd` dengan satu control-plane dan dua
worker:

```text
Creating cluster "llfd" ...
 ✓ Ensuring node image (kindest/node:v1.31.0)
 ✓ Preparing nodes
 ✓ Starting control-plane
 ✓ Installing CNI
 ✓ Installing StorageClass
 ✓ Joining worker nodes
Set kubectl context to "kind-llfd"
```

Pengecekan awal dilakukan terlalu cepat sehingga node masih dalam proses
bootstrap:

```text
NAME                 STATUS     ROLES           AGE   VERSION
llfd-control-plane   NotReady   control-plane   16s   v1.31.0
llfd-worker          NotReady   <none>          5s    v1.31.0
llfd-worker2         NotReady   <none>          4s    v1.31.0
```

Kemudian `./run.sh kind-scale` dijalankan ketika cluster `llfd` sudah dibuat
manual, sehingga versi script lama mencoba membuat cluster kedua:

```text
ERROR: failed to create cluster: node(s) already exist for a cluster with the name "llfd"
```

Script sekarang sudah diperbaiki dengan `ensure_kind_cluster`: jika cluster
`llfd` sudah ada, script akan menggunakannya dan menunggu semua node menjadi
`Ready`; jika belum ada, script akan membuatnya. Jalankan ulang:

```bash
kubectl --context kind-llfd wait --for=condition=Ready nodes --all --timeout=180s
./run.sh kind-scale
```

Dengan demikian, implementasi dan topologi sudah sesuai requirement. Status
eksekusi Kubernetes skala penuh menunggu node Kind selesai bootstrap; hasil
`scale-summary.csv` yang sudah tersedia berasal dari `scale-plan`, bukan
eksekusi worker Kubernetes.
