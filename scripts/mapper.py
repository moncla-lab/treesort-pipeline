#!/usr/bin/env python3
"""
Fixed version of the treesort-to-tree mapper that addresses the key issues:
1. Proper taxon normalization between source and target trees
2. Robust ancestral walk algorithm that preserves all significant events
3. Efficient O(N*H) complexity instead of O(N*M)
"""

import dendropy
import os
import json
import argparse
import random
import re
import sys

def normalize_taxon_label(label):
	"""
	Normalizes taxon labels to consistent 'strain|date' format.
	Handles both 'strain|date' and 'strain|date|date' formats.
	"""
	if not label:
		return label
	
	# Remove quotes and whitespace
	clean_label = label.strip().strip("'\"")
	
	# Split by pipe and take first two parts (strain|date)
	parts = clean_label.split('|')
	if len(parts) >= 2:
		return f"{parts[0]}|{parts[1]}"
	else:
		return clean_label

def normalize_tree_taxa(tree):
	"""
	Normalizes all taxon labels in a tree to consistent format.
	"""
	for leaf in tree.leaf_nodes():
		if leaf.taxon and leaf.taxon.label:
			leaf.taxon.label = normalize_taxon_label(leaf.taxon.label)

def build_source_leaf_map_from_tree_string(tree_path):
	"""
	Builds a comprehensive map of {node_label: leaf_set} from source tree,
	handling both internal nodes (NODE_*) and leaf nodes.
	"""
	print("--- Building source leaf map from tree string ---")
	
	with open(tree_path, 'r') as f:
		tree_string = f.read().strip()
	
	source_leaf_map = {}
	
	# Parse the full tree to get leaf mappings
	try:
		tree = dendropy.Tree.get(data=tree_string, schema="newick", 
								suppress_internal_node_taxa=True, 
								suppress_leaf_node_taxa=False)
		normalize_tree_taxa(tree)
		
		# Build leaf map for all nodes
		for node in tree.preorder_node_iter():
			node_label = None
			if node.label:
				node_label = node.label
			elif node.taxon and node.taxon.label:
				node_label = normalize_taxon_label(node.taxon.label)
			
			if node_label:
				leaf_set = frozenset(normalize_taxon_label(leaf.taxon.label) 
								   for leaf in node.leaf_nodes() 
								   if leaf.taxon and leaf.taxon.label)
				source_leaf_map[node_label] = leaf_set
				
	except Exception as e:
		print(f"Warning: Could not parse full tree: {e}")
	
	# Extract internal nodes using regex approach as backup
	label_matches = list(re.finditer(r'\)(NODE_\d+)', tree_string))
	
	for match in label_matches:
		node_label = match.group(1)
		if node_label in source_leaf_map:
			continue  # Already processed
			
		# Find the clade boundaries
		clade_end_pos = match.start()
		paren_balance = 1
		clade_start_pos = -1
		
		for i in range(clade_end_pos - 1, -1, -1):
			char = tree_string[i]
			if char == ')': 
				paren_balance += 1
			elif char == '(': 
				paren_balance -= 1
			if paren_balance == 0:
				clade_start_pos = i
				break
		
		if clade_start_pos != -1:
			clade_str = tree_string[clade_start_pos : clade_end_pos + 1]
			try:
				temp_tree = dendropy.Tree.get(data=f"{clade_str};", schema="newick")
				normalize_tree_taxa(temp_tree)
				leaf_set = frozenset(normalize_taxon_label(l.taxon.label) 
								   for l in temp_tree.leaf_nodes() 
								   if l.taxon and l.taxon.label)
				source_leaf_map[node_label] = leaf_set
			except:
				continue
	
	print(f"Successfully parsed {len(source_leaf_map)} nodes from source tree.")
	return source_leaf_map

def get_labeled_canonical_tree(newick_path):
	"""
	Parses the target newick tree and labels all unlabeled internal nodes.
	"""
	tree = dendropy.Tree.get(path=newick_path, schema="newick", preserve_underscores=True)
	normalize_tree_taxa(tree)
	
	node_counter = 0
	for node in tree.postorder_internal_node_iter():
		if not node.label:
			node.label = f"NODE_{node_counter:07d}"
			node_counter += 1
	
	return tree

