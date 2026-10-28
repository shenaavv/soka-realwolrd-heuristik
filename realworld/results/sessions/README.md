# Experiment sessions

`run.sh` writes each execution into a timestamped directory:

```text
sessions/<YYYYMMDD_HHMMSS>/
├── logs/llfd.log
├── mappings/llfd_mapping.json
├── parameters.txt
├── summary.csv
└── tasks_LLFD_n<N>_run1.csv
```

The files are intentionally similar to the reference experiment output while
containing LLFD-specific names and metrics.
