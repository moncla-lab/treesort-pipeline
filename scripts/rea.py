import pandas as pd
import os
import re
import sys
import json
import baltic as bt
import random
from collections import defaultdict, Counter

parser = argparse.ArgumentParser()
parser.add_argument('--tree', type=str, required=True, help='annotated reassortment treesort tree')
parser.add_argument('--outdir', type=str, required=True, help='name of reassortment summary json')

args = parser.parse_args()

''' 
this function preps the treesort output to be readable by baltic.
output_filename: it needs to write a tree in order for baltic to read it in

1. converts nexus format to nwk
2. replaces commas with "-" (where the reassorted segments are inferred)
3. remove the single quotation marks around TS_NODE_####
4. replaces ? with _ (where there is an undetermined reassortment event)
   
'''

def prep(rep_path, treesort_path, output_filename):
        
    with open(treesort_path, 'r') as file:
        nexus = file.read()
        
    start_idx = nexus.find('(')
    modified = nexus[start_idx:]
    
    end_idx = modified.find('END;')
    modified = modified[:end_idx]
        
    # removing commas between segments
    modified = re.sub(r'&rea="([^"]+)"', lambda match: f'&rea="{match.group(1).replace(",", "-")}"', modified)
    
    # removing quotation marks around node names
    modified = re.sub(r"'(TS_NODE_\d+)'", r'\1', modified)
    
    # replacing ? with _ so baltic can read it in
    modified = modified.replace('?', '_')
    
    with open(f"{rep_path}/{output_filename}", "w") as output_file:
        output_file.write(modified.strip())
        
    mytree = bt.loadNewick(f"{rep_path}/{output_filename}", absoluteTime= False)
    
    return(mytree)
