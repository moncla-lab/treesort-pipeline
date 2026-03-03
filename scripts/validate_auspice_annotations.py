#!/usr/bin/env python3
"""
Validate that reassortment annotations survive the augur export into Auspice JSON.

Cross-references unannotated nodes from diagnose_unannotated with the final
Auspice tree to classify each into:
- missing_from_auspice: node not present in Auspice tree at all
- in_auspice_no_reassorted: node present but has no 'reassorted' attribute
- in_auspice_with_reassorted: node present AND has reassorted (inconsistency!)
"""

import argparse
import json
import sys


def extract_auspice_nodes(node, nodes_dict):
    """Recursively extract all nodes and their attributes from Auspice tree."""
    name = node.get("name", "")
    attrs = node.get("node_attrs", {})

    if name:
        nodes_dict[name] = {
            "reassorted": attrs.get("reassorted", {}).get("value") if "reassorted" in attrs else None,
            "has_reassorted_attr": "reassorted" in attrs,
        }

    for child in node.get("children", []):
        extract_auspice_nodes(child, nodes_dict)


def validate_auspice(auspice_path, unannotated_path, output_path):
    # Load Auspice JSON
    print("Loading Auspice JSON...", file=sys.stderr)
    with open(auspice_path) as f:
        auspice = json.load(f)

    auspice_nodes = {}
    if "tree" in auspice:
        extract_auspice_nodes(auspice["tree"], auspice_nodes)

    total_auspice = len(auspice_nodes)
    with_reassorted = sum(1 for n in auspice_nodes.values() if n["has_reassorted_attr"])
    print(f"Total Auspice nodes: {total_auspice}", file=sys.stderr)
    print(f"With reassorted attr: {with_reassorted}", file=sys.stderr)

    # Load unannotated nodes from upstream diagnostic
    print("Loading unannotated nodes list...", file=sys.stderr)
    with open(unannotated_path) as f:
        unannotated_data = json.load(f)

    unannotated_list = [
        entry["node"] for entry in unannotated_data.get("unannotated_nodes", [])
    ]

    # Classify each unannotated node
    missing_from_auspice = []
    in_auspice_no_reassorted = []
    in_auspice_with_reassorted = []

    for node_id in unannotated_list:
        # Try different label formats
        found_key = None
        for key in auspice_nodes:
            if node_id in key or node_id.replace("NODE_", "TS_NODE_") in key:
                found_key = key
                break

        if not found_key:
            missing_from_auspice.append(node_id)
        elif not auspice_nodes[found_key]["has_reassorted_attr"]:
            in_auspice_no_reassorted.append(node_id)
        else:
            in_auspice_with_reassorted.append({
                "node": node_id,
                "reassorted_value": auspice_nodes[found_key]["reassorted"],
            })

    result = {
        "total_auspice_nodes": total_auspice,
        "auspice_nodes_with_reassorted": with_reassorted,
        "auspice_nodes_without_reassorted": total_auspice - with_reassorted,
        "unannotated_checked": len(unannotated_list),
        "missing_from_auspice": len(missing_from_auspice),
        "in_auspice_no_reassorted": len(in_auspice_no_reassorted),
        "in_auspice_with_reassorted": len(in_auspice_with_reassorted),
        "inconsistencies": in_auspice_with_reassorted,
        "missing_node_ids": missing_from_auspice,
    }

    if in_auspice_with_reassorted:
        print(
            f"WARNING: {len(in_auspice_with_reassorted)} nodes marked unannotated "
            f"but HAVE reassorted in Auspice!", file=sys.stderr
        )

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Wrote validation to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate reassortment annotations in Auspice JSON"
    )
    parser.add_argument("--auspice", required=True, help="Path to Auspice JSON")
    parser.add_argument("--unannotated", required=True, help="Path to unannotated_nodes.json")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    validate_auspice(args.auspice, args.unannotated, args.output)
