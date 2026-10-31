# Experiment sessions

`run.sh` writes each execution into a timestamped directory (or into
`RESULTS_DIR` when explicitly set):

```text
sessions/<YYYYMMDD_HHMMSS>/
├── parameters.txt
├── logs/
│   ├── llfd.log
│   ├── llfd_100.log
│   └── llfd_1000.log
├── mappings/
│   ├── llfd_mapping.json
│   ├── llfd_mapping_100.json
│   └── llfd_mapping_1000.json
├── summary.csv
├── summary_100.csv
├── summary_1000.csv
├── scale-summary.csv
├── tasks_GoogleClusterTrace_n100_run1.csv
└── tasks_GoogleClusterTrace_n1000_run1.csv
```

The `summary_<size>.csv`, mapping, task CSV, and log with the same size belong
to the same Google Trace dataset. A scale session therefore keeps 100-task and
1000-task results separately instead of mixing them.
