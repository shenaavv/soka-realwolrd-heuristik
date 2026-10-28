# Pemetaan Datacenter, Host, dan VM pada Kubernetes

Dokumen ini menjelaskan cara menunjukkan komponen cloud pada implementasi
LLFD menggunakan Docker dan Kubernetes Kind.

## 1. Struktur Topologi

Implementasi menggunakan satu datacenter logis, dua host, dan dua VM pada
setiap host:

```text
Kubernetes Namespace: dc-1
└── Datacenter logis: DC-1
    ├── Host 1: host-1
    │   ├── VM: vm-1
    │   └── VM: vm-2
    └── Host 2: host-2
        ├── VM: vm-3
        └── VM: vm-4
```

Dengan demikian, implementasi memenuhi:

| Komponen | Jumlah | Nama |
|---|---:|---|
| Datacenter | 1 | `DC-1` |
| Host | 2 | `host-1`, `host-2` |
| VM | 4 | `vm-1`, `vm-2`, `vm-3`, `vm-4` |
| VM per host | 2 | Dua VM pada setiap host |

## 2. Datacenter

Kubernetes tidak menyediakan objek bawaan bernama `Datacenter`. Karena itu,
datacenter direpresentasikan menggunakan Kubernetes Namespace dan label.

Pada file `realworld/k8s-topology.yaml` terdapat:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dc-1
  labels:
    soka.datacenter: DC-1
```

Pemetaan konsepnya:

| Kubernetes | Konsep cloud |
|---|---|
| Namespace `dc-1` | Datacenter |
| Label `soka.datacenter: DC-1` | Identitas datacenter |

Jadi, datacenter pada project ini adalah:

```text
Namespace Kubernetes dc-1 = Datacenter logis DC-1
```

Teman yang menggunakan namespace seperti `datacenter-a` juga menggunakan
pendekatan yang sama. Perbedaannya hanya pada nama namespace dan label.

Untuk menampilkan datacenter:

```bash
kubectl --context kind-llfd get namespace dc-1 --show-labels
```

Contoh output:

```text
NAME   STATUS   AGE   LABELS
dc-1   Active   ...   soka.datacenter=DC-1
```

## 3. Host

Host direpresentasikan oleh Kubernetes worker node. Konfigurasinya berada
di `realworld/kind-config.yaml`:

```yaml
nodes:
  - role: worker
    labels:
      soka.datacenter: DC-1
      soka.host: host-1

  - role: worker
    labels:
      soka.datacenter: DC-1
      soka.host: host-2
```

Pemetaan host:

```text
Kubernetes worker node llfd-worker  = host-1
Kubernetes worker node llfd-worker2 = host-2
```

Kind membuat worker node sebagai container Linux. Oleh karena itu, secara
simulasi infrastrukturnya dapat digambarkan sebagai berikut:

```text
Docker Desktop / WSL
└── Kind cluster: llfd
    ├── llfd-control-plane = Kubernetes control-plane
    ├── llfd-worker        = host-1
    └── llfd-worker2       = host-2
```

`llfd-control-plane` digunakan untuk mengelola cluster dan bukan host utama
untuk VM workload pada topologi ini.

Untuk menampilkan host:

```bash
kubectl --context kind-llfd get nodes \
  --show-labels
```

Atau gunakan output yang lebih ringkas:

```bash
kubectl --context kind-llfd get nodes \
  -l soka.datacenter=DC-1 \
  -L soka.datacenter \
  -L soka.host \
  -o wide
```

Contoh output:

```text
NAME          STATUS   ROLES    SOKA.DATACENTER   SOKA.HOST   INTERNAL-IP
llfd-worker   Ready    <none>   DC-1              host-1      172.18.0.7
llfd-worker2  Ready    <none>   DC-1              host-2      172.18.0.5
```

## 4. VM

Kubernetes juga tidak memiliki objek bawaan bernama `VM` pada deployment
ini. VM direpresentasikan oleh Deployment, Pod, dan Service worker.

Contoh konfigurasi `vm-1`:

```yaml
metadata:
  name: vm-1
  namespace: dc-1
