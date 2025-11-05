#!/usr/bin/env python3
"""
Aggregate Snakemake benchmark files into summary reports.

This script collects all benchmark TSV files, adds metadata about rule name
and wildcards, and produces both detailed and summary reports.
"""

import argparse
import pandas as pd
import re
from pathlib import Path
import sys


def parse_benchmark_path(filepath):
    """Extract metadata from benchmark file path."""
    # Convert to Path object
    path = Path(filepath)

    # Parse the full path to extract rule name correctly
    # Path structure: benchmarks/{rule}/[{rep}/]{filename}.tsv
    parts = path.parts

    # Find the 'benchmarks' directory in the path
    try:
        benchmark_idx = parts.index('benchmarks')
        rule_name = parts[benchmark_idx + 1]  # Rule name comes after 'benchmarks'
    except (ValueError, IndexError):
        rule_name = path.parent.name  # Fallback

    metadata = {'rule': rule_name, 'file': str(filepath)}

    # Get filename without extension
    stem = path.stem

    # Check if parent directory is a replicate number (for nested structure)
    parent_name = path.parent.name
    if parent_name.isdigit():
        metadata['rep'] = int(parent_name)

    # For files like {rep}.tsv (treesort, prep, rea)
    if stem.isdigit() and 'rep' not in metadata:
        metadata['rep'] = int(stem)

    # Extract subtype and segment from filename like h3nx_pb2.tsv
    if '_' in stem and not stem.isdigit():
        parts_name = stem.split('_')
        if len(parts_name) >= 2:
            # Common subtypes
            if parts_name[0] in ['h3nx', 'h1n1', 'h3n2', 'h5n1', 'h7n9']:
                metadata['subtype'] = parts_name[0]
                metadata['segment'] = '_'.join(parts_name[1:])

    return metadata


def read_benchmark_file(filepath):
    """Read a single benchmark TSV file and add metadata."""
    try:
        df = pd.read_csv(filepath, sep='\t')

        # Add metadata from path
        metadata = parse_benchmark_path(filepath)
        for key, value in metadata.items():
            df[key] = value

        return df
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return None


def aggregate_benchmarks(benchmark_files, output_detailed, output_summary):
    """Aggregate all benchmark files into detailed and summary reports."""

    # Read all benchmark files
    dfs = []
    for filepath in benchmark_files:
        df = read_benchmark_file(filepath)
        if df is not None:
            dfs.append(df)

    if not dfs:
        print("Error: No benchmark files could be read!", file=sys.stderr)
        sys.exit(1)

    # Combine all benchmarks
    detailed = pd.concat(dfs, ignore_index=True)

    # Reorder columns to put metadata first
    metadata_cols = ['rule', 'rep', 'subtype', 'segment', 'file']
    metric_cols = ['s', 'h:m:s', 'max_rss', 'max_vms', 'max_uss', 'max_pss',
                   'io_in', 'io_out', 'mean_load', 'cpu_time']

    # Only include columns that exist
    existing_metadata = [col for col in metadata_cols if col in detailed.columns]
    existing_metrics = [col for col in metric_cols if col in detailed.columns]

    detailed = detailed[existing_metadata + existing_metrics]

    # Save detailed report
    detailed.to_csv(output_detailed, index=False)
    print(f"Saved detailed benchmark report to {output_detailed}")

    # Create summary statistics by rule
    # Group by rule and calculate statistics
    numeric_cols = detailed.select_dtypes(include=['number']).columns
    summary_stats = []

    for rule in detailed['rule'].unique():
        rule_data = detailed[detailed['rule'] == rule]

        stats = {'rule': rule, 'n_runs': len(rule_data)}

        for col in numeric_cols:
            if col in ['rep']:  # Skip metadata columns
                continue
            if col in rule_data.columns:
                stats[f'{col}_mean'] = rule_data[col].mean()
                stats[f'{col}_median'] = rule_data[col].median()
                stats[f'{col}_std'] = rule_data[col].std()
                stats[f'{col}_min'] = rule_data[col].min()
                stats[f'{col}_max'] = rule_data[col].max()

        summary_stats.append(stats)

    summary = pd.DataFrame(summary_stats)

    # Round numeric columns for readability
    numeric_cols_summary = summary.select_dtypes(include=['number']).columns
    summary[numeric_cols_summary] = summary[numeric_cols_summary].round(3)

    # Save summary report
    summary.to_csv(output_summary, index=False)
    print(f"Saved summary benchmark report to {output_summary}")

    # Print summary to stdout
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY (by rule)")
    print("="*80)

    # Create a simplified view for terminal output
    simple_summary = summary[['rule', 'n_runs', 's_mean', 's_median',
                               'max_rss_mean', 'cpu_time_mean']].copy()
    simple_summary.columns = ['Rule', 'Runs', 'Time(s) Mean', 'Time(s) Median',
                              'Memory(MB) Mean', 'CPU Time(s) Mean']

    print(simple_summary.to_string(index=False))
    print("="*80)

    # Total pipeline stats
    total_time = detailed['s'].sum()
    total_cpu_time = detailed['cpu_time'].sum() if 'cpu_time' in detailed.columns else 0
    max_memory = detailed['max_rss'].max() if 'max_rss' in detailed.columns else 0

    print(f"\nTOTAL PIPELINE STATS:")
    print(f"  Total wall time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"  Total CPU time: {total_cpu_time:.2f} seconds")
    print(f"  Peak memory usage: {max_memory:.2f} MB")
    print(f"  Total benchmark files: {len(benchmark_files)}")
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate Snakemake benchmark files into summary reports"
    )
    parser.add_argument(
        '--benchmarks',
        nargs='+',
        required=True,
        help='List of benchmark TSV files to aggregate'
    )
    parser.add_argument(
        '--detailed',
        required=True,
        help='Output path for detailed benchmark CSV'
    )
    parser.add_argument(
        '--summary',
        required=True,
        help='Output path for summary statistics CSV'
    )

    args = parser.parse_args()

    aggregate_benchmarks(args.benchmarks, args.detailed, args.summary)


if __name__ == '__main__':
    main()
