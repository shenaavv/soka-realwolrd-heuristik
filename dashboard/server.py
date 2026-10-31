#!/usr/bin/env python3
"""Local monitoring dashboard for SOKA LLFD experiments (stdlib only)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import csv, json, os, subprocess

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = ROOT / "realworld" / "results" / "sessions"
DASHBOARD = Path(__file__).resolve().parent
PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

def read_csv(path):
    try:
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []

def tail(path, limit=250):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-limit:]
    except OSError:
        return []

def latest_session():
    if not SESSIONS.exists():
        return None
    dirs = [p for p in SESSIONS.iterdir() if p.is_dir()]
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None

def docker_status():
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=llfd-vm-",
             "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True, text=True, timeout=3, check=False
        )
        rows = []
        for line in result.stdout.splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                rows.append({"name": name, "status": status,
                             "healthy": "Up" in status and "Exited" not in status})
        return rows
    except (OSError, subprocess.TimeoutExpired):
        return []

def dashboard_data():
    session = latest_session()
    if not session:
        return {"available": False, "message": "Belum ada session LLFD. Jalankan ./run.sh plan atau ./run.sh docker."}
    mapping = read_json(session / "mappings" / "llfd_mapping.json")
    if mapping is None:
        candidates = sorted((session / "mappings").glob("llfd_mapping_*.json")) if (session / "mappings").exists() else []
        mapping = read_json(candidates[-1]) if candidates else {}
    summary_rows = read_csv(session / "summary.csv")
    summary_candidates = sorted(session.glob("summary_*.csv"))
    if not summary_rows:
        if summary_candidates:
            summary_rows = read_csv(summary_candidates[-1])
    summary = summary_rows[0] if summary_rows else {}
    logs_dir = session / "logs"
    log_files = sorted(logs_dir.glob("*.log")) if logs_dir.exists() else []
    logs = []
    for path in log_files:
        for line in tail(path, 180):
            logs.append({"file": path.name, "line": line})
    result = read_json(session / "llfd-result.json")
    selected_summary = summary_candidates[-1].stem.removeprefix("summary_") if summary_candidates else None
    dataset_name = (
        f"GoogleClusterTrace_Dataset_{selected_summary}"
        if selected_summary else Path(session / "parameters.txt").read_text(
            encoding="utf-8", errors="replace"
        ).split("dataset=", 1)[-1].splitlines()[0].rsplit("/", 1)[-1]
        if (session / "parameters.txt").exists() else None
    )
    tasks = mapping.get("tasks", []) if mapping else []
    assignments = mapping.get("assignments", []) if mapping else []
    vms = mapping.get("vms", []) if mapping else []
    loads = mapping.get("loads", {}) if mapping else {}
    completed = len(result.get("completed", [])) if result else 0
    execution_mode = "EXECUTED" if result else "PLAN / WAITING"
    task_count = int(summary.get("tasks", len(tasks)) or len(tasks))
    return {
        "available": True, "session": session.name, "mode": execution_mode,
        "algorithm": (mapping or {}).get("algorithm", "LLFD"),
        "summary": summary, "task_count": task_count, "tasks": tasks,
        "dataset": dataset_name,
        "datasets": [path.stem.removeprefix("summary_") for path in summary_candidates],
        "assignments": assignments, "vms": vms, "loads": loads,
        "makespan": (mapping or {}).get("makespan_predicted_seconds",
                     summary.get("predicted_makespan_seconds")),
        "completed": completed, "elapsed": result.get("elapsed_seconds") if result else None,
        "workers": docker_status(), "logs": logs[-500:],
        "result_available": result is not None,
    }

class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            body = json.dumps(dashboard_data()).encode()
            return self.send_bytes(body, "application/json; charset=utf-8")
        routes = {
            "/": (DASHBOARD / "index.html", "text/html; charset=utf-8"),
            "/static/css/dashboard.css": (DASHBOARD / "static/css/dashboard.css", "text/css; charset=utf-8"),
            "/static/js/dashboard.js": (DASHBOARD / "static/js/dashboard.js", "application/javascript; charset=utf-8"),
        }
        if path not in routes:
            return self.send_bytes(b"Not found", "text/plain", 404)
        file, content_type = routes[path]
        try:
            return self.send_bytes(file.read_bytes(), content_type)
        except OSError:
            return self.send_bytes(b"Dashboard asset missing", "text/plain", 500)

    def log_message(self, fmt, *args):
        print("[dashboard] " + fmt % args)

if __name__ == "__main__":
    print(f"SOKA LLFD Dashboard: http://127.0.0.1:{PORT}")
    print("Data source: realworld/results/sessions (latest session)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