```

Pod VM diberi label:

```yaml
labels:
  soka.vm: vm-1
  soka.host: host-1
```

Kemudian `nodeSelector` memastikan VM dijalankan pada host yang benar:

```yaml
nodeSelector:
  soka.host: host-1
```

Pemetaan VM lengkap:

| Datacenter | Host | VM Kubernetes |
|---|---|---|
| `DC-1` | `host-1` | `vm-1` |
| `DC-1` | `host-1` | `vm-2` |
| `DC-1` | `host-2` | `vm-3` |
| `DC-1` | `host-2` | `vm-4` |

Perintah untuk menampilkan Pod VM:

```bash
kubectl --context kind-llfd \
  -n dc-1 get pods \
  -o custom-columns='VM:.metadata.labels.soka\.vm,HOST:.metadata.labels.soka\.host,POD:.metadata.name,NODE:.spec.nodeName,STATUS:.status.phase'
```

Contoh output:

```text
VM     HOST     POD                     NODE          STATUS
vm-1   host-1   vm-1-xxxxxxxxx-yyyyy   llfd-worker   Running
vm-2   host-1   vm-2-xxxxxxxxx-yyyyy   llfd-worker   Running
vm-3   host-2   vm-3-xxxxxxxxx-yyyyy   llfd-worker2  Running
vm-4   host-2   vm-4-xxxxxxxxx-yyyyy   llfd-worker2  Running
```

Nama Pod memiliki suffix acak karena Pod dibuat oleh Deployment. Identitas
VM tetap dapat diketahui melalui label `soka.vm`.

## 5. Perintah Demonstrasi

Pastikan cluster Kind sudah berjalan:

```bash
kubectl --context kind-llfd get nodes
```

### Menampilkan datacenter

```bash
kubectl --context kind-llfd get namespace dc-1 --show-labels
```

### Menampilkan host

```bash
kubectl --context kind-llfd get nodes \
  -L soka.datacenter \
  -L soka.host \
  -o wide
```

### Menampilkan VM dan host-nya

```bash
kubectl --context kind-llfd \
  -n dc-1 get pods \
  -o custom-columns='VM:.metadata.labels.soka\.vm,HOST:.metadata.labels.soka\.host,NODE:.spec.nodeName,STATUS:.status.phase'
```

### Menampilkan Deployment dan Service VM

```bash
kubectl --context kind-llfd -n dc-1 get deployments,services,pods -o wide
```

## 6. Pemetaan Konsep Cloud ke Kubernetes

| Konsep pada cloud | Representasi pada project |
|---|---|
| Datacenter | Namespace `dc-1` dan label `soka.datacenter=DC-1` |
| Host | Kubernetes worker node Kind |
| VM | Deployment dan Pod worker |
| VM endpoint | Kubernetes Service `vm-1` sampai `vm-4` |
| Container runtime | Docker/containerd |
| Penjadwalan task | LLFD pada `realworld/llfd_scheduler.py` |

Secara khusus:

```text
Namespace dc-1                    = Datacenter DC-1
Node llfd-worker                  = Host host-1
Node llfd-worker2                 = Host host-2
Pod/Service vm-1 dan vm-2         = VM pada host-1
Pod/Service vm-3 dan vm-4         = VM pada host-2
```

## 7. Penjelasan Saat Presentasi

Gunakan penjelasan berikut:

> Pada implementasi ini, namespace Kubernetes `dc-1` merepresentasikan satu
> datacenter logis bernama `DC-1`. Dua Kubernetes worker node diberi label
> sebagai `host-1` dan `host-2`. Setiap host menjalankan dua Pod worker yang
> merepresentasikan VM, yaitu `vm-1` dan `vm-2` pada `host-1`, serta `vm-3`
> dan `vm-4` pada `host-2`. Task kemudian dialokasikan ke VM menggunakan
> algoritma LLFD.

datacenternya:

```text
Datacenter = Namespace dc-1 dengan label soka.datacenter=DC-1
```

host-nya:

```text
Host = Kubernetes worker node llfd-worker dan llfd-worker2
```

VM-nya:

```text
VM = Pod worker vm-1, vm-2, vm-3, dan vm-4
```

