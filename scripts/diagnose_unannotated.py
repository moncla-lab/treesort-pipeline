#!/usr/bin/env python3
"""
Diagnose unannotated nodes: find target tree internal nodes that have no
corresponding entry in the mapper's node.json output.
"""

import argparse
import json
import sys
from tree_utils import (
    normalize_taxon_label,
    load_tree,
    label_internal_nodes,
)


def diagnose_unannotated(target_path, node_data_path, output_path):
    # Load and label target tree
    print("Loading target tree...", file=sys.stderr)
    target = load_tree(target_path)
    label_internal_nodes(target)

    # Build target node inventory (internal nodes only)
    target_nodes = {}
    for node in target.preorder_node_iter():
        label = node.label or (node.taxon and node.taxon.label)
        if label and 'NODE' in label:
            leaves = frozenset(
                normalize_taxon_label(l.taxon.label)
                for l in node.leaf_nodes() if l.taxon
            )
            target_nodes[label] = {
                'num_leaves': len(leaves),
            }

    print(f"Target internal nodes: {len(target_nodes)}", file=sys.stderr)

    # Load mapper output
    print("Loading node.json...", file=sys.stderr)
    with open(node_data_path) as f:
        node_data = json.load(f)

    annotated = set(node_data.get("nodes", {}).keys())
    print(f"Annotated nodes in node.json: {len(annotated)}", file=sys.stderr)

    # Find unannotated: check both TS_NODE_ and NODE_ prefixes
    unannotated = []
    for label in target_nodes:
        if label not in annotated:
            alt = label.replace("TS_NODE_", "NODE_")
            if alt not in annotated:
                unannotated.append(label)

    print(f"Unannotated nodes: {len(unannotated)}", file=sys.stderr)

    # Compute stats
    leaf_counts = [target_nodes[n]['num_leaves'] for n in unannotated]

    result = {
        "total_target_internal": len(target_nodes),
        "annotated_count": len(target_nodes) - len(unannotated),
        "unannotated_count": len(unannotated),
        "unannotated_nodes": [
            {"node": label, "num_leaves": target_nodes[label]['num_leaves']}
            for label in sorted(unannotated)
        ],
    }
    if leaf_counts:
        result["leaf_count_stats"] = {
            "min": min(leaf_counts),
            "max": max(leaf_counts),
            "median": sorted(leaf_counts)[len(leaf_counts) // 2],
        }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Wrote diagnostics to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Diagnose target nodes missing from mapper output"
    )
    parser.add_argument("--target", required=True, help="Path to target tree (original.nwk)")
    parser.add_argument("--node_data", required=True, help="Path to mapper output (node.json)")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    diagnose_unannotated(args.target, args.node_data, args.output)
