#!/usr/bin/env python3
"""
Aggregate Snakemake benchmark TSV files into detailed and summary CSV reports.
"""

import argparse
import csv
import os
import statistics
import sys


KNOWN_SUBTYPES = {"h3nx", "h1n1", "h3n2", "h5n1", "h7n9"}

SNAKEMAKE_COLS = [
    "s", "h:m:s", "max_rss", "max_vms", "max_uss", "max_pss",
    "io_in", "io_out", "mean_load", "cpu_time"
]

NUMERIC_COLS = [
    "s", "max_rss", "max_vms", "max_uss", "max_pss",
    "io_in", "io_out", "mean_load", "cpu_time"
]


def parse_benchmark_path(path):
    """Extract rule, rep, subtype, segment from a benchmark file path."""
    parts = os.path.normpath(path).split(os.sep)

    rule = ""
    rep = ""
    subtype = ""
    segment = ""

    # Find the 'benchmarks' directory in the path
    try:
        bench_idx = parts.index("benchmarks")
    except ValueError:
        return rule, rep, subtype, segment

    # Next component is the rule name
    if bench_idx + 1 < len(parts):
        rule = parts[bench_idx + 1]

    stem = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path))

    # If parent directory is a digit, that's the replicate
    if parent.isdigit():
        rep = parent
    # If the stem is a digit, that's the replicate
    elif stem.isdigit():
        rep = stem

    # Check if stem contains subtype_segment pattern
    if "_" in stem:
        prefix = stem.split("_")[0]
        if prefix in KNOWN_SUBTYPES:
            subtype = prefix
            segment = "_".join(stem.split("_")[1:])

    return rule, rep, subtype, segment


def read_benchmark_tsv(path):
    """Read a single Snakemake benchmark TSV and return the data row as a dict."""
    with open(path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    if rows:
        return rows[0]
    return {}


def aggregate(benchmark_paths, detailed_path, summary_path):
    # Build detailed rows
    detailed_rows = []
    for path in benchmark_paths:
        rule, rep, subtype, segment = parse_benchmark_path(path)
        data = read_benchmark_tsv(path)
        row = {
            "rule": rule,
            "rep": rep,
            "subtype": subtype,
            "segment": segment,
            "file": path,
        }
        for col in SNAKEMAKE_COLS:
            row[col] = data.get(col, "")
        detailed_rows.append(row)

    # Write detailed CSV
    detailed_fields = ["rule", "rep", "subtype", "segment", "file"] + SNAKEMAKE_COLS
    with open(detailed_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detailed_fields)
        writer.writeheader()
        writer.writerows(detailed_rows)
    print(f"Wrote detailed benchmarks to {detailed_path}", file=sys.stderr)

    # Build summary: group by rule
    by_rule = {}
    for row in detailed_rows:
        rule = row["rule"]
        if rule not in by_rule:
            by_rule[rule] = []
        by_rule[rule].append(row)

    summary_rows = []
    for rule in sorted(by_rule.keys()):
        rows = by_rule[rule]
        summary = {"rule": rule, "n_runs": len(rows)}

        for col in NUMERIC_COLS:
            values = []
            for r in rows:
                try:
                    values.append(float(r[col]))
                except (ValueError, KeyError):
                    pass

            if values:
                summary[f"{col}_mean"] = round(statistics.mean(values), 4)
                summary[f"{col}_median"] = round(statistics.median(values), 4)
                summary[f"{col}_std"] = round(statistics.stdev(values), 4) if len(values) > 1 else 0.0
                summary[f"{col}_min"] = round(min(values), 4)
                summary[f"{col}_max"] = round(max(values), 4)
            else:
                for suffix in ("mean", "median", "std", "min", "max"):
                    summary[f"{col}_{suffix}"] = ""

        summary_rows.append(summary)

    # Write summary CSV
    summary_fields = ["rule", "n_runs"]
    for col in NUMERIC_COLS:
        for suffix in ("mean", "median", "std", "min", "max"):
            summary_fields.append(f"{col}_{suffix}")

    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote summary benchmarks to {summary_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Aggregate Snakemake benchmark TSVs into CSV reports"
    )
    parser.add_argument("--benchmarks", nargs="+", required=True,
                        help="Benchmark TSV files to aggregate")
    parser.add_argument("--detailed", required=True,
                        help="Output path for detailed CSV")
    parser.add_argument("--summary", required=True,
                        help="Output path for summary CSV")
    args = parser.parse_args()

    aggregate(args.benchmarks, args.detailed, args.summary)
