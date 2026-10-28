# Results

Folder ini menyimpan output eksekusi LLFD:

- `llfd-plan.json`: detail task, VM, host, assignment, accumulated load, dan
  predicted makespan.
- `llfd-result.json`: hasil eksekusi worker ketika mode `docker` digunakan.
- `run.log`: ringkasan terminal dari `run.sh`.
- `kubernetes-pods.txt`: daftar Pod ketika mode `kind` digunakan.

Jalankan `./run.sh plan` untuk membuat plan tanpa membutuhkan Docker.
