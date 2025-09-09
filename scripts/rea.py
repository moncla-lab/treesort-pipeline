import re
import argparse
import json
import baltic as bt
import random
from collections import defaultdict, Counter

parser = argparse.ArgumentParser()
parser.add_argument('--tree', type=str, required=True, help='annotated reassortment treesort tree')
parser.add_argument('--outdir', type=str, required=True, help='name of baltic readable tree')

args = parser.parse_args()

'''
this function finds sibling branches (tree is binary) with uncertain reassortment events 
and randomly assigns a child branch the reassortment event
this is needed for summarizing reassortment across the treesort runs for each node and leaf

'''

def uncertainty_resolver(mytree):
	
	random.seed(42)
	
	def parse_rea_string(rea_str):
		return [seg for seg in rea_str.strip().split("-") if seg]
	
	def rebuild_rea_string(segments):
		return "-".join(segments) if segments else None
	
	for k in mytree.Objects:
		if k.is_node():
			children = k.children
	
			# only look at nodes whose children are both reassorted 
			# since that is the first requirment for a possible uncertain rea event
			if not all(child.traits.get("is_reassorted") == 1 for child in children):
				continue
	
			seg_lists = []
	
			for child in children:
				raw_rea = child.traits.get("rea", "")
				seg_lists.append(parse_rea_string(raw_rea))
	
			# identify uncertain reassortment segments (start with "_") in both children
			segs0_uncertain = set(seg for seg in seg_lists[0] if seg.startswith("_"))
			segs1_uncertain = set(seg for seg in seg_lists[1] if seg.startswith("_"))
	
			shared_uncertain = segs0_uncertain & segs1_uncertain
	
			# this randomly assigns each uncertain segment to a random child 
			for seg in shared_uncertain:
				# print(seg)
				stripped = seg.lstrip("_")
				chosen = random.choice(children)
				other = [c for c in children if c is not chosen][0]
				# print("chosen: " + chosen.name if chosen.is_leaf() else "chosen: " + chosen.traits["label"])
				# print("other: " + other.name if other.is_leaf() else "other: " + other.traits["label"])
	
				# update chosen: replace _SEG(x) with SEG(x)
				chosen_rea = parse_rea_string(chosen.traits.get("rea", ""))
				chosen_rea.remove(seg)
				chosen_rea.append(stripped)
				chosen.traits["rea"] = rebuild_rea_string(chosen_rea)
	
				# update other: remove the uncertain segment
				other_rea = parse_rea_string(other.traits.get("rea", ""))
				other_rea.remove(seg)
				other.traits["rea"] = rebuild_rea_string(other_rea)
				# print(chosen_rea)
				# print(other_rea)
				# print("\n")
	
			for child in children:
				if child.traits.get("is_reassorted") == 1:
					rea_str = child.traits.get("rea", "")
	
					if not rea_str:
						child.traits["is_reassorted"] = 0
						child.traits.pop("rea", None)
						
	return(mytree)
	
''' 

this generates a rea.json file that stores whether a node/leaf was reassorted for a treesort run

this was adapted from jordan ort's code, translated from phylo.bio to baltic 
and also keeps in divergence values 

'''
	
def reassortment_counter(mytree, output):
	rea_dict = {}
	segments = ["PB2", "PB1", "PA", "HA", "NP", "NA", "MP", "NS"]
	
	for k in mytree.Objects:
		if k.traits["is_reassorted"]:
			raw_segments = k.traits["rea"]
			
			# extract reassorted segments and their divergence values
			# matches 'NS(49)' and returns ('NS', '49')
			segment_info = re.findall(r'(\w+)\((\d+)\)', raw_segments)
			
			segment_names = [seg for seg, _ in segment_info]
			divergence_values = [val for _, val in segment_info]
	
			reassorted_segments = f"{len(segment_names)} ({', '.join(segment_names)})"
			divergence_value = divergence_values[0] if len(divergence_values) == 1 else ", ".join(divergence_values)
			
			
			key = k.traits.get("label") if k.is_node() else k.name
			rea_dict[key] = {
				"Reassorted": "True",
				"Reassorted Segments": reassorted_segments,
				"Divergence Value": divergence_value
			}
			
		else:
			key = k.traits["label"] if k.is_node() else k.name
			rea_dict[key] = {"Reassorted": "False"}
	
	branch_dict = {}
	for k in mytree.Objects:
		if k.traits["is_reassorted"]:
			key = k.traits.get("label") if k.is_node() else k.name
			branch_dict[key] = {
				"labels": {
					'Reassorted Segments': rea_dict[key]['Reassorted Segments']
				}
			}
	
	out_dict = {'nodes': rea_dict, 'branches': branch_dict}
	with open(output, 'w') as f:
		json.dump(out_dict, f)

mytree = bt.loadNewick(args.tree, absoluteTime= False)
mytree = uncertainty_resolver(mytree)

reassortment_counter(mytree, args.outdir)

