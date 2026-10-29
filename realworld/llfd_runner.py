#!/usr/bin/env python3
"""Create an LLFD plan and optionally execute it on workers."""

import argparse
import csv
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic

from llfd_scheduler import VM, Task, plan_as_dict

VMS = (
    VM("vm-1", "host-1", 4, 2500, "http://127.0.0.1:9101"),
    VM("vm-2", "host-1", 2, 1500, "http://127.0.0.1:9102"),
    VM("vm-3", "host-2", 4, 2500, "http://127.0.0.1:9103"),
    VM("vm-4", "host-2", 2, 1500, "http://127.0.0.1:9104"),
)


def optimization_metrics(plan):
    """Return explainable LLFD load-balance indicators."""
    loads = plan["loads"]
    makespan = plan["makespan_predicted_seconds"]
    average_load = sum(loads.values()) / len(loads) if loads else 0.0
    min_load = min(loads.values(), default=0.0)
    max_load = max(loads.values(), default=0.0)
    total_mi = sum(task["length_mi"] for task in plan["tasks"])
    total_mips = sum(vm["mips"] for vm in plan["vms"])
    ideal_makespan = total_mi / total_mips if total_mips else 0.0
    return {
        "average_load_seconds": average_load,
        "min_load_seconds": min_load,
        "max_load_seconds": max_load,
        "load_balance_efficiency_percent": (
            average_load / max_load * 100 if max_load else 100.0
        ),
        "load_imbalance_percent": (
            (max_load - min_load) / max_load * 100 if max_load else 0.0
        ),
        "ideal_makespan_lower_bound_seconds": ideal_makespan,
        "makespan_gap_from_ideal_percent": (
            (makespan / ideal_makespan - 1) * 100
            if ideal_makespan else 0.0
        ),
    }


def print_report(plan, dataset, mode):
    """Print the experiment report in a readable, reference-style format."""
    assignments = plan["assignments"]
    loads = plan["loads"]
    total_mi = sum(task["length_mi"] for task in plan["tasks"])
    print("\n" + "=" * 78)
    print("LLFD REAL-WORLD EXPERIMENT")
    print("=" * 78)
    print(f"algorithm       : LLFD (Least-Loaded First-Fit Decreasing)")
    print(f"mode            : {mode}")
    print(f"dataset         : {dataset}")
    print(f"datacenter      : DC-1")
    print(f"hosts           : 2")
    print(f"vm per host     : 2")
    print(f"total VM        : {len(VMS)}")
    print(f"total task      : {len(plan['tasks'])}")
    print(f"total length MI : {total_mi:,.0f}")
    print("-" * 78)
    print("TOPOLOGY")
    for host in ("host-1", "host-2"):
        host_vms = [vm for vm in VMS if vm.host == host]
        print(f"  DC-1/{host}")
        for vm in host_vms:
            print(f"    {vm.id}: {vm.pes} PE x {vm.mips:,.0f} MIPS -> {vm.endpoint}")
    print("-" * 78)
    print("SCHEDULING TRACE (FFD order, then least accumulated load)")
    print(f"{'order':>5} {'task':>5} {'lengthMI':>12} {'VM':>6} {'host':>8} "
          f"{'exec(s)':>12} {'fallback':>9}")
    for order, item in enumerate(
        sorted(assignments, key=lambda value: (-value["lengthMI"], value["task_id"])), 1
    ):
        print(f"{order:>5} {item['task_id']:>5} {item['lengthMI']:>12,.0f} "
              f"{item['vm']:>6} {item['host']:>8} {item['predicted_seconds']:>12.3f} "
              f"{str(item['fallback']):>9}")
    print("-" * 78)
    print("VM LOAD SUMMARY")
    print(f"{'VM':>6} {'host':>8} {'tasks':>7} {'load(s)':>14} {'share':>10}")
    for vm in VMS:
        count = sum(item["vm"] == vm.id for item in assignments)
        share = loads[vm.id] / plan["makespan_predicted_seconds"] if plan["makespan_predicted_seconds"] else 0
        print(f"{vm.id:>6} {vm.host:>8} {count:>7} {loads[vm.id]:>14.3f} {share:>9.1%}")
    print("-" * 78)
    print("METRICS")
    print(f"  predicted makespan : {plan['makespan_predicted_seconds']:.3f} s")
    print(f"  average VM load    : {sum(loads.values()) / len(loads):.3f} s")
    print(f"  min VM load        : {min(loads.values()):.3f} s")
    print(f"  max VM load        : {max(loads.values()):.3f} s")
    metrics = optimization_metrics(plan)
    print("-" * 78)
    print("LLFD OPTIMIZATION INDICATORS")
    print(f"  load-balance efficiency : "
          f"{metrics['load_balance_efficiency_percent']:.2f}%")
    print(f"  load imbalance          : "
          f"{metrics['load_imbalance_percent']:.2f}%")
    print(f"  ideal makespan lower bound: "
          f"{metrics['ideal_makespan_lower_bound_seconds']:.3f} s")
    print(f"  makespan gap vs ideal   : "
          f"{metrics['makespan_gap_from_ideal_percent']:.2f}%")
    print("=" * 78)


