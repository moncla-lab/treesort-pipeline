# this function converts a nexus tree to a newick format

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--tree', type=str, required=True, help='the nexus tree to be converted')
parser.add_argument('--output', type=str, required=True, help='name of output nwk tree (ex: output.nwk)')

args = parser.parse_args()

with open(args.tree, 'r') as file:
	nexus = file.read()
	
start_idx = nexus.find('(')
modified = nexus[start_idx:]

end_idx = modified.find('END;')
modified = modified[:end_idx]
	
with open(args.output, "w") as output:
	output.write(modified.strip())
	