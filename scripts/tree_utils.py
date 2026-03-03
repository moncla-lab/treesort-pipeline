#!/usr/bin/env python3
"""
Shared tree utilities for the treesort pipeline.

Provides standardized tree loading, taxon normalization, leaf-set mapping,
and ancestral walk algorithms used by mapper.py and diagnostic scripts.
"""

import dendropy
import random


def normalize_taxon_label(label):
    """Normalize taxon labels to consistent 'strain|date' format."""
    if not label:
        return label
    clean_label = label.strip().strip("'\"")
    parts = clean_label.split('|')
    if len(parts) >= 2:
        return f"{parts[0]}|{parts[1]}"
    else:
        return clean_label


def normalize_tree_taxa(tree):
    """Apply normalize_taxon_label to all leaf taxa in a dendropy Tree."""
    for leaf in tree.leaf_nodes():
        if leaf.taxon and leaf.taxon.label:
            leaf.taxon.label = normalize_taxon_label(leaf.taxon.label)


def load_tree(path, suppress_internal_node_taxa=True):
    """Load a newick tree with standard options and normalize taxa."""
    tree = dendropy.Tree.get(
        path=path,
        schema="newick",
        preserve_underscores=True,
        suppress_internal_node_taxa=suppress_internal_node_taxa
    )
    normalize_tree_taxa(tree)
    return tree


def label_internal_nodes(tree):
    """Assign TS_NODE_{counter:07d} labels to unlabeled internal nodes (postorder)."""
    counter = 0
    for node in tree.postorder_internal_node_iter():
        if not node.label:
            node.label = f"TS_NODE_{counter:07d}"
            counter += 1
    return tree


def build_leaf_map(tree):
    """Build {node_label: frozenset(leaf_labels)} for all labeled nodes."""
    leaf_map = {}
    for node in tree.preorder_node_iter():
        node_label = node.label or (node.taxon and node.taxon.label)
        if node_label:
            leaf_set = frozenset(
                leaf.taxon.label
                for leaf in node.leaf_nodes()
                if leaf.taxon and leaf.taxon.label
            )
            leaf_map[node_label] = leaf_set
    return leaf_map


def build_leaf_map_inverse(leaf_map):
    """Invert leaf map to {frozenset(leaf_labels): node_label} for O(1) lookup."""
    return {leaf_set: label for label, leaf_set in leaf_map.items()}


def ancestral_walk(source_leaf_set, target_tree, target_leaf_map_inv):
    """
    Find target node matching a source leaf set via direct match or tree walk.
    Returns target node label or None.
    """
    if source_leaf_set in target_leaf_map_inv:
        return target_leaf_map_inv[source_leaf_set]

    if not source_leaf_set:
        return None

    random_leaf_label = random.choice(list(source_leaf_set))
    leaf_node = target_tree.find_node_with_taxon_label(random_leaf_label)
    if not leaf_node:
        return None

    current_node = leaf_node.parent_node
    while current_node:
        current_leaves = frozenset(
            leaf.taxon.label
            for leaf in current_node.leaf_nodes()
            if leaf.taxon and leaf.taxon.label
        )
        if source_leaf_set.issubset(current_leaves):
            return current_node.label or (current_node.taxon and current_node.taxon.label)
        current_node = current_node.parent_node

    return None
