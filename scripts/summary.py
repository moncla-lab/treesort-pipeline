import re
import argparse
import json
import dendropy
import math
import random
from collections import defaultdict, Counter

parser = argparse.ArgumentParser()
parser.add_argument('--jsons', nargs='+', required=True, help='list of JSON files from different reps')
parser.add_argument('--backbone', type=str, required=True, help='backbone tree to put reassortments back on')
parser.add_argument('--threshold', type=float, default=0.95, help='only annotating reassortment events with a confidence above this threshold')
parser.add_argument('--summary_nwk', type=str, required=True, help='summary nwk tree')
parser.add_argument('--summary_nexus', type=str, required=True, help='summary nexus tree')
parser.add_argument('--node_data', type=str, required=True, help='node data for rule export')

args = parser.parse_args()

def summary_json(jsons, threshold, node_data):

	# need to double check this, just a placeholder for now since nextstrain requires entropy values
	def compute_entropy(prob_dict):
		return -sum(p * math.log2(p) for p in prob_dict.values() if p > 0)
	
	def binary_entropy(p_true, p_false):
		
		H = 0.0
		if p_true > 0:
			H -= p_true * math.log2(p_true)
		if p_false > 0:
			H -= p_false * math.log2(p_false)
			
		return H
	
	n_jsons = len(args.jsons)
	
	node_annotations_summary = defaultdict(lambda: {
		'reassorted': 0,
		'nonreassorted': 0,
		'rea': defaultdict(int),
		'divergence': defaultdict(Counter)
	})
	
	for json_path in jsons:
	
		with open(json_path) as f:
			rea_data = json.load(f)
	
		for node, annotations in rea_data.get("nodes", {}).items():
	
			is_reassorted = annotations.get("Reassorted", "False") == "True"
			if is_reassorted:
				node_annotations_summary[node]['reassorted'] += 1
				seg_str = annotations.get("Reassorted Segments", "")
				div_str = annotations.get("Divergence Value", "")
	
	
				# extract segments: from "3 (PB2, PB1, NP)" → ["PB2", "PB1", "NP"]
				seg_match = re.search(r'\(([^)]+)\)', seg_str)
				segments = [s.strip() for s in seg_match.group(1).split(',')] if seg_match else []
	
				# extract divergence values: from "344, 319, 264" → [344, 319, 264]
				divergence_values = [int(v.strip()) for v in div_str.split(',') if v.strip()]
	
				# map segment ↔ divergence value
				if len(segments) == len(divergence_values):
					for seg, div in zip(segments, divergence_values):
						node_annotations_summary[node]['rea'][seg] += 1
						node_annotations_summary[node]['divergence'][seg][div] += 1
			else:
				node_annotations_summary[node]['nonreassorted'] += 1
	
	formatted_annotations = {"nodes":{}}
	
	for node, counts in node_annotations_summary.items():
		reassorted_count = counts['reassorted']
		nonreassorted_count = counts['nonreassorted']
		confidence_true = reassorted_count / n_jsons
		confidence_false = nonreassorted_count / n_jsons
	
		reassorted_final = confidence_true >= threshold
	
		segment_confidence = {
			seg: counts['rea'][seg] / reassorted_count for seg in counts['rea']
		}
		
		high_conf_segments = [seg for seg, conf in segment_confidence.items() if conf >= threshold]
		
		divergence_mode = {}
		divergence_confidence = {}
		divergence_entropy = {}
		
		for seg, div_counter in counts['divergence'].items():
			most_common_value, most_common_count = div_counter.most_common(1)[0]
			divergence_mode[seg] = str(most_common_value)
			divergence_confidence[seg] = {
				str(div): round(count / reassorted_count, 5)
				for div, count in div_counter.items()
			}
			entropy_val = compute_entropy(divergence_confidence[seg])
			divergence_entropy[seg] = round(entropy_val, 5)
			
			
		segment_entropy = compute_entropy(segment_confidence)
		reassorted_entropy = binary_entropy(confidence_true, confidence_false)
	
		# just as a fail-safe, if reassorted is True but no segment reaches the threshold, 
		# list the most frequently reassorting segment
		if reassorted_final and not high_conf_segments:
			top_seg = max(segment_confidence.items(), key=lambda x: x[1])[0]
			high_conf_segments = [top_seg]
	
		formatted_annotations["nodes"][node] = {
			"reassorted": str(reassorted_final),
			"reassorted_confidence": {
				"True": round(confidence_true, 5),
				"False": round(confidence_false, 5)
			},
			"reassorted_entropy": round(reassorted_entropy, 5),
			"segments": ", ".join(sorted(high_conf_segments)) if reassorted_final else '',
			"segments_confidence": {
				seg: round(conf, 5) for seg, conf in segment_confidence.items()
			},
			"segments_entropy": round(segment_entropy, 5),
			"divergence": ", ".join(
					f"{seg}({divergence_mode[seg]})" for seg in high_conf_segments
				) if reassorted_final else "",
			"divergence_confidence": {
				seg: conf for seg, conf in divergence_confidence.items()
			},
			"divergence_entropy": divergence_entropy
		}
	
	with open(node_data, 'w') as out_f:
		json.dump(formatted_annotations, out_f, indent=4)
		
		
''' 
this makes a summary tree (in both nexus and nwk formats)
without any confidence values for fast visualization

json with confidence values will be supplied as node_data for augur export

'''

def summary_tree(summary_json, backbone, nwk_path, nexus_path):
    
	with open(summary_json) as f:
		summary_data = json.load(f)
	
	tree = dendropy.Tree.get(
		path=backbone,
		schema="newick",
		preserve_underscores=True)
	
	for node in tree.preorder_node_iter():
	
		label = str(node.taxon).replace('Taxon(', '').strip(')"\'') if node.is_leaf() else node.label
	
		if label in summary_data:
	
			info = summary_data[label]
			node.annotations.clear()
			
			is_reassorted = 1 if info["reassorted"] == "True" else 0
			node.annotations.add_new("is_reassorted", is_reassorted)
			
			if info["segments"]:
				node.annotations.add_new("rea", info["segments"])
			
	tree.write(path=nwk_path, schema="newick", suppress_annotations = False)
	tree.write(path=nexus_path, schema="nexus", suppress_annotations = False)

summary_json(args.jsons, args.threshold, args.node_data)
summary_tree(args.node_data, args.backbone, args.summary_nwk, args.summary_nexus)
