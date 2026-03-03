#!/usr/bin/env python3
"""
Diagnose unmapped targets: find target tree nodes that receive NO source mappings.

For each source node, simulates the mapping process (direct match or ancestral walk)
and tracks which target nodes receive mappings. Reports target nodes that are
unreachable from any source node.
"""

import argparse
import json
import sys
from collections import defaultdict
from tree_utils import (
    load_tree,
    label_internal_nodes,
    build_leaf_map,
    build_leaf_map_inverse,
    ancestral_walk,
)


def diagnose_unmapped(source_path, target_path, output_path):
    print("Loading trees...", file=sys.stderr)
    source_tree = load_tree(source_path)
    label_internal_nodes(source_tree)
    target_tree = load_tree(target_path)
    label_internal_nodes(target_tree)

    print("Building leaf maps...", file=sys.stderr)
    source_leaf_map = build_leaf_map(source_tree)
    target_leaf_map = build_leaf_map(target_tree)
    target_leaf_map_inv = build_leaf_map_inverse(target_leaf_map)

    # Simulate mapping: for each source node, find target node
    print("Simulating mapping process...", file=sys.stderr)
    target_receives_from = defaultdict(list)

    for source_label, source_leaf_set in source_leaf_map.items():
        target_label = ancestral_walk(source_leaf_set, target_tree, target_leaf_map_inv)
        if target_label:
            target_receives_from[target_label].append(source_label)

    # Identify unannotated target nodes
    all_target_internal = [
        label for label in target_leaf_map.keys() if 'NODE' in label
    ]
    annotated = [t for t in all_target_internal if t in target_receives_from]
    unannotated = [t for t in all_target_internal if t not in target_receives_from]

    print(f"Target internal nodes: {len(all_target_internal)}", file=sys.stderr)
    print(f"Received at least one mapping: {len(annotated)}", file=sys.stderr)
    print(f"Received NO mappings: {len(unannotated)}", file=sys.stderr)

    # Build detailed info for unannotated nodes
    unannotated_details = []
    source_leaf_sets = list(source_leaf_map.values())
    for target_label in unannotated:
        target_leaves = target_leaf_map[target_label]
        detail = {
            "node": target_label,
            "num_leaves": len(target_leaves),
            "leaf_set_in_source": target_leaves in source_leaf_sets,
        }

        # Find source nodes whose leaf sets are subsets of this target
        containing_source = []
        for src_label, src_leaves in source_leaf_map.items():
            if src_leaves and src_leaves.issubset(target_leaves):
                containing_source.append({
                    "source_node": src_label,
                    "num_leaves": len(src_leaves),
                })
        containing_source.sort(key=lambda x: -x["num_leaves"])
        detail["subset_source_nodes"] = containing_source[:5]
        unannotated_details.append(detail)

    # Write JSON output
    result = {
        "total_target_internal": len(all_target_internal),
        "annotated_count": len(annotated),
        "unannotated_count": len(unannotated),
        "unannotated_nodes": unannotated_details,
    }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Wrote diagnostics to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Diagnose target nodes that receive no source mappings"
    )
    parser.add_argument("--source", required=True, help="Path to source tree (backbone.nwk)")
    parser.add_argument("--target", required=True, help="Path to target tree (original.nwk)")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    diagnose_unmapped(args.source, args.target, args.output)
