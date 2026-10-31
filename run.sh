#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-plan}"
DATASET="${DATASET:-${ROOT_DIR}/src/main/resources/dataset/google_cluster_trace_sample.txt}"
SIZES="${SIZES:-100,1000}"
TRACE_SOURCE="${TRACE_SOURCE:-${ROOT_DIR}/src/main/resources/dataset/google_cluster_trace_sample.txt}"
SESSION_ID="${SESSION_ID:-$(date +%Y%m%d_%H%M%S)}"
RESULTS_DIR="${RESULTS_DIR:-${ROOT_DIR}/realworld/results/sessions/${SESSION_ID}}"
COMPOSE_FILE="${ROOT_DIR}/realworld/docker-compose.yml"
KEEP_RUNTIME="${KEEP_RUNTIME:-1}"
KEEP_CONTAINERS="${KEEP_CONTAINERS:-$KEEP_RUNTIME}"
KEEP_CLUSTER="${KEEP_CLUSTER:-$KEEP_RUNTIME}"
PORT_FORWARD_PIDS=()
LOG_PIDS=()
CLUSTER_CREATED=0

cleanup_kind() {
  local pid
  for pid in "${PORT_FORWARD_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${LOG_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  if [[ "$KEEP_CLUSTER" == "1" ]]; then
    echo "KEEP_CLUSTER=1; resource Kubernetes dan cluster dipertahankan untuk inspeksi."
    return
  fi
  kubectl delete -f "$ROOT_DIR/realworld/k8s-topology.yaml" --ignore-not-found >/dev/null 2>&1 || true
  if ((CLUSTER_CREATED == 1)); then
    kind delete cluster --name llfd >/dev/null 2>&1 || true
  fi
}

ensure_kind_cluster() {
  if kind get clusters 2>/dev/null | grep -qx llfd; then
    echo "Using existing Kind cluster: llfd"
  else
    kind create cluster --config "$ROOT_DIR/realworld/kind-config.yaml" \
      --image "${KIND_NODE_IMAGE:-kindest/node:v1.36.1}" --name llfd
    CLUSTER_CREATED=1
  fi
  kubectl --context kind-llfd wait --for=condition=Ready nodes --all --timeout=180s
}

wait_for_kubernetes_workers() {
  local vm_id attempt health_log
  health_log="$RESULTS_DIR/logs/kubernetes-health.log"
  for vm_id in 1 2 3 4; do
    for ((attempt = 1; attempt <= 30; attempt++)); do
      if curl --fail --silent "http://127.0.0.1:$((9100 + vm_id))/health" \
        | tee -a "$health_log"; then
        printf '\n' | tee -a "$health_log"
        break
      fi
      if ((attempt == 30)); then
        echo "ERROR: Kubernetes worker vm-${vm_id} tidak merespons setelah 30 detik." \
          | tee -a "$health_log" >&2
        return 1
      fi
      sleep 1
    done
  done
}

mkdir -p "$RESULTS_DIR/logs" "$RESULTS_DIR/mappings"
{
  printf 'session=%s\n' "$SESSION_ID"
  printf 'algorithm=LLFD\n'
  printf 'datacenter=DC-1\n'
  printf 'hosts=2\n'
  printf 'vms_per_host=2\n'
  printf 'dataset=%s\n' "$DATASET"
  printf 'mode=%s\n' "$MODE"
} | tee "$RESULTS_DIR/parameters.txt"

case "$MODE" in
  scale-plan)
    python3 "$ROOT_DIR/scripts/generate_google_trace_datasets.py" \
      --source "$TRACE_SOURCE" \
      --output-dir "$ROOT_DIR/src/main/resources/dataset/generated" \
      --sizes "$SIZES" 2>&1 | tee "$RESULTS_DIR/logs/dataset-generation.log"
    printf 'dataset,tasks,predicted_makespan_seconds,average_vm_load_seconds,min_vm_load_seconds,max_vm_load_seconds,load_balance_efficiency_percent,load_imbalance_percent,ideal_makespan_lower_bound_seconds,makespan_gap_from_ideal_percent\n' \
      > "$RESULTS_DIR/scale-summary.csv"
    IFS=',' read -r -a sizes <<< "$SIZES"
    for size in "${sizes[@]}"; do
      dataset="$ROOT_DIR/src/main/resources/dataset/generated/GoogleClusterTrace_Dataset_${size}.txt"
      python3 "$ROOT_DIR/realworld/llfd_runner.py" \
        --dataset "$dataset" \
        --output "$RESULTS_DIR/mappings/llfd_mapping_${size}.json" \
        --task-output "$RESULTS_DIR/tasks_GoogleClusterTrace_n${size}_run1.csv" \
        --summary-output "$RESULTS_DIR/summary_${size}.csv" \
        --plan-only --compact 2>&1 | tee "$RESULTS_DIR/logs/llfd_${size}.log"
      python3 - "$size" "$RESULTS_DIR/summary_${size}.csv" "$RESULTS_DIR/scale-summary.csv" <<'PY'