def read_tasks(path):
    tasks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            tasks.append(Task(len(tasks), float(re.split(r"[,;\s]+", value)[0])))
    if not tasks:
        raise ValueError(f"dataset kosong: {path}")
    return tasks


def post_batch(vm, assignments, iterations_per_mi):
    body = {"tasks": [
        {"id": item["task_id"], "iterations": max(1, int(item["lengthMI"] * iterations_per_mi))}
        for item in assignments
    ]}
    request = urllib.request.Request(
        f"{vm.endpoint}/batch", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3600) as response:
        return [json.loads(line) for line in response.read().decode().splitlines() if line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("realworld/results/llfd-plan.json"))
    parser.add_argument("--task-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--iterations-per-mi", type=float, default=2)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--compact", action="store_true",
                        help="print only summary metrics for large-scale runs")
    args = parser.parse_args()
    if args.iterations_per_mi <= 0:
        parser.error("--iterations-per-mi harus positif")

    plan = plan_as_dict(read_tasks(args.dataset), VMS)
    plan["optimization"] = optimization_metrics(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if args.task_output:
        args.task_output.parent.mkdir(parents=True, exist_ok=True)
        with args.task_output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["task_id", "lengthMI", "pes", "vm", "host", "predicted_seconds"])
            writer.writerows(
                [item["task_id"], item["lengthMI"], item["pes"], item["vm"], item["host"],
                 item["predicted_seconds"]]
                for item in plan["assignments"]
            )
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            loads = plan["loads"].values()
            writer.writerow(["algorithm", "datacenter", "hosts", "vms", "tasks",
                             "total_length_mi", "predicted_makespan_seconds",
                             "average_vm_load_seconds", "min_vm_load_seconds",
                             "max_vm_load_seconds", "load_balance_efficiency_percent",
                             "load_imbalance_percent", "ideal_makespan_lower_bound_seconds",
                             "makespan_gap_from_ideal_percent"])
            writer.writerow([
                "LLFD", "DC-1", 2, 4, len(plan["tasks"]),
                sum(task["length_mi"] for task in plan["tasks"]),
                plan["makespan_predicted_seconds"],
                plan["optimization"]["average_load_seconds"],
                plan["optimization"]["min_load_seconds"],
                plan["optimization"]["max_load_seconds"],
                plan["optimization"]["load_balance_efficiency_percent"],
                plan["optimization"]["load_imbalance_percent"],
                plan["optimization"]["ideal_makespan_lower_bound_seconds"],
                plan["optimization"]["makespan_gap_from_ideal_percent"],
            ])
    if args.compact:
        print(
            f"LLFD dataset={args.dataset.name} tasks={len(plan['tasks'])} "
            f"makespan={plan['makespan_predicted_seconds']:.3f}s "
            f"load_balance_efficiency="
            f"{plan['optimization']['load_balance_efficiency_percent']:.2f}% "
            f"load_imbalance={plan['optimization']['load_imbalance_percent']:.2f}% "
            f"loads={json.dumps(plan['loads'], sort_keys=True)}"
        )
    else:
        print_report(plan, args.dataset, "plan" if args.plan_only else "real-world")
    if args.plan_only:
        return

    started = monotonic()
    grouped = {vm.id: [] for vm in VMS}
    for item in plan["assignments"]:
        grouped[item["vm"]].append(item)
    by_id = {vm.id: vm for vm in VMS}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(post_batch, by_id[vm_id], items, args.iterations_per_mi)
                   for vm_id, items in grouped.items() if items]
        results = [event for future in futures for event in future.result()]
    result = {"algorithm": "LLFD", "elapsed_seconds": monotonic() - started, "completed": results}
    result_path = args.output.parent.parent / "llfd-result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nEXECUTION RESULT: {len(results)} task selesai")
    print(f"real elapsed time : {result['elapsed_seconds']:.3f} s")
    print(f"result file       : {result_path}")


if __name__ == "__main__":
    main()
