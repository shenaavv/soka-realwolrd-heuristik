# Panduan Menjalankan LLFD

Dokumen ini adalah panduan operasional lengkap untuk menjalankan mode plan,
Docker Compose, dan Kubernetes menggunakan Kind.

## 1. Struktur komponen

Istilah `worker` memiliki dua arti yang berbeda:

- **Application worker**: proses Python pada `realworld/worker/worker.py`.
  Proses ini menjalankan satu VM simulasi dan menyediakan endpoint `/health` dan
  `/batch`.
- **Kubernetes worker node**: node Kubernetes yang menjadi host untuk Pod.
  Node ini bukan proses Python worker.

### Docker Compose

Mode Docker Compose membuat **empat container aplikasi**, bukan tiga:

| Container | VM | Host logis |
|---|---|---|
| `llfd-vm-1` | `vm-1` | `host-1` |
| `llfd-vm-2` | `vm-2` | `host-1` |
| `llfd-vm-3` | `vm-3` | `host-2` |
| `llfd-vm-4` | `vm-4` | `host-2` |

Satu container menjalankan satu application worker dan mewakili satu VM.
`host-1` dan `host-2` pada Docker Compose adalah label/topologi logis, bukan
container host terpisah. Network `llfd-dc-1` mewakili datacenter `DC-1`.

Perintah berikut menampilkan container Compose:

```bash
docker compose -f realworld/docker-compose.yml ps
docker ps --filter name=llfd-vm
```

### Kubernetes dengan Kind

Kind membuat cluster yang terdiri dari:

- satu node `control-plane`;
- dua node Kubernetes role `worker`, berlabel `host-1` dan `host-2`;
- empat Pod aplikasi: `vm-1`, `vm-2`, `vm-3`, dan `vm-4`.

Pada implementasi ini, Pod adalah representasi VM. `nodeSelector` menempatkan
dua Pod pada masing-masing node Kubernetes worker. Jadi, pada Kubernetes
`worker node` adalah host, sedangkan container di dalam Pod adalah application
worker.

```text
Kind cluster
├── control-plane
├── worker node: host-1
│   ├── Pod vm-1
│   └── Pod vm-2
└── worker node: host-2
    ├── Pod vm-3
    └── Pod vm-4
```

## 2. Prasyarat

Periksa tool yang diperlukan:

```bash
docker --version
docker compose version
kubectl version --client
kind version
python3 --version
```

Pastikan Docker daemon aktif:

```bash
docker info
```

Jika `kind` belum ada dan tidak memiliki akses root, pasang ke user bin:

```bash
mkdir -p "$HOME/.local/bin"
curl -fsSL -o /tmp/kind \
  https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
chmod +x /tmp/kind
install -m 0755 /tmp/kind "$HOME/.local/bin/kind"
export PATH="$HOME/.local/bin:$PATH"
```

## 3. Menjalankan plan tanpa container

```bash
chmod +x run.sh scripts/*.sh
RESULTS_DIR=realworld/results/sessions/manual-plan ./run.sh plan
```

Output ditampilkan di terminal dan disimpan pada:

```text
realworld/results/sessions/manual-plan/
├── logs/llfd.log
├── mappings/llfd_mapping.json
└── summary.csv
```

Bagian `LLFD OPTIMIZATION INDICATORS` pada terminal menunjukkan:

- **load-balance efficiency**: `average VM load / max VM load`; semakin dekat
  100%, semakin merata beban antar-VM;
- **load imbalance**: `(max load - min load) / max load`; semakin kecil semakin
  seimbang;
- **ideal makespan lower bound**: batas teoritis berdasarkan total workload dan
  total MIPS;
- **makespan gap vs ideal**: selisih makespan LLFD terhadap batas ideal.

Metrik yang sama disimpan dalam `summary.csv` dan bagian `optimization` pada
`mappings/llfd_mapping.json`. Ini adalah metrik prediksi scheduler, bukan
persentase CPU aktual dari Docker atau Kubernetes.

## 4. Menjalankan Docker Compose

Jalankan LLFD pada empat VM Docker:

```bash
RESULTS_DIR=realworld/results/sessions/manual-docker ./run.sh docker
```

Selama proses berjalan:

- output LLFD tampil di terminal;
- log semua worker tampil di terminal;
- log worker tersimpan di `logs/docker-workers.log`;
- output LLFD tersimpan di `logs/llfd.log`;
- hasil eksekusi tersimpan di `llfd-result.json`.

Periksa container dari terminal lain:

```bash
docker compose -f realworld/docker-compose.yml ps
docker logs -f llfd-vm-1
```

Secara default, `run.sh docker` mempertahankan container setelah proses selesai
agar proses pembuatan dan status worker dapat didemonstrasikan. Jalankan:

```bash
docker compose -f realworld/docker-compose.yml up -d --build --wait
docker compose -f realworld/docker-compose.yml logs -f
docker compose -f realworld/docker-compose.yml down
```