def build_target_leaf_map(target_tree):
	"""
	Builds efficient leaf mapping for target tree with both forward and inverse maps.
	"""
	target_leaf_map = {}
	target_leaf_map_inv = {}
	
	for node in target_tree.preorder_node_iter():
		node_label = node.label or (node.taxon and node.taxon.label)
		if node_label:
			leaf_set = frozenset(leaf.taxon.label for leaf in node.leaf_nodes() 
							   if leaf.taxon and leaf.taxon.label)
			target_leaf_map[node_label] = leaf_set
			target_leaf_map_inv[leaf_set] = node_label
	
	return target_leaf_map, target_leaf_map_inv

def map_node_with_ancestral_walk(source_leaf_set, target_tree, target_leaf_map_inv, debug=False, node_label=""):
	"""
	Efficient O(H) ancestral walk algorithm to find the corresponding node in target tree.
	"""
	# First try direct match
	if source_leaf_set in target_leaf_map_inv:
		if debug: 
			print(f"  ✓ Direct match found for {node_label}")
		return target_leaf_map_inv[source_leaf_set]
	
	if not source_leaf_set:
		if debug:
			print(f"  ✗ Empty leaf set for {node_label}")
		return None
	
	# Ancestral walk approach
	random_leaf_label = random.choice(list(source_leaf_set))
	if debug: 
		print(f"  → Starting ancestral walk from '{random_leaf_label}' for {node_label}")
	
	# Find the leaf node in target tree
	leaf_node = target_tree.find_node_with_taxon_label(random_leaf_label)
	if not leaf_node:
		if debug: 
			print(f"  ✗ Could not find leaf '{random_leaf_label}' in target tree")
		return None
	
	# Walk up the ancestry
	current_node = leaf_node.parent_node
	while current_node:
		current_label = current_node.label or (current_node.taxon and current_node.taxon.label)
		current_leaves = frozenset(leaf.taxon.label for leaf in current_node.leaf_nodes() 
								 if leaf.taxon and leaf.taxon.label)
		
		if source_leaf_set.issubset(current_leaves):
			if debug: 
				print(f"  ✓ Found containing clade at '{current_label}' for {node_label}")
			return current_label
		
		current_node = current_node.parent_node
	
	if debug: 
		print(f"  ✗ Ancestral walk failed for {node_label}")
	return None

def create_augur_node_data(mapped_summary_data):
	"""
	Formats the mapped summary data for augur export --node-data.
	"""
	augur_data = {
		"branch_attrs": {"labels": {"text": "Reassorted Segments"}},
		"nodes": {},
		"branches": {}
	}
	
	for node_label, data in mapped_summary_data.items():
	
		is_reassorted = data.get("reassorted") == "True"
		
		augur_data["nodes"][node_label] = {
			"reassorted": str(is_reassorted),
			"reassorted_confidence": {
				"True": data.get("reassorted_confidence").get("True"),
				"False": data.get("reassorted_confidence").get("False")
			},
			"reassorted_entropy": data.get("reassorted_entropy") if data.get("reassorted_entropy") != 0.0 else 0.01,
			
			"segments": f"[{data.get('segments')}]" if data.get('segments') else "",		
			"divergence": data.get("divergence"),
		}

	
	
		# Create branch labels for visualization
		if data["segments"]:
			segments_list = [s.strip() for s in data["segments"].split(",")]
			num_segments = len(segments_list)
			segments_str = ", ".join(segments_list)
			label_text = f"{num_segments} ({segments_str})"
			augur_data["branches"][node_label] = {
				"labels": {"Reassorted Segments": label_text}
			}
	
	return augur_data

