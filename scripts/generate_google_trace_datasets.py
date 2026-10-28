#!/usr/bin/env python3
"""Expand a Google Cluster Workload Trace seed into reproducible task sizes."""

import argparse
import random
from pathlib import Path


def read_values(path):
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.split("#", 1)[0].strip().replace(",", " ").split()
        if token:
            values.append(float(token[0]))
    if not values:
        raise ValueError(f"trace source kosong: {path}")
    return values


def write_dataset(source, destination, size, seed):
    values = read_values(source)
    rng = random.Random(seed + size)
    sample = [values[index] for index in rng.choices(range(len(values)), k=size)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(f"{value:g}" for value in sample) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sizes", default="100,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    sizes = [int(value) for value in args.sizes.split(",")]
    if any(size < 1 for size in sizes):
        parser.error("ukuran task harus positif")
    for size in sizes:
        destination = args.output_dir / f"GoogleClusterTrace_Dataset_{size}.txt"
        write_dataset(args.source, destination, size, args.seed)
        print(f"generated {destination} ({size} tasks)")


if __name__ == "__main__":
    main()
