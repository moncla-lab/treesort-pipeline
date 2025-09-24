import argparse
import baltic
import statistics
import numpy as np
from scipy.optimize import minimize, LinearConstraint
import warnings
from datetime import datetime
import re
from treetime import TreeTime, TreeTimeError, utils
from dendropy import Tree
from Bio import SeqIO
import pandas as pd
import os
import random
import math
import baltic as bt

parser = argparse.ArgumentParser()

parser.add_argument('--trees',  nargs='+', required=True, help='replicate trees')
parser.add_argument('--backbone',  type=str, required=True, help='segment indicated as backbone for treesort')
parser.add_argument('--summary_tree',  type=str, required=True, help='summary tree for molecular clock estimation')
parser.add_argument('--backbone_aln',  type=str, required=True, help='backbone alignment for molecular clock estimation')
parser.add_argument('--log_file', type=str, required=True, help='csv file featuring rea rates and segment info')

args = parser.parse_args()

# from treesort/helpers.py
def parse_dates(aln_path: str):
    records = SeqIO.parse(aln_path, 'fasta')
    dates = {}
    for record in records:
        name = record.name
        # date_str = name.split('|')[-1]
        date = None
        for token in name.split('|'):
            if re.fullmatch(r'[\d\-/]{4,}', token) and not re.fullmatch(r'\d{5,}', token):
                if token.count('/') == 2:
                    date = datetime.strptime(token, '%m/%d/%Y')
                elif token.count('/') == 1:
                    date = datetime.strptime(token, '%m/%Y')
                elif token.count('-') == 2:
                    date = datetime.strptime(token, '%Y-%m-%d')
                elif token.count('-') == 1:
                    date = datetime.strptime(token, '%Y-%m')
                else:
                    date = datetime.strptime(token, '%Y')
        if not date:
            pass
        else:
            dec_date = date.year + ((date.month - 1) * 30 + date.day) / 365.0
            dates[name] = dec_date
    return dates

# from treesort/options.py
# feed it the summary tree and backbone alignment
def estimate_clock_rate(tree_path: str, aln_path: str, outdir='.') -> (float, float):
    # This code was adapted from the  'estimate_clock_model' method in the treetime/wrappers.py.
    tree: Tree = Tree.get(path=tree_path, schema='newick', preserve_underscores=True)
    if len(tree.leaf_nodes()) > 1000:
        tree_path = os.path.join(outdir, os.path.split(tree_path)[-1] + '.sample1k.tre')
        taxa_labels = [t.label for t in tree.taxon_namespace]
        random.shuffle(taxa_labels)
        subtree: Tree = tree.extract_tree_with_taxa_labels(taxa_labels[:1000])
        subtree.write(path=tree_path, schema='newick')

    dates = parse_dates(aln_path)
    
    try:
        timetree = TreeTime(dates=dates, tree=tree_path, aln=aln_path, gtr='JC69', verbose=-1)  # TODO: JC->GTR?
    except TreeTimeError as e:
        parser.error(f"TreeTime exception on the input files {tree_path} and {aln_path}: {e}\n "
                     f"Please make sure that the specified alignments and trees are correct.")
                     
    timetree.clock_filter(n_iqd=3, reroot='least-squares')
    timetree.use_covariation = True
    timetree.reroot()
    timetree.get_clock_model(covariation=True)
    r_val = timetree.clock_model['r_val']
    d2d = utils.DateConversion.from_regression(timetree.clock_model)
    clock_rate = round(d2d.clock_rate, 7)
    return d2d.clock_rate, r_val

def sibling_distance(parent_node):
    return parent_node.children[0].length + parent_node.children[1].length

def top_1(tree, ignore_top_edges):
   
    edge_cutoff = math.inf
    edge_lengths = sorted([node.length for node in tree.Objects if node.length])
    top_percentile = int(round(len(edge_lengths) * (1.0 - ignore_top_edges / 100)))
    edge_cutoff = edge_lengths[top_percentile - 1]
    
    return(edge_cutoff)