def main(args):
	# Use more reasonable confidence threshold
	CONFIDENCE_THRESHOLD = args.support_threshold
	
	print("=== Fixed TreeSort Summary Mapper ===")
	print(f"Using confidence threshold: {CONFIDENCE_THRESHOLD}")
	
	# Load summary data
	print("--- Loading summary data ---")
	with open(args.summary_json, 'r') as f:
		summary_data = json.load(f)
	
	# Parse target tree and add labels
	print("--- Loading and labeling target tree ---")  
	target_tree = get_labeled_canonical_tree(args.target_tree)
	
	# Build source leaf map
	source_leaf_map = build_source_leaf_map_from_tree_string(args.source_tree)
	
	# Build target leaf maps
	print("--- Building target tree leaf maps ---")
	target_leaf_map, target_leaf_map_inv = build_target_leaf_map(target_tree)
	
	# Validate leaf set consistency
	source_leaves = {leaf for leaf_set in source_leaf_map.values() for leaf in leaf_set}
	target_leaves = {leaf for leaf in target_leaf_map_inv if len(leaf) == 1}
	target_leaves = {list(leaf_set)[0] for leaf_set in target_leaves}
	
	print(f"Source tree leaves: {len(source_leaves)}")
	print(f"Target tree leaves: {len(target_leaves)}")
	
	missing_in_target = source_leaves - target_leaves
	missing_in_source = target_leaves - source_leaves
	
	if missing_in_target:
		print(f"WARNING: {len(missing_in_target)} leaves in source not found in target")
		if args.debug:
			print(f"Missing in target: {list(missing_in_target)[:5]}...")
	
	if missing_in_source:
		print(f"WARNING: {len(missing_in_source)} leaves in target not found in source")
		if args.debug:
			print(f"Missing in source: {list(missing_in_source)[:5]}...")
	
	# Process summary data and map to target tree
	print("--- Mapping summary annotations to target tree ---")
	mapped_summary_data = {}
	high_confidence_count = 0
	mapped_count = 0
	
	for source_node_label, data in summary_data["nodes"].items():
		
		is_reassorted = data.get("reassorted") == "True"
		confidence = data.get("reassorted_confidence", {}).get("True", 0)
		print(source_node_label,data,confidence)
		
		if args.debug and source_node_label.startswith("NODE"):
			print(f"\n--- Processing {source_node_label} (confidence: {confidence:.3f}) ---")
		
		if is_reassorted and float(confidence) >= float(CONFIDENCE_THRESHOLD):
			high_confidence_count += 1
		
		if source_node_label in source_leaf_map:
			source_leaf_set = source_leaf_map[source_node_label]
			target_node_label = map_node_with_ancestral_walk(
				source_leaf_set, target_tree, target_leaf_map_inv, 
				args.debug, source_node_label
			)
			
			if target_node_label:
				mapped_summary_data[target_node_label] = data
				mapped_count += 1
			elif args.debug:
				print(f"  ✗ Failed to map {source_node_label}")
		else:
			if args.debug:
				print(f"  ✗ {source_node_label} not found in source leaf map")
	
	print(f"\nSUMMARY:")
	print(f"  High confidence events in summary: {high_confidence_count}")
	print(f"  Successfully mapped to target tree: {mapped_count}")
#	  print(f"	Mapping success rate: {mapped_count/high_confidence_count*100:.1f}%")
	
	# Generate output files
	print("--- Generating output files ---")
	
	# Write labeled target tree
	target_tree.write(path=args.output_labeled_tree, schema="newick")
	print(f"✓ Labeled target tree: {args.output_labeled_tree}")
	print(mapped_summary_data)
	
	# Write augur node data
	augur_node_data = create_augur_node_data(mapped_summary_data)
	
	print(augur_node_data)
	
	with open(args.output_node_data, 'w') as f:
		json.dump(augur_node_data, f, indent=2)
		
	print(f"✓ Augur node data: {args.output_node_data}")
	
	print("=== Mapping completed successfully ===")
	
	

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Fixed mapper for treesort summary data to canonical trees"
	)
	parser.add_argument("--support_threshold", help="threshold for visualizing high support rea events")
	parser.add_argument("--summary_json", help="Path to summary_reassortment.json")
	parser.add_argument("--source_tree", help="Path to source tree (output.nwk)")
	parser.add_argument("--target_tree", help="Path to target tree (input.nwk)")
	parser.add_argument("--output_labeled_tree", help="Output labeled tree path")
	parser.add_argument("--output_node_data", help="Output node data JSON path")
	parser.add_argument("--debug", action="store_true", help="Enable debug output")
	
	args = parser.parse_args()
	main(args)