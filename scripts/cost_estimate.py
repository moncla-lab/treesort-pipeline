#!/usr/bin/env python3
"""Estimate compute cost from Snakemake benchmark summary."""

import argparse
import csv
import sys


def main():
    parser = argparse.ArgumentParser(description="Estimate compute cost from benchmark summary")
    parser.add_argument("--input", required=True, help="Path to all_benchmarks_summary.csv")
    parser.add_argument("--cost", type=float, default=0.035, help="Cost per CPU-hour in dollars (default: 0.035)")
    parser.add_argument("--output", default="results/benchmarks/cost_estimate.csv", help="Output CSV path")
    args = parser.parse_args()

    total_seconds = 0
    rows = []

    with open(args.input) as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = int(row["n_runs"])
            mean_s = float(row["s_mean"])
            rule_total_s = n * mean_s
            rule_total_h = rule_total_s / 3600
            rule_cost = rule_total_h * args.cost
            total_seconds += rule_total_s
            rows.append((row["rule"], n, mean_s, rule_total_h, rule_cost))

    rows.sort(key=lambda x: -x[4])
    total_hours = total_seconds / 3600
    total_cost = total_hours * args.cost

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rule", "n_runs", "mean_s", "total_hours", "cost_usd"])
        for rule, n, mean_s, hours, cost in rows:
            writer.writerow([rule, n, f"{mean_s:.1f}", f"{hours:.4f}", f"{cost:.4f}"])
        writer.writerow(["TOTAL", "", "", f"{total_hours:.4f}", f"{total_cost:.4f}"])

    print(f"Wrote cost estimate to {args.output} (rate: ${args.cost}/cpu-hour)")


if __name__ == "__main__":
    main()