def compute_rea_rate_simple(annotated_tree, evol_rate, ignore_top_edges=1):

    if ignore_top_edges > 0:
        edge_cutoff = top_1(annotated_tree, ignore_top_edges)
    
    rea_events = 0
    for node in annotated_tree.Objects:
        if node.parent is None:
            continue  # Skip the root
        if node.length and node.length >= edge_cutoff:
            continue  # Skip the longest edges
        if node.traits.get('is_reassorted'):
            rea_annotation = node.traits.get('rea')
            is_uncertain = all([g_str.startswith('_') for g_str in rea_annotation.split('-')])
            rea_events += 0.5 if is_uncertain else 1
    
    tree_length = sum(node.length for node in annotated_tree.Objects if node.parent and node.length < edge_cutoff)
    
    rea_rate = rea_events / tree_length * evol_rate if tree_length > 0 else 0.0
    
    return rea_rate
    

def likelihood_binary(x, rea_events, edge_lengths):
    if x < 1e-10:
        return np.inf
    func = 0
    for i in range(len(rea_events)):
        if edge_lengths[i] > 0:
            if rea_events[i] > 0:
                with warnings.catch_warnings():
                    warnings.filterwarnings('error')
                    try:
                        func -= np.log(1 - np.exp(-1 * x * edge_lengths[i]))
                    except Warning:
                        func += np.inf
            else:
                func -= (-1 * x * edge_lengths[i])
    return func

def compute_rea_rate_binary_mle(annotated_tree, evol_rate, backbone_seg):


	seg_lengths = {
    "PB2": 2340,
    "PB1": 2340,
    "PA": 2230,
    "HA": 1770,   
    "NP": 1565,
    "NA": 1400,
    "M": 1027,
    "NS": 890
	}
	
	ref_seg_len = seg_lengths[backbone_seg.upper()]
	rea_events = []
	edge_lengths = []
	processed_uncertain = set()
    
	for node in annotated_tree.Objects:
		if node.parent is None:
			continue  # Skip the root
		is_uncertain = False
		
		if node.traits.get('is_reassorted'):
			rea_annotation = node.traits.get('rea')
			is_uncertain = all([g_str.startswith('_') for g_str in rea_annotation.split('-')])
			if not is_uncertain:
				rea_events.append(1)
		else:
			rea_events.append(0)
		
		edge_length = node.length
        
		if is_uncertain:
			
			siblings = [child for child in node.parent.children if child != node]
			
			#the tree is binary, so there should only be one sibling
			#however, because i prune leaves that are not same host, sometimes there is no sibling
			#i choose to just record this as a rea event, can come back to this
			
			if len(siblings) == 0:
				rea_events.append(1)
				#edge length already = node length from the code above
				processed_uncertain.add(node)
			
			else:
				sibling = siblings[0] 
	
				if sibling not in processed_uncertain:
					rea_events.append(1)
					edge_length = sibling_distance(node.parent)
					processed_uncertain.add(node)
				else:
					continue
        
		if edge_length > 1e-7:
			edge_lengths.append(edge_length / evol_rate)
		elif rea_events[-1] > 0:
			edge_lengths.append((1 / ref_seg_len) / evol_rate)
		else:
			edge_lengths.append(0)
    
	est = compute_rea_rate_simple(annotated_tree, evol_rate, ignore_top_edges=1)
	np_est = np.array([est])
	linear_constraint = LinearConstraint([[1]], [0])
	num_est = minimize(likelihood_binary, np_est, args=(rea_events, edge_lengths), tol=1e-9,
					   constraints=[linear_constraint])
		 
	return num_est.x[0] if num_est.success else None
    

clock_rate, r_val = estimate_clock_rate(args.summary_tree, args.backbone_aln)

rows = []

for rep_tree in args.trees:
	rep = os.path.basename(os.path.dirname(rep_tree))
	
	tree = bt.loadNewick(rep_tree, absoluteTime= False)
	
	simple_rate = compute_rea_rate_simple(tree, clock_rate, ignore_top_edges=1)
	mle_rate = compute_rea_rate_binary_mle(tree, clock_rate, args.backbone)	
	
	rows.append({
		"rep": rep,
		"simple_rate": simple_rate,
		"mle_rate": mle_rate
	})
	
df = pd.DataFrame(rows)

df.to_csv(args.log_file, index=False)	
	