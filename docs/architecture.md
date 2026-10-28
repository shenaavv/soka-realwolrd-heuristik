# LLFD real-world architecture

The repository follows the same experiment-oriented layout as the reference
project:

```text
src/main/resources/dataset/  input datasets
scripts/                     repeatable experiment entry points
realworld/                   Docker, Kubernetes, scheduler, and worker
realworld/results/           logs, mappings, summaries, and per-run outputs
docs/                        architecture and experiment notes
```

## Topology

There is one logical datacenter (`DC-1`) with two hosts. Each host contains two
VMs:

| Datacenter | Host | VM | PE | MIPS |
|---|---|---|---:|---:|
| DC-1 | host-1 | vm-1 | 4 | 2,500 |
| DC-1 | host-1 | vm-2 | 2 | 1,500 |
| DC-1 | host-2 | vm-3 | 4 | 2,500 |
| DC-1 | host-2 | vm-4 | 2 | 1,500 |

Docker represents a VM with a container. Kubernetes represents a VM with one
Deployment replica/Pod. Kubernetes node labels represent the two physical
hosts. The datacenter is represented by the `dc-1` namespace.

## Results

Every `run.sh` execution creates a timestamped folder under
`realworld/results/sessions/` containing:

- `parameters.txt`
- `logs/llfd.log`
- `mappings/llfd_mapping.json`
- `tasks_LLFD_n<N>_run1.csv`
- `summary.csv`

