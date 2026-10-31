# Results

Folder ini menyimpan output eksekusi LLFD:

- `parameters.txt`: konfigurasi session, termasuk mode dan sumber dataset.
- `mappings/llfd_mapping*.json`: detail task, VM, host, assignment,
  accumulated load, dan predicted makespan.
- `tasks_*.csv`: mapping satu baris per task.
- `summary.csv` atau `summary_<size>.csv`: ringkasan metrik scheduler.
- `scale-summary.csv`: ringkasan gabungan untuk mode `scale-plan`.
- `llfd-result.json`: hasil eksekusi worker ketika mode `docker` atau `kind`
  digunakan.
- `logs/`: output terminal dan log worker.
- `kubernetes-pods.txt`: daftar Pod ketika mode `kind` digunakan.

Untuk plan demo kecil, jalankan `./run.sh plan`; mode ini memakai seed sample
default yang berisi 8 task. Untuk dataset Google Trace yang digunakan pada
eksperimen skala, jalankan:

```bash
SIZES=100,1000 ./run.sh scale-plan
```

Generator membuat tepat 100 dan 1000 baris task dari seed Google Trace.