import csv, sys
with open(sys.argv[2], newline="") as source, open(sys.argv[3], "a", newline="") as target:
    row = next(csv.DictReader(source))
    csv.writer(target).writerow([
        f"GoogleClusterTrace_Dataset_{sys.argv[1]}",
        row["tasks"], row["predicted_makespan_seconds"],
        row["average_vm_load_seconds"], row["min_vm_load_seconds"],
        row["max_vm_load_seconds"],
        row["load_balance_efficiency_percent"],
        row["load_imbalance_percent"],
        row["ideal_makespan_lower_bound_seconds"],
        row["makespan_gap_from_ideal_percent"],
    ])
PY
    done
    ;;
  plan)
    python3 "$ROOT_DIR/realworld/llfd_runner.py" \
      --dataset "$DATASET" \
      --output "$RESULTS_DIR/mappings/llfd_mapping.json" \
      --task-output "$RESULTS_DIR/tasks_LLFD_n$(wc -l < "$DATASET")_run1.csv" \
      --summary-output "$RESULTS_DIR/summary.csv" \
      --plan-only 2>&1 | tee "$RESULTS_DIR/logs/llfd.log"
    ;;
  docker)
    docker compose -f "$COMPOSE_FILE" up -d --build --wait
    docker compose -f "$COMPOSE_FILE" logs --no-color --follow vm-1 vm-2 vm-3 vm-4 \
      2>&1 | tee "$RESULTS_DIR/logs/docker-workers.log" &
    LOG_PIDS+=("$!")
    cleanup_docker() {
      local pid
      for pid in "${LOG_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
      done
      docker compose -f "$COMPOSE_FILE" ps \
        | tee "$RESULTS_DIR/logs/docker-compose-final-status.log"
      if [[ "$KEEP_CONTAINERS" == "1" ]]; then
        echo "Container Docker dipertahankan untuk demo/inspeksi."
        return
      fi
      docker compose -f "$COMPOSE_FILE" down
    }
    trap cleanup_docker EXIT
    python3 "$ROOT_DIR/realworld/llfd_runner.py" \
      --dataset "$DATASET" \
      --output "$RESULTS_DIR/mappings/llfd_mapping.json" \
      --task-output "$RESULTS_DIR/tasks_LLFD_n$(wc -l < "$DATASET")_run1.csv" \
      --summary-output "$RESULTS_DIR/summary.csv" 2>&1 | tee "$RESULTS_DIR/logs/llfd.log"
    ;;
  kind)
    if ! command -v kind >/dev/null; then
      echo "ERROR: kind tidak ditemukan; Kubernetes execution belum dapat dijalankan." \
        | tee "$RESULTS_DIR/logs/kubernetes.log" >&2
      exit 1
    fi
    if ! command -v kubectl >/dev/null; then
      echo "ERROR: kubectl tidak ditemukan; Kubernetes execution belum dapat dijalankan." \
        | tee "$RESULTS_DIR/logs/kubernetes.log" >&2
      exit 1
    fi
    ensure_kind_cluster
    trap cleanup_kind EXIT
    docker build -t llfd-worker:1.0 "$ROOT_DIR/realworld"
    kind load docker-image llfd-worker:1.0 --name llfd
    kubectl apply -f "$ROOT_DIR/realworld/k8s-topology.yaml"
    kubectl -n dc-1 rollout status deployment --timeout=120s
    kubectl -n dc-1 get pods -o wide | tee "$RESULTS_DIR/kubernetes-pods.txt"
    for vm_id in 1 2 3 4; do
      kubectl -n dc-1 port-forward "svc/vm-${vm_id}" "$((9100 + vm_id)):8000" \
        >"$RESULTS_DIR/logs/port-forward-vm-${vm_id}.log" 2>&1 &
      PORT_FORWARD_PIDS+=("$!")
      kubectl -n dc-1 logs -f "deployment/vm-${vm_id}" --prefix \
        2>&1 | tee "$RESULTS_DIR/logs/kubernetes-vm-${vm_id}.log" &
      LOG_PIDS+=("$!")
    done
    wait_for_kubernetes_workers
    echo "Kubernetes worker siap; menjalankan LLFD pada 4 VM."
    python3 "$ROOT_DIR/realworld/llfd_runner.py" \
      --dataset "$DATASET" \
      --output "$RESULTS_DIR/mappings/llfd_mapping.json" \
      --task-output "$RESULTS_DIR/tasks_LLFD_n$(wc -l < "$DATASET")_run1.csv" \
      --summary-output "$RESULTS_DIR/summary.csv" 2>&1 | tee "$RESULTS_DIR/logs/llfd.log"
    ;;
  kind-scale)
    missing=()
    command -v kind >/dev/null || missing+=("kind")
    command -v kubectl >/dev/null || missing+=("kubectl")
    command -v docker >/dev/null || missing+=("docker")
    if ((${#missing[@]} > 0)); then
      echo "ERROR: command Kubernetes berikut belum tersedia di PATH: ${missing[*]}" \
        | tee "$RESULTS_DIR/logs/kubernetes.log" >&2
      echo "Install tools tersebut dan aktifkan Docker Desktop WSL integration." \
        | tee -a "$RESULTS_DIR/logs/kubernetes.log" >&2
      exit 1
    fi
    ensure_kind_cluster
    trap cleanup_kind EXIT
    docker build -t llfd-worker:1.0 "$ROOT_DIR/realworld"
    kind load docker-image llfd-worker:1.0 --name llfd
    kubectl apply -f "$ROOT_DIR/realworld/k8s-topology.yaml"
    kubectl -n dc-1 rollout status deployment --timeout=120s
    kubectl -n dc-1 get pods -o wide | tee "$RESULTS_DIR/kubernetes-pods.txt"
    for vm_id in 1 2 3 4; do
      kubectl -n dc-1 port-forward "svc/vm-${vm_id}" "$((9100 + vm_id)):8000" \
        >"$RESULTS_DIR/logs/port-forward-vm-${vm_id}.log" 2>&1 &
      PORT_FORWARD_PIDS+=("$!")
    done
    wait_for_kubernetes_workers
    echo "Kubernetes worker siap; menjalankan LLFD pada ukuran: $SIZES."
    python3 "$ROOT_DIR/scripts/generate_google_trace_datasets.py" \
      --source "$TRACE_SOURCE" \
      --output-dir "$ROOT_DIR/src/main/resources/dataset/generated" \
      --sizes "$SIZES" 2>&1 | tee "$RESULTS_DIR/logs/dataset-generation.log"
    printf 'dataset,tasks,predicted_makespan_seconds,average_vm_load_seconds,min_vm_load_seconds,max_vm_load_seconds,load_balance_efficiency_percent,load_imbalance_percent,ideal_makespan_lower_bound_seconds,makespan_gap_from_ideal_percent\n' \
      > "$RESULTS_DIR/scale-summary.csv"
    IFS=',' read -r -a sizes <<< "$SIZES"
    for size in "${sizes[@]}"; do
      dataset="$ROOT_DIR/src/main/resources/dataset/generated/GoogleClusterTrace_Dataset_${size}.txt"
      python3 "$ROOT_DIR/realworld/llfd_runner.py" \
        --dataset "$dataset" \
        --output "$RESULTS_DIR/mappings/llfd_mapping_${size}.json" \
        --task-output "$RESULTS_DIR/tasks_GoogleClusterTrace_n${size}_run1.csv" \
        --summary-output "$RESULTS_DIR/summary_${size}.csv" \
        --iterations-per-mi 0.00001 2>&1 | tee "$RESULTS_DIR/logs/llfd_${size}.log"
      python3 - "$size" "$RESULTS_DIR/summary_${size}.csv" "$RESULTS_DIR/scale-summary.csv" <<'PY'
import csv, sys
with open(sys.argv[2], newline="") as source, open(sys.argv[3], "a", newline="") as target:
    row = next(csv.DictReader(source))
    csv.writer(target).writerow([
        f"GoogleClusterTrace_Dataset_{sys.argv[1]}",
        row["tasks"], row["predicted_makespan_seconds"],
        row["average_vm_load_seconds"], row["min_vm_load_seconds"],
        row["max_vm_load_seconds"],
        row["load_balance_efficiency_percent"],
        row["load_imbalance_percent"],
        row["ideal_makespan_lower_bound_seconds"],
        row["makespan_gap_from_ideal_percent"],
    ])
PY
    done
    ;;
  *)
    echo "Usage: $0 [plan|scale-plan|docker|kind|kind-scale]" >&2
    echo "  scale-plan: generate and schedule Google Trace datasets with SIZES=${SIZES}" >&2
    exit 2
    ;;
esac
