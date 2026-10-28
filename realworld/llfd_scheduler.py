#!/usr/bin/env python3
"""Least-Loaded First-Fit Decreasing scheduler."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Task:
    id: int
    length_mi: float
    pes: int = 1


@dataclass(frozen=True)
class VM:
    id: str
    host: str
    pes: int
    mips: float
    endpoint: str


def schedule(tasks, vms):
    """Return LLFD assignments and final accumulated loads."""
    task_list = list(tasks)
    vm_list = list(vms)
    if not vm_list:
        raise ValueError("at least one VM is required")
    if any(vm.mips <= 0 or vm.pes <= 0 for vm in vm_list):
        raise ValueError("VM PEs and MIPS must be positive")
    if any(task.length_mi < 0 or task.pes <= 0 for task in task_list):
        raise ValueError("task length must be non-negative and PEs positive")
    if len({vm.id for vm in vm_list}) != len(vm_list):
        raise ValueError("VM IDs must be unique")

    loads = {vm.id: 0.0 for vm in vm_list}
    assignments = []
    for task in sorted(task_list, key=lambda item: (-item.length_mi, item.id)):
        feasible = [vm for vm in vm_list if vm.pes >= task.pes]
        candidates = feasible or vm_list
        vm = min(candidates, key=lambda item: (loads[item.id], item.id))
        predicted = task.length_mi / vm.mips
        loads[vm.id] += predicted
        assignments.append({
            "task_id": task.id,
            "lengthMI": task.length_mi,
            "pes": task.pes,
            "vm": vm.id,
            "host": vm.host,
            "predicted_seconds": predicted,
            "fallback": not bool(feasible),
        })
    assignments.sort(key=lambda item: item["task_id"])
    return assignments, loads


def plan_as_dict(tasks, vms):
    assignments, loads = schedule(tasks, vms)
    return {
        "algorithm": "LLFD",
        "tasks": [asdict(task) for task in tasks],
        "vms": [asdict(vm) for vm in vms],
        "assignments": assignments,
        "loads": loads,
        "makespan_predicted_seconds": max(loads.values(), default=0.0),
    }