Opsi `--wait` memastikan keempat worker sudah `healthy` sebelum LLFD
mengirimkan task. Tanpa menunggu healthcheck, worker yang baru mulai dapat
menyebabkan koneksi HTTP ter-reset.

Untuk mematikan container setelah demo:

```bash
docker compose -f realworld/docker-compose.yml down
```

Untuk mengaktifkan cleanup otomatis pada satu kali eksekusi:

```bash
KEEP_RUNTIME=0 ./run.sh docker
```

Status akhir Compose selalu disimpan ke
`logs/docker-compose-final-status.log`.

## 5. Menjalankan Kubernetes dengan Kind

Gunakan mode `kind`:

```bash
export PATH="$HOME/.local/bin:$PATH"
RESULTS_DIR=realworld/results/sessions/manual-kind ./run.sh kind
```

Skrip akan:

1. membuat cluster Kind `llfd`;
2. membuat image `llfd-worker:1.0`;
3. memuat image ke seluruh node Kind;
4. menerapkan Namespace, Deployment, dan Service;
5. menunggu empat Deployment siap;
6. melakukan port-forward ke empat Service;
7. melakukan health check;
8. menjalankan LLFD;
9. menampilkan log Pod dan menyimpannya ke file;
10. mempertahankan resource dan cluster agar dapat didemonstrasikan.

Periksa cluster atau Pod secara manual:

```bash
kind get clusters
kubectl --context kind-llfd get nodes -o wide
kubectl --context kind-llfd -n dc-1 get pods -L soka.host -o wide
kubectl --context kind-llfd -n dc-1 get services
```

Log Kubernetes tersimpan di:

```text
realworld/results/sessions/manual-kind/
├── kubernetes-pods.txt
├── logs/kubernetes-health.log
├── logs/kubernetes-vm-1.log
├── logs/kubernetes-vm-2.log
├── logs/kubernetes-vm-3.log
├── logs/kubernetes-vm-4.log
└── logs/llfd.log
```

Secara default, cluster dan Pod tetap hidup setelah `run.sh kind` selesai.
Untuk cleanup manual setelah demo:

```bash
kubectl --context kind-llfd delete namespace dc-1 --ignore-not-found
kind delete cluster --name llfd
```

Jika ingin mengaktifkan cleanup otomatis pada satu kali eksekusi:

```bash
KEEP_RUNTIME=0 ./run.sh kind
```

`KEEP_CONTAINERS` dan `KEEP_CLUSTER` tetap dapat digunakan terpisah jika hanya
salah satu runtime yang ingin dipertahankan.

```bash
kind get clusters
kubectl --context kind-llfd get nodes -o wide
kubectl --context kind-llfd -n dc-1 get pods -L soka.host -o wide
kubectl --context kind-llfd -n dc-1 get services
```

Jika menggunakan `KEEP_RUNTIME=0` atau `KEEP_CLUSTER=0`, cleanup otomatis
menghapus Namespace, Deployment, Service, dan cluster Kind. Jadi
`No resources found in dc-1 namespace` setelah cleanup adalah kondisi normal,
bukan tanda VM gagal dibuat.

## 6. Menjalankan eksperimen skala besar

Mode Docker:

```bash
./run.sh scale-plan
```

Mode Kubernetes:

```bash
export PATH="$HOME/.local/bin:$PATH"
./run.sh kind-scale
```

Mode `kind-scale` membutuhkan Docker, Kind, kubectl, dan resource CPU/RAM lebih
besar karena task benar-benar dikirim ke Pod Kubernetes.

Secara default `run.sh scale-plan` dan `run.sh kind-scale` selalu membuat dan
menjalankan dataset Google Trace berukuran 100 dan 1000 task. Ukuran lain hanya
dijalankan jika diberikan secara eksplisit, misalnya `SIZES=10000 ./run.sh
scale-plan`.

## 7. Perubahan konfigurasi yang terdokumentasi

Konfigurasi topologi yang sudah benar tidak diubah. Perubahan yang terkait
operasional dan logging adalah:

- `run.sh` menampilkan log worker Docker/Kubernetes ke terminal sekaligus file;
- health check Kubernetes menggunakan retry, bukan hanya menunggu waktu tetap;
- `k8s-topology.yaml` memiliki Service untuk keempat VM agar seluruh port-forward
  dapat berjalan;
- `run.sh` memakai image node Kind lokal/default `kindest/node:v1.36.1`, yang
  dapat dioverride dengan `KIND_NODE_IMAGE`;
- README dan dokumen ini menjelaskan perubahan tersebut serta pemetaan
  container, node, Pod, host, dan VM.


## Command untuk demo

```bash
docker compose -f realworld/docker-compose.yml ps

kind get clusters

kubectl --context kind-llfd get nodes -o wide

kubectl --context kind-llfd -n dc-1 get pods -L soka.host -o wide

kubectl --context kind-llfd -n dc-1 get services
```

## Command untuk cleanup setelah selesai demo
```bash
docker compose -f realworld/docker-compose.yml down
kind delete cluster --name llfd
```